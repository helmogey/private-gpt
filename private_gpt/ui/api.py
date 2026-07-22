import logging
import os
import json
import warnings
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
import httpx

# Suppress the deprecation warning to keep logs clean
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
import google.generativeai as genai

from private_gpt.open_ai.extensions.context_filter import ContextFilter
from private_gpt.database import (
    get_llm_config, 
    save_llm_config,
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
    admin_update_user,
    add_document_tags,      
    get_document_tags,      
    get_docs_by_tag,
    create_mcp_config,      
    get_all_mcp_configs,    
    delete_mcp_config,
    update_mcp_config       
)
from private_gpt.di import global_injector
from private_gpt.server.chat.chat_service import ChatService
from private_gpt.server.chunks.chunks_service import ChunksService
from private_gpt.server.ingest.ingest_service import IngestService
from private_gpt.settings.settings import settings

# This should match the value in launcher.py
SESSION_MAX_AGE = 600

api_router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

@api_router.get("/branding")
def get_branding_info():
    """Provides the application name and logo URL from environment variables."""
    app_name = os.getenv("APP_NAME", "DocuMind")
    logo_url = os.getenv("APP_LOGO_URL", "/assets/NEC-Logo.svg")
    return JSONResponse(content={"appName": app_name, "logoUrl": logo_url})

# --- [2025-12-03] New Endpoint to Expose Valid Tags ---
@api_router.get("/tags")
def get_tags():
    """
    [2025-12-03] Returns the list of valid tags/categories from the environment.
    Used by the frontend to populate upload dropdowns and admin filters.
    """
    default_categories = "GENERAL,EMPLOYEE,SERVER,ZABBIX"
    valid_categories_str = os.getenv("VALID_QUERY_CATEGORIES", default_categories)
    valid_categories = [cat.strip().upper() for cat in valid_categories_str.split(',') if cat.strip()]
    return JSONResponse(content=valid_categories)

class Modes(str, Enum):
    RAG_MODE = "RAG"
    SEARCH_MODE = "Search"

# --- Dependency Injectors ---

def get_chat_service() -> ChatService:
    return global_injector.get(ChatService)

def get_chunks_service() -> ChunksService:
    return global_injector.get(ChunksService)

def get_ingest_service() -> IngestService:
    return global_injector.get(IngestService)

# --- Utility and Authentication ---

async def require_admin(request: Request):
    """Dependency to check if the user has an 'admin' role."""
    if request.session.get("user_role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Requires admin privileges")
    return True

# --- [2025-12-03] Category Identification Helper ---

def identify_query_category(chat_service: ChatService, user_query: str) -> str:
    """
    Classifies the user intent using the LLM into specific categories.
    Returns one of the categories defined in VALID_QUERY_CATEGORIES env var.
    """
    try:
        # Access the LLM directly from the component within chat_service
        llm = chat_service.llm_component.llm
        
        # Default prompt if .env variable is missing
        default_prompt = (
            "You are a query router. Classify the user's input into one of the following categories:\n"
            "1. 'GENERAL': General information requests or casual chat.\n"
            "2. 'EMPLOYEE': Requests about employee details, roles, HR info, or teams.\n"
            "3. 'SERVER': Requests about server specs, hardware, or general infrastructure info (excluding live monitoring).\n"
            "4. 'ZABBIX': Specific monitoring requests, plots, CPU/Memory stats, active problems, or Zabbix alerts.\n\n"
            "User Query: {user_query}\n\n"
            "Respond ONLY with the category name (e.g., 'ZABBIX', 'EMPLOYEE')."
        )
        
        # Load prompt from environment variable, fallback to default
        prompt_template = os.getenv("CATEGORY_CLASSIFICATION_PROMPT", default_prompt)
        prompt_template = prompt_template.replace('\\n', '\n')
        
        # Inject the user query into the template
        if "{user_query}" in prompt_template:
            classification_prompt = prompt_template.replace("{user_query}", user_query)
        else:
            logger.warning("CATEGORY_CLASSIFICATION_PROMPT missing '{user_query}' placeholder. Appending query to end.")
            classification_prompt = f"{prompt_template}\n\nUser Query: {user_query}"
        
        # Use a temporary ChatMessage list for this classification call
        response = llm.chat([ChatMessage(role=MessageRole.USER, content=classification_prompt)])
        category = response.message.content.strip().upper()
        
        # Load valid categories from Env
        default_categories = "GENERAL,EMPLOYEE,SERVER,ZABBIX"
        valid_categories_str = os.getenv("VALID_QUERY_CATEGORIES", default_categories)
        valid_categories = [cat.strip().upper() for cat in valid_categories_str.split(',') if cat.strip()]
        
        for valid in valid_categories:
            if valid in category:
                return valid
        
        if "GENERAL" in valid_categories:
            return "GENERAL"
        return valid_categories[0] if valid_categories else "GENERAL"
        
    except Exception as e:
        logger.error(f"Error identifying category: {e}")
        return "GENERAL"

