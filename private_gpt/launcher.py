import logging
import os
from injector import Injector
from fastapi import Depends, FastAPI, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from private_gpt.constants import PROJECT_ROOT_PATH
from private_gpt.server.chat.chat_router import chat_router
from private_gpt.server.chunks.chunks_router import chunks_router
from private_gpt.server.completions.completions_router import completions_router
from private_gpt.server.embeddings.embeddings_router import embeddings_router
from private_gpt.server.health.health_router import health_router
from private_gpt.server.ingest.ingest_router import ingest_router
from private_gpt.settings.settings import Settings
from private_gpt.database import init_db, get_user, verify_password, get_llm_config
from private_gpt.ui.api import api_router

logger = logging.getLogger(__name__)

# --- FIX: Unified Assets Path ---
# Based on user input: "all login.html and other html... are inside assets inside ui inside priv-gpt"
ASSETS_PATH = PROJECT_ROOT_PATH / "private_gpt" / "ui" / "assets"

# Log the path to help debugging
logger.info(f"Assets Path configured as: {ASSETS_PATH}")
if not os.path.exists(ASSETS_PATH):
    logger.error(f"CRITICAL: Assets directory NOT found at {ASSETS_PATH}")
    # Fallback/Debug: List contents of parent directory to see structure
    parent = PROJECT_ROOT_PATH / "private_gpt" / "ui"
    if os.path.exists(parent):
        logger.error(f"Contents of {parent}: {os.listdir(parent)}")
else:
    logger.info(f"Assets directory found. Contents: {os.listdir(ASSETS_PATH)}")

# Both static files and templates are in the same folder
templates = Jinja2Templates(directory=str(ASSETS_PATH))

SESSION_MAX_AGE = 600

class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        allowed_paths = [
            "/login",          
            "/docs",           
            "/openapi.json",   
            "/v1",             
            "/health",         
            "/assets",         
            "/api/branding"    
        ]

        if any(request.url.path.startswith(p) for p in allowed_paths):
            return await call_next(request)

        if not request.session.get("logged_in"):
            return RedirectResponse(url="/login", status_code=303)

        return await call_next(request)

def create_app(root_injector: Injector) -> FastAPI:
    load_dotenv()
    init_db() 
    
    # --- NEW: Patch Environment with DB Config BEFORE Settings are injected ---
    config = get_llm_config()
    if config:
        os.environ["LLM_MODE"] = config.get("llm_provider", "ollama").lower()
        if config.get("llm_provider") == "Ollama":
            os.environ["OLLAMA_API_BASE"] = config.get("llm_url", "")
            os.environ["OLLAMA_MODEL"] = config.get("llm_model", "")
        elif config.get("llm_provider") == "Gemini":
            os.environ["GOOGLE_API_KEY"] = config.get("llm_token", "")
            os.environ["GEMINI_MODEL"] = config.get("llm_model", "")

    async def bind_injector_to_request(request: Request) -> None:
        request.state.injector = root_injector

    app = FastAPI(dependencies=[Depends(bind_injector_to_request)])
    
    app.add_middleware(AuthenticationMiddleware)
    app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "a_very_secret_key"), max_age=SESSION_MAX_AGE)

    # --- FIX: Mount Assets ---
    if os.path.exists(ASSETS_PATH):
        app.mount("/assets", StaticFiles(directory=str(ASSETS_PATH)), name="assets")
    else:
        logger.warning(f"Assets directory not found at {ASSETS_PATH}")

    # --- Login Routes ---
    @app.get("/login", response_class=HTMLResponse, tags=["UI"])
    async def get_login_page(request: Request):
        app_name = os.getenv("APP_NAME", "DocuMind")
        app_logo_url = os.getenv("APP_LOGO_URL_Black", "/assets/NEC-Logo.svg") 
        return templates.TemplateResponse("login.html", {"request": request, "app_name": app_name, "app_logo_url": app_logo_url})
        
    @app.post("/login", tags=["UI"])
    async def handle_login_form(request: Request, username: str = Form(...), password: str = Form(...)):
        db_user = get_user(username.lower())

        if db_user and verify_password(password, db_user['hashed_password']):
            request.session["logged_in"] = True
            request.session["user_id"] = db_user['id'] 
            request.session["username"] = db_user['username']
            request.session["user_role"] = db_user['role']
            request.session["user_teams"] = db_user['teams']
            request.session["user_name"] = db_user['name'] 
            return RedirectResponse(url="/", status_code=303)
        else:
            app_name = os.getenv("APP_NAME", "DocuMind")
            app_logo_url = os.getenv("APP_LOGO_URL_Black", "/assets/NEC-Logo.svg")

        return templates.TemplateResponse(
            "login.html",
            {
                "request": request, 
                "error": "Invalid username or password", 
                "app_name": app_name,
                "app_logo_url": app_logo_url
            },
            status_code=401,
        )

    @app.get("/logout", tags=["UI"])
    async def handle_logout(request: Request):
        request.session.clear()
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie("session", path="/")
        return response
    
    # --- FIX: Root Route ---
    @app.get("/", response_class=HTMLResponse)
    async def read_root():
        return FileResponse(os.path.join(ASSETS_PATH, "index.html"))

    @app.get("/admin", response_class=HTMLResponse)
    async def read_admin():
        return FileResponse(os.path.join(ASSETS_PATH, "admin.html"))

    # Include API Routers
    app.include_router(api_router) # Custom router
    
    app.include_router(completions_router)
    app.include_router(chat_router)
    app.include_router(chunks_router)
    app.include_router(ingest_router)
    app.include_router(health_router)
    
    settings = root_injector.get(Settings)
    if settings.server.cors.enabled:
        app.add_middleware(CORSMiddleware, **settings.server.cors.model_dump(exclude={'enabled'}))
        
    return app