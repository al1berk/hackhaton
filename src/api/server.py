# src/api/server.py
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
from datetime import datetime
import uvicorn
import logging
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage  # Bu satırı ekledim
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
        logger.info(f"✅ Google API Key: {Config.GOOGLE_API_KEY[:10]}...")
        logger.info("✅ Chat Manager başlatıldı")
    except Exception as e:
        logger.error(f"❌ Startup hatası: {e}")
        logger.error(f"❌ Config durumu: GOOGLE_API_KEY={'Var' if Config.GOOGLE_API_KEY else 'Yok'}")
        raise e

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
    <link rel="stylesheet" href="/static/css/test-styles.css">
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
        
        success = vector_store.add_document_from_path(
            file_path=str(file_path),  # Dosyanın yolunu string olarak gönder
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
    
@app.post("/chats/{chat_id}/upload-image")
async def upload_image_to_chat(chat_id: str, file: UploadFile = File(...)):
    try:
        chat_info = chat_manager.get_chat_info(chat_id)
        if not chat_info:
            raise HTTPException(status_code=404, detail="Sohbet bulunamadı")
        
        # Dosya formatı kontrolü (isteğe bağlı, DocumentProcessor da yapabilir)
        allowed_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.webp']
        if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
            raise HTTPException(status_code=400, detail=f"Sadece resim dosyaları desteklenir: {', '.join(allowed_extensions)}")
        
        if file.size > Config.MAX_IMAGE_SIZE: # Config'e MAX_IMAGE_SIZE ekle (örn: 10 * 1024 * 1024)
            raise HTTPException(status_code=400, detail=f"Dosya boyutu {Config.MAX_IMAGE_SIZE // 1024 // 1024}MB'tan büyük olamaz")
        
        chat_upload_dir = chat_manager.get_chat_pdf_directory(chat_id) # Aynı klasörü kullanabiliriz
        chat_upload_dir.mkdir(exist_ok=True)
        
        safe_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file_path = chat_upload_dir / safe_filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        vector_store = VectorStore(Config.VECTOR_STORE_PATH, chat_id=chat_id)
        
        # Yine aynı fonksiyonu çağırıyoruz, çünkü DocumentProcessor dosya türünü anlıyor
        success = vector_store.add_document_from_path(
            file_path=str(file_path),
            filename=file.filename,
            metadata={
                "upload_path": str(file_path),
                "original_size": file.size,
                "safe_filename": safe_filename,
                "chat_id": chat_id,
                "source_type": "ocr"
            }
        )
        
        if success:
            stats = vector_store.get_stats()
            chat_manager.update_pdf_count(chat_id, stats["total_documents"]) # İsmi yanıltıcı olsa da şimdilik belge sayısını tutar
            
            return JSONResponse({
                "success": True,
                "message": f"'{file.filename}' başarıyla yüklendi ve OCR ile işlendi",
                "filename": file.filename,
                "stats": stats
            })
        else:
            file_path.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail="Resim işlenirken hata oluştu")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Resim yükleme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Resim yükleme hatası: {str(e)}")


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

