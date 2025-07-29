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
    SYSTEM_PROMPT = """Sen LangGraph ve CrewAI ile güçlendirilmiş akıllı bir asistansın. 
    Kullanıcılarla Türkçe konuşuyorsun ve onlara yardımcı olmaya odaklanıyorsun.
    
    Özellikleriniz:
    - Web araştırması yapabilirsin
    - Soru üretebilirsin  
    - Veri analizi yapabilirsin
    - Metin özetleyebilirsin
    
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
        
        return True

# Config doğrulaması
try:
    Config.validate_config()
    print("✅ Konfigürasyon başarıyla yüklendi")
except ValueError as e:
    print(f"❌ Konfigürasyon hatası: {e}")