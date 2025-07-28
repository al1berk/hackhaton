import os
import json
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool
from faster_whisper import WhisperModel
from araclar import YouTubeSearchTool, YouTubeTranscriptTool, JSONValidatorTool, JSONSaverTool, FileReaderTool

# .env dosyasını ve API anahtarlarını yükle
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

if not all([GOOGLE_API_KEY, SERPER_API_KEY, YOUTUBE_API_KEY]):
    raise ValueError("Lütfen .env dosyanızda GOOGLE_API_KEY, SERPER_API_KEY ve YOUTUBE_API_KEY'i tanımlayın.")

# LLM yapılandırması
try:
    gemini_llm = LLM(
        model="gemini/gemini-2.5-flash",
        api_key=GOOGLE_API_KEY,
        temperature=0.6
    )
    gemini_llm_pro = LLM(
        model="gemini/gemini-2.5-pro",
        api_key=GOOGLE_API_KEY,
        temperature=0.6
    )
    print("✅ Gemini LLM başarıyla yapılandırıldı.")
except Exception as e:
    raise ValueError(f"GOOGLE_API_KEY bulunamadı veya geçersiz. .env dosyanızı kontrol edin. Hata: {e}")

# Whisper modeli yükleme
model_boyutu = "base"
print(f"🚀 Whisper modeli '{model_boyutu}' yükleniyor...")
whisper_model = WhisperModel(model_boyutu, device="cpu", compute_type="int8")
print(f"✅ Whisper modeli '{model_boyutu}' başarıyla yüklendi.")

# Araçları tanımlama
web_search_tool = SerperDevTool()
youtube_tool = YouTubeSearchTool(api_key=YOUTUBE_API_KEY)
youtube_transcript_tool = YouTubeTranscriptTool(model=whisper_model)
json_validator_tool = JSONValidatorTool()
json_saver_tool = JSONSaverTool()
file_reader_tool = FileReaderTool()

# Kendi oluşturduğumuz araçları import ediyoruz
from araclar import YouTubeSearchTool, YouTubeTranscriptTool, JSONValidatorTool, JSONSaverTool, FileReaderTool

# Ajanları tanımlama
web_researcher = Agent(
    role='Kıdemli Araştırma Stratejisti',
    goal='Verilen konuda webdeki metin tabanlı kaynakları kullanarak kapsamlı bir ilk analiz yapmak.',
    backstory="Bilginin yeterli olup olmadığını sezme konusunda usta bir araştırmacı.",
    verbose=True,
    allow_delegation=True,
    tools=[web_search_tool],
    llm=gemini_llm
)

youtube_analyst = Agent(
    role='YouTube İçerik Analisti',
    goal='Belirli bir konu hakkında en alakalı YouTube videolarını bulmak, transkriptlerini çıkarmak ve bu içerikten önemli bilgileri sentezlemek.',
    backstory="Video içeriklerindeki değerli bilgileri ve ana temaları ortaya çıkarma konusunda uzmanlaşmış bir analist.",
    verbose=True,
    allow_delegation=False,
    tools=[youtube_tool, youtube_transcript_tool],
    llm=gemini_llm
)

report_processor = Agent(
    role='Rapor İşleme Uzmanı',
    goal='Tamamlanmış raporları alt başlıklara böler ve yapılandırır.',
    backstory="Karmaşık raporları anlaşılır bölümlere ayırma konusunda uzman bir editör.",
    verbose=True,
    allow_delegation=False,
    tools=[],
    llm=gemini_llm_pro
)

json_converter = Agent(
    role='JSON Dönüştürme Uzmanı',
    goal='Yapılandırılmış içeriği geçerli JSON formatına dönüştürür.',
    backstory="Veri yapılarını JSON formatına dönüştürme konusunda uzman bir geliştirici.",
    verbose=True,
    allow_delegation=False,
    tools=[json_validator_tool],
    llm=gemini_llm
)

detail_researcher = Agent(
    role='Detay Araştırma Uzmanı',
    goal='Belirli alt başlıkları derinlemesine araştırır ve detaylandırır.',
    backstory="Spesifik konularda derinlemesine araştırma yapma konusunda uzman bir araştırmacı.",
    verbose=True,
    allow_delegation=False,
    tools=[web_search_tool],
    llm=gemini_llm_pro
)

