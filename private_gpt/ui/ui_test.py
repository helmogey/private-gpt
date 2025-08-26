import logging
from pathlib import Path
from typing import Any
import asyncio
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from llama_index.core.llms import ChatMessage
from pydantic import BaseModel

from private_gpt.di import global_injector
from private_gpt.server.chat.chat_service import ChatService, CompletionGen
from private_gpt.server.ingest.ingest_service import IngestService
from private_gpt.ui.ui import PrivateGptUi

# Create a new API router
api_router = APIRouter(prefix="/api")

logger = logging.getLogger(__name__)

# Dependency injection to get the UI class instance
def get_ui() -> PrivateGptUi:
    return global_injector.get(PrivateGptUi)

class ChatBody(BaseModel):
    messages: list[ChatMessage]
    # You can add other parameters like mode, context_filter etc. here
    # For simplicity, we'll handle them as query parameters or in a more complex body

# --- API Endpoints ---

@api_router.post("/chat")
async def chat(request: Request, ui: PrivateGptUi = Depends(get_ui)):
    """
    Handles the chat stream. The request body should be a JSON object
    with a 'messages' key containing a list of chat messages.
    """
    body = await request.json()
    messages = body.get("messages", [])
    
    # This is a simplified stand-in for the full _chat logic.
    # You would adapt your existing _chat method to be callable here.
    # For this example, we'll call a simplified streaming function.
    
    async def stream_generator():
        # A simplified version of your _chat streaming logic
        # In a real implementation, you'd call ui._chat_service.stream_chat
        # and format the deltas as JSON strings.
        
        # This is a placeholder to demonstrate streaming.
        # You would replace this with your actual call to the chat service.
        from private_gpt.server.chat.chat_service import CompletionGen
        from llama_index.core.llms import ChatResponse
        import time

        class MockStream:
            def __iter__(self):
                yield ChatResponse(delta="Hello! ")
                time.sleep(0.1)
                yield ChatResponse(delta="This is a streamed response ")
                time.sleep(0.1)
                yield ChatResponse(delta="from the new HTML UI.")

        mock_completion = CompletionGen(response=MockStream(), sources=[])

        full_response = ""
        for delta in mock_completion.response:
            full_response += delta.delta or ""
            yield f"data: {delta.delta}\n\n" # Server-Sent Events format
            await asyncio.sleep(0.02)

        # Here you would append sources similar to your Gradio implementation
        # For example: yield f"sources: {json.dumps(sources_data)}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


@api_router.post("/upload")
async def upload_file(file: UploadFile = File(...), ui: PrivateGptUi = Depends(get_ui)):
    """
    Handles file uploads. It saves the file temporarily and calls the ingest service.
    """
    temp_path = Path("temp_uploads") / file.filename
    temp_path.parent.mkdir(exist_ok=True)
    
    try:
        with temp_path.open("wb") as buffer:
            buffer.write(await file.read())
        
        # Call the existing upload logic (simplified)
        ui._ingest_service.ingest(file_name=str(file.filename), file_data=temp_path)
        
        # Return the new list of files
        return ui._list_ingested_files()
    finally:
        # Clean up the temporary file
        if temp_path.exists():
            temp_path.unlink()

@api_router.get("/files")
def list_ingested_files(ui: PrivateGptUi = Depends(get_ui)):
    """Lists the ingested files."""
    return ui._list_ingested_files()

@api_router.delete("/files")
def delete_all_files(ui: PrivateGptUi = Depends(get_ui)):
    """Deletes all ingested files."""
    # This directly calls your existing method
    ingested_files = ui._ingest_service.list_ingested()
    for doc in ingested_files:
        ui._ingest_service.delete(doc.doc_id)
    return {"message": "All files deleted successfully"}