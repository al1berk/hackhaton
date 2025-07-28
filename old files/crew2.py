import os
import sys
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool, YoutubeChannelSearchTool, YoutubeVideoSearchTool
import requests
import json
from typing import Optional, List, Dict
from urllib.parse import quote
import re

# .env dosyasını yükle
load_dotenv()

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    TRANSCRIPT_AVAILABLE = True
except ImportError:
    TRANSCRIPT_AVAILABLE = False
    print("⚠️  youtube-transcript-api paketi yüklü değil. Transcript özelliği sınırlı olacak.")
    print("   Yüklemek için: pip install youtube-transcript-api")

class YouTubeTranscriptTool:
    """YouTube video transkriptlerini almak için gelişmiş araç"""
    
    def __init__(self):
        self.name = "youtube_transcript_tool"
        self.description = "YouTube videolarının transkriptlerini alır ve analiz eder"
    
    def get_transcript(self, video_url: str) -> str:
        """YouTube video transkriptini al"""
        try:
            video_id = self.extract_video_id(video_url)
            if not video_id:
                return "❌ Video ID alınamadı"
            
            if not TRANSCRIPT_AVAILABLE:
                return f"📝 Video ID: {video_id} - Transcript paketi yüklü değil"
            
            # Transkripti al
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['tr', 'en'])
            
            # Transkripti birleştir
            full_transcript = " ".join([item['text'] for item in transcript_list])
            
            # Transkripti temizle ve özetle
            summary = self.summarize_transcript(full_transcript)
            
            return f"📝 Video Transkripti Özeti (ID: {video_id}):\n{summary}"
            
        except Exception as e:
            return f"❌ Transcript alınırken hata: {str(e)}"
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """YouTube URL'den video ID'sini çıkar"""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)',
            r'youtube\.com/watch\?.*v=([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def summarize_transcript(self, transcript: str) -> str:
        """Transkripti özetle"""
        # Basit özetleme - ilk 500 kelime + anahtar noktalar
        words = transcript.split()
        if len(words) > 500:
            summary = " ".join(words[:500]) + "..."
        else:
            summary = transcript
        
        return summary

class AdvancedWebSearchTool:
    """Gelişmiş web arama aracı"""
    
    def __init__(self):
        self.serper_tool = SerperDevTool()
    
    def search_multiple_sources(self, topic: str) -> List[Dict]:
        """Farklı kaynaklarda arama yap"""
        searches = [
            f"{topic} nedir nasıl çalışır",
            f"{topic} tutorial örnekler",
            f"{topic} github açık kaynak",
            f"{topic} 2024 2025 güncel",
            f"{topic} documentation dokümantasyon"
        ]
        
        results = []
        for search_query in searches:
            try:
                result = self.serper_tool._run(search_query)
                results.append({
                    "query": search_query,
                    "result": result
                })
            except Exception as e:
                results.append({
                    "query": search_query,
                    "result": f"Arama hatası: {str(e)}"
                })
        
        return results

