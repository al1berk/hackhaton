import os
import time
import yt_dlp
from faster_whisper import WhisperModel
from googleapiclient.discovery import build
from dotenv import load_dotenv

# --- 1. ADIM: Kurulum ve Yapılandırma ---
load_dotenv()
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
if not YOUTUBE_API_KEY:
    print("HATA: .env dosyasında YOUTUBE_API_KEY bulunamadı.")
    exit()

try:
    youtube_service = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    print("✅ YouTube servisi başarıyla oluşturuldu.")
except Exception as e:
    print(f"❌ YouTube servis hatası: {e}")
    exit()

# --- 2. ADIM: Gerekli Fonksiyonlar ---

def youtube_video_ara(arama_terimi, maks_sonuc=3):
    """Verilen terim için YouTube'da arama yapar ve video bilgilerini döndürür."""
    print(f"\n🔍 '{arama_terimi}' için YouTube'da videolar aranıyor...")
    try:
        request = youtube_service.search().list(
            q=arama_terimi, part="snippet", type="video", maxResults=maks_sonuc)
        response = request.execute()
        video_bilgileri = []
        for item in response.get('items', []):
            video_id = item.get('id', {}).get('videoId')
            if video_id:
                video_bilgileri.append({
                    'id': video_id, 
                    'baslik': item['snippet']['title'],
                    'url': f"https://www.youtube.com/watch?v={video_id}"
                })
        print(f"✅ {len(video_bilgileri)} video bulundu.")
        return video_bilgileri
    except Exception as e:
        print(f"❌ YouTube aramasında hata: {e}")
        return []

def transkripti_al(video_url, model):
    """Videoyu indirir, transkriptini oluşturur ve dosyayı siler."""
    print("🔊 Ses indiriliyor ve transkript oluşturuluyor...")
    
    # Her dosya için benzersiz bir isim oluşturarak çakışmaları önle
    output_filename = f"temp_audio_{int(time.time() * 1000)}.mp3"
    
    # Adım 1: Sesi İndir
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
        'outtmpl': output_filename.replace('.mp3', ''),
        'quiet': True, 'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        if not os.path.exists(output_filename):
            return "HATA: Ses dosyası indirilemedi."
    except Exception as e:
        return f"HATA: Ses indirilirken hata oluştu - {e}"

    # Adım 2: Transkript Oluştur
    try:
        segments, info = model.transcribe(output_filename, beam_size=5, vad_filter=True)
        transcript_text = "".join(segment.text for segment in segments).strip()
        print(f"✅ Transkript oluşturuldu (Tespit edilen dil: {info.language})")
        return transcript_text
    except Exception as e:
        return f"HATA: Transkript oluşturulurken hata oluştu - {e}"
    finally:
        # Adım 3: Geçici Dosyayı Sil
        if os.path.exists(output_filename):
            os.remove(output_filename)

# --- 3. ADIM: Ana Çalıştırma Bloğu ---
if __name__ == '__main__':
    print("--- YouTube Video Transkript Aracı ---")
    
    # M1 için en iyi HIZ/DOĞRULUK dengesini sunan model
    model_size = "base"
    
    print(f"\n🚀 Whisper modeli '{model_size}' yükleniyor (ilk çalıştırmada uzun sürebilir)...")
    try:
        # M1 (Apple Silicon) için en iyi ayarlar: device="cpu", compute_type="int8"
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        print("✅ Whisper modeli başarıyla yüklendi.")
    except Exception as e:
        print(f"❌ Whisper modeli yüklenemedi: {e}")
        exit()

    arama_konusu = input("\nYouTube'da ne hakkında videolar aramak istersiniz?: ")

    if not arama_konusu.strip():
        print("Geçerli bir konu girmediniz.")
    else:
        videolar = youtube_video_ara(arama_konusu)

        if videolar:
            for video in videolar:
                print("\n" + "="*80)
                print(f"📹 VİDEO BAŞLIĞI: {video['baslik']}")
                print(f"🔗 LİNK: {video['url']}")
                print("-" * 80)
                
                # Transkripti al ve yazdır
                transcript = transkripti_al(video['url'], model)
                print("\n--- 🔥 TRANSKRİPT 🔥 ---")
                print(transcript if transcript else "Transkript alınamadı.")
            
            print("\n" + "="*80)
            print("✨ İşlem tamamlandı! ✨")