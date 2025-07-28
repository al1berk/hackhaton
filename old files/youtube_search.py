import os
import google.generativeai as genai
from dotenv import load_dotenv
from googleapiclient.discovery import build
import requests
import re
import json
from urllib.parse import urlparse, parse_qs
import time
import random
from bs4 import BeautifulSoup
import yt_dlp
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import concurrent.futures
from threading import Lock

# --- Enhanced Configuration ---
load_dotenv()
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

# Rate limiting configuration
RATE_LIMIT_DELAY = (2, 5)  # Random delay between requests
MAX_RETRIES = 3
BACKOFF_FACTOR = 2

# Thread safety
print_lock = Lock()

def safe_print(message):
    """Thread-safe printing"""
    with print_lock:
        print(message)

# --- Initialize APIs ---
if not YOUTUBE_API_KEY or not GEMINI_API_KEY:
    print("HATA: .env dosyanızda 'YOUTUBE_API_KEY' veya 'GOOGLE_API_KEY' bulunamadı.")
    exit()

try:
    genai.configure(api_key=GEMINI_API_KEY)
    safe_print("✅ Gemini API başarıyla yapılandırıldı.")
except Exception as e:
    print(f"❌ Gemini API hatası: {e}")
    exit()

try:
    youtube_service = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    safe_print("✅ YouTube servisi başarıyla oluşturuldu.")
except Exception as e:
    print(f"❌ YouTube servis hatası: {e}")
    exit()

# --- Enhanced HTTP Session ---
def create_robust_session():
    """Create a robust HTTP session with retry strategy"""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Add random user agents
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    ]
    
    session.headers.update({
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    })
    
    return session

# --- YouTube Search ---
def youtube_video_ara(arama_terimi, maks_sonuc=20):
    safe_print(f"\n🔍 '{arama_terimi}' için YouTube'da arama yapılıyor...")
    try:
        request = youtube_service.search().list(
            q=f"{arama_terimi}",
            part="snippet", 
            type="video", 
            maxResults=maks_sonuc,
            order="relevance",
            regionCode="US",  # Better results
            relevanceLanguage="en"
        )
        response = request.execute()
        
        video_bilgileri = []
        for item in response.get('items', []):
            try:
                # Safely extract video ID
                video_id = None
                if 'id' in item:
                    if isinstance(item['id'], dict) and 'videoId' in item['id']:
                        video_id = item['id']['videoId']
                    elif isinstance(item['id'], str):
                        video_id = item['id']
                
                if not video_id:
                    safe_print(f"⚠️  Video ID bulunamadı: {item.get('snippet', {}).get('title', 'Unknown')}")
                    continue
                
                video_info = {
                    'id': video_id, 
                    'baslik': item['snippet']['title'],
                    'kanal': item['snippet']['channelTitle'],
                    'tarih': item['snippet']['publishedAt'][:10],
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'aciklama': item['snippet'].get('description', '')[:500]  # Preview
                }
                video_bilgileri.append(video_info)
                
            except Exception as item_error:
                safe_print(f"⚠️  Video işlenirken hata: {item_error}")
                continue
        
        safe_print(f"✅ {len(video_bilgileri)} adet video bulundu.")
        return video_bilgileri
        
    except Exception as e:
        safe_print(f"❌ YouTube aramasında hata: {e}")
        safe_print(f"🔍 Hata detayı: {type(e).__name__}")
        
        # Try alternative search without advanced parameters
        try:
            safe_print("🔄 Basit arama deneniyor...")
            request = youtube_service.search().list(
                q=arama_terimi,
                part="snippet", 
                type="video", 
                maxResults=min(maks_sonuc, 10)
            )
            response = request.execute()
            
            video_bilgileri = []
            for item in response.get('items', []):
                try:
                    video_id = item['id']['videoId'] if 'videoId' in item['id'] else item['id']
                    video_info = {
                        'id': video_id, 
                        'baslik': item['snippet']['title'],
                        'kanal': item['snippet']['channelTitle'],
                        'tarih': item['snippet']['publishedAt'][:10],
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'aciklama': item['snippet'].get('description', '')[:300]
                    }
                    video_bilgileri.append(video_info)
                except:
                    continue
            
            safe_print(f"✅ {len(video_bilgileri)} adet video bulundu (basit arama).")
            return video_bilgileri
            
        except Exception as fallback_error:
            safe_print(f"❌ Basit arama da başarısız: {fallback_error}")
            return []