class DynamicResearchSystem:
    def __init__(self):
        self.setup_llm()
        self.setup_tools()
        
    def setup_llm(self):
        """LLM konfigürasyonu"""
        # API keylerini kontrol et
        google_api_key = os.getenv("GOOGLE_API_KEY")
        serper_api_key = os.getenv("SERPER_API_KEY")
        
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY .env dosyasında bulunamadı. Lütfen .env dosyanızı kontrol edin.")
        
        if not serper_api_key:
            raise ValueError("SERPER_API_KEY .env dosyasında bulunamadı. Lütfen .env dosyanızı kontrol edin.")
        
        # CrewAI için LLM konfigürasyonu
        try:
            # Gemini için doğru konfigürasyon
            self.gemini_llm = LLM(
                model="gemini/gemini-1.5-flash",
                api_key=google_api_key,
                temperature=0.7
            )
            
            # CrewAI'ın global LLM ayarını da yapalım
            os.environ["OPENAI_API_KEY"] = "dummy"  # CrewAI bazen bunu kontrol ediyor
            
        except Exception as e:
            raise ValueError(f"LLM konfigürasyonu başarısız. Hata: {e}")
    
    def setup_tools(self):
        """Araçları hazırla"""
        self.search_tool = SerperDevTool()
        self.youtube_search_tool = YoutubeVideoSearchTool()
        self.transcript_tool = YouTubeTranscriptTool()
        self.advanced_search_tool = AdvancedWebSearchTool()
    
    def get_user_topic(self) -> str:
        """Kullanıcıdan araştırma konusunu al"""
        print("🔍 Hangi konuyu araştırmak istiyorsunuz?")
        print("Örnek: A2A, MCP, CrewAI, LangGraph, makine öğrenmesi, blockchain vb.")
        print("-" * 50)
        
        topic = input("Araştırma konusu: ").strip()
        
        if not topic:
            print("❌ Geçerli bir konu girmelisiniz!")
            return self.get_user_topic()
        
        return topic
    
    def create_dynamic_agents(self, topic: str):
        """Konuya göre dinamik ajanlar oluştur"""
        
        # Web Araştırma Uzmanı
        self.web_researcher = Agent(
            role=f'{topic} Web Araştırma Uzmanı',
            goal=f'{topic} konusunda kapsamlı web araştırması yaparak güncel bilgileri toplamak',
            backstory=(
                f"{topic} alanında uzmanlaşmış araştırmacı. "
                "Web üzerinden en güncel ve güvenilir kaynakları bulma konusunda uzman. "
                "Karmaşık teknik konuları detaylı şekilde araştırır ve analiz eder."
            ),
            verbose=True,
            allow_delegation=False,
            tools=[self.search_tool],
            llm=self.gemini_llm
        )
        
        # YouTube Araştırma Uzmanı
        self.youtube_researcher = Agent(
            role=f'{topic} YouTube İçerik Uzmanı',
            goal=f'{topic} konusunda YouTube videolarını bularak içeriklerini analiz etmek',
            backstory=(
                f"{topic} konusunda video içerik analizi uzmanı. "
                "YouTube platformunda en kaliteli ve güncel içerikleri bulur. "
                "Video transkriptlerini analiz ederek önemli bilgileri çıkarır."
            ),
            verbose=True,
            allow_delegation=False,
            tools=[self.youtube_search_tool],
            llm=self.gemini_llm
        )
        
        # Sentez Uzmanı
        self.synthesis_expert = Agent(
            role=f'{topic} Bilgi Sentezi Uzmanı',
            goal=f'{topic} hakkındaki tüm bilgileri sentezleyerek kapsamlı rapor hazırlamak',
            backstory=(
                f"{topic} alanında bilgi sentezi uzmanı. "
                "Farklı kaynaklardan gelen bilgileri birleştirerek tutarlı ve kapsamlı raporlar hazırlar. "
                "Teknik bilgileri anlaşılır şekilde sunar ve pratik öneriler geliştirir."
            ),
            verbose=True,
            allow_delegation=False,
            tools=[],
            llm=self.gemini_llm
        )
    
    def create_dynamic_tasks(self, topic: str):
        """Konuya göre dinamik görevler oluştur"""
        
        # Web Araştırma Görevi
        self.web_research_task = Task(
            description=(
                f"{topic} konusunda kapsamlı web araştırması yap. "
                f"Aşağıdaki noktalara odaklan:\n"
                f"1. {topic} nedir ve nasıl çalışır?\n"
                f"2. {topic}'nin güncel durumu ve son gelişmeleri\n"
                f"3. {topic}'nin avantajları ve dezavantajları\n"
                f"4. {topic}'nin kullanım alanları ve örnekleri\n"
                f"5. {topic} ile ilgili araçlar, kütüphaneler, çerçeveler\n"
                f"6. {topic}'nin geleceği ve trendleri\n"
                f"7. {topic} öğrenmek isteyenler için kaynaklar\n\n"
                f"Güncel ve güvenilir kaynaklardan bilgi topla. "
                f"Resmi dokümantasyonları, açık kaynak projeleri, uzman görüşlerini araştır."
            ),
            expected_output=(
                f"{topic} hakkında detaylı web araştırması raporu. "
                f"Her başlık altında 2-3 paragraf açıklama, "
                f"önemli kaynaklar ve linkler dahil edilmeli."
            ),
            agent=self.web_researcher
        )
        
        # YouTube Araştırma Görevi
        self.youtube_research_task = Task(
            description=(
                f"{topic} konusunda YouTube'da kapsamlı video araştırması yap. "
                f"Aşağıdaki adımları takip et:\n\n"
                f"1. {topic} ile ilgili en popüler ve güncel videoları bul\n"
                f"2. Tutorial ve eğitim videolarını tespit et\n"
                f"3. Uzman konuşmaları ve konferans videolarını ara\n"
                f"4. Pratik örnek ve demo videolarını listele\n"
                f"5. Her video için aşağıdaki bilgileri topla:\n"
                f"   - Video başlığı ve açıklaması\n"
                f"   - Kanal adı ve güvenilirliği\n"
                f"   - Video süresi ve görüntülenme sayısı\n"
                f"   - Video URL'si\n"
                f"   - Video içeriğinin kısa özeti\n\n"
                f"6. Mümkünse video transkriptlerini inceleyip önemli noktaları çıkar\n"
                f"7. Videolardan öğrenilebilecek temel konuları listele\n\n"
                f"En az 10-15 kaliteli video bul ve analiz et. "
                f"Başlangıç seviyesinden ileri seviyeye kadar farklı zorluk derecelerini kapsasın."
            ),
            expected_output=(
                f"{topic} konusunda bulunan YouTube videolarının kapsamlı analizi. "
                f"Kategorilere ayrılmış video listesi:\n"
                f"- Başlangıç Seviyesi Videolar\n"
                f"- Orta Seviye Videolar\n"
                f"- İleri Seviye Videolar\n"
                f"- Konferans ve Sunum Videoları\n"
                f"Her video için detaylı bilgiler ve öğrenme değeri açıklaması dahil."
            ),
            agent=self.youtube_researcher
        )
        
        # Sentez Görevi
        self.synthesis_task = Task(
            description=(
                f"Web araştırması ve YouTube araştırması sonuçlarını birleştirerek "
                f"{topic} hakkında kapsamlı bir öğrenme rehberi hazırla. "
                f"Rehber şu bölümleri içermeli:\n\n"
                f"1. {topic} NEDİR?\n"
                f"2. TEMEL KAVRAMLAR VE PRENSİPLER\n"
                f"3. GÜNCEL DURUM VE GELİŞMELER\n"
                f"4. KULLANIM ALANLARI VE ÖRNEKLER\n"
                f"5. ARAÇLAR VE TEKNOLOJİLER\n"
                f"6. ÖĞRENME KAYNAKLARI\n"
                f"   - Web Kaynakları\n"
                f"   - Önerilen YouTube Videoları\n"
                f"   - Dokümantasyon ve Kılavuzlar\n"
                f"7. UYGULAMA ÖNERİLERİ\n"
                f"8. GELECEK TRENDLER VE TAVSİYELER\n\n"
                f"Rehber yeni başlayanlar için anlaşılır olmalı ama ileri seviye bilgiler de içermeli."
            ),
            expected_output=(
                f"{topic} Kapsamlı Öğrenme Rehberi - "
                f"Başlıklı, paragraflar halinde düzenlenmiş, "
                f"kaynak linklerini ve video önerilerini içeren detaylı rehber."
            ),
            agent=self.synthesis_expert,
            context=[self.web_research_task, self.youtube_research_task]
        )
    
    def run_research(self, topic: str):
        """Araştırmayı başlat"""
        print(f"🚀 '{topic}' konusunda araştırma başlatılıyor...")
        print("📊 Aşamalar: Web Araştırması → YouTube Araştırması → Bilgi Sentezi")
        print("-" * 60)
        
        # Dinamik ajanlar ve görevler oluştur
        self.create_dynamic_agents(topic)
        self.create_dynamic_tasks(topic)
        
        # Crew oluştur
        crew = Crew(
            agents=[self.web_researcher, self.youtube_researcher, self.synthesis_expert],
            tasks=[self.web_research_task, self.youtube_research_task, self.synthesis_task],
            process=Process.sequential,
            verbose=True
        )
        
        try:
            # Araştırmayı başlat
            result = crew.kickoff()
            
            # Sonucu göster
            self.display_results(result, topic)
            
        except Exception as e:
            print(f"❌ Araştırma sırasında hata oluştu: {e}")
            import traceback
            print(f"Detaylı hata: {traceback.format_exc()}")
    
    def display_results(self, result, topic: str):
        """Sonuçları göster"""
        print("\n" + "="*80)
        print(f"📋 {topic.upper()} ARAŞTIRMA SONUÇLARI")
        print("="*80 + "\n")
        
        # Result objesinin içeriğini kontrol et
        if hasattr(result, 'raw'):
            print(result.raw)
        elif hasattr(result, 'result'):
            print(result.result)
        else:
            print(str(result))
        
        print("\n" + "="*80)
        print("✅ Araştırma tamamlandı!")
        print("💡 İpucu: Sonuçları bir dosyaya kaydetmek için çıktıyı yönlendirebilirsiniz:")
        print(f"   python research.py > {topic.lower().replace(' ', '_')}_research.txt")

def main():
    """Ana program"""
    print("🧠 Dinamik AI Araştırma Sistemi")
    print("=" * 50)
    
    try:
        # Sistem başlat
        research_system = DynamicResearchSystem()
        
        # Kullanıcıdan konu al
        topic = research_system.get_user_topic()
        
        # Araştırmayı başlat
        research_system.run_research(topic)
        
    except KeyboardInterrupt:
        print("\n\n❌ Kullanıcı tarafından durduruldu.")
    except Exception as e:
        print(f"❌ Sistem hatası: {e}")
        print("\n--- 🔧 Muhtemel Çözümler ---")
        print("1. .env dosyasında GOOGLE_API_KEY ve SERPER_API_KEY'in doğru tanımlandığından emin olun")
        print("2. pip install --upgrade crewai crewai-tools python-dotenv youtube-transcript-api komutunu çalıştırın")
        print("3. API key'lerinizin geçerli ve aktif olduğunu kontrol edin")
        print("4. İnternet bağlantınızı kontrol edin")

if __name__ == "__main__":
    main()