@app.post("/chats/{chat_id}/evaluate-test")
async def evaluate_test_results(chat_id: str, test_results: dict):
    """Test sonuçlarını değerlendirir ve eksik konuları analiz eder"""
    try:
        chat_info = chat_manager.get_chat_info(chat_id)
        if not chat_info:
            raise HTTPException(status_code=404, detail="Sohbet bulunamadı")
        
        # Test sonuçlarını analiz et
        correct_answers = 0
        total_questions = 0
        wrong_topics = []
        
        for question_result in test_results.get("results", []):
            total_questions += 1
            if question_result.get("is_correct", False):
                correct_answers += 1
            else:
                # Yanlış cevaplanan sorunun konusunu ekle
                topic = question_result.get("topic", "Genel")
                if topic not in wrong_topics:
                    wrong_topics.append(topic)
        
        # Başarı oranını hesapla
        success_rate = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        
        # Eksik konuları belirle
        weak_areas = []
        for topic in wrong_topics:
            weak_areas.append({
                "topic": topic,
                "importance": "high" if success_rate < 50 else "medium"
            })
        
        # Test değerlendirme raporu
        evaluation_result = {
            "test_id": test_results.get("test_id"),
            "chat_id": chat_id,
            "evaluation_date": datetime.now().isoformat(),
            "statistics": {
                "total_questions": total_questions,
                "correct_answers": correct_answers,
                "wrong_answers": total_questions - correct_answers,
                "success_rate": round(success_rate, 2)
            },
            "performance_level": (
                "excellent" if success_rate >= 90 else
                "good" if success_rate >= 70 else
                "fair" if success_rate >= 50 else
                "needs_improvement"
            ),
            "weak_areas": weak_areas,
            "recommendations": generate_recommendations(success_rate, weak_areas)
        }
        
        # Sonuçları chat'e mesaj olarak kaydet
        evaluation_message = format_evaluation_message(evaluation_result)
        chat_manager.save_message(chat_id, {
            "type": "system",
            "content": evaluation_message,
            "metadata": {
                "message_type": "test_evaluation",
                "evaluation_data": evaluation_result
            }
        })
        
        # YENİ: Eksik konuları ayrı mesajlar olarak da kaydet
        if evaluation_result["weak_areas"]:
            topics_message = "🎯 **Eksik Olduğun Konular:**\n\n"
            for i, area in enumerate(evaluation_result["weak_areas"], 1):
                topics_message += f"{i}. **{area['topic']}**\n"
                topics_message += f"   💡 Bu konuyu detaylı açıklamamı istersen: \"'{area['topic']}' konusunu açıkla\"\n\n"
            
            topics_message += "📝 **Not:** Yukarıdaki konulardan herhangi birini seçerek benden detaylı açıklama isteyebilirsin!"
            
            chat_manager.save_message(chat_id, {
                "type": "ai",
                "content": topics_message,
                "metadata": {
                    "message_type": "weak_areas_suggestions",
                    "weak_areas": [area["topic"] for area in evaluation_result["weak_areas"]]
                }
            })
        
        return JSONResponse({
            "success": True,
            "evaluation": evaluation_result,
            "message": "Test değerlendirmesi tamamlandı"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test değerlendirme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Test değerlendirme hatası: {str(e)}")

async def evaluate_test_results_internal(chat_id: str, test_results: dict):
    """İç kullanım için test sonuçlarını değerlendirir"""
    try:
        # Test sonuçlarını analiz et
        correct_answers = 0
        total_questions = 0
        wrong_topics = []
        
        for question_result in test_results.get("detailed_results", []):
            total_questions += 1
            if question_result.get("is_correct", False):
                correct_answers += 1
            else:
                # Yanlış cevaplanan sorunun konusunu ekle
                topic = question_result.get("topic", "Genel")
                if topic not in wrong_topics:
                    wrong_topics.append(topic)
        
        # Başarı oranını hesapla
        success_rate = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        
        # Eksik konuları belirle
        weak_areas = []
        for topic in wrong_topics:
            weak_areas.append({
                "topic": topic,
                "importance": "high" if success_rate < 50 else "medium"
            })
        
        # Test değerlendirme raporu
        evaluation_result = {
            "test_id": test_results.get("test_id"),
            "chat_id": chat_id,
            "evaluation_date": datetime.now().isoformat(),
            "statistics": {
                "total_questions": total_questions,
                "correct_answers": correct_answers,
                "wrong_answers": total_questions - correct_answers,
                "success_rate": round(success_rate, 2)
            },
            "performance_level": (
                "excellent" if success_rate >= 90 else
                "good" if success_rate >= 70 else
                "fair" if success_rate >= 50 else
                "needs_improvement"
            ),
            "weak_areas": weak_areas,
            "recommendations": generate_recommendations(success_rate, weak_areas)
        }
        
        # Sonuçları chat'e mesaj olarak kaydet
        evaluation_message = format_evaluation_message(evaluation_result)
        chat_manager.save_message(chat_id, {
            "type": "system",
            "content": evaluation_message,
            "metadata": {
                "message_type": "test_evaluation",
                "evaluation_data": evaluation_result
            }
        })
        
        return evaluation_result
        
    except Exception as e:
        logger.error(f"❌ İç test değerlendirme hatası: {e}")
        raise e

async def evaluate_classic_answer_with_llm(prompt: str, llm) -> str:
    """LLM kullanarak klasik soru cevabını değerlendirir"""
    try:
        from langchain_core.messages import HumanMessage
        
        # LLM'e gönder
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        # Yanıtı string olarak döndür
        if hasattr(response, 'content'):
            return response.content
        else:
            return str(response)
            
    except Exception as e:
        logger.error(f"❌ LLM değerlendirme hatası: {e}")
        # Fallback yanıt
        return "DOĞRU/YANLIŞ: Doğru\nPUAN: 70\nGERİ BİLDİRİM: Değerlendirme yapılamadı, cevabınız kaydedildi."

def generate_recommendations(success_rate: float, weak_areas: list) -> list:
    """Başarı oranı ve eksik konulara göre öneriler üretir"""
    recommendations = []
    
    if success_rate >= 90:
        recommendations.append("🎉 Mükemmel performans! Konuyu çok iyi anlamışsın.")
        recommendations.append("📈 Daha zorlu konulara geçebilir veya bu konuyu başkalarına öğretmeyi deneyebilirsin.")
    elif success_rate >= 70:
        recommendations.append("👍 İyi bir performans gösterdin!")
        recommendations.append("🔄 Eksik kalan konuları tekrar ederek %90'ın üzerine çıkabilirsin.")
    elif success_rate >= 50:
        recommendations.append("📚 Orta seviyede bir performans. Daha fazla çalışmayla iyileştirebilirsin.")
        recommendations.append("🎯 Eksik konulara odaklanarak tekrar yapmakta fayda var.")
    else:
        recommendations.append("💪 Bu konuyu daha detaylı çalışman gerekiyor.")
        recommendations.append("📖 Temel kavramları tekrar gözden geçirmeyi öneririm.")
    
    if weak_areas:
        topics_text = ", ".join([area["topic"] for area in weak_areas])
        recommendations.append(f"🎯 Özellikle şu konulara odaklan: {topics_text}")
        recommendations.append("💡 Bu konular için benden detaylı açıklama isteyebilirsin!")
    
    return recommendations

def format_evaluation_message(evaluation: dict) -> str:
    """Test değerlendirmesini kullanıcı dostu mesaja çevirir"""
    stats = evaluation["statistics"]
    success_rate = stats["success_rate"]
    
    # Emoji ve seviye belirleme
    if success_rate >= 90:
        emoji = "🎉"
        level_text = "Mükemmel"
        color = "🟢"
    elif success_rate >= 70:
        emoji = "👍"
        level_text = "İyi"
        color = "🟡"
    elif success_rate >= 50:
        emoji = "📚"
        level_text = "Orta"
        color = "🟠"
    else:
        emoji = "💪"
        level_text = "Gelişime Açık"
        color = "🔴"
    
    message = f"{emoji} **Test Değerlendirmen**\n\n"
    message += f"{color} **Performans Seviyesi:** {level_text}\n"
    message += f"📊 **Başarı Oranı:** %{success_rate}\n"
    message += f"✅ **Doğru:** {stats['correct_answers']}/{stats['total_questions']}\n"
    message += f"❌ **Yanlış:** {stats['wrong_answers']}\n\n"
    
    # Eksik konular
    if evaluation["weak_areas"]:
        message += "🎯 **Eksik Olduğun Konular:**\n"
        for area in evaluation["weak_areas"]:
            message += f"• {area['topic']}\n"
        message += "\n"
    
    # Öneriler
    message += "💡 **Önerilerim:**\n"
    for rec in evaluation["recommendations"]:
        message += f"• {rec}\n"
    
    message += "\n📖 **Eksik konuları anlatmamı istersen, sadece söyle!**"
    
    return message


# WebSocket endpoint - SORUNLAR DÜZELTİLDİ

@app.websocket("/ws/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: str):
    await websocket.accept()
    logger.info(f"🔌 WebSocket bağlantısı kuruldu - Chat: {chat_id}")
    
    # Chat ID 'default' ise yeni chat oluştur
    if chat_id == 'default':
        try:
            chat_id = chat_manager.create_new_chat()
            logger.info(f"✅ 'default' chat ID için yeni chat oluşturuldu: {chat_id}")
        except Exception as e:
            logger.error(f"❌ Yeni chat oluşturma hatası: {e}")
            chat_id = 'default'
    
    # Chat klasörünün var olduğundan emin ol
    try:
        chat_info = chat_manager.get_chat_info(chat_id)
        if not chat_info:
            # Chat yoksa oluştur
            chat_id = chat_manager.create_new_chat()
            logger.info(f"✅ Chat mevcut değildi, yeni oluşturuldu: {chat_id}")
    except Exception as e:
        logger.error(f"❌ Chat kontrol hatası: {e}")
        # Fallback olarak yeni chat oluştur
        try:
            chat_id = chat_manager.create_new_chat()
            logger.info(f"✅ Fallback: Yeni chat oluşturuldu: {chat_id}")
        except Exception as create_error:
            logger.error(f"❌ Fallback chat oluşturma hatası: {create_error}")
            chat_id = 'emergency_default'
    
    async def websocket_callback(message: str):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"❌ WebSocket gönderim hatası: {e}")
    
    # Dialog instance'ı oluştur veya al
    if chat_id not in dialog_instances:
        dialog_instances[chat_id] = AsyncLangGraphDialog(
            websocket_callback=websocket_callback,
            chat_id=chat_id,
            chat_manager=chat_manager
        )
    else:
        # Mevcut instance'ı güncelle
        dialog_instances[chat_id].websocket_callback = websocket_callback
        dialog_instances[chat_id].chat_manager = chat_manager
    
    dialog = dialog_instances[chat_id]
    
    # Sohbet geçmişini yükle
    try:
        chat_messages = chat_manager.get_chat_messages(chat_id)
        if chat_messages:
            dialog.load_conversation_from_messages(chat_messages)
    except Exception as e:
        logger.error(f"❌ Sohbet geçmişi yükleme hatası: {e}")
    
    # Client'a gerçek chat ID'yi gönder
    try:
        # Vector store istatistiklerini al
        vector_store = VectorStore(Config.VECTOR_STORE_PATH, chat_id=chat_id)
        stats = vector_store.get_stats()
        
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "chat_id": chat_id,
            "message": f"Bağlantı kuruldu - Chat: {chat_id}",
            "vector_store_stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }))
        logger.info(f"✅ Client'a bağlantı onayı gönderildi - Chat: {chat_id}")
    except Exception as e:
        logger.error(f"❌ Bağlantı onay mesajı hatası: {e}")
    
    try:
        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                if message_data.get("type") == "user_message":
                    # YENİ DÜZELTME: Mesaj formatını düzelt
                    if "message" in message_data:
                        user_message = message_data["message"]
                    else:
                        # Legacy destek için direkt message olabilir
                        user_message = message_data.get("content", "")
                    
                    # Eğer mesaj nested object ise
                    if isinstance(user_message, dict):
                        user_message = user_message.get("message", "")
                    
                    # String'e çevir ve temizle
                    user_message = str(user_message).strip()
                    
                    # YENİ: force_web_research parametresini kontrol et
                    force_web_research = message_data.get("force_web_research", False)
                    if force_web_research:
                        dialog.conversation_state["force_web_research"] = True
                    
                    if user_message:
                        response = await dialog.process_user_message(user_message)
                        if response:
                            await websocket.send_text(json.dumps({
                                "type": "ai_response",
                                "message": response,
                                "timestamp": datetime.utcnow().isoformat(),
                                "chat_id": chat_id
                            }))
                
                elif message_data.get("type") == "test_parameters_response":
                    # SORUN DÜZELTİLDİ: Test parametreleri yanıtını doğru şekilde işle
                    response_data = message_data.get("response", {})
                    
                    if not isinstance(response_data, dict):
                        logger.warning(f"❌ Geçersiz test parametre formatı: {response_data}")
                        continue

                    # SORUN DÜZELTİLMESİ: Gelen veriyi doğrudan state'e ekle
                    logger.info(f"📝 Test parametreleri alındı: {response_data}")
                    
                    # 1. Gelen yapısal veriyi doğrudan konuşma durumuna (state) ekle
                    dialog.conversation_state["partial_test_params"].update(response_data)
                    
                    # 2. Test parametresi bekleme durumunu işaretle
                    if not dialog.conversation_state.get("awaiting_test_params"):
                        dialog.conversation_state["awaiting_test_params"] = True
                        dialog.conversation_state["test_param_stage"] = "question_types"
                    
                    # 3. Durum makinesinin bir sonraki adımı tetiklemesi için genel bir mesaj oluştur
                    user_message = "Kullanıcı test parametrelerini seçti."
                    
                    # 4. Grafiği normal akışında çalıştır
                    response = await dialog.process_user_message(user_message)

                    # Eğer LangGraph'tan direct bir yanıt gelirse, WebSocket üzerinden gönder
                    if response:
                        await websocket.send_text(json.dumps({
                            "type": "ai_response",
                            "message": response,
                            "timestamp": datetime.utcnow().isoformat(),
                            "chat_id": chat_id
                        }))
                
                elif message_data.get("type") == "start_test":
                    # Test başlatma komutu
                    test_data = message_data.get("test_data", {})
                    
                    # Test verilerini localStorage için gönder
                    await websocket.send_text(json.dumps({
                        "type": "test_data_ready",
                        "test_data": test_data,
                        "timestamp": datetime.utcnow().isoformat(),
                        "chat_id": chat_id
                    }))
                
                elif message_data.get("type") == "test_completed":
                    # Test tamamlandı, sonuçları değerlendir
                    test_results = message_data.get("results", {})
                    
                    try:
                        # Test sonuçlarını analiz et ve chat'e kaydet
                        evaluation_result = await evaluate_test_results_internal(chat_id, test_results)
                        
                        # YENİ: Eksik konuları WebSocket üzerinden direkt gönder
                        if evaluation_result.get("weak_areas"):
                            # Ana değerlendirme mesajını gönder
                            await websocket.send_text(json.dumps({
                                "type": "ai_response", 
                                "message": format_evaluation_message(evaluation_result),
                                "timestamp": datetime.utcnow().isoformat(),
                                "chat_id": chat_id
                            }))
                            
                            # Eksik konuları ayrı mesaj olarak gönder
                            topics_message = "🎯 **Eksik Olduğun Konular:**\n\n"
                            topics_message += "Bu konularda biraz daha çalışmanda fayda var:\n\n"
                            
                            for i, area in enumerate(evaluation_result["weak_areas"], 1):
                                topic_name = area["topic"] if isinstance(area, dict) else area
                                topics_message += f"{i}. **{topic_name}**\n"
                                topics_message += f"   💡 Bu konuyu detaylı açıklamamı istersen: *\"{topic_name} konusunu açıkla\"*\n\n"
                            
                            topics_message += "📝 **Not:** Yukarıdaki konulardan herhangi birini seçerek benden detaylı açıklama isteyebilirsin! Birlikte öğrenelim! 🤝"
                            
                            await websocket.send_text(json.dumps({
                                "type": "ai_response",
                                "message": topics_message,
                                "timestamp": datetime.utcnow().isoformat(),
                                "chat_id": chat_id
                            }))
                        else:
                            # Eksik konu yoksa sadece ana değerlendirme mesajını gönder
                            await websocket.send_text(json.dumps({
                                "type": "ai_response",
                                "message": format_evaluation_message(evaluation_result) + "\n\n🎉 **Harika!** Tüm konularda başarılısın! Böyle devam et! 👏",
                                "timestamp": datetime.utcnow().isoformat(),
                                "chat_id": chat_id
                            }))
                        
                        # Ayrıca eski formatı da gönder (geriye dönük uyumluluk için)
                        await websocket.send_text(json.dumps({
                            "type": "test_evaluation_complete",
                            "evaluation": evaluation_result,
                            "timestamp": datetime.utcnow().isoformat(),
                            "chat_id": chat_id
                        }))
                        
                    except Exception as e:
                        logger.error(f"❌ Test değerlendirme hatası: {e}")
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": f"Test değerlendirme hatası: {str(e)}"
                        }))
                
                elif message_data.get("type") == "llm_evaluation_request":
                    prompt = message_data.get("prompt", "")
                    question_index = message_data.get("questionIndex", 0)
                    metadata = message_data.get("metadata", {})
                    
                    logger.info(f"🤖 LLM değerlendirme isteği alındı (Soru: {question_index})")
                    
                    try:
                        # LLM çağrısına 30 saniyelik zaman aşımı ekle
                        evaluation_result = await asyncio.wait_for(
                            evaluate_classic_answer_with_llm(prompt, dialog.llm),
                            timeout=30.0
                        )
                        
                        await websocket.send_text(json.dumps({
                            "type": "llm_evaluation_response",
                            "questionIndex": question_index,
                            "evaluation": evaluation_result,
                            "metadata": metadata,
                            "timestamp": datetime.utcnow().isoformat(),
                            "chat_id": chat_id
                        }))
                        logger.info(f"✅ LLM değerlendirmesi tamamlandı (Soru: {question_index})")

                    except asyncio.TimeoutError:
                        logger.error(f"⏰ LLM değerlendirmesi zaman aşımına uğradı (Soru: {question_index})")
                        # Zaman aşımı durumunda kullanıcıya özel bir mesaj gönder
                        await websocket.send_text(json.dumps({
                            "type": "llm_evaluation_response",
                            "questionIndex": question_index,
                            "evaluation": "DOĞRU/YANLIŞ: Doğru\nPUAN: 70\nGERİ BİLDİRİM: Değerlendirme zaman aşımına uğradı, bu nedenle cevabınız geçici olarak doğru kabul edildi.",
                            "metadata": metadata,
                            "timestamp": datetime.utcnow().isoformat(),
                            "chat_id": chat_id
                        }))
                    except Exception as e:
                        # Diğer tüm hataları yakala ve logla
                        logger.error(f"❌ LLM değerlendirme hatası (Soru: {question_index}): {e}", exc_info=True)
                        # Genel hata durumunda kullanıcıya mesaj gönder
                        await websocket.send_text(json.dumps({
                            "type": "llm_evaluation_response",
                            "questionIndex": question_index,
                            "evaluation": "DOĞRU/YANLIŞ: Doğru\nPUAN: 70\nGERİ BİLDİRİM: Değerlendirme sırasında bir hata oluştu, bu nedenle cevabınız geçici olarak doğru kabul edildi.",
                            "metadata": metadata,
                            "timestamp": datetime.utcnow().isoformat(),
                            "chat_id": chat_id
                        }))
                
                elif message_data.get("type") == "explain_topic":
                    # Eksik konu açıklaması istendi
                    topic = message_data.get("topic", "")
                    
                    # Bu konuyu açıklama talebini normal mesaj olarak işle
                    explain_message = f"'{topic}' konusunu detaylı olarak açıklayabilir misin?"
                    response = await dialog.process_user_message(explain_message)
                    
                    if response:
                        await websocket.send_text(json.dumps({
                            "type": "topic_explanation",
                            "topic": topic,
                            "explanation": response,
                            "timestamp": datetime.utcnow().isoformat(),
                            "chat_id": chat_id
                        }))
                
                elif message_data.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    }))
            
            except WebSocketDisconnect:
                logger.info(f"🔌 WebSocket bağlantısı kesildi - Chat: {chat_id}")
                break
            except json.JSONDecodeError:
                logger.error("❌ Geçersiz JSON formatı")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Geçersiz mesaj formatı"
                }))
            except Exception as e:
                logger.error(f"❌ WebSocket mesaj işleme hatası: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Mesaj işlenirken hata oluştu: {str(e)}"
                }))
    
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket bağlantısı sonlandı - Chat: {chat_id}")
    except Exception as e:
        logger.error(f"❌ WebSocket genel hatası: {e}")
    finally:
        # Cleanup
        if chat_id in dialog_instances:
            dialog_instances[chat_id].websocket_callback = None