# --- Enhanced Transcript Methods ---
def ytdlp_transkript_al_gelismis(video_url, max_retries=3):
    """Enhanced yt-dlp transcript extraction with better error handling"""
    safe_print(f"📝 yt-dlp ile transkript alınıyor: {video_url}")
    
    for attempt in range(max_retries):
        try:
            # Random delay to avoid rate limiting
            if attempt > 0:
                delay = random.uniform(5, 10) * (attempt + 1)
                safe_print(f"⏱️  {delay:.1f} saniye bekleniyor (deneme {attempt + 1}/{max_retries})")
                time.sleep(delay)
            
            ydl_opts = {
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'tr'],  # English first
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 30,
                'retries': 3,
                # Use proxy rotation if needed
                'proxy': None,  # Add proxy here if you have one
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                
                subtitles = info.get('subtitles', {})
                automatic_captions = info.get('automatic_captions', {})
                
                # Try manual subtitles first
                for lang in ['en', 'tr']:
                    if lang in subtitles:
                        safe_print(f"✅ Manuel altyazı bulundu ({lang})")
                        subtitle_url = subtitles[lang][0]['url']
                        transcript = indir_ve_parse_subtitle_gelismis(subtitle_url, lang)
                        if transcript:
                            return transcript
                
                # Try automatic captions
                for lang in ['en', 'tr']:
                    if lang in automatic_captions:
                        safe_print(f"🤖 Otomatik altyazı bulundu ({lang})")
                        subtitle_url = automatic_captions[lang][0]['url']
                        transcript = indir_ve_parse_subtitle_gelismis(subtitle_url, lang)
                        if transcript:
                            return transcript
                
                safe_print("❌ Hiç altyazı bulunamadı")
                return None
                
        except Exception as e:
            safe_print(f"❌ yt-dlp hatası (deneme {attempt + 1}): {str(e)[:100]}")
            if "429" in str(e) or "Too Many Requests" in str(e):
                # Exponential backoff for rate limiting
                delay = (2 ** attempt) * random.uniform(10, 20)
                safe_print(f"⏸️  Rate limit detected, {delay:.1f} saniye bekleniyor...")
                time.sleep(delay)
            elif attempt == max_retries - 1:
                return None
    
    return None

def indir_ve_parse_subtitle_gelismis(subtitle_url, lang):
    """Enhanced subtitle download and parsing"""
    max_attempts = 3
    
    for attempt in range(max_attempts):
        try:
            session = create_robust_session()
            
            # Progressive delay
            delay = random.uniform(2, 5) * (attempt + 1)
            safe_print(f"⏱️  {delay:.1f}s bekleniyor (altyazı indirme, deneme {attempt + 1})")
            time.sleep(delay)
            
            # Try different approaches
            headers = session.headers.copy()
            if attempt > 0:
                headers.update({
                    'Referer': 'https://www.youtube.com/',
                    'Origin': 'https://www.youtube.com'
                })
            
            response = session.get(subtitle_url, headers=headers, timeout=45)
            response.raise_for_status()
            
            content = response.text
            
            # Enhanced VTT/JSON parsing
            if 'json3' in subtitle_url or subtitle_url.endswith('json3'):
                result = parse_json3_subtitle(content)
            else:
                result = parse_vtt_subtitle(content)
            
            if result and len(result) > 50:
                safe_print(f"✅ Altyazı başarıyla alındı ({lang}) - {len(result)} karakter")
                return result
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                safe_print(f"⚠️  Rate limit (deneme {attempt + 1})")
                if attempt < max_attempts - 1:
                    time.sleep(random.uniform(10, 20) * (attempt + 1))
                    continue
            elif e.response.status_code == 403:
                safe_print(f"⚠️  Erişim reddedildi (403)")
                break
            else:
                safe_print(f"❌ HTTP Error {e.response.status_code}")
                
        except requests.exceptions.ConnectionError as e:
            safe_print(f"⚠️  Bağlantı hatası (deneme {attempt + 1})")
            if attempt < max_attempts - 1:
                time.sleep(random.uniform(5, 10))
                continue
                
        except requests.exceptions.Timeout as e:
            safe_print(f"⚠️  Zaman aşımı (deneme {attempt + 1})")
            if attempt < max_attempts - 1:
                time.sleep(random.uniform(3, 8))
                continue
                
        except Exception as e:
            safe_print(f"❌ Genel hata: {str(e)[:100]}")
            break
    
    safe_print(f"❌ Altyazı indirme başarısız ({lang})")
    return None

