import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# .env dosyasındaki değişkenleri yükle
load_dotenv()

# API anahtarını .env dosyasından al
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

if not YOUTUBE_API_KEY:
    print("HATA: .env dosyasında YOUTUBE_API_KEY bulunamadı.")
else:
    print("API Anahtarı başarıyla yüklendi.")
    
    try:
        print("YouTube servisi oluşturuluyor... (build fonksiyonu çağrılıyor)")
        # Bu satır 'Resource' nesnesini oluşturur.
        youtube_service = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        print("Servis başarıyla oluşturuldu. Nesne tipi:", type(youtube_service))

        print("\nArama isteği hazırlanıyor... (youtube_service.search().list() çağrılıyor)")
        # Bu satır, 'Resource' nesnesinin bir metodunu çağırır. Hata burada oluyorsa
        # 'youtube_service' değişkeni beklenen türde bir nesne değildir.
        request = youtube_service.search().list(
            q="crewai",
            part="snippet",
            type="video",
            maxResults=1
        )
        print("Arama isteği başarıyla hazırlandı.")
        
        print("Arama isteği çalıştırılıyor... (request.execute())")
        response = request.execute()

        print("\n--- BAŞARILI ---")
        print("API isteği başarıyla tamamlandı.")
        print("Bulunan ilk video başlığı:")
        print(response['items'][0]['snippet']['title'])

    except HttpError as e:
        print(f"\n--- API HATASI ---")
        print(f"Bir HTTP Hatası oluştu. API anahtarınız veya yetkileriniz hatalı olabilir.")
        print(f"Hata Detayı: {e.content}")
        
    except Exception as e:
        print(f"\n--- GENEL HATA ---")
        print(f"Beklenmedik bir hata oluştu: {e}")
        print(f"Hatanın Tipi: {type(e).__name__}")