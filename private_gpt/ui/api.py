import logging
from pathlib import Path
from typing import Any
import asyncio
import json
from enum import Enum
from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from llama_index.core.llms import ChatMessage, MessageRole
from pydantic import BaseModel
from fastapi.responses import StreamingResponse, JSONResponse

from private_gpt.database import save_chat_message, get_chat_history
from private_gpt.di import global_injector
from private_gpt.server.chat.chat_service import ChatService, CompletionGen
from private_gpt.server.chunks.chunks_service import Chunk, ChunksService
from private_gpt.server.ingest.ingest_service import IngestService
from private_gpt.settings.settings import settings

# Re-define Modes here or move to a shared models file to avoid circular imports
class Modes(str, Enum):
    RAG_MODE = "RAG"
    SEARCH_MODE = "Search"

# Create a new API router
api_router = APIRouter(prefix="/api")

logger = logging.getLogger(__name__)

# This function now uses a string "PrivateGptUi" as a type hint (Forward Reference)
# and imports the class *inside* the function. This delays the import until
# the function is called, breaking the import cycle.
def get_ui() -> "PrivateGptUi":
    from private_gpt.ui.ui import PrivateGptUi 
    return global_injector.get(PrivateGptUi)

# Add ChunksService dependency
def get_chunks_service() -> ChunksService:
    return global_injector.get(ChunksService)

class ChatBody(BaseModel):
    messages: list[dict[str, str]]
    mode: str = "RAG" # ADDED MODE
    context_filter: dict | None = None

# --- API Endpoints ---

@api_router.get("/chat/history")
async def get_history(request: Request):
    """
    Retrieves the most recent chat history for the logged-in user and sets
    the session ID to continue the conversation.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(content={"error": "User not authenticated"}, status_code=401)
    
    history_data = get_chat_history(user_id)
    
    # If a previous session is found, set it in the user's cookie so new messages
    # are added to the same conversation.
    if history_data.get("session_id"):
        request.session["chat_session_id"] = history_data["session_id"]
        
    return JSONResponse(content={"history": history_data["messages"]})


@api_router.post("/chat")
async def chat(
    request: Request, 
    ui: "PrivateGptUi" = Depends(get_ui),
    chunks_service: ChunksService = Depends(get_chunks_service)
):
    """
    Handles the chat stream, saves messages to the database, and calls the existing logic.
    """
    # Get user and session info from the secure session cookie
    user_id = request.session.get("user_id")
    session_id = request.session.get("chat_session_id")
    if not session_id:
        session_id = str(uuid4())
        request.session["chat_session_id"] = session_id

    body = await request.json()
    chat_body = ChatBody.parse_obj(body)

    messages = [ChatMessage(role=MessageRole(m['role']), content=m['content']) for m in chat_body.messages]
    last_message = messages[-1] if messages else ChatMessage(role=MessageRole.USER, content="")

    # Save the user's message to the database if a user is logged in
    if user_id:
        save_chat_message(user_id, session_id, 'user', last_message.content)

    # Sanitize content for processing
    current_day = datetime.now().day
    processed_message = last_message.content.lower().replace("today's", f"at Day {current_day}").replace("today", f"at Day {current_day}")
    sanitized_content = processed_message.replace("{", "{{").replace("}", "}}")
    
    # --- MODE HANDLING ---
    if chat_body.mode == Modes.SEARCH_MODE:
        if settings().rag.rerank.enabled:
            n_chunks = settings().rag.rerank.top_n
        else:
            n_chunks = settings().rag.similarity_top_k
        
        relevant_chunks = chunks_service.retrieve_relevant(
            text=sanitized_content, limit=n_chunks, prev_next_chunks=0
        )
        
        sources_data = [
            {
                "file": chunk.document.doc_metadata.get("file_name", "-") if chunk.document.doc_metadata else "-",
                "page": chunk.document.doc_metadata.get("page_label", "-") if chunk.document.doc_metadata else "-",
                "text": chunk.text,
            }
            for chunk in relevant_chunks
        ]
        
        search_response_text = "\n\n\n".join(
            f"{index}. **{source['file']} (page {source['page']})**\n{source['text']}"
            for index, source in enumerate(sources_data, start=1)
        )
        
        # Save the assistant's search response to the database
        if user_id:
            save_chat_message(user_id, session_id, 'assistant', search_response_text)
        
        async def search_stream_generator():
            yield f"data: {json.dumps({'delta': search_response_text})}\n\n"

        return StreamingResponse(search_stream_generator(), media_type="text/event-stream")

    # --- RAG MODE LOGIC ---
    messages[-1] = ChatMessage(role=last_message.role, content=sanitized_content)

    completion_gen = ui._chat_service.stream_chat(
        messages=messages,
        use_context=True,
        context_filter=chat_body.context_filter,
    )

    async def stream_generator():
        full_response = ""
        for delta in completion_gen.response:
            text_delta = delta if isinstance(delta, str) else delta.delta
            full_response += text_delta  # Accumulate the response
            yield f"data: {json.dumps({'delta': text_delta})}\n\n"
            await asyncio.sleep(0.02)
        
        # After the stream is complete, save the full assistant response
        if user_id:
            save_chat_message(user_id, session_id, 'assistant', full_response)
        
        if completion_gen.sources:
            sources_data = [
                {
                    "file": chunk.document.doc_metadata.get("file_name", "-") if chunk.document.doc_metadata else "-",
                    "page": chunk.document.doc_metadata.get("page_label", "-") if chunk.document.doc_metadata else "-",
                    "text": chunk.text,
                }
                for chunk in completion_gen.sources
            ]
            yield f"data: {json.dumps({'sources': sources_data})}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


@api_router.post("/upload")
async def upload_file(file: UploadFile = File(...), ui: "PrivateGptUi" = Depends(get_ui)):
    temp_path = Path("temp_uploads") / file.filename
    temp_path.parent.mkdir(exist_ok=True)
    try:
        with temp_path.open("wb") as buffer:
            buffer.write(await file.read())
        ui._ingest_service.bulk_ingest([(str(file.filename), temp_path)])
        return ui._list_ingested_files()
    finally:
        if temp_path.exists():
            temp_path.unlink()

@api_router.get("/files")
def list_ingested_files(ui: "PrivateGptUi" = Depends(get_ui)):
    return ui._list_ingested_files()

@api_router.delete("/files/{file_name}")
def delete_selected_file(file_name: str, ui: "PrivateGptUi" = Depends(get_ui)):
    for doc in ui._ingest_service.list_ingested():
        if doc.doc_metadata and doc.doc_metadata.get("file_name") == file_name:
            ui._ingest_service.delete(doc.doc_id)
    return {"message": f"File '{file_name}' deleted successfully"}


@api_router.delete("/files")
def delete_all_files(ui: "PrivateGptUi" = Depends(get_ui)):
    ingested_files = ui._ingest_service.list_ingested()
    for doc in ingested_files:
        ui._ingest_service.delete(doc.doc_id)
    return {"message": "All files deleted successfully"}
