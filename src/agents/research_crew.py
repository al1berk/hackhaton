# src/agents/research_crew.py

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import aiofiles
from dotenv import load_dotenv
from crewai import LLM, Agent, Task, Crew, Process
from langchain_google_genai import ChatGoogleGenerativeAI
from crewai_tools import SerperDevTool
from faster_whisper import WhisperModel
from concurrent.futures import ThreadPoolExecutor
from tools.custom_tools import YouTubeSearchTool, YouTubeTranscriptTool, JSONValidatorTool, JSONSaverTool, FileReaderTool
from core.config import Config

# .env dosyasını yükle
load_dotenv()

@dataclass
class ResearchStep:
    step_id: str
    title: str
    status: str
    result: Optional[str] = None
    timestamp: Optional[str] = None
    progress: int = 0
    agent: Optional[str] = None

class AsyncCrewAIResearchTool:
    def __init__(self, websocket_callback=None):
        self.websocket_callback = websocket_callback
        self.research_steps = []
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.setup_llm_and_tools()
        self.setup_agents()

    async def send_workflow_message(self, agent_name: str, message: str, data: Dict = None):
        if self.websocket_callback:
            workflow_message = {
                "type": "workflow_message",
                "agent": agent_name,
                "message": message,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.websocket_callback(json.dumps(workflow_message))
            print(f"📡 Workflow Message Sent: {agent_name} -> {message}")

    def setup_llm_and_tools(self):
        """LLM ve araçları ayarla"""
        try:
            self.gemini_llm = LLM(
                model="gemini/gemini-2.5-flash",
                api_key=Config.GOOGLE_API_KEY,
                temperature=0.6
            )
            self.gemini_llm_pro = LLM(
                model="gemini/gemini-2.5-flash",
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
        if self.websocket_callback:
            a2a_message = {
                "type": "a2a_message",
                "agent": agent_name,
                "message": message,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.websocket_callback(json.dumps(a2a_message))

    async def send_subtopic_update(self, subtopic_title: str, status: str, content: str = ""):
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
        if self.websocket_callback:
            update_data = {
                "type": "subtopics_found",
                "subtopics": subtopics,
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.websocket_callback(json.dumps(update_data))

    def run_crew_sync(self, crew):
        try:
            result = crew.kickoff()
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def run_crew_async(self, crew):
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self.executor, self.run_crew_sync, crew)
        return result

    async def comprehensive_research(self, topic: str) -> Dict[str, Any]:
        research_data = {
            "topic": topic,
            "timestamp": datetime.utcnow().isoformat(),
            "subtopics": [],
            "detailed_research": {},
            "final_report": ""
        }
        try:
            await self.send_workflow_message("WebResearcher", "🔍 Web araştırması başlatılıyor...")
            initial_task = Task(
                description=f"'{topic}' hakkında kapsamlı bir ön araştırma raporu oluştur.",
                expected_output="Detaylı, iyi yapılandırılmış ve bilgilendirici ön araştırma raporu.",
                agent=self.web_researcher
            )
            crew1 = Crew(agents=[self.web_researcher], tasks=[initial_task])
            result1 = await self.run_crew_async(crew1)
            if not result1["success"]:
                raise Exception(f"Web araştırması hatası: {result1['error']}")
            await self.send_workflow_message("WebResearcher", "✅ Web araştırması tamamlandı")

            await self.send_workflow_message("YouTubeAnalyst", "📹 YouTube analizi başlatılıyor...")
            youtube_task = Task(
                description=f"'{topic}' hakkında en popüler ve bilgilendirici YouTube videolarını bul. En iyi videonun transkriptini çıkar ve anahtar noktaları özetle.",
                expected_output="YouTube video analizi, transkript özeti ve önemli bulgular.",
                agent=self.youtube_analyst
            )
            crew2 = Crew(agents=[self.youtube_analyst], tasks=[youtube_task])
            result2 = await self.run_crew_async(crew2)
            if not result2["success"]:
                raise Exception(f"YouTube analizi hatası: {result2['error']}")
            await self.send_workflow_message("YouTubeAnalyst", "✅ YouTube analizi tamamlandı")

            await self.send_workflow_message("ReportProcessor", "📋 Rapor yapılandırılıyor...")
            combined_content = f"WEB ARAŞTIRMA SONUÇLARI:\n{result1['result']}\n\nYOUTUBE ANALİZ SONUÇLARI:\n{result2['result']}"
            structure_result = await self.structure_report_with_retry_async(combined_content, topic)
            if not structure_result:
                raise Exception("Rapor yapılandırması başarısız oldu.")
            await self.send_workflow_message("ReportProcessor", "✅ Rapor yapılandırması tamamlandı")
            await self.send_subtopics_found(structure_result)

            detailed_sections = await self.detail_each_section_async(structure_result, topic)
            research_data["detailed_research"] = detailed_sections

            final_report = self.create_presentation_summary(detailed_sections, topic)
            research_data["final_report"] = final_report

            saved_file = await self.save_final_research(detailed_sections, topic)
            if saved_file:
                research_data["saved_file"] = saved_file
            
            return research_data
        except Exception as e:
            error_report = f"Üzgünüm, '{topic}' araştırması sırasında bir hata oluştu: {e}"
            return {"final_report": error_report, "detailed_research": []}

    async def structure_report_with_retry_async(self, content: str, topic: str, max_retries: int = 3) -> List[Dict]:
        for attempt in range(max_retries):
            try:
                await self.send_progress_update(f"📋 Rapor yapılandırma denemesi {attempt + 1}/{max_retries}")
                structure_task = Task(
                    description=(
                        f"Aşağıdaki araştırma içeriğini analiz et ve {topic} konusu için "
                        f"mantıklı alt başlıklara böl:\n\n{content[:2000]}...\n\n"
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
                
                cleaned_json = str(result["result"]).strip().replace('```json', '', 1).replace('```', '', 1).strip()
                parsed = json.loads(cleaned_json)
                
                if isinstance(parsed, list) and len(parsed) > 0:
                    if all(isinstance(item, dict) and "alt_baslik" in item and "aciklama" in item for item in parsed):
                        await self.send_progress_update(f"✅ JSON başarıyla oluşturuldu (deneme {attempt + 1})")
                        return parsed
                raise ValueError("JSON yapısı hatalı veya boş liste")
            except Exception as e:
                await self.send_progress_update(f"❌ JSON hatası (deneme {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:
                    return None
                await asyncio.sleep(1)
        return None

    async def detail_each_section_async(self, sections: List[Dict], topic: str) -> List[Dict]:
        detailed_sections = []
        for i, section in enumerate(sections, 1):
            alt_baslik = section['alt_baslik']
            mevcut_aciklama = section['aciklama']
            
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
            crew = Crew(agents=[self.detail_researcher], tasks=[detail_task])
            
            result = await self.run_crew_async(crew)
            detailed_content = str(result["result"]).strip() if result["success"] else f"Hata: {result['error']}"
            
            detailed_sections.append({"alt_baslik": alt_baslik, "aciklama": detailed_content})
            
            await self.send_subtopic_update(alt_baslik, "completed", detailed_content)
            await self.send_agent_message("DetailResearcher", f"✅ '{alt_baslik}' detaylandırıldı ({i}/{len(sections)})")
            await asyncio.sleep(0.5)
        return detailed_sections

    async def save_final_research(self, detailed_sections: List[Dict], topic: str) -> Optional[str]:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).rstrip().replace(' ', '_')[:30]
            filename = f"crew_research_{safe_topic}_{timestamp}.json"
            
            research_dir = Path("research_data")
            research_dir.mkdir(exist_ok=True)
            file_path = research_dir / filename
            
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
            
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(final_data, ensure_ascii=False, indent=2))
            
            return str(file_path)
            
        except Exception as e:
            await self.send_progress_update(f"❌ Dosya kaydetme hatası: {str(e)}")
            return None

    def create_presentation_summary(self, detailed_sections: List[Dict], topic: str) -> str:
        summary = f"🔍 **'{topic}' Araştırması Tamamlandı!**\n\n"
        summary += "📋 **CrewAI Multi-Agent Sistemi Tarafından Keşfedilen Konular:**\n"
        for i, section in enumerate(detailed_sections, 1):
            summary += f"{i}. {section['alt_baslik']}\n"
        summary += f"\n🚀 **İlk konu ile başlıyorum:** {detailed_sections[0]['alt_baslik'] if detailed_sections else 'Genel bilgiler'}\n\n"
        
        if detailed_sections:
            first_section = detailed_sections[0]
            summary += f"**{first_section['alt_baslik']} Hakkında:**\n"
            description = first_section['aciklama']
            summary += (description[:500] + "...") if len(description) > 500 else (description + "\n")
        
        summary += f"\n📊 **Toplam {len(detailed_sections)} konu detaylandırıldı**"
        summary += f"\n🤖 **CrewAI Multi-Agent sistemi (Asenkron) kullanıldı**"
        summary += f"\n⏰ **Araştırma tarihi:** {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        return summary


class AsyncCrewAIA2AHandler:
    def __init__(self, websocket_callback):
        self.websocket_callback = websocket_callback
        self.crew_tool = AsyncCrewAIResearchTool(websocket_callback)
    
    async def send_workflow_message(self, agent_name: str, message: str, data: Dict = None):
        if self.websocket_callback:
            workflow_message = {
                "type": "workflow_message",
                "agent": agent_name,
                "message": message,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.websocket_callback(json.dumps(workflow_message))
    
    async def research_workflow(self, query: str) -> Dict:
        await self.send_workflow_message("CrewAI-Manager", "🚀 Asenkron Multi-Agent araştırma sistemi başlatılıyor", {
            "query": query,
            "agents": ["WebResearcher", "YouTubeAnalyst", "ReportProcessor", "DetailResearcher", "DataManager"],
            "mode": "async"
        })
        
        result = await self.crew_tool.comprehensive_research(query)
        
        await self.send_workflow_message("CrewAI-Manager", "✅ Asenkron Multi-Agent araştırma workflow'u tamamlandı", {
            "subtopics_count": len(result.get("detailed_research", [])),
            "workflow_steps": result.get("workflow_steps", []),
            "saved_files": result.get("saved_files", [])
        })
        
        return result