def parse_json3_subtitle(content):
    """Parse JSON3 format subtitles"""
    try:
        data = json.loads(content)
        texts = []
        
        for event in data.get('events', []):
            if 'segs' in event:
                for seg in event['segs']:
                    if 'utf8' in seg:
                        text = seg['utf8'].strip()
                        if text and not text.startswith('[') and not text.startswith('('):
                            texts.append(text)
        
        return ' '.join(texts)
    except Exception as e:
        safe_print(f"❌ JSON3 parsing error: {e}")
        return None

def parse_vtt_subtitle(content):
    """Parse VTT format subtitles"""
    try:
        lines = content.split('\n')
        texts = []
        
        for line in lines:
            line = line.strip()
            if (not line.startswith('WEBVTT') and 
                not line.startswith('NOTE') and 
                not '-->' in line and 
                not line.startswith('<') and
                line and 
                not line.isdigit() and
                not re.match(r'^\d{2}:\d{2}', line)):
                
                clean_line = re.sub(r'<[^>]+>', '', line)
                clean_line = re.sub(r'\[.*?\]', '', clean_line)
                clean_line = re.sub(r'\(.*?\)', '', clean_line)
                
                if clean_line.strip():
                    texts.append(clean_line.strip())
        
        return ' '.join(texts)
    except Exception as e:
        safe_print(f"❌ VTT parsing error: {e}")
        return None

# --- Alternative Transcript Methods ---
def alternatif_transkript_yontemleri(video_url, video_id):
    """Try alternative methods if yt-dlp fails"""
    safe_print("🔄 Alternatif yöntemler deneniyor...")
    
    # Method 1: Try simpler yt-dlp configuration
    try:
        safe_print("📝 Basitleştirilmiş yt-dlp konfigürasyonu...")
        ydl_opts = {
            'writesubtitles': False,
            'writeautomaticsub': False,
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            # Get description
            description = info.get('description', '')
            if description and len(description) > 200:
                safe_print(f"📄 Video açıklaması alındı ({len(description)} karakter)")
                return description[:2000]  # Limit size
                
            # Get title and other metadata
            title = info.get('title', '')
            uploader = info.get('uploader', '')
            
            if title:
                combined_text = f"Başlık: {title}\nKanal: {uploader}\nAçıklama: {description[:1000]}"
                if len(combined_text) > 100:
                    safe_print("📋 Video metadata'sı birleştirildi")
                    return combined_text
                    
    except Exception as e:
        safe_print(f"⚠️  Basit yt-dlp hatası: {str(e)[:50]}")
    
    # Method 2: Try to get video page content
    try:
        safe_print("🌐 Video sayfası içeriği alınıyor...")
        session = create_robust_session()
        
        # Add YouTube-specific headers
        headers = session.headers.copy()
        headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        })
        
        response = session.get(video_url, headers=headers, timeout=20)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to extract title and description from meta tags
            title_tag = soup.find('meta', property='og:title')
            desc_tag = soup.find('meta', property='og:description')
            
            title = title_tag['content'] if title_tag else ''
            description = desc_tag['content'] if desc_tag else ''
            
            # Look for JSON-LD structured data
            json_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and 'description' in data:
                        description = data['description']
                        break
                except:
                    continue
            
            if title or description:
                combined = f"Başlık: {title}\nAçıklama: {description}"
                if len(combined) > 50:
                    safe_print(f"📝 Sayfa içeriği alındı ({len(combined)} karakter)")
                    return combined
                    
    except Exception as e:
        safe_print(f"⚠️  Web scraping hatası: {str(e)[:50]}")
    
    # Method 3: Use YouTube API for detailed video info
    try:
        safe_print("🔍 YouTube API ile detaylı bilgi alınıyor...")
        video_request = youtube_service.videos().list(
            part="snippet,contentDetails",
            id=video_id
        )
        video_response = video_request.execute()
        
        if video_response['items']:
            video = video_response['items'][0]
            snippet = video['snippet']
            
            title = snippet.get('title', '')
            description = snippet.get('description', '')
            tags = snippet.get('tags', [])
            
            combined = f"""Başlık: {title}
Açıklama: {description[:1500]}
Etiketler: {', '.join(tags[:10])}"""
            
            if len(combined) > 100:
                safe_print(f"📊 API ile video bilgisi alındı ({len(combined)} karakter)")
                return combined
                
    except Exception as e:
        safe_print(f"⚠️  YouTube API hatası: {str(e)[:50]}")
    
    # Method 4: Return basic info if available
    try:
        basic_info = f"Video URL: {video_url}\nVideo ID: {video_id}"
        safe_print("📄 Temel video bilgisi döndürülüyor")
        return basic_info
    except:
        pass
    
    safe_print("❌ Tüm alternatif yöntemler başarısız")
    return None

