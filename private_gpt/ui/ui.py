# In private_gpt/ui/ui.py
import os
import logging
import base64
from typing import Any
from pathlib import Path
from fastapi import FastAPI
import gradio as gr
from injector import inject, singleton
from llama_index.core.llms import ChatMessage, ChatResponse, MessageRole
from llama_index.core.types import TokenGen
from pydantic import BaseModel
import time
from collections.abc import Iterable
from enum import Enum

from private_gpt.constants import PROJECT_ROOT_PATH
from private_gpt.di import global_injector
from private_gpt.open_ai.extensions.context_filter import ContextFilter
from private_gpt.server.chat.chat_service import ChatService, CompletionGen
from private_gpt.server.chunks.chunks_service import Chunk, ChunksService
from private_gpt.server.ingest.ingest_service import IngestService
from private_gpt.settings.settings import settings
from private_gpt.ui.images import logo_svg

logger = logging.getLogger(__name__)

THIS_DIRECTORY_RELATIVE = Path(__file__).parent.relative_to(PROJECT_ROOT_PATH)
AVATAR_BOT = THIS_DIRECTORY_RELATIVE / "assets/avatar-bot.png"
UI_TAB_TITLE = "NEC GPT"
SOURCES_SEPARATOR = "<hr>Sources: \n"

class Modes(str, Enum):
    RAG_MODE = "RAG"
    SEARCH_MODE = "Search"

MODES: list[Modes] = [Modes.RAG_MODE, Modes.SEARCH_MODE]

class Source(BaseModel):
    file: str; page: str; text: str
    class Config: frozen = True
    @staticmethod
    def curate_sources(sources: list[Chunk]) -> list["Source"]:
        curated_sources = []
        for chunk in sources:
            doc_metadata = chunk.document.doc_metadata
            file_name = doc_metadata.get("file_name", "-") if doc_metadata else "-"
            page_label = doc_metadata.get("page_label", "-") if doc_metadata else "-"
            source = Source(file=file_name, page=page_label, text=chunk.text)
            curated_sources.append(source)
        return list(dict.fromkeys(curated_sources).keys())

def get_model_label() -> str | None:
    # ... (This function remains unchanged)
    return settings().llamacpp.llm_hf_model_file # Simplified for brevity

