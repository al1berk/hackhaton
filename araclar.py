# araclar.py

import json
import os
import time
import yt_dlp
from faster_whisper import WhisperModel
from crewai.tools import BaseTool  # DEĞİŞİKLİK BURADA
from googleapiclient.discovery import build

# --- YOUTUBE TRANSKRİPT ARACI ---
class YouTubeTranscriptTool(BaseTool):
    name: str = "YouTube Video Transcript Tool"
    description: str = (
        "Bir YouTube video linkini girdi olarak alır ve videonun tam metin transkriptini döndürür. "
        "Girdi mutlaka geçerli bir YouTube video URL'si olmalıdır."
    )
    model: WhisperModel

    def _run(self, video_url: str) -> str:
        output_filename = f"temp_audio_{int(time.time() * 1000)}.mp3"
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
            'outtmpl': output_filename.replace('.mp3', ''), 'quiet': True, 'no_warnings': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            if not os.path.exists(output_filename): return "HATA: Ses dosyası indirilemedi."
            
            segments, _ = self.model.transcribe(output_filename, beam_size=5, vad_filter=True)
            transcript_text = "".join(segment.text for segment in segments).strip()
            return transcript_text if transcript_text else "Transkript boş veya oluşturulamadı."
        except Exception as e:
            return f"HATA: Transkript oluşturulurken bir hata oluştu - {e}"
        finally:
            if os.path.exists(output_filename): os.remove(output_filename)

# --- YOUTUBE ARAMA ARACI ---
class YouTubeSearchTool(BaseTool):
    name: str = "YouTube Video Search Tool"
    description: str = (
        "Belirli bir konu hakkında YouTube'da arama yapar ve en alakalı videoların "
        "başlıklarını ve URL'lerini bir metin olarak döndürür. "
        "Girdi, 'yapay zeka trendleri' gibi bir arama sorgusu olmalıdır."
    )
    api_key: str

    def _run(self, search_query: str, max_results: int = 3) -> str:
        try:
            youtube_service = build('youtube', 'v3', developerKey=self.api_key)
            request = youtube_service.search().list(
                q=search_query, part="snippet", type="video", maxResults=max_results, order="relevance"
            )
            response = request.execute()
            
            results = []
            for item in response.get('items', []):
                video_id = item.get('id', {}).get('videoId')
                if video_id:
                    results.append({
                        'title': item['snippet']['title'],
                        'url': f'https://www.youtube.com/watch?v={video_id}'
                    })
            
            if not results: return "Bu konuda video bulunamadı."
            return "\n".join([f"Başlık: {r['title']}, URL: {r['url']}" for r in results])
        except Exception as e:
            return f"HATA: YouTube'da arama yapılırken hata oluştu - {e}"
        


# --- JSON DOĞRULAMA ARACI ---
class JSONValidatorTool(BaseTool):
    name: str = "JSON Validator Tool"
    description: str = (
        "Verilen JSON metninin geçerli olup olmadığını kontrol eder ve "
        "beklenen yapıya sahip olup olmadığını doğrular. "
        "Girdi: Kontrol edilecek JSON metni"
    )
    
    def _run(self, json_text: str) -> str:
        try:
            cleaned_json = json_text.strip()
            if cleaned_json.startswith('```json'):
                cleaned_json = cleaned_json[7:]
            if cleaned_json.endswith('```'):
                cleaned_json = cleaned_json[:-3]
            cleaned_json = cleaned_json.strip()
            
            parsed_json = json.loads(cleaned_json)
            
            if isinstance(parsed_json, list):
                for item in parsed_json:
                    if not isinstance(item, dict):
                        return "HATA: Liste elemanları dict olmalı"
                    if "alt_baslik" not in item or "aciklama" not in item:
                        return "HATA: Her eleman 'alt_baslik' ve 'aciklama' anahtarlarına sahip olmalı"
            else:
                return "HATA: JSON bir liste olmalı"
                
            return "GECERLI: JSON yapısı doğru"
            
        except json.JSONDecodeError as e:
            return f"HATA: Geçersiz JSON formatı - {str(e)}"

# --- JSON KAYDETME ARACI ---
class JSONSaverTool(BaseTool):
    name: str = "JSON Saver Tool"
    description: str = (
        "İçeriği JSON dosyasına kaydeder. "
        "İki parametre alır: content (JSON içeriği) ve filename (dosya adı). "
        "Girdi formatı: 'content|filename' şeklinde olmalıdır."
    )
    
    def _run(self, input_data: str) -> str:
        try:
            # Input'u parse et (content|filename formatında)
            if '|' not in input_data:
                return "HATA: Girdi formatı 'content|filename' şeklinde olmalıdır."
            
            content, filename = input_data.split('|', 1)
            
            # JSON formatını kontrol et
            parsed_content = json.loads(content.strip())
            
            # Dosyaya kaydet
            with open(filename.strip(), 'w', encoding='utf-8') as f:
                json.dump(parsed_content, f, ensure_ascii=False, indent=2)
            
            return f"✅ İçerik başarıyla {filename.strip()} dosyasına kaydedildi."
            
        except ValueError as e:
            return f"❌ Input parse hatası: {str(e)}"
        except json.JSONDecodeError as e:
            return f"❌ JSON decode hatası: {str(e)}"
        except Exception as e:
            return f"❌ Kaydetme hatası: {str(e)}"

# --- DOSYA OKUMA ARACI ---
class FileReaderTool(BaseTool):
    name: str = "File Reader Tool"
    description: str = (
        "Belirtilen dosyayı okur ve içeriğini döndürür. "
        "Girdi: Okunacak dosyanın yolu"
    )
    
    def _run(self, filepath: str) -> str:
        try:
            if not os.path.exists(filepath):
                return f"HATA: '{filepath}' dosyası bulunamadı."
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return content if content else "Dosya boş."
            
        except Exception as e:
            return f"HATA: Dosya okuma hatası - {str(e)}"