# --- Enhanced Video Analysis ---
def gelismis_video_analizi_paralel(video_data, aranan_konu):
    """Enhanced video analysis with better prompts"""
    if not video_data:
        return "Video verisi bulunamadı."
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        analiz_metni = f"""
📺 Video: {video_data['baslik']}
👤 Kanal: {video_data['kanal']}
📊 Görüntülenme: {video_data['goruntulenme']}
📅 Tarih: {video_data.get('tarih', 'N/A')}

📝 Açıklama (İlk 800 karakter):
{video_data['aciklama'][:800]}

🏷️ Etiketler:
{', '.join(video_data.get('etiketler', [])[:15])}

💬 En İlgili Yorumlar:
{chr(10).join([f"• {yorum[:100]}" for yorum in video_data.get('yorumlar', [])[:8]])}
"""
        
        prompt = f"""Bu YouTube videosunu '{aranan_konu}' konusu açısından analiz et.

SKOR VER (1-10):
- Konu İlgisi: ?/10
- İçerik Kalitesi: ?/10  
- Öğretici Değer: ?/10

ÖZET ÇIKAR:
- Ana konular neler?
- Hedef kitle kimler?
- Pratik değer var mı?

ÖNERI:
Bu videoyu izlemeli miyim? Neden?

Analiz edilecek video:
---
{analiz_metni}
---

Kısa ve net yanıt ver (maksimum 300 kelime)."""
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Analiz hatası: {e}"

# --- Main Analysis Function ---
def akilli_video_analizi_sistemi(arama_terimi, aranan_konu, max_videos=10):
    """Smart video analysis system with multiple approaches"""
    videolar = youtube_video_ara(arama_terimi, max_videos)
    
    if not videolar:
        safe_print("❌ Video bulunamadı.")
        return
    
    basarili_analizler = 0
    analiz_sonuclari = []
    
    for i, video in enumerate(videolar):
        safe_print(f"\n{'='*80}")
        safe_print(f"📹 [{i+1}/{len(videolar)}] {video['baslik'][:60]}...")
        safe_print(f"🏢 {video['kanal']} | 🔗 {video['url']}")
        safe_print('='*80)
        
        # Strategy 1: Try transcript first
        transkript = ytdlp_transkript_al_gelismis(video['url'])
        
        analiz_sonucu = {
            'video': video,
            'transkript_var': False,
            'analiz': None
        }
        
        if transkript and len(transkript) > 100:
            # Transcript analysis
            safe_print("✅ Transkript bulundu, analiz ediliyor...")
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""Bu YouTube transkriptini '{aranan_konu}' konusu için analiz et:

Transkript (ilk 4000 karakter):
---
{transkript[:4000]}
---

Değerlendirme:
• Konu relevansı (1-10): ?
• İçerik kalitesi (1-10): ?  
• Pratik değer (1-10): ?
• Ana öğretiler: ?
• İzlemeye değer mi?: ?

Kısa ve öz yanıt (max 200 kelime)."""
            
            try:
                response = model.generate_content(prompt)
                safe_print("🎯 TRANSKRİPT ANALİZİ:")
                safe_print(response.text)
                analiz_sonucu['transkript_var'] = True
                analiz_sonucu['analiz'] = response.text
                basarili_analizler += 1
            except Exception as e:
                safe_print(f"❌ Transkript analiz hatası: {e}")
        
        if not analiz_sonucu['transkript_var']:
            # Strategy 2: Try alternative transcript methods
            safe_print("🔄 Alternatif transkript yöntemleri deneniyor...")
            alt_transkript = alternatif_transkript_yontemleri(video['url'], video['id'])
            
            if alt_transkript and len(alt_transkript) > 100:
                safe_print("✅ Alternatif yöntemle transkript bulundu!")
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                prompt = f"""Bu YouTube içeriğini '{aranan_konu}' konusu için analiz et:

İçerik:
---
{alt_transkript[:3000]}
---

Değerlendirme:
• Konu relevansı (1-10): ?
• İçerik kalitesi (1-10): ?  
• Pratik değer (1-10): ?
• Ana öğretiler: ?
• İzlemeye değer mi?: ?

