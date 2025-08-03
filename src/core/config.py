import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

class Config:
    # API Keys
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    SERPER_API_KEY = os.getenv("SERPER_API_KEY")
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
    BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")

    # Model configurations
    GEMINI_MODEL = "gemini-2.5-flash"
    GEMINI_TEMPERATURE = 0.7
    GEMINI_MAX_TOKENS = 2048

    # Chat configurations
    MAX_HISTORY_LENGTH = 50
    
    # GÜNCELLENEN SATIR 20-37: Vector Store ve PDF konfigürasyonları eklendi
    # Vector Store configurations
    VECTOR_STORE_PATH = "chroma_db"
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    MAX_PDF_SIZE = 50 * 1024 * 1024  # 50MB
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    MAX_IMAGE_SIZE = 10 * 1024 * 1024 # 10MB
    
    # PDF Upload configurations  
    UPLOAD_DIR = "uploads"
    ALLOWED_EXTENSIONS = {'.pdf'}
    
    # RAG configurations
    RAG_TOP_K = 5  # Kaç doküman parçası getirilecek
    RAG_SIMILARITY_THRESHOLD = 0.3  # Minimum benzerlik skoru
    RAG_ENABLED = True  # RAG sistemini açık/kapalı

    # GÜNCELLENEN SATIR 38-50: System prompt RAG desteği ile genişletildi
    SYSTEM_PROMPT = """Sen LangGraph ve CrewAI ile güçlendirilmiş akıllı bir asistansın.
Kullanıcılarla Türkçe konuşuyorsun ve onlara yardımcı olmaya odaklanıyorsun.

Özelliklerinz:
- Web araştırması yapabilirsin
- Soru üretebilirsin  
- Veri analizi yapabilirsin
- Metin özetleyebilirsin
- Yüklenen PDF dokümanlarından bilgi çıkarabilirsin (RAG sistemi)
- Önceden yüklenmiş dokümanlar arasında arama yapabilirsin

Eğer kullanıcının sorusuyla ilgili yüklenmiş PDF dokümanlarında bilgi varsa, 
öncelikle o bilgileri kullan ve hangi dokümanlardan geldiğini belirt.

Her zaman yardımcı, samimi ve profesyonel ol."""

    @classmethod
    def validate_config(cls):
        """API anahtarlarının varlığını kontrol et"""
        required_keys = ["GOOGLE_API_KEY"]
        missing_keys = []
        
        for key in required_keys:
            if not getattr(cls, key):
                missing_keys.append(key)
        
        if missing_keys:
            raise ValueError(f"Eksik API anahtarları: {', '.join(missing_keys)}")
        
        # YENI SATIRLAR 61-66: Upload dizinini oluştur
        # Upload dizinini oluştur
        upload_dir = Path(cls.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True)
        
        return True

# YENI SATIRLAR 68-76: Path import'u eklendi
from pathlib import Path

# Config doğrulaması
try:
    Config.validate_config()
    print("✅ Konfigürasyon başarıyla yüklendi")
except ValueError as e:
    print(f"❌ Konfigürasyon hatası: {e}")