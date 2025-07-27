from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
import uvicorn
import asyncio
from datetime import datetime
from langgraph_dialog import AsyncLangGraphDialog
from config import Config

app = FastAPI(
    title="LangGraph + CrewAI Async Multi-Agent Chat",
    description="Gemini ve CrewAI ile asenkron güçlendirilmiş akıllı araştırma asistanı",
    version="2.1.0"
)

# Static directory setup
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

# Research data directory
research_dir = Path("research_data")
research_dir.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Active dialog instances
dialog_instances = {}
connection_stats = {
    "total_connections": 0,
    "active_connections": 0,
    "messages_processed": 0,
    "crew_researches": 0,
    "async_operations": 0,
    "start_time": datetime.utcnow()
}

@app.on_event("startup")
async def startup_event():
    """Application startup tasks"""
    print("🚀 Async LangGraph + CrewAI Multi-Agent System başlatılıyor...")
    
    try:
        # Config doğrulaması
        Config.validate_config()
        print("✅ API anahtarları doğrulandı")
        
        # Test async connections
        test_dialog = AsyncLangGraphDialog()
        print("✅ Async LangGraph + CrewAI sistemi hazır")
        
    except Exception as e:
        print(f"❌ Startup hatası: {e}")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Ana chat arayüzünü serve et"""
    return FileResponse("index.html")

@app.get("/health")
async def health_check():
    """Sistem sağlık kontrolü"""
    uptime = datetime.utcnow() - connection_stats["start_time"]
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "uptime_seconds": int(uptime.total_seconds()),
        "systems": {
            "gemini": "connected",
            "crewai": "async-ready",
            "langgraph": "async-active"
        },
        "stats": {
            "active_connections": connection_stats["active_connections"],
            "total_messages": connection_stats["messages_processed"],
            "crew_researches": connection_stats["crew_researches"],
            "async_operations": connection_stats["async_operations"]
        }
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint - Async Gemini + CrewAI ile gerçek zamanlı chat"""
    client_id = None
    
    try:
        await websocket.accept()
        client_id = id(websocket)
        
        # Connection stats update
        connection_stats["total_connections"] += 1
        connection_stats["active_connections"] += 1
        
        # Create dialog instance with websocket callback
        async def websocket_callback(message):
            try:
                await websocket.send_text(message)
                connection_stats["async_operations"] += 1
            except Exception as e:
                print(f"WebSocket callback error: {e}")
        
        dialog_instances[client_id] = AsyncLangGraphDialog(websocket_callback)
        
        print(f"🔌 Yeni asenkron bağlantı: Client {client_id}")
        
        # Welcome message
        welcome_msg = {
            "type": "system",
            "content": "🤖 Async LangGraph + CrewAI Multi-Agent sistemine hoş geldiniz! Real-time progress tracking ile kapsamlı araştırma yapabilirim.",
            "timestamp": datetime.utcnow().isoformat(),
            "stats": dialog_instances[client_id].get_conversation_stats()
        }
        await websocket.send_text(json.dumps(welcome_msg))
        
        while True:
            # Receive message
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if "message" in message_data:
                user_message = message_data["message"]
                connection_stats["messages_processed"] += 1
                
                # CrewAI araştırması mı kontrol et
                if any(keyword in user_message.lower() for keyword in ["araştır", "research", "incele", "analiz"]):
                    connection_stats["crew_researches"] += 1
                
                print(f"📨 Async Client {client_id}: {user_message[:50]}...")
                
                try:
                    # ASENKRON olarak process et - UI donmayacak!
                    response = await dialog_instances[client_id].process_user_message(user_message)
                    
                    # Get conversation stats
                    stats = dialog_instances[client_id].get_conversation_stats()
                    
                    # Send response
                    response_data = {
                        "type": "message",
                        "content": response,
                        "timestamp": datetime.utcnow().isoformat(),
                        "intent": stats["current_intent"],
                        "stats": {
                            "total_messages": stats["total_messages"],
                            "intent": stats["current_intent"],
                            "crew_ai_enabled": stats["crew_ai_enabled"],
                            "has_research": stats["has_research_data"],
                            "async_mode": stats["async_mode"]
                        }
                    }
                    
                    await websocket.send_text(json.dumps(response_data))
                    print(f"✅ Async Client {client_id}: Yanıt gönderildi (Intent: {stats['current_intent']})")
                    
                except Exception as e:
                    # Error handling
                    error_response = {
                        "type": "error",
                        "content": f"Üzgünüm, mesajınızı işlerken bir hata oluştu: {str(e)}",
                        "timestamp": datetime.utcnow().isoformat(),
                        "error_code": "ASYNC_PROCESSING_ERROR"
                    }
                    
                    await websocket.send_text(json.dumps(error_response))
                    print(f"❌ Async Client {client_id}: Hata - {str(e)}")
            
            elif message_data.get("type") == "ping":
                # Heartbeat response
                pong_data = {
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat(),
                    "stats": connection_stats,
                    "async_mode": True
                }
                await websocket.send_text(json.dumps(pong_data))
    
    except WebSocketDisconnect:
        print(f"🔌 Async Client {client_id} bağlantısı kesildi")
    
    except Exception as e:
        print(f"❌ Async WebSocket hatası (Client {client_id}): {e}")
    
    finally:
        # Cleanup
        if client_id:
            connection_stats["active_connections"] -= 1
            
            if client_id in dialog_instances:
                del dialog_instances[client_id]
                print(f"🧹 Async Client {client_id} temizlendi")