Kısa ve öz yanıt (max 200 kelime)."""
                
                try:
                    response = model.generate_content(prompt)
                    safe_print("🎯 ALTERNATİF İÇERİK ANALİZİ:")
                    safe_print(response.text)
                    analiz_sonucu['transkript_var'] = True
                    analiz_sonucu['analiz'] = response.text
                    basarili_analizler += 1
                except Exception as e:
                    safe_print(f"❌ Alternatif analiz hatası: {e}")
        
        if not analiz_sonucu['transkript_var']:
            # Strategy 3: Metadata analysis
            safe_print("📊 Metadata analizi yapılıyor...")
            video_data = video_metadata_analizi_gelismis(video['id'])
            if video_data:
                analiz = gelismis_video_analizi_paralel(video_data, aranan_konu)
                safe_print("📋 METADATA ANALİZİ:")
                safe_print(analiz)
                analiz_sonucu['analiz'] = analiz
                basarili_analizler += 1
        
        analiz_sonuclari.append(analiz_sonucu)
        
        # Stop after 5 successful analyses
        if basarili_analizler >= 5:
            safe_print(f"\n✅ {basarili_analizler} video analiz edildi.")
            break
        
        # Rate limiting delay
        time.sleep(random.uniform(*RATE_LIMIT_DELAY))
    
    # Final summary
    safe_print(f"\n{'='*80}")
    safe_print("📊 ANALİZ ÖZET RAPORU")
    safe_print('='*80)
    safe_print(f"🔍 Arama terimi: {arama_terimi}")
    safe_print(f"🎯 Aranan konu: {aranan_konu}")
    safe_print(f"📈 Analiz edilen video sayısı: {basarili_analizler}")
    safe_print(f"📝 Transkript alınan video sayısı: {sum(1 for r in analiz_sonuclari if r['transkript_var'])}")

def video_metadata_analizi_gelismis(video_id):
    """Enhanced video metadata analysis"""
    safe_print(f"📊 Video metadata analizi: {video_id}")
    
    try:
        # Get video details
        video_request = youtube_service.videos().list(
            part="snippet,contentDetails,statistics",
            id=video_id
        )
        video_response = video_request.execute()
        
        if not video_response['items']:
            return None
        
        video = video_response['items'][0]
        snippet = video['snippet']
        stats = video['statistics']
        
        video_data = {
            'baslik': snippet['title'],
            'aciklama': snippet.get('description', ''),
            'etiketler': snippet.get('tags', []),
            'kanal': snippet['channelTitle'],
            'tarih': snippet['publishedAt'][:10],
            'sure': video['contentDetails']['duration'],
            'goruntulenme': stats.get('viewCount', '0'),
            'begeni': stats.get('likeCount', '0'),
            'yorum_sayisi': stats.get('commentCount', '0')
        }
        
        # Get comments with rate limiting
        try:
            time.sleep(random.uniform(0.5, 1.5))
            comments_request = youtube_service.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=15,
                order="relevance"
            )
            comments_response = comments_request.execute()
            
            yorumlar = []
            for item in comments_response.get('items', []):
                comment = item['snippet']['topLevelComment']['snippet']
                yorum_text = comment['textDisplay']
                if len(yorum_text) > 20:  # Filter short comments
                    yorumlar.append(yorum_text)
            
            video_data['yorumlar'] = yorumlar
            safe_print(f"✅ {len(yorumlar)} yorum alındı")
            
        except Exception as e:
            safe_print(f"⚠️  Yorum alma sınırlı: {str(e)[:50]}")
            video_data['yorumlar'] = []
        
        return video_data
        
    except Exception as e:
        safe_print(f"❌ Metadata analizi hatası: {e}")
        return None

# --- Main Execution ---
if __name__ == '__main__':
    safe_print("🚀 GELİŞMİŞ YOUTUBE ANALİZ SİSTEMİ")
    safe_print("="*50)
    safe_print("✨ Özellikler:")
    safe_print("• Akıllı rate limiting")
    safe_print("• Çoklu transkript yöntemi") 
    safe_print("• Gelişmiş hata yönetimi")
    safe_print("• Paralel analiz desteği")
    safe_print("• Detaylı raporlama")
    
    # Check dependencies
    try:
        import yt_dlp
        safe_print("\n✅ yt-dlp kütüphanesi hazır")
    except ImportError:
        print("❌ yt-dlp bulunamadı. Kurulum: pip install yt-dlp")
        exit()
    
    safe_print("\n" + "="*50)
    youtube_arama_terimi = input("🔍 YouTube'da ne aramak istersiniz? : ")
    aranacak_ozel_konu = input("🎯 Videolarda hangi konuyu arıyorsunuz? : ")
    
    try:
        max_video_sayisi = int(input("📊 Kaç video analiz edilsin? (varsayılan: 10): ") or "10")
    except ValueError:
        max_video_sayisi = 10
    
    safe_print(f"\n🚀 Analiz başlıyor...")
    akilli_video_analizi_sistemi(youtube_arama_terimi, aranacak_ozel_konu, max_video_sayisi)