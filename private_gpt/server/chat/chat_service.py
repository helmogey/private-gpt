import logging
import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from injector import inject, singleton
from llama_index.core.chat_engine import ContextChatEngine, SimpleChatEngine
from llama_index.core.indices import VectorStoreIndex
from llama_index.core.indices.postprocessor import MetadataReplacementPostProcessor
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.postprocessor import (
    SentenceTransformerRerank,
    SimilarityPostprocessor,
)
from llama_index.core.storage import StorageContext
from pydantic import BaseModel

from private_gpt.components.embedding.embedding_component import EmbeddingComponent
from private_gpt.components.llm.llm_component import LLMComponent
from private_gpt.components.node_store.node_store_component import NodeStoreComponent
from private_gpt.components.vector_store.vector_store_component import VectorStoreComponent
from private_gpt.open_ai.extensions.context_filter import ContextFilter
from private_gpt.server.chunks.chunks_service import Chunk
from private_gpt.settings.settings import Settings

from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.query_engine import RetrieverQueryEngine

logger = logging.getLogger(__name__)

try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

if TYPE_CHECKING:
    from llama_index.core.postprocessor.types import BaseNodePostprocessor

class AsyncCompletionGen:
    """Standardized Async Generator Wrapper for streaming responses"""
    def __init__(self, response_stream, sources):
        self.response_stream = response_stream
        self.sources = sources
        
    async def async_response_gen(self):
        async for item in self.response_stream:
            yield item

class AsyncWorkflowAgentWrapper:
    """Natively executes the Agent as an asynchronous workflow."""
    def __init__(self, agent):
        self.agent = agent
        
    async def astream_chat(self, message: str, chat_history=None):
        try:
            # Await the execution fully on the async loop to allow tools to run cleanly
            handler = self.agent.run(user_msg=message)
            result = await handler
            final_text = str(result)
        except Exception as e:
            import traceback
            logger.error(f"Agent execution failed: {traceback.format_exc()}")
            final_text = f"Error executing agent: {e}"
            
        async def stream():
            chunk_size = 15
            for i in range(0, len(final_text), chunk_size):
                yield final_text[i:i+chunk_size]
                await asyncio.sleep(0.01) # Yield to event loop to simulate streaming cleanly
                
        return AsyncCompletionGen(stream(), [])

class Completion(BaseModel):
    response: str
    sources: list[Chunk] | None = None

class CompletionGen(BaseModel):
    response: Any  
    sources: list[Chunk] | None = None

@dataclass
class ChatEngineInput:
    system_message: ChatMessage | None = None
    last_message: ChatMessage | None = None
    chat_history: list[ChatMessage] | None = None

    @classmethod
    def from_messages(cls, messages: list[ChatMessage]) -> "ChatEngineInput":
        system_message = messages[0] if len(messages) > 0 and messages[0].role == MessageRole.SYSTEM else None
        last_message = messages[-1] if len(messages) > 0 and messages[-1].role == MessageRole.USER else None
        if system_message: messages.pop(0)
        if last_message: messages.pop(-1)
        chat_history = messages if len(messages) > 0 else None
        return cls(system_message=system_message, last_message=last_message, chat_history=chat_history)

