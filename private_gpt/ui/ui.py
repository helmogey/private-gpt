import os
import logging
from pathlib import Path
from typing import Any
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from injector import inject, singleton
from llama_index.core.llms import ChatMessage, MessageRole
from enum import Enum
from private_gpt.constants import PROJECT_ROOT_PATH
from private_gpt.di import global_injector
from private_gpt.open_ai.extensions.context_filter import ContextFilter
from private_gpt.server.chat.chat_service import ChatService
from private_gpt.server.ingest.ingest_service import IngestService
from private_gpt.settings.settings import settings
from private_gpt.ui.api import api_router # IMPORT THE NEW API ROUTER

logger = logging.getLogger(__name__)

THIS_DIRECTORY_RELATIVE = Path(__file__).parent.relative_to(PROJECT_ROOT_PATH)
UI_TAB_TITLE = "NEC GPT"

class Modes(str, Enum):
    RAG_MODE = "RAG"
    SEARCH_MODE = "Search"

@singleton
class PrivateGptUi:
    @inject
    def __init__(
        self,
        ingest_service: IngestService,
        chat_service: ChatService,
    ) -> None:
        self._ingest_service = ingest_service
        self._chat_service = chat_service
        self._selected_filename = None

        default_mode_map = {mode.value: mode for mode in Modes}
        self._default_mode = default_mode_map.get(
            settings().ui.default_mode, Modes.RAG_MODE
        )
        self._system_prompt = self._get_default_system_prompt(self._default_mode)

    def _get_default_system_prompt(self, mode: Modes) -> str:
        p = ""
        if mode == Modes.RAG_MODE:
            p = settings().ui.default_query_system_prompt
        return p

    def _list_ingested_files(self) -> list[list[str]]:
        files = set()
        for ingested_document in self._ingest_service.list_ingested():
            if ingested_document.doc_metadata is None:
                continue
            file_name = ingested_document.doc_metadata.get(
                "file_name", "[FILE NAME MISSING]"
            )
            files.add(file_name)
        return [[row] for row in sorted(list(files))]

    def mount_in_app(self, app: FastAPI, path: str) -> None:
        """
        Mounts the HTML frontend and the API endpoints in the FastAPI app.
        """
        assets_path = Path(__file__).parent.absolute() / "assets"
        
        app.mount(
            "/assets",
            StaticFiles(directory=assets_path),
            name="assets",
        )
        
        app.include_router(api_router)

        @app.get("/", include_in_schema=False)
        async def root() -> FileResponse:
            return FileResponse(assets_path / "index.html")

