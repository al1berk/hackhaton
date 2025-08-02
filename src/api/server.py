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
from core.vector_store import VectorStore
from core.chat_manager import ChatManager
import shutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = PROJECT_ROOT / "static"
STATIC_DIR.mkdir(exist_ok=True)

UPLOAD_DIR = Path(Config.UPLOAD_DIR)
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="LangGraph + CrewAI Async Multi-Agent Chat with RAG")

origins = ["http://localhost", "http://localhost:8000", "http://127.0.0.1", "http://127.0.0.1:8000"]

app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Global değişkenler
dialog_instances = {}
chat_manager = ChatManager()

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Async LangGraph + CrewAI Multi-Agent System with RAG ve Chat History başlatılıyor...")
    try:
        Config.validate_config()
        logger.info("✅ API anahtarları doğrulandı")
        logger.info("✅ Chat Manager başlatıldı")
    except Exception as e:
        logger.error(f"❌ Startup hatası: {e}")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        # HTML dosyasını oluştur
        html_content = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LangGraph AI Assistant</title>
    <link rel="stylesheet" href="/static/css/main.css">
    <link rel="stylesheet" href="/static/css/components/chat_history.css">
    <link rel="stylesheet" href="/static/css/components/toast.css">
    <link rel="stylesheet" href="/static/css/components/error_fallback.css">
    <link rel="stylesheet" href="/static/css/components/welcome_actions.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
