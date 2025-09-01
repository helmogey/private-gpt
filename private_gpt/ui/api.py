import logging
from pathlib import Path
from typing import Any
import asyncio
import json
from enum import Enum
from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from llama_index.core.llms import ChatMessage, MessageRole
from pydantic import BaseModel
from fastapi.responses import StreamingResponse, JSONResponse

from private_gpt.database import (
    save_chat_message, 
    get_all_chat_sessions, 
    get_chat_history_by_session,
    create_user,
    get_all_users,
    get_user
)

from private_gpt.database import save_chat_message, get_all_chat_sessions, get_chat_history_by_session
from private_gpt.di import global_injector
from private_gpt.server.chat.chat_service import ChatService, CompletionGen
from private_gpt.server.chunks.chunks_service import Chunk, ChunksService
from private_gpt.server.ingest.ingest_service import IngestService
from private_gpt.settings.settings import settings

class Modes(str, Enum):
    RAG_MODE = "RAG"
    SEARCH_MODE = "Search"

api_router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

def get_ui() -> "PrivateGptUi":
    from private_gpt.ui.ui import PrivateGptUi 
    return global_injector.get(PrivateGptUi)

def get_chunks_service() -> ChunksService:
    return global_injector.get(ChunksService)

class ChatBody(BaseModel):
    messages: list[dict[str, str]]
    mode: str = "RAG"
    context_filter: dict | None = None
    session_id: str | None = None



async def require_admin(request: Request):
    """Dependency to check if the user has an 'admin' role."""
    if request.session.get("user_role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Requires admin privileges")
    return True

# --- API Endpoints ---

@api_router.get("/chats")
async def get_chats(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(content={"error": "User not authenticated"}, status_code=401)
    sessions = get_all_chat_sessions(user_id)
    return JSONResponse(content=sessions)

@api_router.get("/chat/history/{session_id}")
async def get_history_by_session(session_id: str, request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(content={"error": "User not authenticated"}, status_code=401)
    history_data = get_chat_history_by_session(user_id, session_id)
    return JSONResponse(content={"history": history_data["messages"]})


@api_router.post("/chat")
async def chat(
    request: Request, 
    ui: "PrivateGptUi" = Depends(get_ui),
    chunks_service: ChunksService = Depends(get_chunks_service)
):
    user_id = request.session.get("user_id")
    body = await request.json()
    chat_body = ChatBody.parse_obj(body)
    
    session_id = chat_body.session_id
    is_new_chat = not session_id
    if is_new_chat:
        session_id = str(uuid4())

    messages = [ChatMessage(role=MessageRole(m['role']), content=m['content']) for m in chat_body.messages]
    last_message = messages[-1] if messages else ChatMessage(role=MessageRole.USER, content="")

    if user_id and chat_body.mode == Modes.RAG_MODE:
        save_chat_message(user_id, session_id, 'user', last_message.content, is_new_chat)
    elif user_id and chat_body.mode == Modes.SEARCH_MODE and is_new_chat:
        # For Search mode, we only save one message to create the session.
        save_chat_message(user_id, session_id, 'user', last_message.content, is_new_chat)


    sanitized_content = last_message.content.replace("{", "{{").replace("}", "}}")
    
    if chat_body.mode == Modes.SEARCH_MODE:
        n_chunks = settings().rag.rerank.top_n if settings().rag.rerank.enabled else settings().rag.similarity_top_k
        relevant_chunks = chunks_service.retrieve_relevant(text=sanitized_content, limit=n_chunks, prev_next_chunks=0)
        
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
        
        async def search_stream_generator():
            if is_new_chat:
                yield f"data: {json.dumps({'session_id': session_id})}\n\n"
            yield f"data: {json.dumps({'delta': search_response_text})}\n\n"

        return StreamingResponse(search_stream_generator(), media_type="text/event-stream")

    messages[-1] = ChatMessage(role=last_message.role, content=sanitized_content)

    completion_gen = ui._chat_service.stream_chat(
        messages=messages,
        use_context=True,
        context_filter=chat_body.context_filter,
    )

    async def stream_generator():
        full_response = ""
        if is_new_chat:
            yield f"data: {json.dumps({'session_id': session_id})}\n\n"
            
        for delta in completion_gen.response:
            text_delta = delta if isinstance(delta, str) else delta.delta
            full_response += text_delta
            yield f"data: {json.dumps({'delta': text_delta})}\n\n"
            await asyncio.sleep(0.02)
        
        if user_id:
            save_chat_message(user_id, session_id, 'assistant', full_response, False)
        
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
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return JSONResponse(content={"message": "File uploaded successfully"}, status_code=200)

@api_router.get("/files")
def list_ingested_files(ui: "PrivateGptUi" = Depends(get_ui)):
    files = set()
    for ingested_document in ui._ingest_service.list_ingested():
        if ingested_document.doc_metadata:
            files.add(ingested_document.doc_metadata.get("file_name", "[FILE NAME MISSING]"))
    return JSONResponse(content=[[row] for row in sorted(list(files))])

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


# --- Admin Endpoints ---

@api_router.get("/admin/users", dependencies=[Depends(require_admin)])
async def list_users():
    """Lists all users. Admin only."""
    users = get_all_users()
    return JSONResponse(content=users)

class CreateUserBody(BaseModel):
    username: str
    password: str
    role: str

@api_router.post("/admin/create-user", dependencies=[Depends(require_admin)])
async def handle_create_user(body: CreateUserBody):
    """Creates a new user. Admin only."""
    if get_user(body.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    if body.role not in ['admin', 'user']:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'user'.")
        
    try:
        create_user(body.username, body.password, body.role)
        return JSONResponse(content={"message": f"User '{body.username}' created successfully."}, status_code=201)
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while creating user.")
    