@app.post("/chats/{chat_id}/save-test")
async def save_test_to_chat(chat_id: str, test_data: dict):
    """Test verilerini chat'e kalıcı olarak kaydet"""
    try:
        chat_info = chat_manager.get_chat_info(chat_id)
        if not chat_info:
            raise HTTPException(status_code=404, detail="Sohbet bulunamadı")
        
        # Test verilerini chat klasörüne kaydet
        chat_dir = chat_manager.get_chat_directory(chat_id)
        test_file = chat_dir / "saved_tests.json"
        
        # Mevcut testleri yükle
        saved_tests = []
        if test_file.exists():
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    saved_tests = json.load(f)
            except Exception as e:
                logger.warning(f"Saved tests dosyası okunamadı: {e}")
                saved_tests = []
        
        # Yeni test ekle
        test_entry = {
            "test_id": test_data.get("test_id", f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
            "created_at": datetime.now().isoformat(),
            "questions": test_data.get("questions", {}),
            "parameters": test_data.get("parameters", {}),
            "title": test_data.get("title", "Oluşturulan Test")
        }
        
        saved_tests.append(test_entry)
        
        # Dosyaya kaydet
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(saved_tests, f, ensure_ascii=False, indent=2)
        
        # Chat mesajı olarak da kaydet
        chat_manager.save_message(chat_id, {
            "type": "system",
            "content": f"🧠 **Test Kaydedildi:** {test_entry['title']}\n📊 Test ID: {test_entry['test_id']}\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            "metadata": {
                "message_type": "test_saved",
                "test_id": test_entry['test_id']
            }
        })
        
        return JSONResponse({
            "success": True,
            "message": "Test başarıyla kaydedildi",
            "test_id": test_entry['test_id']
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test kaydetme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Test kaydetme hatası: {str(e)}")

@app.get("/chats/{chat_id}/tests")
async def get_chat_tests(chat_id: str):
    """Chat'e ait kaydedilmiş testleri getir"""
    try:
        chat_info = chat_manager.get_chat_info(chat_id)
        if not chat_info:
            raise HTTPException(status_code=404, detail="Sohbet bulunamadı")
        
        # Test dosyasını oku
        chat_dir = chat_manager.get_chat_directory(chat_id)
        test_file = chat_dir / "saved_tests.json"
        
        saved_tests = []
        if test_file.exists():
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    saved_tests = json.load(f)
            except Exception as e:
                logger.warning(f"Saved tests dosyası okunamadı: {e}")
                saved_tests = []
        
        return JSONResponse({
            "success": True,
            "tests": saved_tests,
            "chat_id": chat_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test listesi hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Test listesi hatası: {str(e)}")

@app.get("/chats/{chat_id}/tests/{test_id}")
async def get_test_by_id(chat_id: str, test_id: str):
    """Belirli bir test'i ID ile getir"""
    try:
        chat_info = chat_manager.get_chat_info(chat_id)
        if not chat_info:
            raise HTTPException(status_code=404, detail="Sohbet bulunamadı")
        
        # Test dosyasını oku
        chat_dir = chat_manager.get_chat_directory(chat_id)
        test_file = chat_dir / "saved_tests.json"
        
        if not test_file.exists():
            raise HTTPException(status_code=404, detail="Test bulunamadı")
        
        with open(test_file, 'r', encoding='utf-8') as f:
            saved_tests = json.load(f)
        
        # Test'i bul
        test_data = None
        for test in saved_tests:
            if test.get("test_id") == test_id:
                test_data = test
                break
        
        if not test_data:
            raise HTTPException(status_code=404, detail="Test bulunamadı")
        
        return JSONResponse({
            "success": True,
            "test": test_data,
            "chat_id": chat_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Test getirme hatası: {e}")
        raise HTTPException(status_code=500, detail=f"Test getirme hatası: {str(e)}")
