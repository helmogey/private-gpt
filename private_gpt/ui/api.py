import logging
import os
import json
from pathlib import Path
from typing import List
from enum import Enum
from uuid import uuid4
from datetime import datetime
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from llama_index.core.llms import ChatMessage, MessageRole
from pydantic import BaseModel

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
    add_document_teams,
    get_document_teams,
)
from private_gpt.di import global_injector
from private_gpt.server.chat.chat_service import ChatService
from private_gpt.server.chunks.chunks_service import ChunksService
from private_gpt.settings.settings import settings

# This should match the value in launcher.py
SESSION_MAX_AGE = 600

api_router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

@api_router.get("/app-name")
def get_app_name():
    """Provides the application name from environment variables."""
    app_name = os.getenv("APP_NAME", "DocuMind")
    return JSONResponse(content={"appName": app_name})

class Modes(str, Enum):
    RAG_MODE = "RAG"
    SEARCH_MODE = "Search"

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

class DocumentPermissionBody(BaseModel):
    doc_id: str
    teams: list[str]

# --- UI Session & User Info Endpoints ---

@api_router.get("/session/expiry")
def get_session_expiry(request: Request):
    if request.session.get("logged_in"):
        return JSONResponse(content={"max_age": SESSION_MAX_AGE})
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
    ingest_service: "IngestService" = Depends(get_ingest_service)
):
    user_id = request.session.get("user_id")
    user_role = request.session.get("user_role")
    user_team = request.session.get("user_team")

    messages = [ChatMessage(role=MessageRole(m['role']), content=m['content']) for m in chat_body.messages]
    last_message = messages[-1] if messages else ChatMessage(role=MessageRole.USER, content="")

    # Save the original user message to the database before modifying it
    session_id = chat_body.session_id
    is_new_chat = not session_id
    if is_new_chat:
        session_id = str(uuid4())

    if user_id:
        save_chat_message(user_id, session_id, 'user', last_message.content, is_new_chat)

    # NEW: Conditionally add date context
    time_keywords = [
        "today", "yesterday", "tomorrow", "week", "month", "year", "now",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "january", "february", "march", "april", "may", "june", "july",
        "august", "september", "october", "november", "december"
    ]
    
    if any(keyword in last_message.content.lower() for keyword in time_keywords):
        current_date_str = datetime.now().strftime("%A, %B %d, %Y")
        prompt_with_date = (
            f"Assuming today's date is {current_date_str}, "
            f"please answer the following user query:\n\n{last_message.content}"
        )
        if messages:
            messages[-1].content = prompt_with_date

    # Handle Search Mode for Admins
    if user_role == 'admin' and chat_body.mode == Modes.SEARCH_MODE:
        context_filter = None
        if chat_body.context_filter and chat_body.context_filter.get("docs_ids"):
             context_filter = ContextFilter(docs_ids=chat_body.context_filter.get("docs_ids"))

        n_chunks = settings().rag.rerank.top_n if settings().rag.rerank.enabled else settings().rag.similarity_top_k
        relevant_chunks = chunks_service.retrieve_relevant(
            text=last_message.content, # Use original message for search
            limit=n_chunks, 
            prev_next_chunks=0,
            context_filter=context_filter
        )
        
        sources_data = [
            {
                "file": chunk.document.doc_metadata.get("file_name", "-") if chunk.document.doc_metadata else "-",
                "page": chunk.document.doc_metadata.get("page_label", "-") if chunk.document.doc_metadata else "-",
                "text": chunk.text,
            }
            for chunk in relevant_chunks
        ]
        
        search_response_text = "\n\n---\n\n".join(
            f"**Source:** {source['file']} (Page {source['page']})\n\n{source['text']}"
            for source in sources_data
        ) or "No relevant documents found for your search."
        
        if user_id:
            save_chat_message(user_id, session_id, 'assistant', search_response_text, False)

        async def search_stream_generator():
            if is_new_chat:
                yield f"data: {json.dumps({'session_id': session_id})}\n\n"
            yield f"data: {json.dumps({'delta': search_response_text})}\n\n"
            if sources_data:
                yield f"data: {json.dumps({'sources': sources_data})}\n\n"

        return StreamingResponse(search_stream_generator(), media_type="text/event-stream")

    # RAG Mode for all users (including Admins not in Search Mode)
    final_context_filter = None

    if user_role != 'admin':
        all_docs = ingest_service.list_ingested()
        allowed_doc_ids = [
            doc.doc_id for doc in all_docs if user_team in get_document_teams(doc.doc_id)
        ]
        if not allowed_doc_ids:
            async def empty_stream():
                if is_new_chat:
                    yield f"data: {json.dumps({'session_id': session_id})}\n\n"
                yield f"data: {json.dumps({'delta': 'You do not have access to any documents.'})}\n\n"
            return StreamingResponse(empty_stream(), media_type="text/event-stream")
        if chat_body.context_filter and chat_body.context_filter.get("docs_ids"):
            requested_doc_id = chat_body.context_filter["docs_ids"][0]
            if requested_doc_id in allowed_doc_ids:
                final_context_filter = ContextFilter(docs_ids=[requested_doc_id])
            else:
                async def denied_stream():
                    if is_new_chat:
                        yield f"data: {json.dumps({'session_id': session_id})}\n\n"
                    yield f"data: {json.dumps({'delta': 'Access denied to the selected document.'})}\n\n"
                return StreamingResponse(denied_stream(), media_type="text/event-stream")
        else:
            final_context_filter = ContextFilter(docs_ids=allowed_doc_ids)
    
    elif chat_body.context_filter and chat_body.context_filter.get("docs_ids"):
        final_context_filter = ContextFilter(docs_ids=chat_body.context_filter.get("docs_ids"))
    
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