@app.get("/api/stats")
async def get_detailed_stats():
    """Detaylı uygulama istatistikleri"""
    uptime = datetime.utcnow() - connection_stats["start_time"]
    
    return {
        "connections": {
            "active": connection_stats["active_connections"],
            "total": connection_stats["total_connections"]
        },
        "messages": {
            "total_processed": connection_stats["messages_processed"],
            "crew_researches": connection_stats["crew_researches"],
            "async_operations": connection_stats["async_operations"],
            "avg_per_connection": connection_stats["messages_processed"] / max(connection_stats["total_connections"], 1)
        },
        "uptime": {
            "seconds": int(uptime.total_seconds()),
            "formatted": str(uptime)
        },
        "system": {
            "gemini_model": Config.GEMINI_MODEL,
            "max_tokens": Config.GEMINI_MAX_TOKENS,
            "temperature": Config.GEMINI_TEMPERATURE,
            "features": ["Async LangGraph", "Async CrewAI", "Multi-Agent", "A2A Protocol", "Real-time Progress"],
            "mode": "FULL_ASYNC"
        }
    }

if __name__ == "__main__":
    print("🌟 Async LangGraph + CrewAI Multi-Agent Chat System")
    print("=" * 60)
    print("🔑 API Anahtarları:")
    print(f"   ✅ Google API Key: {'✓' if Config.GOOGLE_API_KEY else '❌'}")
    print(f"   📊 Serper API Key: {'✓' if Config.SERPER_API_KEY else '❌'}")
    print(f"   🎥 YouTube API Key: {'✓' if Config.YOUTUBE_API_KEY else '❌'}")
    print(f"   🦁 Brave API Key: {'✓' if Config.BRAVE_API_KEY else '❌'}")
    print("=" * 60)
    print("🚀 Sistem Özellikleri:")
    print("   ✅ FULL ASYNC LangGraph Conversation Flow")
    print("   ✅ ASYNC Gemini Pro Integration")
    print("   ✅ ASYNC CrewAI Multi-Agent System")
    print("   ✅ Real-time A2A Protocol Communication")
    print("   ✅ Non-blocking Progress Updates")
    print("   ✅ UI Responsive during LLM operations")
    print("   ✅ ThreadPoolExecutor for CrewAI")
    print("=" * 60)
    print("🚀 Başlatılıyor...")
    print("📱 Web UI: http://localhost:8000")
    print("🔗 WebSocket: ws://localhost:8000/ws")
    print("📊 Stats API: http://localhost:8000/api/stats")
    print("💡 Durdurmak için: Ctrl+C")
    print("💫 UI artık LLM işlemleri sırasında DONMAYACAK!")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )