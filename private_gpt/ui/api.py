import logging
from pathlib import Path
from typing import Any, List
import asyncio
import json
from enum import Enum
from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from llama_index.core.llms import ChatMessage, MessageRole
from pydantic import BaseModel

from private_gpt.database import (
    save_chat_message, 
    get_all_chat_sessions, 
    get_chat_history_by_session,
    create_user,
    get_all_users,
    get_user,
    update_user_details,
    update_user_password,
)
from private_gpt.di import global_injector
from private_gpt.server.chunks.chunks_service import ChunksService
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

# --- User Session & Info ---

@api_router.get("/session/expiry")
def get_session_expiry(request: Request):
    max_age = request.app.state.session_max_age
    return JSONResponse(content={"max_age": max_age if request.session.get("logged_in") else 0})

@api_router.get("/user/info")
def get_user_info(request: Request):
    if not request.session.get("logged_in"):
        return JSONResponse(content={"error": "Not authenticated"}, status_code=401)
    
    username = request.session.get("username", "user")
    db_user = get_user(username)

    if not db_user:
        return JSONResponse(content={"error": "User not found"}, status_code=404)

    return JSONResponse(content={
        "username": db_user['username'],
        "role": db_user['role'],
        "name": db_user['name'],
        "email": db_user['email'],
    })

# --- Chat Endpoints ---

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
    current_day = datetime.now().day
    processed_message = last_message.content.lower().replace("today's", f"at Day {current_day}").replace("today", f"at Day {current_day}")
    sanitized_content = processed_message.replace("{", "{{").replace("}", "}}")
    
    if chat_body.mode == Modes.SEARCH_MODE:
        # For search mode, save user message and assistant message together
        if user_id:
            save_chat_message(user_id, session_id, 'user', last_message.content, is_new_chat)

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
        
        if user_id:
            save_chat_message(user_id, session_id, 'assistant', search_response_text, False)
        
        async def search_stream_generator():
            if is_new_chat:
                yield f"data: {json.dumps({'session_id': session_id})}\n\n"
            yield f"data: {json.dumps({'delta': search_response_text})}\n\n"
            yield f"data: {json.dumps({'sources': sources_data})}\n\n"

        return StreamingResponse(search_stream_generator(), media_type="text/event-stream")

    # RAG Mode
    else:
        if user_id:
            save_chat_message(user_id, session_id, 'user', last_message.content, is_new_chat)
            
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

# --- File Management ---

@api_router.post("/upload", dependencies=[Depends(require_admin)])
async def upload_files(files: List[UploadFile] = File(...), ui: "PrivateGptUi" = Depends(get_ui)):
    temp_paths = []
    ingest_data = []
    
    try:
        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(exist_ok=True)

        for file in files:
            temp_path = temp_dir / file.filename
            
            with temp_path.open("wb") as buffer:
                buffer.write(await file.read())
                
            temp_paths.append(temp_path)
            ingest_data.append((str(file.filename), temp_path))

        if ingest_data:
            ui._ingest_service.bulk_ingest(ingest_data)
            
    finally:
        for path in temp_paths:
            if path.exists():
                path.unlink()
                
    return JSONResponse(content={"message": f"{len(files)} file(s) uploaded successfully"}, status_code=200)

@api_router.get("/files")
def list_ingested_files(ui: "PrivateGptUi" = Depends(get_ui)):
    files = set()
    for ingested_document in ui._ingest_service.list_ingested():
        if ingested_document.doc_metadata:
            files.add(ingested_document.doc_metadata.get("file_name", "[FILE NAME MISSING]"))
    return JSONResponse(content=[[row] for row in sorted(list(files))])

@api_router.delete("/files/{file_name}", dependencies=[Depends(require_admin)])
def delete_selected_file(file_name: str, ui: "PrivateGptUi" = Depends(get_ui)):
    for doc in ui._ingest_service.list_ingested():
        if doc.doc_metadata and doc.doc_metadata.get("file_name") == file_name:
            ui._ingest_service.delete(doc.doc_id)
    return {"message": f"File '{file_name}' deleted successfully"}

@api_router.delete("/files", dependencies=[Depends(require_admin)])
def delete_all_files(ui: "PrivateGptUi" = Depends(get_ui)):
    ingested_files = ui._ingest_service.list_ingested()
    for doc in ingested_files:
        ui._ingest_service.delete(doc.doc_id)
    return {"message": "All files deleted successfully"}

# --- Admin & Profile Endpoints ---

class UserUpdateBody(BaseModel):
    name: str | None = None
    email: str | None = None
    new_password: str | None = None

@api_router.post("/user/update")
async def handle_update_user(request: Request, body: UserUpdateBody):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    try:
        update_user_details(user_id, body.name, body.email)
        if body.new_password:
            update_user_password(user_id, body.new_password)
        return JSONResponse(content={"message": "Profile updated successfully."}, status_code=200)
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while updating profile.")

@api_router.get("/admin/users", dependencies=[Depends(require_admin)])
async def list_users():
    users = get_all_users()
    return JSONResponse(content=users)

class CreateUserBody(BaseModel):
    username: str
    password: str
    role: str

@api_router.post("/admin/create-user", dependencies=[Depends(require_admin)])
async def handle_create_user(body: CreateUserBody):
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

