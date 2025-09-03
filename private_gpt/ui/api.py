import logging
import os
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
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters
from pydantic import BaseModel

# ADDED: Import the ContextFilter object
from private_gpt.open_ai.extensions.context_filter import ContextFilter
from private_gpt.database import (
    save_chat_message, 
    get_all_chat_sessions, 
    get_chat_history_by_session,
    create_user,
    get_all_users,
    get_user,
    update_user_details,
    update_user_password,
    delete_user,
    add_document_tags,
    get_files_for_teams,
    delete_document_tags,
)
from private_gpt.di import global_injector
from private_gpt.server.chat.chat_service import ChatService
from private_gpt.server.chunks.chunks_service import ChunksService
from private_gpt.settings.settings import settings

class Modes(str, Enum):
    RAG_MODE = "RAG"
    SEARCH_MODE = "Search"

api_router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

# --- Dependency Injectors ---

def get_chat_service() -> ChatService:
    return global_injector.get(ChatService)

def get_chunks_service() -> ChunksService:
    return global_injector.get(ChunksService)

def get_ingest_service() -> "IngestService":
    from private_gpt.server.ingest.ingest_service import IngestService
    return global_injector.get(IngestService)

# --- Utility and Authentication ---

async def require_admin(request: Request):
    """Dependency to check if the user has an 'admin' role."""
    if request.session.get("user_role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Requires admin privileges")
    return True

# --- Pydantic Models ---

class ChatBody(BaseModel):
    messages: list[dict[str, str]]
    mode: str = "RAG"
    context_filter: dict | None = None
    session_id: str | None = None

class CreateUserBody(BaseModel):
    username: str
    password: str
    role: str
    team: str

class UpdateUserBody(BaseModel):
    name: str
    email: str
    new_password: str | None = None

# --- UI Session & User Info Endpoints ---

@api_router.get("/session/expiry")
def get_session_expiry(request: Request):
    if request.session.get("logged_in"):
        return JSONResponse(content={"max_age": settings().server.session_max_age})
    return JSONResponse(content={"max_age": 0}, status_code=401)

@api_router.get("/user/info")
def get_user_info(request: Request):
    if not request.session.get("logged_in"):
        return JSONResponse(content={"error": "Not authenticated"}, status_code=401)
    
    username = request.session.get("username", "user")
    db_user = get_user(username)

    if not db_user:
        return JSONResponse(content={"error": "User not found"}, status_code=404)

    display_name = db_user['name'] if db_user['name'] else db_user['username']

    return JSONResponse(content={
        "username": db_user['username'],
        "role": db_user['role'],
        "name": db_user['name'],
        "email": db_user['email'],
        "display_name": display_name,
        "team": db_user['team'],
    })