</head>
<body>
    <div class="app-container">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="logo">
                    <i class="fas fa-robot"></i>
                    <span>AI Assistant</span>
                </div>
                <button class="new-chat-btn" onclick="startNewChat()">
                    <i class="fas fa-plus"></i>
                    Yeni Sohbet
                </button>
            </div>
            
            <!-- PDF yönetim bölümü -->
            <div class="pdf-section">
                <div class="pdf-header">
                    <h3><i class="fas fa-file-pdf"></i> PDF Dokümanlar</h3>
                    <button class="upload-pdf-btn" onclick="document.getElementById('pdfFileInput').click()">
                        <i class="fas fa-upload"></i>
                        PDF Yükle
                    </button>
                </div>
                <div class="pdf-stats" id="pdfStats">
                    <div class="stat-item">
                        <span class="stat-label">Toplam PDF:</span>
                        <span class="stat-value" id="totalPdfs">0</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Vektör Parça:</span>
                        <span class="stat-value" id="totalChunks">0</span>
                    </div>
                </div>
                <div class="pdf-list" id="pdfList">
                    <!-- PDF listesi buraya yüklenecek -->
                </div>
            </div>
            
            <!-- Gizli file input -->
            <input type="file" id="pdfFileInput" accept=".pdf" style="display: none;">
            
            <!-- Sohbet geçmişi -->
            <div class="chat-history">
                <div class="chat-history-header">
                    <h3>Sohbet Geçmişi</h3>
                </div>
                <div class="chat-list" id="chatList">
                    <!-- Chat history items will be populated here -->
                </div>
            </div>
            
            <div class="sidebar-footer">
                <div class="user-info">
                    <div class="user-avatar">
                        <i class="fas fa-user"></i>
                    </div>
                    <div class="user-details">
                        <span class="username">Kullanıcı</span>
                        <span class="status">Çevrimiçi</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Main Chat Area -->
        <div class="main-content">
            <!-- Header -->
            <div class="chat-header">
                <div class="header-left">
                    <h1>LangGraph AI Assistant</h1>
                    <span class="subtitle">CrewAI + RAG ile Güçlendirilmiş Akıllı Asistan</span>
                </div>
                <div class="header-right">
                    <div class="connection-status" id="connectionStatus">
                        <div class="status-indicator disconnected"></div>
                        <span>Bağlanıyor...</span>
                    </div>
                    <button class="settings-btn" onclick="toggleSettings()">
                        <i class="fas fa-cog"></i>
                    </button>
                </div>
            </div>

            <!-- Messages Container -->
            <div class="messages-container" id="messagesContainer">
                <div class="welcome-message">
                    <div class="welcome-icon">
                        <i class="fas fa-robot"></i>
                    </div>
                    <h2>Merhaba! 👋</h2>
                    <p>Size nasıl yardımcı olabilirim? Aşağıdaki konularda uzmanım:</p>
                    <div class="feature-list">
                        <div class="feature-item"><i class="fas fa-search"></i> Web araştırması</div>
                        <div class="feature-item"><i class="fas fa-file-pdf"></i> PDF doküman analizi</div>
                        <div class="feature-item"><i class="fas fa-brain"></i> Akıllı soru-cevap</div>
                        <div class="feature-item"><i class="fas fa-chart-line"></i> Veri analizi</div>
                    </div>
                    <div class="welcome-actions">
                        <button class="action-btn" onclick="startNewChat()">
                            <i class="fas fa-plus"></i>
                            Yeni Sohbet Başlat
                        </button>
                        <button class="action-btn" onclick="document.getElementById('pdfFileInput').click()">
                            <i class="fas fa-file-upload"></i>
                            PDF Yükle
                        </button>
                    </div>
                </div>
            </div>

            <!-- Input Area -->
            <div class="input-area">
                <div class="input-container">
                    <div class="input-wrapper">
                        <textarea 
                            id="messageInput" 
                            placeholder="Mesajınızı buraya yazın veya PDF yükleyerek dokümanlarınız hakkında soru sorun..." 
                            rows="1"
                            maxlength="2000"
                        ></textarea>
                        <div class="input-actions">
                            <button class="attach-btn" title="PDF Yükle" onclick="document.getElementById('pdfFileInput').click()">
                                <i class="fas fa-file-pdf"></i>
                            </button>
                            <button class="emoji-btn" title="Emoji Ekle">
                                <i class="fas fa-smile"></i>
                            </button>
                            <button class="send-btn" id="sendBtn" onclick="sendMessage()" disabled>
                                <i class="fas fa-paper-plane"></i>
                            </button>
                        </div>
                    </div>
                    <div class="input-info">
                        <span class="char-count" id="charCount">0/2000</span>
                        <span class="tip">Enter ile gönder, Shift+Enter ile yeni satır</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Settings Modal -->
    <div class="modal-overlay" id="settingsModal">
        <div class="modal">
            <div class="modal-header">
                <h3>Ayarlar</h3>
                <button class="close-btn" onclick="toggleSettings()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="modal-body">
                <div class="setting-group">
                    <label>Tema</label>
                    <select id="themeSelect">
                        <option value="light">Açık</option>
                        <option value="dark">Koyu</option>
                        <option value="auto">Otomatik</option>
                    </select>
                </div>
                <div class="setting-group">
                    <label>Yazı Boyutu</label>
                    <select id="fontSizeSelect">
                        <option value="small">Küçük</option>
                        <option value="medium" selected>Orta</option>
                        <option value="large">Büyük</option>
                    </select>
                </div>
                <div class="setting-group">
                    <label>Ses Bildirimleri</label>
                    <input type="checkbox" id="soundNotifications" checked>
                </div>
                <div class="setting-group">
                    <label>PDF Araştırması (RAG)</label>
                    <input type="checkbox" id="ragEnabled" checked>
                    <small>PDF dokümanlarınızda otomatik arama</small>
                </div>
            </div>
        </div>
    </div>

    <!-- PDF Upload Progress Modal -->
    <div class="modal-overlay" id="uploadModal" style="display: none;">
        <div class="modal upload-modal">
            <div class="modal-header">
                <h3><i class="fas fa-upload"></i> PDF Yükleniyor</h3>
            </div>
            <div class="modal-body">
                <div class="upload-progress">
                    <div class="upload-info">
                        <div class="upload-filename" id="uploadFilename">Dosya seçiliyor...</div>
                        <div class="upload-status" id="uploadStatus">Hazırlanıyor...</div>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" id="progressFill"></div>
                    </div>
                    <div class="upload-details" id="uploadDetails">
                        <div class="detail-item">
                            <span>Boyut:</span>
                            <span id="fileSize">-</span>
                        </div>
                        <div class="detail-item">
                            <span>Durum:</span>
                            <span id="processStatus">Bekliyor</span>
                        </div>
                    </div>
                </div>
                <div class="upload-actions">
                    <button class="cancel-upload-btn" onclick="cancelUpload()">İptal</button>
                </div>
            </div>
        </div>
    </div>

    <script type="module" src="/static/js/main.js"></script>