@singleton
class ChatService:
    @inject
    def __init__(
        self,
        settings: Settings,
        llm_component: LLMComponent,
        vector_store_component: VectorStoreComponent,
        embedding_component: EmbeddingComponent,
        node_store_component: NodeStoreComponent,
    ) -> None:
        self.settings = settings
        self.llm_component = llm_component
        self.vector_store_component = vector_store_component
        self.index = VectorStoreIndex.from_vector_store(
            vector_store_component.vector_store,
            storage_context=StorageContext.from_defaults(
                vector_store=vector_store_component.vector_store,
                docstore=node_store_component.doc_store,
                index_store=node_store_component.index_store,
            ),
            llm=llm_component.llm,
            embed_model=embedding_component.embedding_model,
        )

    def _chat_engine(self, system_prompt: str | None, use_context: bool, context_filter: ContextFilter | None, tools: list[Any] | None = None) -> Any:
        mcp_tools = tools or []

        retriever = self.vector_store_component.get_retriever(
            index=self.index,
            context_filter=context_filter,
            similarity_top_k=self.settings.rag.similarity_top_k,
        )
        
        node_postprocessors: list[BaseNodePostprocessor] = [
            MetadataReplacementPostProcessor(target_metadata_key="window"),
        ]
        if self.settings.rag.similarity_value:
            node_postprocessors.append(SimilarityPostprocessor(similarity_cutoff=self.settings.rag.similarity_value))
        if self.settings.rag.rerank.enabled:
            node_postprocessors.append(SentenceTransformerRerank(model=self.settings.rag.rerank.model, top_n=self.settings.rag.rerank.top_n))

        if mcp_tools:
            logger.info(f"MCP Tools active. Initializing LlamaIndex v0.11+ Workflow ReActAgent...")
            try:
                query_engine = RetrieverQueryEngine.from_args(
                    retriever=retriever,
                    node_postprocessors=node_postprocessors,
                    llm=self.llm_component.llm,
                )
                rag_tool = QueryEngineTool(
                    query_engine=query_engine,
                    metadata=ToolMetadata(name="rag_search", description="Search internal documentation. Use this first for general knowledge!")
                )
                
                from llama_index.core.agent.workflow import ReActAgent
                
                agent = ReActAgent(
                    name="Zabbix_Support_Agent",
                    tools=[rag_tool] + mcp_tools,
                    llm=self.llm_component.llm,
                    system_prompt=system_prompt or "You are a helpful assistant with access to tools."
                )
                
                return AsyncWorkflowAgentWrapper(agent)
                
            except Exception as e:
                logger.error(f"Failed to initialize Workflow Agent: {e}")
                logger.info("Falling back to standard Context Engine.")
                pass

        if use_context:
            return ContextChatEngine.from_defaults(
                system_prompt=system_prompt,
                retriever=retriever,
                llm=self.llm_component.llm,
                node_postprocessors=node_postprocessors,
            )
        else:
            return SimpleChatEngine.from_defaults(
                system_prompt=system_prompt,
                llm=self.llm_component.llm,
            )

    # --- PURE ASYNC PATHWAY FOR API ---
    async def astream_chat(self, messages: list[ChatMessage], use_context: bool = False, context_filter: ContextFilter | None = None, tools: list[Any] | None = None, system_prompt_override: str | None = None) -> AsyncCompletionGen:
        input_data = ChatEngineInput.from_messages(messages)
        final_system_prompt = system_prompt_override if system_prompt_override else (input_data.system_message.content if input_data.system_message else None)

        engine = self._chat_engine(
            system_prompt=final_system_prompt,
            use_context=use_context,
            context_filter=context_filter,
            tools=tools
        )
        msg_content = input_data.last_message.content if input_data.last_message else ""
        
        if isinstance(engine, AsyncWorkflowAgentWrapper):
            return await engine.astream_chat(msg_content, chat_history=input_data.chat_history)
        else:
            # Fallback to standard native engine async streaming
            response = await engine.astream_chat(msg_content, chat_history=input_data.chat_history)
            source_nodes = getattr(response, "source_nodes", [])
            sources = [Chunk.from_node(node) for node in source_nodes]
            return AsyncCompletionGen(response.async_response_gen(), sources)

    # Legacy Sync Pathways (Keep these alive for backwards compatibility)
    def stream_chat(self, messages: list[ChatMessage], use_context: bool = False, context_filter: ContextFilter | None = None, tools: list[Any] | None = None, system_prompt_override: str | None = None) -> CompletionGen:
        input_data = ChatEngineInput.from_messages(messages)
        final_system_prompt = system_prompt_override if system_prompt_override else (input_data.system_message.content if input_data.system_message else None)
        engine = self._chat_engine(system_prompt=final_system_prompt, use_context=use_context, context_filter=context_filter, tools=tools)
        msg_content = input_data.last_message.content if input_data.last_message else ""
        response = engine.stream_chat(msg_content, chat_history=input_data.chat_history)
        source_nodes = getattr(response, "source_nodes", [])
        sources = [Chunk.from_node(node) for node in source_nodes]
        return CompletionGen(response=response.response_gen, sources=sources)
        
    def chat(self, messages: list[ChatMessage], use_context: bool = False, context_filter: ContextFilter | None = None, tools: list[Any] | None = None, system_prompt_override: str | None = None) -> Completion:
        input_data = ChatEngineInput.from_messages(messages)
        final_system_prompt = system_prompt_override if system_prompt_override else (input_data.system_message.content if input_data.system_message else None)
        engine = self._chat_engine(system_prompt=final_system_prompt, use_context=use_context, context_filter=context_filter, tools=tools)
        response = engine.chat(input_data.last_message.content if input_data.last_message else "", chat_history=input_data.chat_history)
        source_nodes = getattr(response, "source_nodes", [])
        sources = [Chunk.from_node(node) for node in source_nodes]
        return Completion(response=response.response, sources=sources)