json_manager = Agent(
    role='JSON Dosya Yöneticisi',
    goal='JSON verilerini dosyalara kaydetmek ve yönetmek.',
    backstory="Veri yönetimi ve dosya işlemleri konusunda uzman bir sistem yöneticisi.",
    verbose=True,
    allow_delegation=False,
    tools=[json_saver_tool, file_reader_tool],
    llm=gemini_llm
)

def run_initial_research():
    """İlk araştırma aşamasını çalıştırır"""
    arastirma_konusu = input("Lütfen araştırmak istediğiniz konuyu girin: ")
    
    master_task = Task(
        description=(
            f"'{arastirma_konusu}' konusu hakkında detaylı ve anlaşılır bir rapor hazırla.\n"
            "1. İlk olarak, web'de kapsamlı bir araştırma yap ve konunun temelini anlatan bir taslak oluştur.\n"
            "2. Değerlendirme yap: Eğer bulduğun yazılı kaynaklar konuyu tam olarak açıklamıyorsa, YouTube Analistinden yardım iste. "
            "Ona konuyu vererek en alakalı videoları bulmasını ve en iyi videonun transkriptini çıkarıp sana özetlemesini söyle.\n"
            "3. Son olarak, hem kendi web araştırmanı hem de YouTube'dan gelen bilgileri birleştirerek nihai ve kapsamlı raporunu oluştur."
        ),
        expected_output="Konu hakkında tüm önemli noktaları içeren, iyi yapılandırılmış tam bir rapor.",
        agent=web_researcher
    )
    
    crew = Crew(
        agents=[web_researcher, youtube_analyst],
        tasks=[master_task],
        process=Process.hierarchical,
        manager_llm=gemini_llm
    )
    
    print("\n" + "="*50)
    print("🚀 Akıllı Araştırma Ekibi işe başlıyor...")
    print("="*50 + "\n")
    
    result = crew.kickoff()
    
    print("\n" + "="*50)
    print("✨ İLK ARAŞTIRMA TAMAMLANDI ✨")
    print("="*50 + "\n")
    
    return result, arastirma_konusu