</body>
</html>"""
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    return FileResponse(index_path)

# Chat API endpoints
@app.get("/chats")
async def get_chats():
    try:
        chats = chat_manager.get_all_chats()
        return JSONResponse({
            "success": True,
            "chats": chats
        })
    except Exception as e:
        logger.error(f"❌ Sohbet listeleme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Sohbet listeleme hatası: {str(e)}")

@app.post("/chats/new")
async def create_new_chat():
    try:
        chat_id = chat_manager.create_new_chat()
        chat_info = chat_manager.get_chat_info(chat_id)
        
        return JSONResponse({
            "success": True,
            "chat": chat_info
        })
    except Exception as e:
        logger.error(f"❌ Yeni sohbet oluşturma hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Sohbet oluşturma hatası: {str(e)}")

@app.get("/chats/{chat_id}")
async def get_chat_details(chat_id: str):
    try:
        chat_info = chat_manager.get_chat_info(chat_id)
        if not chat_info:
            raise HTTPException(status_code=404, detail="Sohbet bulunamadı")
        
        messages = chat_manager.get_chat_messages(chat_id)
        
        vector_store = VectorStore(Config.VECTOR_STORE_PATH, chat_id=chat_id)
        stats = vector_store.get_stats()
        
        return JSONResponse({
            "success": True,
            "chat": chat_info,
            "messages": messages,
            "vector_store_stats": stats
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Sohbet detay hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Sohbet detay hatası: {str(e)}")

@app.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str):
    try:
        success = chat_manager.delete_chat(chat_id)
        if success:
            return JSONResponse({
                "success": True,
                "message": "Sohbet başarıyla silindi"
            })
        else:
            raise HTTPException(status_code=404, detail="Sohbet bulunamadı")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Sohbet silme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Sohbet silme hatası: {str(e)}")

@app.post("/chats/{chat_id}/upload-pdf")
async def upload_pdf_to_chat(chat_id: str, file: UploadFile = File(...)):
    try:
        chat_info = chat_manager.get_chat_info(chat_id)
        if not chat_info:
            raise HTTPException(status_code=404, detail="Sohbet bulunamadı")
        
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Sadece PDF dosyaları desteklenir")
        
        if file.size > Config.MAX_PDF_SIZE:
            raise HTTPException(status_code=400, detail=f"Dosya boyutu {Config.MAX_PDF_SIZE // 1024 // 1024}MB'tan büyük olamaz")
        
        chat_upload_dir = chat_manager.get_chat_pdf_directory(chat_id)
        chat_upload_dir.mkdir(exist_ok=True)
        
        safe_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file_path = chat_upload_dir / safe_filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        vector_store = VectorStore(Config.VECTOR_STORE_PATH, chat_id=chat_id)
        
        with open(file_path, "rb") as pdf_file:
            success = vector_store.add_pdf_document(
                pdf_file=pdf_file,
                filename=file.filename,
                metadata={
                    "upload_path": str(file_path),
                    "original_size": file.size,
                    "safe_filename": safe_filename,
                    "chat_id": chat_id
                }
            )
        
        if success:
            stats = vector_store.get_stats()
            chat_manager.update_pdf_count(chat_id, stats["total_documents"])
            
            return JSONResponse({
                "success": True,
                "message": f"'{file.filename}' başarıyla yüklendi ve vektörleştirildi",
                "filename": file.filename,
                "safe_filename": safe_filename,
                "stats": stats,
                "chat_id": chat_id
            })
        else:
            file_path.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail="PDF işlenirken hata oluştu")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ PDF yükleme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"PDF yükleme hatası: {str(e)}")

@app.get("/chats/{chat_id}/pdfs")
async def list_chat_pdfs(chat_id: str):
    try:
        chat_info = chat_manager.get_chat_info(chat_id)
        if not chat_info:
            raise HTTPException(status_code=404, detail="Sohbet bulunamadı")
        
        vector_store = VectorStore(Config.VECTOR_STORE_PATH, chat_id=chat_id)
        documents = vector_store.get_all_documents()
        stats = vector_store.get_stats()
        
        return JSONResponse({
            "success": True,
            "documents": documents,
            "stats": stats,
            "chat_id": chat_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ PDF listeleme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"PDF listeleme hatası: {str(e)}")

@app.delete("/chats/{chat_id}/pdfs/{file_hash}")
async def delete_chat_pdf(chat_id: str, file_hash: str):
    try:
        chat_info = chat_manager.get_chat_info(chat_id)
        if not chat_info:
            raise HTTPException(status_code=404, detail="Sohbet bulunamadı")
        
        vector_store = VectorStore(Config.VECTOR_STORE_PATH, chat_id=chat_id)
        success = vector_store.delete_document(file_hash)
        
        if success:
            stats = vector_store.get_stats()
            chat_manager.update_pdf_count(chat_id, stats["total_documents"])
            
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

# WebSocket endpoint - FİX EDİLDİ
@app.websocket("/ws/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: str):
    await websocket.accept()
    
    # WebSocket callback fonksiyonu
    async def websocket_callback(message):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"❌ WebSocket send error: {e}")
    
    # Dialog instance oluştur
    dialog = AsyncLangGraphDialog(
        websocket_callback=websocket_callback,
        chat_id=chat_id,
        chat_manager=chat_manager
    )
    
    dialog_instances[chat_id] = dialog
    
    # Chat'in mevcut mesajlarını yükle
    try:
        chat_info = chat_manager.get_chat_info(chat_id)
        if chat_info:
            messages = chat_manager.get_chat_messages(chat_id)
            dialog.load_conversation_from_messages(messages)
    except Exception as e:
        logger.error(f"❌ Chat loading error: {e}")
    
    # Vector store stats gönder
    try:
        vector_stats = dialog.vector_store.get_stats()
        await websocket_callback(json.dumps({
            "type": "connection_established",
            "message": f"WebSocket bağlantısı kuruldu - Chat: {chat_id}",
            "chat_id": chat_id,
            "vector_store_stats": vector_stats,
            "chat_info": chat_info
        }))
    except Exception as e:
        logger.error(f"❌ Initial stats error: {e}")
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "confirmation_response":
                # Onay yanıtları için özel işlem
                user_message = message_data.get("message", "")
                response = await dialog.process_user_message(user_message)
                
                if response:
                    await websocket_callback(json.dumps({
                        "type": "message",
                        "content": response,
                        "timestamp": datetime.utcnow().isoformat(),
                        "chat_id": chat_id
                    }))
            else:
                # Normal mesajlar
                user_message = message_data.get("message", "")
                force_web_research = message_data.get("force_web_research", False)
                
                if user_message:
                    # Force web research flag'ini conversation state'e ekle
                    dialog.conversation_state["force_web_research"] = force_web_research
                    
                    response = await dialog.process_user_message(user_message)
                    
                    if response:
                        await websocket_callback(json.dumps({
                            "type": "message",
                            "content": response,
                            "timestamp": datetime.utcnow().isoformat(),
                            "chat_id": chat_id
                        }))
                        
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected for chat: {chat_id}")
        if chat_id in dialog_instances:
            del dialog_instances[chat_id]
    except Exception as e:
        logger.error(f"❌ WebSocket error for chat {chat_id}: {e}")
        if chat_id in dialog_instances:
            del dialog_instances[chat_id]

# Default WebSocket (yeni chat için)
@app.websocket("/ws")
async def default_websocket_endpoint(websocket: WebSocket):
    # Yeni chat oluştur
    chat_id = chat_manager.create_new_chat()
    
    # Chat-specific WebSocket'e yönlendir
    await websocket_endpoint(websocket, chat_id)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)