# --- Pydantic Models ---

class ChatBody(BaseModel):
    messages: list[dict[str, str]]
    mode: str = "RAG"
    context_filter: dict | None = None
    session_id: str | None = None
    # [2025-12-14] Add category field for manual selection
    category: str | None = "Default"

class CreateUserBody(BaseModel):
    username: str
    password: str
    role: str
    team: List[str]

class UpdateUserBody(BaseModel):
    name: str
    email: str
    new_password: str | None = None

class AdminUpdateUserBody(BaseModel):
    username: str
    new_role: str
    new_teams: List[str]

class AdminResetPasswordBody(BaseModel):
    username: str
    new_password: str
    
class DocumentPermissionBody(BaseModel):
    file_name: str
    teams: List[str]
    tags: List[str] = []

class LLMModelsRequest(BaseModel):
    provider: str
    url: str | None = None
    token: str | None = None

class LLMConfigRequest(BaseModel):
    provider: str
    url: str | None = None
    token: str | None = None
    model: str

class MCPConfigBody(BaseModel):
    name: str
    transport_type: str
    command: str
    args: List[str] = []
    env_vars: dict = {}

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
        "teams": db_user['teams'] 
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
    ingest_service: IngestService = Depends(get_ingest_service)
):
    from private_gpt.launcher import mcp_manager # Fetch global MCP manager
    
    user_id = request.session.get("user_id")
    user_role = request.session.get("user_role")
    user_teams = request.session.get("user_teams", [])

    messages = [ChatMessage(role=MessageRole(m['role']), content=m['content']) for m in chat_body.messages]
    last_message = messages[-1] if messages else ChatMessage(role=MessageRole.USER, content="")

    user_selected_category = chat_body.category
    
    # Define categories that have MCP tools attached
    tool_categories = ["ZABBIX"]
    
    if user_selected_category and user_selected_category.upper() != "DEFAULT":
        query_category = user_selected_category.upper()
        logger.info(f"Incoming Query: '{last_message.content}' | Manual Category: {query_category}")
    else:
        query_category = identify_query_category(chat_service, last_message.content)
        logger.info(f"Incoming Query: '{last_message.content}' | Identified Category (Auto): {query_category}")

    # --- NEW: Retrieve and filter active MCP Tools for this category ---
    active_mcp_tools = []
    all_mcp_tools = mcp_manager.get_all_tools()
    
    system_prompt_override = None

    if query_category == "ZABBIX":
        # Broaden the filter to capture initMAX tools like host_get, problem_get, etc., 
        # regardless of what the MCP connection is named in the DB.
        active_mcp_tools = [
            tool for tool in all_mcp_tools 
            if any(keyword in tool.metadata.name.lower() or keyword in tool.metadata.description.lower() 
                   for keyword in ["zabbix", "host", "problem", "trigger", "event"])
        ]
        
        if active_mcp_tools:
            system_prompt_override = (
                "You are an expert Zabbix administrator monitoring infrastructure.\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. You have access to specific Zabbix tools (e.g., host_get, problem_get, trigger_get).\n"
                "2. YOU MUST USE these tools to fetch live data to answer the user's question.\n"
                "3. Do not guess, use RAG, or make up data. Always call the relevant tool first.\n"
                "4. If a tool returns an error, stop and report the error to the user."
            )
    # -------------------------------------------------------------------

    session_id = chat_body.session_id
    is_new_chat = not session_id
    if is_new_chat:
        session_id = str(uuid4())

    if user_id:
        save_chat_message(user_id, session_id, 'user', last_message.content, is_new_chat)

    time_keywords = [
        "today", "yesterday", "tomorrow", "week", "month", "year", "now",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
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
            text=last_message.content, 
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

    final_context_filter = None

    if user_role != 'admin':
        all_docs = ingest_service.list_ingested()
        allowed_docs = [doc for doc in all_docs if any(team in get_document_teams(doc.doc_id) for team in user_teams)]

        tagged_doc_ids = get_docs_by_tag(query_category)
        allowed_docs = [doc for doc in allowed_docs if doc.doc_id in tagged_doc_ids]
        allowed_doc_ids = [doc.doc_id for doc in allowed_docs]

        if not allowed_doc_ids and not active_mcp_tools:
            msg = f"No documents or tools found for category '{query_category}' that you have access to."
            async def empty_stream():
                yield f"data: {json.dumps({'delta': msg})}\n\n"
            return StreamingResponse(empty_stream(), media_type="text/event-stream")
            
        if chat_body.context_filter and chat_body.context_filter.get("docs_ids"):
            requested_doc_id = chat_body.context_filter["docs_ids"][0]
            if requested_doc_id in allowed_doc_ids:
                final_context_filter = ContextFilter(docs_ids=[requested_doc_id])
            else:
                async def denied_stream():
                    yield f"data: {json.dumps({'delta': 'Access denied to the selected document.'})}\n\n"
                return StreamingResponse(denied_stream(), media_type="text/event-stream")
        else:
            final_context_filter = ContextFilter(docs_ids=allowed_doc_ids) if allowed_doc_ids else None
    
    elif chat_body.context_filter and chat_body.context_filter.get("docs_ids"):
        docs = ingest_service.list_ingested()
        selected_filename = chat_body.context_filter.get("docs_ids")[0]
        doc_ids_for_file = [doc.doc_id for doc in docs if doc.doc_metadata and doc.doc_metadata.get("file_name") == selected_filename]
        
        if doc_ids_for_file:
            final_context_filter = ContextFilter(docs_ids=doc_ids_for_file)
        else:
            final_context_filter = None
            
    elif user_role == 'admin' and final_context_filter is None:
         tagged_doc_ids = get_docs_by_tag(query_category)
         if tagged_doc_ids:
             final_context_filter = ContextFilter(docs_ids=tagged_doc_ids)
         elif not active_mcp_tools:
             msg = f"No documents or tools found for category '{query_category}'."
             async def empty_stream_admin():
                yield f"data: {json.dumps({'delta': msg})}\n\n"
             return StreamingResponse(empty_stream_admin(), media_type="text/event-stream")

    try:
        # UPDATED TO AWAIT THE ASYNC NATIVE METHOD
        completion_gen = await chat_service.astream_chat(
            messages=messages,
            use_context=True,
            context_filter=final_context_filter,
            tools=active_mcp_tools,
            system_prompt_override=system_prompt_override
        )

        async def stream_generator():
            full_response = ""
            if is_new_chat:
                yield f"data: {json.dumps({'session_id': session_id})}\n\n"
            
            # Use async for directly over the newly formatted stream
            async for delta in completion_gen.async_response_gen():
                text_delta = delta if isinstance(delta, str) else getattr(delta, "delta", str(delta))
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
        
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Error during Chat/RAG/MCP execution:\n{tb}")
        
        error_message = (
            f"**System Error**: The execution failed.\n\n"
            f"Details: {str(e)}\n\n"
            "**Fix**: Please check your API keys, backend connection, or tool configuration."
        )
        
        async def error_stream():
            if is_new_chat:
                yield f"data: {json.dumps({'session_id': session_id})}\n\n"
            yield f"data: {json.dumps({'delta': error_message})}\n\n"
            
        return StreamingResponse(error_stream(), media_type="text/event-stream")

@api_router.post("/upload", dependencies=[Depends(require_admin)])
async def upload_files(
    files: List[UploadFile] = File(...), 
    teams: str = Form(...),
    tags: str = Form(default="[]"), 
    ingest_service: IngestService = Depends(get_ingest_service)
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
            try:
                ingested_docs = ingest_service.bulk_ingest(ingested_docs_info)
            except Exception as e:
                logger.error(f"Ingestion failed: {e}")
                msg = f"Ingestion failed: {str(e)}"
                if "size of tensor a" in str(e) and "must match the size of tensor b" in str(e):
                    msg += " (Hint: Your document chunks might be too large for the embedding model. Try reducing 'chunk_size' in settings.yaml)"
                raise HTTPException(status_code=500, detail=msg)

            team_list = json.loads(teams)
            tag_list = json.loads(tags)
            
            for doc in ingested_docs:
                add_document_teams(doc.doc_id, team_list)
                if tag_list:
                    add_document_tags(doc.doc_id, tag_list) 
            
    finally:
        for path in temp_paths:
            if path.exists():
                path.unlink()
                
    return JSONResponse(content={"message": f"{len(files)} file(s) uploaded successfully"}, status_code=200)

@api_router.get("/files")
def list_ingested_files(request: Request, ingest_service: IngestService = Depends(get_ingest_service)):
    user_role = request.session.get("user_role")
    user_teams = request.session.get("user_teams", [])
    
    all_docs = ingest_service.list_ingested()
    visible_files = set()

    for doc in all_docs:
        if doc.doc_metadata:
            file_name = doc.doc_metadata.get("file_name")
            if not file_name:
                continue
            
            doc_teams = get_document_teams(doc.doc_id)
            if user_role == 'admin' or any(team in doc_teams for team in user_teams):
                visible_files.add(file_name)
    
    return JSONResponse(content=[[name] for name in sorted(list(visible_files))])


@api_router.delete("/files/{file_name}", dependencies=[Depends(require_admin)])
def delete_selected_file(file_name: str, ingest_service: IngestService = Depends(get_ingest_service)):
    decoded_file_name = unquote(file_name)
    
    all_docs = ingest_service.list_ingested()
    doc_ids_to_delete = [
        doc.doc_id for doc in all_docs 
        if doc.doc_metadata and doc.doc_metadata.get("file_name") == decoded_file_name
    ]

    if not doc_ids_to_delete:
        raise HTTPException(status_code=404, detail=f"File '{decoded_file_name}' not found.")

    for doc_id in doc_ids_to_delete:
        ingest_service.delete(doc_id)
    
    return JSONResponse(content={"message": f"File '{decoded_file_name}' deleted successfully"}, status_code=200)


@api_router.delete("/files", dependencies=[Depends(require_admin)])
def delete_all_files(ingest_service: IngestService = Depends(get_ingest_service)):
    ingested_files = ingest_service.list_ingested()
    for doc in ingested_files:
        ingest_service.delete(doc.doc_id)
    return {"message": "All files deleted successfully"}

# --- Admin Endpoints ---

@api_router.get("/admin/teams")
async def get_teams_list():
    """Provides the list of available teams from environment variables."""
    teams_str = os.getenv("TEAMS_LIST", "Default")
    teams_list = [team.strip() for team in teams_str.split(',')]
    return JSONResponse(content=teams_list)

@api_router.get("/admin/documents", dependencies=[Depends(require_admin)])
async def get_all_documents_with_permissions(ingest_service: IngestService = Depends(get_ingest_service)):
    all_docs = ingest_service.list_ingested()
    docs_by_filename = {}
    for doc in all_docs:
        if doc.doc_metadata and "file_name" in doc.doc_metadata:
            filename = doc.doc_metadata["file_name"]
            if filename not in docs_by_filename:
                docs_by_filename[filename] = {
                    "file_name": filename,
                    "teams": get_document_teams(doc.doc_id),
                    "tags": get_document_tags(doc.doc_id) 
                }
    return JSONResponse(content=list(docs_by_filename.values()))

@api_router.post("/admin/documents/permissions", dependencies=[Depends(require_admin)])
async def update_document_permissions(
    body: DocumentPermissionBody,
    ingest_service: IngestService = Depends(get_ingest_service)
):
    all_docs = ingest_service.list_ingested()
    doc_ids_to_update = [
        doc.doc_id for doc in all_docs
        if doc.doc_metadata and doc.doc_metadata.get("file_name") == body.file_name
    ]
    
    if not doc_ids_to_update:
        raise HTTPException(status_code=404, detail=f"No document found with name '{body.file_name}'.")

    for doc_id in doc_ids_to_update:
        add_document_teams(doc_id, body.teams)
        if body.tags:
             add_document_tags(doc_id, body.tags)

    return JSONResponse(content={"message": "Permissions updated successfully."})


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
    
    if not body.team:
         raise HTTPException(status_code=400, detail="At least one team must be selected.")
         
    for team in body.team:
        if team not in teams_list:
            raise HTTPException(status_code=400, detail=f"Invalid team '{team}'. Must be one of {teams_list}")
        
    try:
        create_user(body.username, body.password, body.role, body.team)
        return JSONResponse(content={"message": f"User '{body.username}' created successfully."}, status_code=201)
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while creating user.")

@api_router.put("/admin/users/edit", dependencies=[Depends(require_admin)])
async def handle_edit_user(body: AdminUpdateUserBody, request: Request):
    """Updates a user's role and teams. Admin only."""
    
    if body.new_role not in ['admin', 'user']:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'user'.")

    teams_str = os.getenv("TEAMS_LIST", "Default")
    teams_list = [team.strip() for team in teams_str.split(',')]
    
    if not body.new_teams:
         raise HTTPException(status_code=400, detail="At least one team must be selected.")
         
    for team in body.new_teams:
        if team not in teams_list:
            raise HTTPException(status_code=400, detail=f"Invalid team '{team}'. Must be one of {teams_list}")

    logged_in_user = request.session.get("username")
    if body.username == logged_in_user:
        raise HTTPException(status_code=400, detail="Admins cannot edit their own role or teams.")
        
    try:
        admin_update_user(body.username, new_role=body.new_role, new_teams=body.new_teams)
        
        return JSONResponse(content={"message": f"User '{body.username}' updated successfully."}, status_code=200)
    except Exception as e:
        logger.error(f"Error updating user '{body.username}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error while updating user.")

@api_router.post("/admin/users/reset-password", dependencies=[Depends(require_admin)])
async def handle_reset_password(body: AdminResetPasswordBody, request: Request):
    """Resets a user's password. Admin only."""
    
    logged_in_user = request.session.get("username")
    if body.username == logged_in_user:
        raise HTTPException(status_code=400, detail="You cannot reset your own password from this panel.")
        
    if not body.new_password:
        raise HTTPException(status_code=400, detail="New password cannot be empty.")

    try:
        update_user_password(body.username, body.new_password)
        
        return JSONResponse(content={"message": f"Password for '{body.username}' reset successfully."}, status_code=200)
    except Exception as e:
        logger.error(f"Error resetting password for user '{body.username}': {e}")
        raise HTTPException(status_code=500, detail="Internal server error while resetting password.")

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

@api_router.get("/admin/llm/config", dependencies=[Depends(require_admin)])
async def fetch_current_llm_config():
    config = get_llm_config()
    return JSONResponse(content=config or {})

@api_router.post("/admin/llm/models", dependencies=[Depends(require_admin)])
async def fetch_llm_models(body: LLMModelsRequest):
    if body.provider == "Ollama":
        try:
            url = body.url.rstrip('/') if body.url else "http://localhost:11434"
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{url}/api/tags", timeout=5.0)
                resp.raise_for_status()
                models = [m["name"] for m in resp.json().get("models", [])]
                return JSONResponse(content={"models": models})
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ollama connection failed: {str(e)}")
    
    elif body.provider == "Gemini":
        try:
            if not body.token:
                raise ValueError("Token is required for Gemini.")
            genai.configure(api_key=body.token)
            models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
            return JSONResponse(content={"models": models})
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Gemini connection failed: {str(e)}")
            
    raise HTTPException(status_code=400, detail="Invalid provider")

@api_router.post("/admin/llm/config", dependencies=[Depends(require_admin)])
async def save_llm_cfg(body: LLMConfigRequest):
    save_llm_config(body.provider, body.url, body.token, body.model)
    return JSONResponse(content={"message": "LLM Configuration saved! Please restart PrivateGPT to apply changes globally."})

# --- MCP Admin Endpoints ---

@api_router.get("/admin/mcp", dependencies=[Depends(require_admin)])
async def fetch_mcp_configs():
    configs = get_all_mcp_configs()
    return JSONResponse(content=configs)

@api_router.post("/admin/mcp", dependencies=[Depends(require_admin)])
async def handle_create_mcp(body: MCPConfigBody):
    try:
        create_mcp_config(
            name=body.name,
            transport_type=body.transport_type,
            command=body.command,
            args=body.args,
            env_vars=body.env_vars
        )
        return JSONResponse(content={"message": f"MCP '{body.name}' created successfully."}, status_code=201)
    except Exception as e:
        logger.error(f"Error creating MCP config: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while saving MCP configuration.")

@api_router.put("/admin/mcp/{mcp_id}", dependencies=[Depends(require_admin)])
async def handle_update_mcp(mcp_id: int, body: MCPConfigBody):
    try:
        update_mcp_config(
            mcp_id=mcp_id,
            name=body.name,
            transport_type=body.transport_type,
            command=body.command,
            args=body.args,
            env_vars=body.env_vars
        )
        return JSONResponse(content={"message": f"MCP '{body.name}' updated successfully."}, status_code=200)
    except Exception as e:
        logger.error(f"Error updating MCP config {mcp_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while updating MCP configuration.")

@api_router.post("/admin/mcp/test", dependencies=[Depends(require_admin)])
async def handle_test_mcp(body: MCPConfigBody):
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.session import ClientSession
    from contextlib import AsyncExitStack
    import os
    import asyncio

    try:
        # 10 SECOND TIMEOUT
        async with asyncio.timeout(10.0):
            async with AsyncExitStack() as stack:
                if body.transport_type == "stdio":
                    env = os.environ.copy()
                    if body.env_vars:
                        env.update(body.env_vars)
                    server_params = StdioServerParameters(command=body.command, args=body.args, env=env)
                    read, write = await stack.enter_async_context(stdio_client(server_params))
                elif body.transport_type == "sse":
                    read, write = await stack.enter_async_context(sse_client(url=body.command, headers=body.env_vars))
                else:
                    return JSONResponse(content={"error": "Invalid transport type"}, status_code=400)
                
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                mcp_tools = await session.list_tools()
                
                tools = [{"name": t.name, "description": t.description} for t in mcp_tools.tools]
                return JSONResponse(content={"message": f"Successfully connected! Found {len(tools)} tools.", "tools": tools})
                
    except asyncio.TimeoutError:
        return JSONResponse(content={"error": "Connection timed out. Ensure the command/URL is correct."}, status_code=400)
    except Exception as e:
        error_msg = str(e)
        if hasattr(e, 'exceptions'):
            sub_errors = [str(sub_e) for sub_e in e.exceptions]
            error_msg = " | ".join(sub_errors)
            
        logger.error(f"MCP Test Failed: {error_msg}")
        return JSONResponse(content={"error": f"Connection failed: {error_msg}"}, status_code=400)

@api_router.delete("/admin/mcp/{mcp_id}", dependencies=[Depends(require_admin)])
async def handle_delete_mcp(mcp_id: int):
    try:
        delete_mcp_config(mcp_id)
        return JSONResponse(content={"message": f"MCP integration deleted successfully."}, status_code=200)
    except Exception as e:
        logger.error(f"Error deleting MCP config {mcp_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while deleting MCP configuration.")