def process_report_to_json_with_retry(report_content, topic, max_retries=3):
    """Raporu JSON'a çevirir, hata durumunda yeniden deneme yapar"""
    
    for attempt in range(max_retries):
        print(f"🔄 JSON dönüştürme denemesi {attempt + 1}/{max_retries}")
        
        # Raporu alt başlıklara bölme görevi
        structure_task = Task(
            description=(
                f"Aşağıdaki raporu analiz et ve mantıklı alt başlıklara böl:\n\n"
                f"RAPOR İÇERİĞİ:\n{report_content}\n\n"
                "GÖREV:\n"
                "1. Raporun içeriğini incele\n"
                "2. Ana konuları belirle\n"
                "3. Her ana konu için uygun bir alt başlık oluştur\n"
                "4. Her alt başlık için rapordaki ilgili bilgileri özetle\n"
                "5. Sonucu şu formatta yaz:\n"
                "ALT BAŞLIK 1: [Başlık adı]\n"
                "AÇIKLAMA: [Rapordaki ilgili bilgilerin özeti]\n\n"
                "ALT BAŞLIK 2: [Başlık adı]\n"
                "AÇIKLAMA: [Rapordaki ilgili bilgilerin özeti]\n\n"
                "... ve böyle devam et"
            ),
            expected_output="Alt başlıklara bölünmüş, yapılandırılmış rapor içeriği",
            agent=report_processor
        )
        
        # JSON'a dönüştürme görevi (retry bilgisi eklendi)
        retry_instruction = ""
        if attempt > 0:
            retry_instruction = f"\n⚠️ BU {attempt + 1}. DENEME! Önceki denemede JSON formatı hatalıydı. DAHA DİKKATLİ OL!\n"
        
        json_task = Task(
            description=(
                f"{retry_instruction}"
                "Önceki görevden gelen yapılandırılmış içeriği JSON formatına dönüştür.\n"
                "HEDEF FORMAT:\n"
                "[\n"
                "  {\n"
                '    "alt_baslik": "Başlık 1",\n'
                '    "aciklama": "Açıklama metni"\n'
                "  },\n"
                "  {\n"
                '    "alt_baslik": "Başlık 2",\n'
                '    "aciklama": "Açıklama metni"\n'
                "  }\n"
                "]\n\n"
                "KRİTİK KURALLAR:\n"
                "- SADECE SADE JSON ÇıKTıSı VER, hiçbir ek açıklama veya ``` bloğu KULLANMA\n"
                "- Her eleman 'alt_baslik' ve 'aciklama' anahtarlarına sahip olmalı\n"
                "- JSON formatını kontrol etmek için JSONValidatorTool'u MUTLAKA kullan\n"
                "- Eğer JSON geçersizse, HEMEN düzelt ve tekrar kontrol et\n"
                "- Çıktın DOĞRUDAN JSON array olmalı, başka hiçbir şey olmamalı\n"
                "- Türkçe karakterleri düzgün kodla\n"
                "- Tırnak işaretlerini kaçırma (escape) yap\n"
                f"- Bu {attempt + 1}. deneme, daha dikkatli ol!"
            ),
            expected_output="Geçerli JSON formatında alt başlıklar ve açıklamalar (sadece JSON array)",
            agent=json_converter
        )
        
        crew = Crew(
            agents=[report_processor, json_converter],
            tasks=[structure_task, json_task],
            process=Process.sequential
        )
        
        print(f"📝 JSON dönüştürme denemesi {attempt + 1} başlıyor...")
        result = crew.kickoff()
        
        # JSON doğrulaması yap
        try:
            cleaned_json = str(result).strip()
            if cleaned_json.startswith('```json'):
                cleaned_json = cleaned_json[7:]
            if cleaned_json.endswith('```'):
                cleaned_json = cleaned_json[:-3]
            cleaned_json = cleaned_json.strip()
            
            # JSON parse testi
            parsed = json.loads(cleaned_json)
            
            # Yapı doğrulaması
            if isinstance(parsed, list) and len(parsed) > 0:
                for item in parsed:
                    if not isinstance(item, dict):
                        raise ValueError("Liste elemanları dict olmalı")
                    if "alt_baslik" not in item or "aciklama" not in item:
                        raise ValueError("Eksik anahtarlar")
                
                print(f"✅ JSON başarıyla oluşturuldu (deneme {attempt + 1})")
                return result
            else:
                raise ValueError("JSON liste formatında değil veya boş")
                
        except Exception as e:
            print(f"❌ JSON hatası (deneme {attempt + 1}): {str(e)}")
            if attempt == max_retries - 1:
                print(f"💀 {max_retries} denemede JSON oluşturulamadı!")
                return None
            else:
                print(f"🔄 Yeniden deneniyor... ({attempt + 2}/{max_retries})")
                continue
    
    return None

