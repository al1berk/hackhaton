# src/api/server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
from datetime import datetime
import uvicorn
import logging
from fastapi.middleware.cors import CORSMiddleware
from core.conversation import AsyncLangGraphDialog
from core.config import Config
# YENI SATIRLAR 12-13: Vector store ve file handling imports
from core.vector_store import VectorStore
import shutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = PROJECT_ROOT / "static"
STATIC_DIR.mkdir(exist_ok=True)

# YENI SATIRLAR 21-22: Upload dizinini oluştur
UPLOAD_DIR = Path(Config.UPLOAD_DIR)
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="LangGraph + CrewAI Async Multi-Agent Chat with RAG")

origins = ["http://localhost", "http://localhost:8000", "http://127.0.0.1", "http://127.0.0.1:8000"]

app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

dialog_instances = {}

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Async LangGraph + CrewAI Multi-Agent System with RAG başlatılıyor...")
    try:
        Config.validate_config()
        logger.info("✅ API anahtarları doğrulandı")
        
        # YENI SATIRLAR 39-43: Vector store test
        vector_store = VectorStore()
        stats = vector_store.get_stats()
        logger.info(f"✅ Vector Store başlatıldı: {stats['total_documents']} PDF, {stats['total_chunks']} parça")
        
    except Exception as e:
        logger.error(f"❌ Startup hatası: {e}")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = STATIC_DIR / "index.html"
    return FileResponse(index_path)

# YENI ENDPOINT: PDF yükleme (SATIRLAR 50-89)
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """PDF dosyası yükler ve vektörleştirir"""
    try:
        # Dosya doğrulaması
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Sadece PDF dosyaları desteklenir")
        
        if file.size > Config.MAX_PDF_SIZE:
            raise HTTPException(status_code=400, detail=f"Dosya boyutu {Config.MAX_PDF_SIZE // 1024 // 1024}MB'tan büyük olamaz")
        
        # Güvenli dosya adı oluştur
        safe_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file_path = UPLOAD_DIR / safe_filename
        
        # Dosyayı kaydet
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Vector store'a ekle
        vector_store = VectorStore()
        
        with open(file_path, "rb") as pdf_file:
            success = vector_store.add_pdf_document(
                pdf_file=pdf_file,
                filename=file.filename,
                metadata={
                    "upload_path": str(file_path),
                    "original_size": file.size,
                    "safe_filename": safe_filename
                }
            )
        
        if success:
            # İstatistikleri al
            stats = vector_store.get_stats()
            
            return JSONResponse({
                "success": True,
                "message": f"'{file.filename}' başarıyla yüklendi ve vektörleştirildi",
                "filename": file.filename,
                "safe_filename": safe_filename,
                "stats": stats
            })
        else:
            # Başarısız olursa dosyayı sil
            file_path.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail="PDF işlenirken hata oluştu")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ PDF yükleme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"PDF yükleme hatası: {str(e)}")

# YENI ENDPOINT: PDF listesini getir (SATIRLAR 91-104)
@app.get("/list-pdfs")
async def list_pdfs():
    """Yüklenmiş PDF'leri listeler"""
    try:
        vector_store = VectorStore()
        documents = vector_store.get_all_documents()
        stats = vector_store.get_stats()
        
        return JSONResponse({
            "success": True,
            "documents": documents,
            "stats": stats
        })
        
    except Exception as e:
        logger.error(f"❌ PDF listeleme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"PDF listeleme hatası: {str(e)}")

# YENI ENDPOINT: PDF sil (SATIRLAR 106-123)
@app.delete("/delete-pdf/{file_hash}")
async def delete_pdf(file_hash: str):
    """PDF'i siler"""
    try:
        vector_store = VectorStore()
        success = vector_store.delete_document(file_hash)
        
        if success:
            stats = vector_store.get_stats()
            return JSONResponse({
                "success": True,
                "message": "PDF başarıyla silindi",
                "stats": stats
            })
        else:
            raise HTTPException(status_code=404, detail="PDF bulunamadı")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ PDF silme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"PDF silme hatası: {str(e)}")

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
        # GÜNCELLENEN SATIRLAR 142-146: Bağlantı kurulduğunda vector store istatistiklerini gönder
        vector_store = VectorStore()
        stats = vector_store.get_stats()
        await websocket.send_text(json.dumps({
            "type": "connection_established", 
            "vector_store_stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # GÜNCELLENEN SATIRLAR 152-168: PDF yükleme mesajlarını handle et
            if message_data.get("type") == "pdf_uploaded":
                # PDF yüklendiği bilgisini kullanıcıya bildir
                await websocket.send_text(json.dumps({
                    "type": "system",
                    "content": f"📚 '{message_data.get('filename', 'PDF')}' başarıyla yüklendi ve vektörleştirildi. Artık bu doküman hakkında sorular sorabilirsiniz!",
                    "timestamp": datetime.utcnow().isoformat()
                }))
                continue
            
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