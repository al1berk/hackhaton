import os
from dotenv import load_dotenv
from pathlib import Path

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
    
    # Vector Store configurations
    VECTOR_STORE_PATH = "chroma_db"
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    MAX_PDF_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB - OCR için resim boyutu
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    
    # PDF ve Resim Upload configurations  
    UPLOAD_DIR = "uploads"
    ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.bmp', '.webp'}  # OCR destekli formatlar
    
    # RAG configurations
    RAG_TOP_K = 5  # Kaç doküman parçası getirilecek
    RAG_SIMILARITY_THRESHOLD = 0.3  # Minimum benzerlik skoru
    RAG_ENABLED = True  # RAG sistemini açık/kapalı

    # Test Generation configurations
    DEFAULT_QUESTION_COUNT = 5
    DEFAULT_DIFFICULTY = "orta"
    DEFAULT_STUDENT_LEVEL = "lise"
    SUPPORTED_QUESTION_TYPES = ['coktan_secmeli', 'klasik', 'bosluk_doldurma', 'dogru_yanlis']

    SYSTEM_PROMPT = """Sen LangGraph ve CrewAI ile güçlendirilmiş akıllı bir asistansın.
Kullanıcılarla Türkçe konuşuyorsun ve onlara yardımcı olmaya odaklanıyorsun.

Özelliklerinz:
- Web araştırması yapabilirsin
- Dokümanlardan test soruları üretebilirsin (çoktan seçmeli, klasik, boşluk doldurma, doğru-yanlış)
- Veri analizi yapabilirsin
- Metin özetleyebilirsin
- Yüklenen PDF dokümanlarından ve resimlerden (OCR ile) bilgi çıkarabilirsin (RAG sistemi)
- Önceden yüklenmiş dokümanlar arasında arama yapabilirsin
- Test sonuçlarını analiz edip eksik konuları belirleyebilirsin

Eğer kullanıcının sorusuyla ilgili yüklenmiş dokümanlarında bilgi varsa, 
öncelikle o bilgileri kullan ve hangi dokümanlardan geldiğini belirt.

Test üretimi için kullanıcıdan soru sayısı, zorluk seviyesi ve soru türlerini sor.
Test tamamlandıktan sonra eksik konuları analiz et ve öğrenme önerileri sun.

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
        
        # Upload dizinini oluştur
        upload_dir = Path(cls.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True)
        
        return True

# Config doğrulaması
try:
    Config.validate_config()
    print("✅ Konfigürasyon başarıyla yüklendi")
except ValueError as e:
    print(f"❌ Konfigürasyon hatası: {e}")