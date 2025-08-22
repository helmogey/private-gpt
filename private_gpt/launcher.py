# In private_gpt/launcher.py

import logging
import os
from injector import Injector
from fastapi import Depends, FastAPI, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
from fastapi.middleware.cors import CORSMiddleware
from llama_index.core.settings import Settings as LlamaIndexSettings

from private_gpt.constants import PROJECT_ROOT_PATH
from private_gpt.server.chat.chat_router import chat_router
from private_gpt.server.chunks.chunks_router import chunks_router
from private_gpt.server.completions.completions_router import completions_router
from private_gpt.server.embeddings.embeddings_router import embeddings_router
from private_gpt.server.health.health_router import health_router
from private_gpt.server.ingest.ingest_router import ingest_router
from private_gpt.server.recipes.summarize.summarize_router import summarize_router
from private_gpt.settings.settings import Settings
from private_gpt.server.chat.chat_service import ChatService
from llama_index.core.llms import ChatMessage
from fastapi import Request, Form
from fastapi.responses import StreamingResponse


logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory=str(PROJECT_ROOT_PATH / "templates"))
UI_USERNAME = os.getenv("UI_USERNAME", "admin")
UI_PASSWORD = os.getenv("UI_PASSWORD", "admin")

# class AuthenticationMiddleware(BaseHTTPMiddleware):
#     async def dispatch(self, request: Request, call_next: Callable) -> Response:
#         allowed_paths = ["/login", "/static", "/docs", "/openapi.json", "/favicon.ico"]
#         if any(request.url.path.startswith(p) for p in allowed_paths):
#             return await call_next(request)
#         if not request.session.get("logged_in"):
#             return RedirectResponse(url="/login", status_code=303)
#         return await call_next(request)


# In launcher.py

class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # These paths are required for the login page and the Gradio UI to function correctly.
        allowed_paths = [
            "/login",          # The login page itself
            "/custom",
            "/static",         # Static assets for the login page
            "/docs",           # API documentation
            "/openapi.json",   # API schema
            "/theme.css",      # Gradio theme
            "/assets",         # Gradio assets
            "/file",           # Access to uploaded files for Gradio
            "/queue",          # Gradio's WebSocket queue for interactivity
            "/api"             # Gradio's internal API
        ]
        # If the request path starts with any of the allowed paths, let it through.
        if any(request.url.path.startswith(p) for p in allowed_paths):
            return await call_next(request)

        # For all other paths (like the root '/'), check if the user is logged in.
        if not request.session.get("logged_in"):
            return RedirectResponse(url="/login", status_code=303)

        # If logged in, allow the request to proceed.
        return await call_next(request)

def create_app(root_injector: Injector) -> FastAPI:
    async def bind_injector_to_request(request: Request) -> None:
        request.state.injector = root_injector

    app = FastAPI(dependencies=[Depends(bind_injector_to_request)])
    
    app.add_middleware(AuthenticationMiddleware)
    app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "a_very_secret_key"))

###############################################################################################
# Custom HTML
###############################################################################################
    
    # @app.get("/custom", response_class=HTMLResponse, tags=["UI"])
    # async def get_custom_chat(request: Request):
    #     return templates.TemplateResponse("custom.html", {"request": request})
    
    # @app.post("/custom", tags=["UI"])
    # async def chat_stream_endpoint(request: Request):
    #     injector = request.state.injector
    #     chat_service = injector.get(ChatService)
    #     body = await request.json()
    #     messages = [ChatMessage(**msg) for msg in body["messages"]]

    #     # This calls the same chat service logic as before
    #     completion_gen = chat_service.stream_chat(messages=messages, use_context=True)

    #     async def stream_generator():
    #         for chunk in completion_gen.response:
    #             yield chunk.delta or ""

    #     return StreamingResponse(stream_generator(), media_type="text/event-stream")







###############################################################################################
# login
###############################################################################################

    @app.get("/login", response_class=HTMLResponse, tags=["UI"])
    async def get_login_page(request: Request):
        return templates.TemplateResponse("login.html", {"request": request})

    @app.post("/login", tags=["UI"])
    async def handle_login_form(request: Request, username: str = Form(...), password: str = Form(...)):
        if username == UI_USERNAME and password == UI_PASSWORD:
            request.session["logged_in"] = True
            return RedirectResponse(url="/", status_code=303)
        else:
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Invalid username or password"},
                status_code=401,
            )
################################################################################################
    app.include_router(completions_router)
    app.include_router(chat_router)
    app.include_router(chunks_router)
    app.include_router(ingest_router)
    app.include_router(summarize_router)
    app.include_router(embeddings_router)
    app.include_router(health_router)
    
    settings = root_injector.get(Settings)
    if settings.server.cors.enabled:
        app.add_middleware(CORSMiddleware, **settings.server.cors.model_dump(exclude={'enabled'}))
        
    if settings.ui.enabled:
        from private_gpt.ui.ui import PrivateGptUi
        ui = root_injector.get(PrivateGptUi)
        ui.mount_in_app(app, settings.ui.path)

    return app