@api_router.post("/upload", dependencies=[Depends(require_admin)])
async def upload_files(
    files: List[UploadFile] = File(...), 
    teams: str = Form(...),
    ingest_service: "IngestService" = Depends(get_ingest_service)
):
    temp_paths = []
    ingested_docs_info = []
    
    try:
        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(exist_ok=True)

        for file in files:
            temp_path = temp_dir / file.filename
            with temp_path.open("wb") as buffer:
                buffer.write(await file.read())
            temp_paths.append(temp_path)
            ingested_docs_info.append((str(file.filename), temp_path))

        if ingested_docs_info:
            ingested_docs = ingest_service.bulk_ingest(ingested_docs_info)
            team_list = json.loads(teams)
            
            # Group ingested docs by filename to correctly assign teams
            docs_by_filename = {}
            for doc in ingested_docs:
                filename = doc.doc_metadata.get("file_name")
                if filename:
                    if filename not in docs_by_filename:
                        docs_by_filename[filename] = []
                    docs_by_filename[filename].append(doc.doc_id)

            for filename, doc_ids in docs_by_filename.items():
                # Associate all doc_ids for a file with the selected teams
                for doc_id in doc_ids:
                    add_document_teams(doc_id, team_list)
            
    finally:
        for path in temp_paths:
            if path.exists():
                path.unlink()
                
    return JSONResponse(content={"message": f"{len(files)} file(s) uploaded successfully"}, status_code=200)

@api_router.get("/files")
def list_ingested_files(request: Request, ingest_service: "IngestService" = Depends(get_ingest_service)):
    user_role = request.session.get("user_role")
    user_team = request.session.get("user_team")
    
    all_docs = ingest_service.list_ingested()
    visible_files = {} # Use a dict to store name and one doc_id

    # Create a mapping from doc_id to its teams for efficient lookup
    doc_teams_map = {doc.doc_id: get_document_teams(doc.doc_id) for doc in all_docs}

    for doc in all_docs:
        if doc.doc_metadata:
            file_name = doc.doc_metadata.get("file_name")
            if not file_name:
                continue
            
            doc_teams = doc_teams_map.get(doc.doc_id, [])
            if user_role == 'admin' or user_team in doc_teams:
                # Store the filename and one associated doc_id
                if file_name not in visible_files:
                    visible_files[file_name] = doc.doc_id
    
    # Format for the frontend [[file_name, doc_id]]
    return JSONResponse(content=[[name, doc_id] for name, doc_id in sorted(visible_files.items())])


