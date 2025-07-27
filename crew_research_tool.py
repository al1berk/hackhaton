import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import aiofiles
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool
from faster_whisper import WhisperModel
from araclar import YouTubeSearchTool, YouTubeTranscriptTool, JSONValidatorTool, JSONSaverTool, FileReaderTool
from config import Config
import threading
from concurrent.futures import ThreadPoolExecutor

# .env dosyasını yükle
load_dotenv()

@dataclass
class ResearchStep:
    step_id: str
    title: str
    status: str  # "pending", "running", "completed", "failed"
    result: Optional[str] = None
    timestamp: Optional[str] = None
    progress: int = 0  # 0-100
    agent: Optional[str] = None

class AsyncCrewAIResearchTool:
    def __init__(self, websocket_callback=None):
        self.websocket_callback = websocket_callback
        self.research_steps = []
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.setup_llm_and_tools()
        self.setup_agents()
        
    def setup_llm_and_tools(self):
        """LLM ve araçları ayarla"""
        try:
            self.gemini_llm = LLM(
                model="gemini/gemini-2.5-flash",
                api_key=Config.GOOGLE_API_KEY,
                temperature=0.6
            )
            self.gemini_llm_pro = LLM(
                model="gemini/gemini-2.5-pro", 
                api_key=Config.GOOGLE_API_KEY,
                temperature=0.6
            )
            
            # Whisper model
            self.whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
            
            # Araçları tanımla
            self.web_search_tool = SerperDevTool()
            self.youtube_tool = YouTubeSearchTool(api_key=Config.YOUTUBE_API_KEY)
            self.youtube_transcript_tool = YouTubeTranscriptTool(model=self.whisper_model)
            self.json_validator_tool = JSONValidatorTool()
            self.json_saver_tool = JSONSaverTool()
            self.file_reader_tool = FileReaderTool()
            
            print("✅ CrewAI araçları başarıyla yapılandırıldı")
            
        except Exception as e:
            raise ValueError(f"CrewAI setup hatası: {e}")
    
    def setup_agents(self):
        """CrewAI ajanlarını oluştur"""
        self.web_researcher = Agent(
            role='Kıdemli Web Araştırma Uzmanı',
            goal='Verilen konuda kapsamlı web araştırması yaparak detaylı bilgi toplamak',
            backstory="Web'deki en güncel ve güvenilir kaynakları bulma konusunda uzman bir araştırmacı.",
            verbose=True,
            allow_delegation=True,
            tools=[self.web_search_tool],
            llm=self.gemini_llm
        )
        
        self.youtube_analyst = Agent(
            role='YouTube İçerik Analisti',
            goal='Konuyla ilgili en iyi YouTube videolarını bulup analiz etmek',
            backstory="Video içeriklerindeki değerli bilgileri çıkarma konusunda uzman analist.",
            verbose=True,
            allow_delegation=False,
            tools=[self.youtube_tool, self.youtube_transcript_tool],
            llm=self.gemini_llm
        )
        
        self.report_processor = Agent(
            role='Rapor Yapılandırma Uzmanı',
            goal='Araştırma sonuçlarını yapılandırılmış alt başlıklara böler',
            backstory="Karmaşık bilgileri organize etme ve yapılandırma konusunda uzman.",
            verbose=True,
            allow_delegation=False,
            tools=[],
            llm=self.gemini_llm_pro
        )
        
        self.json_converter = Agent(
            role='JSON Dönüştürme Uzmanı',
            goal='Yapılandırılmış içeriği hatasız JSON formatına dönüştürür',
            backstory="Veri formatlaması ve JSON yapıları konusunda uzman geliştirici.",
            verbose=True,
            allow_delegation=False,
            tools=[self.json_validator_tool],
            llm=self.gemini_llm
        )
        
        self.detail_researcher = Agent(
            role='Detay Araştırma Uzmanı',
            goal='Belirlenen alt başlıkları derinlemesine araştırır',
            backstory="Spesifik konularda derinlemesine araştırma yapma uzmanı.",
            verbose=True,
            allow_delegation=False,
            tools=[self.web_search_tool],
            llm=self.gemini_llm_pro
        )
        
        self.json_manager = Agent(
            role='Veri Yöneticisi',
            goal='JSON verilerini güvenli şekilde dosyalara kaydeder',
            backstory="Veri yönetimi ve dosya işlemleri uzmanı.",
            verbose=True,
            allow_delegation=False,
            tools=[self.json_saver_tool, self.file_reader_tool],
            llm=self.gemini_llm
        )
    
    async def send_progress_update(self, message: str, step_data: Dict = None, agent_name: str = None):
        """A2A protokolü ile ilerleme güncellemesi gönder"""
        if self.websocket_callback:
            update_data = {
                "type": "crew_progress",
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "agent": agent_name or "CrewAI",
                "step_data": step_data or {}
            }
            await self.websocket_callback(json.dumps(update_data))
    
    async def send_agent_message(self, agent_name: str, message: str, data: Dict = None):
        """Agent'tan A2A mesajı gönder"""
        if self.websocket_callback:
            a2a_message = {
                "type": "a2a_message",
                "agent": agent_name,
                "message": message,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.websocket_callback(json.dumps(a2a_message))
    
    async def send_main_step_update(self, step_id: str, status: str, message: str = ""):
        """Ana adım güncellemesi gönder"""
        if self.websocket_callback:
            update_data = {
                "type": "workflow_message",
                "agent": f"Step-{step_id}",
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "step_data": {
                    "main_step": step_id,
                    "status": status
                }
            }
            await self.websocket_callback(json.dumps(update_data))
    
    async def send_subtopic_update(self, subtopic_title: str, status: str, content: str = ""):
        """Alt konu güncellemesi gönder"""
        if self.websocket_callback:
            update_data = {
                "type": "subtopic_progress",
                "subtopic": subtopic_title,
                "status": status,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.websocket_callback(json.dumps(update_data))
    
    async def send_subtopics_found(self, subtopics: List[Dict]):
        """Bulunan alt konuları gönder"""
        if self.websocket_callback:
            update_data = {
                "type": "subtopics_found",
                "subtopics": subtopics,
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.websocket_callback(json.dumps(update_data))
    
    def run_crew_sync(self, crew):
        """CrewAI'ı senkron olarak çalıştır"""
        try:
            result = crew.kickoff()
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def run_crew_async(self, crew):
        """CrewAI'ı asenkron olarak çalıştır"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self.executor, self.run_crew_sync, crew)
        return result
    
    async def comprehensive_research(self, topic: str) -> Dict[str, Any]:
        """Kapsamlı araştırma workflow'u - Tam asenkron"""
        research_data = {
            "topic": topic,
            "timestamp": datetime.utcnow().isoformat(),
            "user": "al1berk",
            "subtopics": [],
            "detailed_research": {},
            "final_report": "",
            "saved_files": [],
            "workflow_steps": []
        }
        
        try:
            # Başlangıç mesajı
            await self.send_progress_update("🚀 CrewAI Multi-Agent sistemi başlatılıyor...")
            await asyncio.sleep(0.5)  # UI'ın güncellenmesi için kısa bekleme
            
            # Step 1: Web araştırması başlat
            await self.send_main_step_update("step1", "running", "🔍 Web araştırması başlatılıyor...")
            await self.send_agent_message("WebResearcher", "🚀 Web araştırması başlatılıyor...", {"topic": topic})
            
            initial_task = Task(
                description=(
                    f"'{topic}' konusu hakkında kapsamlı web araştırması yap.\n"
                    "1. Konunun temel bilgilerini araştır\n"
                    "2. Ana alt konuları belirle\n"
                    "3. Güncel gelişmeleri araştır\n"
                    "4. Kapsamlı bir ön rapor oluştur"
                ),
                expected_output="Konuyla ilgili kapsamlı ön araştırma raporu",
                agent=self.web_researcher
            )
            
            crew1 = Crew(
                agents=[self.web_researcher],
                tasks=[initial_task],
                process=Process.sequential
            )
            
            # Asenkron çalıştır
            result1 = await self.run_crew_async(crew1)
            if not result1["success"]:
                raise Exception(f"Web araştırması hatası: {result1['error']}")
            
            initial_result = result1["result"]
            await self.send_main_step_update("step1", "completed", "✅ Web araştırması tamamlandı")
            await self.send_agent_message("WebResearcher", "✅ Web araştırması tamamlandı", {
                "result_length": len(str(initial_result))
            })
            research_data["workflow_steps"].append("initial_web_research")
            
            # Step 2: YouTube analizi başlat
            await self.send_main_step_update("step2", "running", "📹 YouTube analizi başlatılıyor...")
            await self.send_agent_message("YouTubeAnalyst", "📹 YouTube içerik analizi başlatılıyor...", {"topic": topic})
            
            youtube_task = Task(
                description=(
                    f"'{topic}' konusu hakkında YouTube'da araştırma yap.\n"
                    "1. En alakalı videoları bul\n"
                    "2. En iyi videonun transkriptini çıkar\n"
                    "3. Video içeriğini özetle\n"
                    "4. Web araştırmasını tamamlayacak bilgileri çıkar"
                ),
                expected_output="YouTube videolarından çıkarılan ek bilgiler",
                agent=self.youtube_analyst
            )
            
            crew2 = Crew(
                agents=[self.youtube_analyst],
                tasks=[youtube_task],
                process=Process.sequential
            )
            
            # Asenkron çalıştır
            result2 = await self.run_crew_async(crew2)
            if not result2["success"]:
                raise Exception(f"YouTube analizi hatası: {result2['error']}")
            
            youtube_result = result2["result"]
            await self.send_main_step_update("step2", "completed", "✅ YouTube analizi tamamlandı")
            await self.send_agent_message("YouTubeAnalyst", "✅ YouTube analizi tamamlandı", {
                "result_length": len(str(youtube_result))
            })
            research_data["workflow_steps"].append("youtube_analysis")
            
            # Step 3: Rapor yapılandırma başlat
            await self.send_main_step_update("step3", "running", "📋 Rapor yapılandırılıyor...")
            await self.send_agent_message("ReportProcessor", "📋 Rapor yapılandırması başlatılıyor...", {})
            
            combined_content = f"WEB ARAŞTIRMASI:\n{initial_result}\n\nYOUTUBE ANALİZİ:\n{youtube_result}"
            
            structure_result = await self.structure_report_with_retry_async(combined_content, topic)
            if not structure_result:
                raise Exception("Rapor yapılandırması başarısız")
            
            research_data["subtopics"] = structure_result
            
            await self.send_main_step_update("step3", "completed", "✅ Rapor yapılandırması tamamlandı")
            await self.send_agent_message("ReportProcessor", "✅ Rapor yapılandırması tamamlandı", {
                "subtopics_count": len(structure_result)
            })
            research_data["workflow_steps"].append("report_structuring")
            
            # Alt konuları gönder
            await self.send_subtopics_found(structure_result)
            await asyncio.sleep(1)  # UI'ın alt konuları göstermesi için
            
            # Step 4: Alt başlıkları detaylandır
            await self.send_agent_message("DetailResearcher", "🔍 Alt başlıklar detaylandırılıyor...", {
                "subtopics_count": len(structure_result)
            })
            
            detailed_sections = await self.detail_each_section_async(structure_result, topic)
            research_data["detailed_research"] = detailed_sections
            research_data["workflow_steps"].append("detailed_research")
            
            await self.send_agent_message("DetailResearcher", "✅ Tüm alt başlıklar detaylandırıldı", {
                "detailed_count": len(detailed_sections)
            })
            
            # Step 5: Final raporu kaydet
            await self.send_agent_message("DataManager", "💾 Final rapor kaydediliyor...", {})
            
            saved_file = await self.save_final_research(detailed_sections, topic)
            if saved_file:
                research_data["saved_files"].append(saved_file)
            
            research_data["workflow_steps"].append("file_saving")
            
            await self.send_agent_message("DataManager", "✅ Rapor başarıyla kaydedildi", {
                "filename": saved_file
            })
            
            # Final özet oluştur
            research_data["final_report"] = await self.create_presentation_summary(detailed_sections, topic)
            
            await self.send_progress_update("🎉 Araştırma tamamen tamamlandı!", {
                "total_subtopics": len(detailed_sections),
                "saved_file": saved_file,
                "workflow_completed": True
            })
            
            return research_data
            
        except Exception as e:
            await self.send_progress_update(f"❌ Araştırma hatası: {str(e)}", {
                "error": str(e),
                "workflow_failed": True
            })
            raise e
    
    async def structure_report_with_retry_async(self, content: str, topic: str, max_retries: int = 3) -> List[Dict]:
        """Raporu yapılandır - Asenkron retry mekanizması ile"""
        
        for attempt in range(max_retries):
            try:
                await self.send_progress_update(f"📋 Rapor yapılandırma denemesi {attempt + 1}/{max_retries}")
                
                structure_task = Task(
                    description=(
                        f"Aşağıdaki araştırma içeriğini analiz et ve {topic} konusu için "
                        f"mantıklı alt başlıklara böl:\n\n{content[:2000]}...\n\n"  # Content'i kısalt
                        "GÖREV:\n"
                        "1. İçeriği incele ve ana konuları belirle\n"
                        "2. 4-6 arası alt başlık oluştur\n"
                        "3. Her alt başlık için kısa açıklama yaz\n"
                        "4. Sonucu şu formatta ver:\n"
                        "ALT BAŞLIK 1: [Başlık]\n"
                        "AÇIKLAMA: [Kısa açıklama]\n\n"
                        "ALT BAŞLIK 2: [Başlık]\n"
                        "AÇIKLAMA: [Kısa açıklama]\n"
                    ),
                    expected_output="Alt başlıklara bölünmüş yapılandırılmış içerik",
                    agent=self.report_processor
                )
                
                json_task = Task(
                    description=(
                        f"Önceki görevden gelen yapılandırılmış içeriği JSON formatına dönüştür.\n"
                        f"Bu {attempt + 1}. deneme, daha dikkatli ol!\n\n"
                        "HEDEF FORMAT:\n"
                        "[\n"
                        "  {\n"
                        '    "alt_baslik": "Başlık 1",\n'
                        '    "aciklama": "Açıklama metni"\n'
                        "  }\n"
                        "]\n\n"
                        "KRİTİK KURALLAR:\n"
                        "- SADECE JSON array ver, başka hiçbir şey ekleme\n"
                        "- JSONValidatorTool ile kontrol et\n"
                        "- Türkçe karakterleri düzgün kodla\n"
                    ),
                    expected_output="Geçerli JSON formatında alt başlıklar",
                    agent=self.json_converter
                )
                
                crew = Crew(
                    agents=[self.report_processor, self.json_converter],
                    tasks=[structure_task, json_task],
                    process=Process.sequential
                )
                
                result = await self.run_crew_async(crew)
                if not result["success"]:
                    raise Exception(result["error"])
                
                # JSON doğrula
                cleaned_json = str(result["result"]).strip()
                if cleaned_json.startswith('```json'):
                    cleaned_json = cleaned_json[7:]
                if cleaned_json.endswith('```'):
                    cleaned_json = cleaned_json[:-3]
                cleaned_json = cleaned_json.strip()
                
                parsed = json.loads(cleaned_json)
                
                if isinstance(parsed, list) and len(parsed) > 0:
                    for item in parsed:
                        if not isinstance(item, dict) or "alt_baslik" not in item or "aciklama" not in item:
                            raise ValueError("JSON yapısı hatalı")
                    
                    await self.send_progress_update(f"✅ JSON başarıyla oluşturuldu (deneme {attempt + 1})")
                    return parsed
                else:
                    raise ValueError("JSON liste formatında değil")
                    
            except Exception as e:
                await self.send_progress_update(f"❌ JSON hatası (deneme {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:
                    return None
                await asyncio.sleep(1)  # Kısa bekleme
        
        return None
    
    async def detail_each_section_async(self, sections: List[Dict], topic: str) -> List[Dict]:
        """Her alt başlığı asenkron olarak detaylandır"""
        detailed_sections = []
        
        for i, section in enumerate(sections, 1):
            alt_baslik = section['alt_baslik']
            mevcut_aciklama = section['aciklama']
            
            # Alt konu başladığını bildir
            await self.send_subtopic_update(alt_baslik, "running")
            await self.send_agent_message("DetailResearcher", f"🔍 Alt başlık {i}/{len(sections)} detaylandırılıyor: {alt_baslik}")
            
            detail_task = Task(
                description=(
                    f"'{alt_baslik}' konusunu '{topic}' ana konusu bağlamında detaylandır.\n\n"
                    f"MEVCUT AÇIKLAMA:\n{mevcut_aciklama}\n\n"
                    "GÖREV:\n"
                    "1. Bu alt başlık hakkında ek web araştırması yap\n"
                    "2. Mevcut açıklamayı genişlet ve derinleştir\n"
                    "3. Güncel bilgileri, örnekleri ve detayları ekle\n"
                    "4. Kapsamlı ve anlaşılır bir açıklama oluştur\n"
                    "5. En az 200 kelimelik detaylı açıklama ver\n\n"
                    "ÇIKTI: Sadece detaylandırılmış açıklama metnini ver."
                ),
                expected_output=f"'{alt_baslik}' için kapsamlı detaylı açıklama",
                agent=self.detail_researcher
            )
            
            crew = Crew(
                agents=[self.detail_researcher],
                tasks=[detail_task],
                process=Process.sequential
            )
            
            # Asenkron çalıştır
            result = await self.run_crew_async(crew)
            if not result["success"]:
                detailed_content = f"Hata: {result['error']}"
            else:
                detailed_content = str(result["result"]).strip()
            
            detailed_sections.append({
                "alt_baslik": alt_baslik,
                "aciklama": detailed_content
            })
            
            # Alt konu tamamlandığını bildir
            await self.send_subtopic_update(alt_baslik, "completed", detailed_content)
            await self.send_agent_message("DetailResearcher", f"✅ '{alt_baslik}' detaylandırıldı ({i}/{len(sections)})")
            
            # Her alt konu arasında kısa bekleme
            await asyncio.sleep(0.5)
        
        return detailed_sections
    
    async def save_final_research(self, detailed_sections: List[Dict], topic: str) -> str:
        """Final araştırmayı dosyaya kaydet"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_topic = safe_topic.replace(' ', '_')[:30]
            filename = f"crew_research_{safe_topic}_{timestamp}.json"
            
            # Research dizini oluştur
            research_dir = Path("research_data")
            research_dir.mkdir(exist_ok=True)
            file_path = research_dir / filename
            
            # Veriyi hazırla
            final_data = {
                "topic": topic,
                "timestamp": datetime.utcnow().isoformat(),
                "user": "al1berk",
                "research_method": "CrewAI Multi-Agent Async",
                "subtopics": detailed_sections,
                "summary": {
                    "total_subtopics": len(detailed_sections),
                    "research_depth": "detailed",
                    "sources": "web + youtube"
                }
            }
            
            # Dosyaya kaydet
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(final_data, ensure_ascii=False, indent=2))
            
            return str(file_path)
            
        except Exception as e:
            await self.send_progress_update(f"❌ Dosya kaydetme hatası: {str(e)}")
            return None
    
    async def create_presentation_summary(self, detailed_sections: List[Dict], topic: str) -> str:
        """Sunum için özet oluştur"""
        summary = f"🔍 **'{topic}' Araştırması Tamamlandı!**\n\n"
        summary += "📋 **CrewAI Multi-Agent Sistemi Tarafından Keşfedilen Konular:**\n"
        
        for i, section in enumerate(detailed_sections, 1):
            summary += f"{i}. {section['alt_baslik']}\n"
        
        summary += f"\n🚀 **İlk konu ile başlıyorum:** {detailed_sections[0]['alt_baslik'] if detailed_sections else 'Genel bilgiler'}\n\n"
        
        # İlk konuyu detaylandır
        if detailed_sections:
            first_section = detailed_sections[0]
            summary += f"**{first_section['alt_baslik']} Hakkında:**\n"
            
            # İlk konunun açıklamasının ilk 500 karakteri
            description = first_section['aciklama']
            if len(description) > 500:
                summary += description[:500] + "...\n"
            else:
                summary += description + "\n"
        
        summary += f"\n📊 **Toplam {len(detailed_sections)} konu detaylandırıldı**"
        summary += f"\n🤖 **CrewAI Multi-Agent sistemi (Asenkron) kullanıldı**"
        summary += f"\n⏰ **Araştırma tarihi:** {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        return summary

# A2A Protocol Handler for Async CrewAI
class AsyncCrewAIA2AHandler:
    """Asenkron CrewAI için Agent-to-Agent communication handler"""
    
    def __init__(self, websocket_callback):
        self.websocket_callback = websocket_callback
        self.crew_tool = AsyncCrewAIResearchTool(websocket_callback)
    
    async def research_workflow(self, query: str) -> Dict:
        """CrewAI ile Asenkron A2A protokolü research workflow'u"""
        
        # Workflow başlangıcı
        await self.send_workflow_message("CrewAI-Manager", "🚀 Asenkron Multi-Agent araştırma sistemi başlatılıyor", {
            "query": query,
            "agents": ["WebResearcher", "YouTubeAnalyst", "ReportProcessor", "DetailResearcher", "DataManager"],
            "mode": "async"
        })
        
        # Ana araştırmayı başlat
        result = await self.crew_tool.comprehensive_research(query)
        
        # Workflow tamamlanması
        await self.send_workflow_message("CrewAI-Manager", "✅ Asenkron Multi-Agent araştırma workflow'u tamamlandı", {
            "subtopics_count": len(result.get("detailed_research", [])),
            "workflow_steps": result.get("workflow_steps", []),
            "saved_files": result.get("saved_files", [])
        })
        
        return result
    
    async def send_workflow_message(self, agent_name: str, message: str, data: Dict = None):
        """Workflow mesajı gönder"""
        if self.websocket_callback:
            workflow_message = {
                "type": "workflow_message",
                "agent": agent_name,
                "message": message,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.websocket_callback(json.dumps(workflow_message))

# Test fonksiyonu
async def test_async_crew_research():
    """Asenkron CrewAI research tool'u test et"""
    print("🧪 Async CrewAI Research Tool Test")
    print("=" * 50)
    
    async def mock_websocket_callback(message):
        data = json.loads(message)
        print(f"📡 {data['type']}: {data.get('message', '')}")
    
    try:
        handler = AsyncCrewAIA2AHandler(mock_websocket_callback)
        result = await handler.research_workflow("Python web development")
        
        print("\n✅ Test Sonuçları:")
        print(f"📋 Alt başlık sayısı: {len(result.get('detailed_research', []))}")
        print(f"💾 Kaydedilen dosyalar: {result.get('saved_files', [])}")
        print(f"🔄 Workflow adımları: {result.get('workflow_steps', [])}")
        
    except Exception as e:
        print(f"❌ Test hatası: {e}")

if __name__ == "__main__":
    asyncio.run(test_async_crew_research())