@api_router.post("/user/update")
async def handle_update_user(request: Request, body: UpdateUserBody):
    if not request.session.get("logged_in"):
        raise HTTPException(status_code=401, detail="Not authenticated")

    username = request.session.get("username")
    update_user_details(username, body.name, body.email)

    if body.new_password:
        update_user_password(username, body.new_password)
    
    return JSONResponse(content={"message": "Profile updated successfully."}, status_code=200)

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
    chat_body: ChatBody,
    chat_service: ChatService = Depends(get_chat_service),
    chunks_service: ChunksService = Depends(get_chunks_service),
    ingest_service: "IngestService" = Depends(get_ingest_service),
):
    user_id = request.session.get("user_id")
    user_team = request.session.get("user_team")
    user_role = request.session.get("user_role")

    session_id = chat_body.session_id
    is_new_chat = not session_id
    if is_new_chat:
        session_id = str(uuid4())

    # --- MODIFIED: Build a proper ContextFilter object using doc_ids ---
    final_context_filter = None
    doc_ids_to_filter_by = []
    
    # Check if a specific file was selected in the UI. The frontend sends file names in the 'docs_ids' key.
    selected_filenames = chat_body.context_filter.get("docs_ids") if chat_body.context_filter else None

    if selected_filenames:
        # User selected a specific file, so we filter by it.
        # This applies to both admins and regular users.
        all_ingested_docs = ingest_service.list_ingested()
        doc_ids_to_filter_by = [
            doc.doc_id
            for doc in all_ingested_docs
            if doc.doc_metadata and doc.doc_metadata.get("file_name") in selected_filenames
        ]
    elif user_role != 'admin':
        # No specific file selected, so apply team-based filtering for non-admins.
        all_ingested_docs = ingest_service.list_ingested()
        allowed_files_for_team = get_files_for_teams([user_team]) if user_team else []
        
        if allowed_files_for_team:
            doc_ids_to_filter_by = [
                doc.doc_id
                for doc in all_ingested_docs
                if doc.doc_metadata and doc.doc_metadata.get("file_name") in allowed_files_for_team
            ]

    # If after all filtering, the list is empty for a non-admin or for a selection,
    # we must provide a dummy ID to search for nothing.
    if (selected_filenames or user_role != 'admin') and not doc_ids_to_filter_by:
        doc_ids_to_filter_by = ["dummy-id-that-will-not-be-found"]

    # Only create a context filter if there are specific doc IDs to filter by.
    # An admin querying all docs will have an empty list, and final_context_filter will be None.
    if doc_ids_to_filter_by:
        final_context_filter = ContextFilter(docs_ids=doc_ids_to_filter_by)

    messages = [ChatMessage(role=MessageRole(m['role']), content=m['content']) for m in chat_body.messages]
    last_message = messages[-1] if messages else ChatMessage(role=MessageRole.USER, content="")
    current_day = datetime.now().day
    processed_message = last_message.content.lower().replace("today's", f"at Day {current_day}").replace("today", f"at Day {current_day}")
    sanitized_content = processed_message.replace("{", "{{").replace("}", "}}")

    if user_id:
        save_chat_message(user_id, session_id, 'user', last_message.content, is_new_chat)
    
    if chat_body.mode == Modes.SEARCH_MODE:
        n_chunks = settings().rag.rerank.top_n if settings().rag.rerank.enabled else settings().rag.similarity_top_k
        relevant_chunks = chunks_service.retrieve_relevant(
            text=sanitized_content, 
            limit=n_chunks, 
            prev_next_chunks=0,
            context_filter=final_context_filter 
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
        
        if user_id:
            save_chat_message(user_id, session_id, 'assistant', search_response_text, False)

        async def search_stream_generator():
            if is_new_chat:
                yield f"data: {json.dumps({'session_id': session_id})}\n\n"
            yield f"data: {json.dumps({'delta': search_response_text})}\n\n"
            if sources_data:
                yield f"data: {json.dumps({'sources': sources_data})}\n\n"

        return StreamingResponse(search_stream_generator(), media_type="text/event-stream")

    messages[-1] = ChatMessage(role=last_message.role, content=sanitized_content)

    completion_gen = chat_service.stream_chat(
        messages=messages,
        use_context=True,
        context_filter=final_context_filter,
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

# --- File Management Endpoints ---

@api_router.post("/upload", dependencies=[Depends(require_admin)])
async def upload_files(
    files: List[UploadFile] = File(...), 
    teams: str = Form("[]"),
    ingest_service: "IngestService" = Depends(get_ingest_service)
):
    try:
        teams_list = json.loads(teams)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid format for teams. Must be a JSON array string.")

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
            ingest_service.bulk_ingest(ingest_data)
            for file in files:
                add_document_tags(file.filename, teams_list)
            
    finally:
        for path in temp_paths:
            if path.exists():
                path.unlink()
                
    return JSONResponse(content={"message": f"{len(files)} file(s) uploaded and tagged successfully"}, status_code=200)

@api_router.get("/files")
def list_ingested_files(request: Request, ingest_service: "IngestService" = Depends(get_ingest_service)):
    user_team = request.session.get("user_team")
    user_role = request.session.get("user_role")

    ingested_files_in_store = {
        doc.doc_metadata.get("file_name")
        for doc in ingest_service.list_ingested()
        if doc.doc_metadata and doc.doc_metadata.get("file_name")
    }

    if user_role == 'admin':
        allowed_files = list(ingested_files_in_store)
    elif user_team:
        files_for_team = set(get_files_for_teams([user_team]))
        allowed_files = list(ingested_files_in_store.intersection(files_for_team))
    else:
        allowed_files = []

    return JSONResponse(content=[[row] for row in sorted(allowed_files)])

@api_router.delete("/files/{file_name}", dependencies=[Depends(require_admin)])
def delete_selected_file(file_name: str, ingest_service: "IngestService" = Depends(get_ingest_service)):
    doc_ids_to_delete = [
        doc.doc_id
        for doc in ingest_service.list_ingested()
        if doc.doc_metadata and doc.doc_metadata.get("file_name") == file_name
    ]
    
    if not doc_ids_to_delete:
        logger.warning(f"File '{file_name}' not found in vector store, but attempting to clear tags.")
    
    for doc_id in doc_ids_to_delete:
        ingest_service.delete(doc_id)
        
    delete_document_tags(file_name)
    
    return {"message": f"File '{file_name}' and its tags deleted successfully"}

@api_router.delete("/files", dependencies=[Depends(require_admin)])
def delete_all_files(ingest_service: "IngestService" = Depends(get_ingest_service)):
    ingested_files = ingest_service.list_ingested()
    for doc in ingested_files:
        ingest_service.delete(doc.doc_id)
        if doc.doc_metadata and doc.doc_metadata.get("file_name"):
            delete_document_tags(doc.doc_metadata.get("file_name"))
    return {"message": "All files and their tags have been deleted successfully"}

# --- Admin Endpoints ---

@api_router.get("/admin/teams")
async def get_teams_list():
    """Provides the list of available teams from environment variables."""
    teams_str = os.getenv("TEAMS_LIST", "Default")
    teams_list = [team.strip() for team in teams_str.split(',')]
    return JSONResponse(content=teams_list)

@api_router.get("/admin/users", dependencies=[Depends(require_admin)])
async def list_users():
    """Lists all users. Admin only."""
    users = get_all_users()
    return JSONResponse(content=users)

@api_router.post("/admin/create-user", dependencies=[Depends(require_admin)])
async def handle_create_user(body: CreateUserBody):
    """Creates a new user. Admin only."""
    if get_user(body.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    if body.role not in ['admin', 'user']:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'user'.")
    
    teams_str = os.getenv("TEAMS_LIST", "Default")
    teams_list = [team.strip() for team in teams_str.split(',')]
    if body.team not in teams_list:
        raise HTTPException(status_code=400, detail=f"Invalid team '{body.team}'. Must be one of {teams_list}")
        
    try:
        create_user(body.username, body.password, body.role, body.team)
        return JSONResponse(content={"message": f"User '{body.username}' created successfully."}, status_code=201)
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while creating user.")
    

@api_router.delete("/admin/users/{username}", dependencies=[Depends(require_admin)])
async def handle_delete_user(username: str, request: Request):
    """Deletes a user. Admin only."""
    logged_in_user = request.session.get("username")
    if username == logged_in_user:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")

    try:
        delete_user(username)
        return JSONResponse(content={"message": f"User '{username}' deleted successfully."}, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting user '{username}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error while deleting user.")