@api_router.delete("/files/{file_name}", dependencies=[Depends(require_admin)])
def delete_selected_file(file_name: str, ingest_service: "IngestService" = Depends(get_ingest_service)):
    decoded_file_name = unquote(file_name)
    
    all_docs = ingest_service.list_ingested()
    doc_ids_to_delete = [
        doc.doc_id for doc in all_docs 
        if doc.doc_metadata and doc.doc_metadata.get("file_name") == decoded_file_name
    ]

    if not doc_ids_to_delete:
        raise HTTPException(status_code=404, detail=f"File '{decoded_file_name}' not found.")

    for doc_id in doc_ids_to_delete:
        try:
            ingest_service.delete(doc_id)
        except Exception as e:
            logger.error(f"Error deleting chunk {doc_id} for file {decoded_file_name}: {e}")

    return JSONResponse(content={"message": f"File '{decoded_file_name}' deleted successfully"}, status_code=200)


@api_router.delete("/files", dependencies=[Depends(require_admin)])
def delete_all_files(ingest_service: "IngestService" = Depends(get_ingest_service)):
    ingested_files = ingest_service.list_ingested()
    for doc in ingested_files:
        ingest_service.delete(doc.doc_id)
    return {"message": "All files deleted successfully"}

# --- Admin Endpoints ---

@api_router.get("/admin/documents/permissions", dependencies=[Depends(require_admin)])
def get_documents_with_permissions(ingest_service: "IngestService" = Depends(get_ingest_service)):
    """Retrieves all unique documents and their associated teams."""
    all_docs = ingest_service.list_ingested()
    
    # Use a dictionary to handle multiple chunks from the same file
    unique_files = {}
    for doc in all_docs:
        if doc.doc_metadata and doc.doc_metadata.get("file_name"):
            file_name = doc.doc_metadata.get("file_name")
            # Store the first doc_id found for a given file name
            if file_name not in unique_files:
                unique_files[file_name] = doc.doc_id

    result = []
    for file_name, doc_id in unique_files.items():
        teams = get_document_teams(doc_id)
        result.append({
            "doc_id": doc_id, # We only need one ID to manage teams for the whole file
            "file_name": file_name,
            "teams": teams
        })
        
    return JSONResponse(content=sorted(result, key=lambda x: x['file_name']))

@api_router.post("/admin/documents/permissions", dependencies=[Depends(require_admin)])
def update_document_permissions(body: DocumentPermissionBody, ingest_service: "IngestService" = Depends(get_ingest_service)):
    """Updates the team permissions for all chunks of a document."""
    try:
        # Find the target document from the list of all ingested documents
        all_docs = ingest_service.list_ingested()
        target_doc = next((doc for doc in all_docs if doc.doc_id == body.doc_id), None)

        if not target_doc or not target_doc.doc_metadata:
            raise HTTPException(status_code=404, detail="Document not found.")
        
        file_name = target_doc.doc_metadata.get("file_name")
        if not file_name:
            raise HTTPException(status_code=400, detail="Document is missing a file name.")

        # Find all doc_ids associated with that file_name
        doc_ids_to_update = [
            doc.doc_id for doc in all_docs 
            if doc.doc_metadata and doc.doc_metadata.get("file_name") == file_name
        ]

        # Update teams for every chunk of the document
        for doc_id in doc_ids_to_update:
            add_document_teams(doc_id, body.teams)
            
        return JSONResponse(content={"message": "Permissions updated successfully"})
    except Exception as e:
        logger.error(f"Error updating permissions for doc_id {body.doc_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

