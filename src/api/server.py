# src/api/server.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
from datetime import datetime
import uvicorn
import logging

from fastapi.middleware.cors import CORSMiddleware
from core.conversation import AsyncLangGraphDialog
from core.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = PROJECT_ROOT / "static"

STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(title="LangGraph + CrewAI Async Multi-Agent Chat")

origins = ["http://localhost", "http://localhost:8000", "http://127.0.0.1", "http://127.0.0.1:8000"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

dialog_instances = {}

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Async LangGraph + CrewAI Multi-Agent System başlatılıyor...")
    try:
        Config.validate_config()
        logger.info("✅ API anahtarları doğrulandı")
    except Exception as e:
        logger.error(f"❌ Startup hatası: {e}")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = STATIC_DIR / "index.html"
    return FileResponse(index_path)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_id = id(websocket)
    await websocket.accept()
    logger.info(f"🔌 WebSocket bağlantısı kabul edildi: Client {client_id}")
    
    async def websocket_callback(message):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"❌ WebSocket callback hatası: {e}")
    
    dialog_instances[client_id] = AsyncLangGraphDialog(websocket_callback)
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message")
            if user_message:
                response = await dialog_instances[client_id].process_user_message(user_message)
                if response:
                    await websocket.send_text(json.dumps({"type": "message", "content": response}))
    except WebSocketDisconnect:
        logger.info(f"🔌 Client {client_id} bağlantısı kesildi.")
    except Exception as e:
        logger.error(f"❌ Mesaj işleme hatası (Client {client_id}): {e}", exc_info=True)
    finally:
        if client_id in dialog_instances:
            del dialog_instances[client_id]
            logger.info(f"🧹 Client {client_id} temizlendi.")

if __name__ == "__main__":
    print("=" * 60)
    print("BU SCRIPT'İ DOĞRUDAN ÇALIŞTIRMAYIN!")
    print("Lütfen projenin ana dizininden aşağıdaki komutu kullanın:")
    print("uvicorn api.server:app --reload --app-dir src")
    print("=" * 60)