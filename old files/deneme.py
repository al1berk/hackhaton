import os
import yt_dlp
from faster_whisper import WhisperModel

def download_audio_from_youtube(video_url: str, output_path: str = "temp_audio.mp3") -> str | None:
    """
    Verilen YouTube URL'sinden sadece sesi indirir ve MP3 olarak kaydeder.
    İndirilen dosyanın yolunu döndürür.
    """
    print(f"\n[1/3] 🔊 Ses indiriliyor: {video_url}")
    
    ydl_opts = {
        'format': 'bestaudio/best', # En iyi kalitedeki sesi seç
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',      # MP3 formatına dönüştür
            'preferredquality': '192',    # Kalite (192 kbps)
        }],
        'outtmpl': output_path.replace('.mp3', ''), # Dosya adını uzantısız ver
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        # Eğer dosya başarıyla oluşturulduysa, yolunu döndür
        if os.path.exists(output_path):
            print(f"✅ Ses başarıyla '{output_path}' olarak indirildi.")
            return output_path
        else:
            print("❌ HATA: Ses dosyası indirme sonrası bulunamadı.")
            return None
            
    except Exception as e:
        print(f"❌ Ses indirilirken bir hata oluştu: {e}")
        return None

def transcribe_audio_with_whisper(audio_path: str, model: WhisperModel) -> str:
    """
    Verilen ses dosyasının yolunu kullanarak faster-whisper ile transkript oluşturur.
    """
    print(f"\n[2/3] ✍️ Transkript oluşturuluyor (Bu işlem sesin uzunluğuna göre sürebilir)...")
    
    # beam_size=5, daha doğru sonuçlar için popüler bir parametredir.
    segments, info = model.transcribe(audio_path, beam_size=5)
    
    print(f"✅ Dil tespiti yapıldı: {info.language} (olasılık: {info.language_probability:.2f})")

    transcript_text = "".join(segment.text for segment in segments)
    
    print("✅ Transkript başarıyla oluşturuldu.")
    return transcript_text.strip()

def cleanup_file(file_path: str):
    """
    Verilen dosya yolundaki dosyayı siler.
    """
    print(f"\n[3/3] 🧹 Geçici dosya siliniyor: {file_path}")
    try:
        os.remove(file_path)
        print("✅ Geçici dosya başarıyla silindi.")
    except OSError as e:
        print(f"❌ Dosya silinirken hata oluştu: {e}")

# --- Ana Çalıştırma Bloğu ---
if __name__ == '__main__':
    print("--- Yerel Whisper ile YouTube Transkript Oluşturma Aracı ---")
    
    # Model seçimi: "tiny", "base", "small", "medium", "large-v3"
    # "base" çoğu durum için iyi bir başlangıçtır.
    # Daha doğru sonuçlar için "medium" kullanabilirsiniz ama daha yavaştır.
    model_size = "base"
    
    print(f"\nWhisper modeli '{model_size}' yükleniyor (ilk çalıştırmada uzun sürebilir)...")
    try:
        # Modeli CPU üzerinde int8 optimizasyonu ile çalıştırarak hız kazan
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        print("✅ Whisper modeli başarıyla yüklendi.")
    except Exception as e:
        print(f"❌ Whisper modeli yüklenemedi: {e}")
        print("Lütfen 'faster-whisper' ve 'torch' kütüphanelerinin doğru kurulduğundan emin olun.")
        exit()

    video_link = input("\nLütfen transkriptini oluşturmak istediğiniz YouTube videosunun linkini girin: ")

    if not video_link.strip():
        print("Geçerli bir link girmediniz.")
    else:
        audio_file = None
        try:
            # 1. Adım: Sesi indir
            audio_file = download_audio_from_youtube(video_link)

            if audio_file:
                # 2. Adım: Transkript oluştur
                transcript = transcribe_audio_with_whisper(audio_file, model)
                
                print("\n" + "="*80)
                print("                       🔥🔥🔥 TRANSKRİPT METNİ 🔥🔥🔥")
                print("="*80)
                print(transcript)
                print("\n" + "="*80)
        finally:
            # 3. Adım: Her durumda geçici dosyayı temizle
            if audio_file and os.path.exists(audio_file):
                cleanup_file(audio_file)