def detail_each_section(json_content, topic):
    """Her alt başlığı detaylandırır"""
    try:
        # JSON formatını temizle (```json blokları varsa)
        cleaned_json = json_content.strip()
        if cleaned_json.startswith('```json'):
            cleaned_json = cleaned_json[7:]  # ```json kısmını çıkar
        if cleaned_json.endswith('```'):
            cleaned_json = cleaned_json[:-3]  # ``` kısmını çıkar
        cleaned_json = cleaned_json.strip()
        
        # Değişkenler için debug çıktısı
        print(f"🔍 Debug: json_content ilk 200 karakter:")
        print(f"'{str(json_content)[:200]}...'")
        print(f"🔍 Debug: cleaned_json ilk 200 karakter:")
        print(f"'{cleaned_json[:200]}...'")
        
        sections = json.loads(cleaned_json)
        detailed_sections = []
        
        print(f"\n🔍 {len(sections)} alt başlık detaylandırılacak...\n")
        
        for i, section in enumerate(sections, 1):
            alt_baslik = section['alt_baslik']
            mevcut_aciklama = section['aciklama']
            
            print(f"📖 Alt başlık {i}/{len(sections)} işleniyor: {alt_baslik}")
            
            # Her alt başlık için detaylı araştırma görevi
            detail_task = Task(
                description=(
                    f"'{alt_baslik}' konusunu '{topic}' ana konusu bağlamında detaylandır.\n\n"
                    f"MEVCUT AÇIKLAMA:\n{mevcut_aciklama}\n\n"
                    "GÖREV:\n"
                    "1. Bu alt başlık hakkında web'de ek araştırma yap\n"
                    "2. Mevcut açıklamayı genişlet ve derinleştir\n"
                    "3. Önemli detayları, örnekleri ve açıklamaları ekle\n"
                    "4. Güncel bilgileri araştır ve dahil et\n"
                    "5. Kapsamlı ve detaylı bir açıklama oluştur\n\n"
                    "ÇIKTI: Sadece detaylandırılmış açıklama metnini ver, başka hiçbir şey ekleme."
                ),
                expected_output=f"'{alt_baslik}' için kapsamlı ve detaylı açıklama",
                agent=detail_researcher
            )
            
            crew = Crew(
                agents=[detail_researcher],
                tasks=[detail_task],
                process=Process.sequential
            )
            
            detailed_result = crew.kickoff()
            
            detailed_sections.append({
                "alt_baslik": alt_baslik,
                "aciklama": str(detailed_result)
            })
            
            print(f"✅ '{alt_baslik}' detaylandırıldı\n")
        
        return detailed_sections
    
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse hatası: {e}")
        print(f"🔍 İlk 500 karakter: '{str(json_content)[:500]}'")
        return None
    except Exception as e:
        print(f"❌ Genel hata: {e}")
        return None

def save_final_json(detailed_sections, topic):
    """Son JSON dosyasını kaydeder"""
    filename = f"{topic.replace(' ', '_')}_detayli_rapor.json"
    
    save_task = Task(
        description=(
            f"Aşağıdaki detaylandırılmış içeriği '{filename}' dosyasına kaydet:\n\n"
            f"{json.dumps(detailed_sections, ensure_ascii=False, indent=2)}\n\n"
            "JSONSaverTool'u kullanarak dosyaya kaydet. "
            "Girdi formatı: 'content|filename' şeklinde ver."
        ),
        expected_output="Dosya kaydetme işleminin sonucu",
        agent=json_manager
    )
    
    crew = Crew(
        agents=[json_manager],
        tasks=[save_task],
        process=Process.sequential
    )
    
    result = crew.kickoff()
    return result, filename

def main():
    """Ana işlem akışı - geliştirilmiş retry ile"""
    try:
        # 1. İlk araştırma
        print("🚀 AŞAMA 1: İlk Araştırma")
        report, topic = run_initial_research()
        
        # 2. Raporu işle ve JSON'a çevir (retry ile)
        print("\n🚀 AŞAMA 2: Rapor İşleme ve JSON Dönüştürme (Retry Mekanizması)")
        json_result = process_report_to_json_with_retry(str(report), topic, max_retries=3)
        
        if json_result is None:
            print("❌ JSON dönüştürme başarısız oldu. İşlem durduruldu.")
            return
        
        # 3. Her alt başlığı detaylandır
        print("\n🚀 AŞAMA 3: Alt Başlıkları Detaylandırma")
        detailed_sections = detail_each_section(str(json_result), topic)
        
        if detailed_sections:
            # 4. Final JSON'ı kaydet
            print("\n🚀 AŞAMA 4: Final JSON Kaydetme")
            save_result, filename = save_final_json(detailed_sections, topic)
            
            print("\n" + "="*60)
            print("🎉 TÜM İŞLEMLER BAŞARIYLA TAMAMLANDI! 🎉")
            print("="*60)
            print(f"📄 Detaylı rapor: {filename}")
            print(f"📊 Toplam alt başlık: {len(detailed_sections)}")
            print("="*60 + "\n")
            
            # Özet göster
            print("📋 RAPOR ÖZETİ:")
            for i, section in enumerate(detailed_sections, 1):
                print(f"{i}. {section['alt_baslik']}")
            print()
            
        else:
            print("❌ Alt başlık detaylandırma işlemi başarısız oldu.")
            
    except Exception as e:
        print(f"❌ Genel hata: {e}")

if __name__ == "__main__":
    main()