@singleton
class PrivateGptUi:
    @inject
    def __init__(
        self,
        ingest_service: IngestService,
        chat_service: ChatService,
        chunks_service: ChunksService,
    ) -> None:
        self._ingest_service = ingest_service
        self._chat_service = chat_service
        self._chunks_service = chunks_service

        # Cache the UI blocks
        self._ui_block = None

        self._selected_filename = None

        # Initialize system prompt based on default mode
        default_mode_map = {mode.value: mode for mode in Modes}
        self._default_mode = default_mode_map.get(
            settings().ui.default_mode, Modes.RAG_MODE
        )
        self._system_prompt = self._get_default_system_prompt(self._default_mode)

    def _chat(self, message: str, history: list[dict[str, str]], mode: Modes, *_: Any) -> Any:
        # The history format is now a list of dictionaries, e.g., [{"role": "user", "content": "Hello"}]
        def yield_deltas(completion_gen: CompletionGen) -> Iterable[Any]:
            # This inner function streams the main response
            full_response = {"role": "assistant", "content": ""}
            stream = completion_gen.response
            for delta in stream:
                if isinstance(delta, str):
                    full_response["content"] += str(delta)
                elif isinstance(delta, ChatResponse):
                    full_response["content"] += delta.delta or ""
                yield full_response
                time.sleep(0.02)

            # This inner function streams the sources
            if completion_gen.sources:
                sources_content = '<div class="sources-container">'
                sources_content += SOURCES_SEPARATOR
                cur_sources = Source.curate_sources(completion_gen.sources)
                sources_text = "\n\n"
                used_files = set()
                for index, source in enumerate(cur_sources, start=1):
                    if f"{source.file}-{source.page}" not in used_files:
                        sources_text += f"{index}. {source.file} (page {source.page}) \n\n"
                        used_files.add(f"{source.file}-{source.page}")
                sources_text += "<hr>\n\n"
                sources_content += sources_text
                sources_content += "</div>"

                full_response["content"] += sources_content
    
                # Yield the final, combined message
                yield full_response

        # This is the main logic for the _chat method
        def build_history() -> list[ChatMessage]:
            # UPDATED: This function is now much simpler
            return [ChatMessage(**message) for message in history]

        new_message = ChatMessage(content=message, role=MessageRole.USER)
        all_messages = [*build_history(), new_message]

        if self._system_prompt:
            all_messages.insert(0, ChatMessage(content=self._system_prompt, role=MessageRole.SYSTEM))

        match mode:
            case Modes.RAG_MODE:
                context_filter = None
                if self._selected_filename:
                    # ... (rest of the logic is the same)
                    docs_ids = [doc.doc_id for doc in self._ingest_service.list_ingested() if doc.doc_metadata and doc.doc_metadata.get("file_name") == self._selected_filename]
                    context_filter = ContextFilter(docs_ids=docs_ids)

                query_stream = self._chat_service.stream_chat(
                    messages=all_messages,
                    use_context=True,
                    context_filter=context_filter,
                )
                yield from yield_deltas(query_stream)

            case Modes.SEARCH_MODE:
                # ... (rest of the logic is the same)
                if settings().rag.rerank.enabled:
                    n_chunks = settings().rag.rerank.top_n
                else:
                    n_chunks = settings().rag.similarity_top_k
                response = self._chunks_service.retrieve_relevant(
                    text=message, limit=n_chunks, prev_next_chunks=0
                )
                sources = Source.curate_sources(response)

                # Format the search results as a single message
                search_response = "\n\n\n".join(
                    f"{index}. **{source.file} (page {source.page})**\n{source.text}"
                    for index, source in enumerate(sources, start=1)
                )
                yield {"role": "assistant", "content": search_response}


    @staticmethod
    def _get_default_system_prompt(mode: Modes) -> str:
        p = ""
        match mode:
            # For query chat mode, obtain default system prompt from settings
            case Modes.RAG_MODE:
                p = settings().ui.default_query_system_prompt
            # For any other mode, clear the system prompt
            case _:
                p = ""
        return p


    @staticmethod
    def _get_default_mode_explanation(mode: Modes) -> str:
        match mode:
            case Modes.RAG_MODE:
                return "Get contextualized answers from selected files."
            case Modes.SEARCH_MODE:
                return "Find relevant chunks of text in selected files."
            case _:
                return ""

    def _set_system_prompt(self, system_prompt_input: str) -> None:
        logger.info(f"Setting system prompt to: {system_prompt_input}")
        self._system_prompt = system_prompt_input

    def _set_explanatation_mode(self, explanation_mode: str) -> None:
        self._explanation_mode = explanation_mode

    def _set_current_mode(self, mode: Modes) -> Any:
        self.mode = mode
        self._set_system_prompt(self._get_default_system_prompt(mode))
        self._set_explanatation_mode(self._get_default_mode_explanation(mode))
        interactive = self._system_prompt is not None
        return [
            gr.update(placeholder=self._system_prompt, interactive=interactive),
            gr.update(value=self._explanation_mode),
        ]

    def _list_ingested_files(self) -> list[list[str]]:
        files = set()
        for ingested_document in self._ingest_service.list_ingested():
            if ingested_document.doc_metadata is None:
                # Skipping documents without metadata
                continue
            file_name = ingested_document.doc_metadata.get(
                "file_name", "[FILE NAME MISSING]"
            )
            files.add(file_name)
        return [[row] for row in files]

    def _upload_file(self, files: list[str]) -> None:
        logger.debug("Loading count=%s files", len(files))
        paths = [Path(file) for file in files]

        # remove all existing Documents with name identical to a new file upload:
        file_names = [path.name for path in paths]
        doc_ids_to_delete = []
        for ingested_document in self._ingest_service.list_ingested():
            if (
                ingested_document.doc_metadata
                and ingested_document.doc_metadata["file_name"] in file_names
            ):
                doc_ids_to_delete.append(ingested_document.doc_id)
        if len(doc_ids_to_delete) > 0:
            logger.info(
                "Uploading file(s) which were already ingested: %s document(s) will be replaced.",
                len(doc_ids_to_delete),
            )
            for doc_id in doc_ids_to_delete:
                self._ingest_service.delete(doc_id)

        self._ingest_service.bulk_ingest([(str(path.name), path) for path in paths])

    def _delete_all_files(self) -> Any:
        ingested_files = self._ingest_service.list_ingested()
        logger.debug("Deleting count=%s files", len(ingested_files))
        for ingested_document in ingested_files:
            self._ingest_service.delete(ingested_document.doc_id)
        return [
            gr.List(self._list_ingested_files()),
            gr.components.Button(interactive=False),
            gr.components.Button(interactive=False),
            gr.components.Textbox("All files"),
        ]

    def _delete_selected_file(self) -> Any:
        logger.debug("Deleting selected %s", self._selected_filename)
        # Note: keep looping for pdf's (each page became a Document)
        for ingested_document in self._ingest_service.list_ingested():
            if (
                ingested_document.doc_metadata
                and ingested_document.doc_metadata["file_name"]
                == self._selected_filename
            ):
                self._ingest_service.delete(ingested_document.doc_id)
        return [
            gr.List(self._list_ingested_files()),
            gr.components.Button(interactive=False),
            gr.components.Button(interactive=False),
            gr.components.Textbox("All files"),
        ]

    def _deselect_selected_file(self) -> Any:
        self._selected_filename = None
        return [
            gr.components.Button(interactive=False),
            gr.components.Button(interactive=False),
            gr.components.Textbox("All files"),
        ]

    def _selected_a_file(self, select_data: gr.SelectData) -> Any:
        self._selected_filename = select_data.value
        return [
            gr.components.Button(interactive=True),
            gr.components.Button(interactive=True),
            gr.components.Textbox(self._selected_filename),
        ]
    

    def get_ui_blocks(self) -> gr.Blocks:
        if self._ui_block is None: self._ui_block = self._build_ui_blocks()
        return self._ui_block

    def _build_ui_blocks(self) -> gr.Blocks:
        logger.debug("Creating the UI blocks")
        avatar_user = THIS_DIRECTORY_RELATIVE / "assets/avatar-user.png"

        def get_model_label() -> str | None:
            config_settings = settings()
            if config_settings is None: raise ValueError("Settings are not configured.")
            llm_mode = config_settings.llm.mode
            model_mapping = {
                "llamacpp": config_settings.llamacpp.llm_hf_model_file,
                "openai": config_settings.openai.model, "openailike": config_settings.openai.model,
                "azopenai": config_settings.azopenai.llm_model, "sagemaker": config_settings.sagemaker.llm_endpoint_name,
                "mock": llm_mode, "ollama": config_settings.ollama.llm_model, "gemini": config_settings.gemini.model,
            }
            if llm_mode not in model_mapping: return None
            return model_mapping[llm_mode]

        with gr.Blocks(
            title=UI_TAB_TITLE,
            theme=gr.themes.Default(primary_hue="slate", secondary_hue="purple"),
            css="./assets/style.css",
        ) as blocks:
            with gr.Row():
                gr.HTML(
                        f"""
                        <div class="logo-container">
                            <img src="{logo_svg}" alt="NEC GPT Logo" width="100" height="100">
                            <h1 class="fancy-header-text">NEC GPT</h1>
                        </div>
                        """
                    )

            with gr.Row(equal_height=False):
                with gr.Column(scale=3, elem_classes=["glass-panel", "sidebar"]):
                    theme_toggle_btn = gr.Button("🌓 Switch Theme", size="sm", elem_id="theme-toggle-btn")
                    gr.Markdown("### File Management")
                    upload_button = gr.components.UploadButton("📤 Upload File(s)", type="filepath", file_count="multiple", size="sm")
                    ingested_dataset = gr.List(self._list_ingested_files, headers=["File name"], label="Ingested Files", interactive=False, render=False)
                    ingested_dataset.render()
                    selected_text = gr.components.Textbox("All files", label="Selected File", max_lines=1, interactive=False)
                    with gr.Row():
                        deselect_file_button = gr.components.Button("✖️ De-select", size="sm", interactive=False)
                        delete_file_button = gr.components.Button("🗑️ Delete", size="sm", visible=settings().ui.delete_file_button_enabled, interactive=False)
                        delete_files_button = gr.components.Button("⚠️ Delete ALL", size="sm", visible=settings().ui.delete_all_files_button_enabled)
                    gr.Markdown("### Chat Settings")
                    mode = gr.Radio([mode.value for mode in MODES], label="Mode", value=self._default_mode)
                    system_prompt_input = gr.Textbox(placeholder=self._system_prompt, label="System Prompt", lines=2, interactive=True, render=False)
                    clear_chat_button = gr.Button("✨ Clear Chat", variant="secondary")
                    upload_button.upload(self._upload_file, inputs=upload_button, outputs=ingested_dataset)
                    ingested_dataset.change(self._list_ingested_files, outputs=ingested_dataset)
                    deselect_file_button.click(self._deselect_selected_file, outputs=[delete_file_button, deselect_file_button, selected_text])
                    ingested_dataset.select(fn=self._selected_a_file, outputs=[delete_file_button, deselect_file_button, selected_text])
                    delete_file_button.click(self._delete_selected_file, outputs=[ingested_dataset, delete_file_button, deselect_file_button, selected_text])
                    delete_files_button.click(self._delete_all_files, outputs=[ingested_dataset, delete_file_button, deselect_file_button, selected_text])
                    mode.change(self._set_current_mode, inputs=mode, outputs=[system_prompt_input])
                    system_prompt_input.blur(self._set_system_prompt, inputs=system_prompt_input)

                with gr.Column(scale=7, elem_id="col"):
                    gr.HTML("""<div class="chat-header"><h2>Chat</h2></div>""")
                    model_label = get_model_label()
                    label_text = f"LLM: {settings().llm.mode}"
                    if model_label is not None: label_text += f" | Model: {model_label}"
                    # THE FIX IS HERE: wrapping avatar paths with str()
                    chatbot = gr.Chatbot(
                        label=label_text, 
                        show_copy_button=True,
                        type="messages",
                        elem_id="chatbot", 
                        render=False, 
                        avatar_images=(str(avatar_user), str(AVATAR_BOT)) # See problem 2
                    )
                    _ = gr.ChatInterface(
                        self._chat,
                        chatbot=chatbot,
                        type="messages",
                        additional_inputs=[mode, upload_button, system_prompt_input]
                    )

            def clear_chat() -> None: return None
            clear_chat_button.click(fn=clear_chat, outputs=chatbot)
            
            theme_toggle_btn.click(None, None, None, js="""
                function() {
                    const url = new URL(window.location);
                    const currentTheme = url.searchParams.get('__theme') || 'dark';
                    if (currentTheme === 'dark') { url.searchParams.set('__theme', 'light'); } 
                    else { url.searchParams.set('__theme', 'dark'); }
                    window.location.href = url.toString();
                }
            """)
            return blocks
        
    def mount_in_app(self, app: FastAPI, path: str) -> None:
        blocks = self.get_ui_blocks()
        blocks.queue()
        logger.info("Mounting the gradio UI, at path=%s", path)
        gr.mount_gradio_app(app, blocks, path=path)
