# hybrid_research_system.py
import os
import json
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

# CrewAI imports
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool
from faster_whisper import WhisperModel

# LangGraph imports
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import Tool

# Custom tools import
from araclar import YouTubeSearchTool, YouTubeTranscriptTool, JSONValidatorTool, JSONSaverTool, FileReaderTool

class MessageType(Enum):
    RESEARCH_REQUEST = "research_request"
    RESEARCH_COMPLETE = "research_complete"
    JSON_PROCESS_REQUEST = "json_process_request"
    JSON_PROCESS_COMPLETE = "json_process_complete"
    ERROR = "error"
    STATUS_UPDATE = "status_update"

@dataclass
class A2AMessage:
    """Agent-to-Agent Protocol Message"""
    message_type: MessageType
    sender: str
    receiver: str
    payload: Dict[str, Any]
    message_id: str
    timestamp: float

class ResearchState:
    """LangGraph State for the research process"""
    def __init__(self):
        self.topic: str = ""
        self.initial_report: str = ""
        self.structured_data: List[Dict] = []
        self.detailed_sections: List[Dict] = []
        self.current_section_index: int = 0
        self.max_retries: int = 3
        self.retry_count: int = 0
        self.json_validation_passed: bool = False
        self.final_filename: str = ""
        self.errors: List[str] = []
        self.messages: List[A2AMessage] = []

class CrewAIResearchSystem:
    """CrewAI tabanlı araştırma sistemi"""
    
    def __init__(self):
        self._setup_llm()
        self._setup_tools()
        self._setup_agents()
        
    def _setup_llm(self):
        """LLM konfigürasyonu"""
        from dotenv import load_dotenv
        load_dotenv()
        
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.SERPER_API_KEY = os.getenv("SERPER_API_KEY")
        self.YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
        
        if not all([self.GOOGLE_API_KEY, self.SERPER_API_KEY, self.YOUTUBE_API_KEY]):
            raise ValueError("API anahtarları eksik!")
            
        self.gemini_llm = LLM(
            model="gemini/gemini-2.5-flash",
            api_key=self.GOOGLE_API_KEY,
            temperature=0.6
        )
        
        self.gemini_llm_pro = LLM(
            model="gemini/gemini-2.5-pro",
            api_key=self.GOOGLE_API_KEY,
            temperature=0.6
        )
        
    def _setup_tools(self):
        """Araçları yapılandır"""
        # Whisper model
        self.whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        
        # Tools
        self.web_search_tool = SerperDevTool()
        self.youtube_tool = YouTubeSearchTool(api_key=self.YOUTUBE_API_KEY)
        self.youtube_transcript_tool = YouTubeTranscriptTool(model=self.whisper_model)
        
    def _setup_agents(self):
        """CrewAI ajanlarını oluştur"""
        self.web_researcher = Agent(
            role='Kıdemli Araştırma Stratejisti',
            goal='Verilen konuda webdeki metin tabanlı kaynakları kullanarak kapsamlı bir ilk analiz yapmak.',
            backstory="Bilginin yeterli olup olmadığını sezme konusunda usta bir araştırmacı.",
            verbose=True,
            allow_delegation=True,
            tools=[self.web_search_tool],
            llm=self.gemini_llm
        )

        self.youtube_analyst = Agent(
            role='YouTube İçerik Analisti',
            goal='Belirli bir konu hakkında en alakalı YouTube videolarını bulmak, transkriptlerini çıkarmak ve bu içerikten önemli bilgileri sentezlemek.',
            backstory="Video içeriklerindeki değerli bilgileri ve ana temaları ortaya çıkarma konusunda uzmanlaşmış bir analist.",
            verbose=True,
            allow_delegation=False,
            tools=[self.youtube_tool, self.youtube_transcript_tool],
            llm=self.gemini_llm
        )

        self.detail_researcher = Agent(
            role='Detay Araştırma Uzmanı',
            goal='Belirli alt başlıkları derinlemesine araştırır ve detaylandırır.',
            backstory="Spesifik konularda derinlemesine araştırma yapma konusunda uzman bir araştırmacı.",
            verbose=True,
            allow_delegation=False,
            tools=[self.web_search_tool],
            llm=self.gemini_llm_pro
        )
    
    async def conduct_initial_research(self, topic: str) -> Dict[str, Any]:
        """İlk araştırmayı gerçekleştir"""
        print(f"🔍 CrewAI: '{topic}' için araştırma başlatılıyor...")
        
        master_task = Task(
            description=(
                f"'{topic}' konusu hakkında detaylı ve anlaşılır bir rapor hazırla.\n"
                "1. İlk olarak, web'de kapsamlı bir araştırma yap ve konunun temelini anlatan bir taslak oluştur.\n"
                "2. Değerlendirme yap: Eğer bulduğun yazılı kaynaklar konuyu tam olarak açıklamıyorsa, YouTube Analistinden yardım iste.\n"
                "3. Son olarak, hem kendi web araştırmanı hem de YouTube'dan gelen bilgileri birleştirerek nihai ve kapsamlı raporunu oluştur."
            ),
            expected_output="Konu hakkında tüm önemli noktaları içeren, iyi yapılandırılmış tam bir rapor.",
            agent=self.web_researcher
        )
        
        crew = Crew(
            agents=[self.web_researcher, self.youtube_analyst],
            tasks=[master_task],
            process=Process.hierarchical,
            manager_llm=self.gemini_llm
        )
        
        result = crew.kickoff()
        
        return {
            "status": "success",
            "report": str(result),
            "topic": topic
        }
    
    async def detail_section_research(self, section_title: str, section_description: str, main_topic: str) -> Dict[str, Any]:
        """Belirli bir bölümü detaylandır"""
        print(f"📖 CrewAI: '{section_title}' bölümü detaylandırılıyor...")
        
        detail_task = Task(
            description=(
                f"'{section_title}' konusunu '{main_topic}' ana konusu bağlamında detaylandır.\n\n"
                f"MEVCUT AÇIKLAMA:\n{section_description}\n\n"
                "GÖREV:\n"
                "1. Bu alt başlık hakkında web'de ek araştırma yap\n"
                "2. Mevcut açıklamayı genişlet ve derinleştir\n"
                "3. Önemli detayları, örnekleri ve açıklamaları ekle\n"
                "4. Güncel bilgileri araştır ve dahil et\n"
                "5. Kapsamlı ve detaylı bir açıklama oluştur\n\n"
                "ÇIKTI: Sadece detaylandırılmış açıklama metnini ver, başka hiçbir şey ekleme."
            ),
            expected_output=f"'{section_title}' için kapsamlı ve detaylı açıklama",
            agent=self.detail_researcher
        )
        
        crew = Crew(
            agents=[self.detail_researcher],
            tasks=[detail_task],
            process=Process.sequential,
            manager_llm=self.gemini_llm_pro

        )
        
        result = crew.kickoff()
        
        return {
            "status": "success",
            "detailed_content": str(result),
            "section_title": section_title
        }

class LangGraphJSONProcessor:
    """LangGraph tabanlı JSON işleme sistemi"""
    
    def __init__(self):
        self._setup_llm()
        self._setup_tools()
        self._setup_graph()
    
    def _setup_llm(self):
        """LLM ayarla"""
        from dotenv import load_dotenv
        load_dotenv()
        
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        
        self.gemini_llm = LLM(
            model="gemini/gemini-2.5-flash",
            api_key=self.GOOGLE_API_KEY,
            temperature=0.3
        )
    
    def _setup_tools(self):
        """JSON işleme araçlarını ayarla"""
        self.json_validator_tool = JSONValidatorTool()
        self.json_saver_tool = JSONSaverTool()
        self.file_reader_tool = FileReaderTool()
    
    def _setup_graph(self):
        """LangGraph workflow'unu ayarla"""
        from langgraph.graph import StateGraph
        
        workflow = StateGraph(dict)
        
        # Düğümleri tanımla
        workflow.add_node("llm_structure_report", self.llm_structure_report)
        workflow.add_node("llm_convert_to_json", self.llm_convert_to_json)
        workflow.add_node("validate_json", self.validate_json_structure)
        workflow.add_node("retry_json", self.retry_json_creation)
        workflow.add_node("save_initial_json", self.save_initial_structure)
        workflow.add_node("process_detailed_sections", self.process_detailed_sections)
        workflow.add_node("save_final_json", self.save_final_json)
        workflow.add_node("handle_error", self.handle_error)
        
        # Başlangıç noktası
        workflow.set_entry_point("llm_structure_report")
        
        # Koşullu geçişler
        workflow.add_conditional_edges(
            "validate_json",
            self.should_retry_json,
            {
                "retry": "retry_json",
                "continue": "save_initial_json",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "retry_json",
            self.check_retry_limit,
            {
                "validate": "validate_json",
                "error": "handle_error"
            }
        )
        
        # Sıralı geçişler
        workflow.add_edge("llm_structure_report", "llm_convert_to_json")
        workflow.add_edge("llm_convert_to_json", "validate_json")
        workflow.add_edge("save_initial_json", "process_detailed_sections")
        workflow.add_edge("process_detailed_sections", "save_final_json")
        workflow.add_edge("save_final_json", END)
        workflow.add_edge("handle_error", END)
        
        self.graph = workflow.compile()
    
    def llm_structure_report(self, state: dict) -> dict:
        """LLM ile raporu yapılandır"""
        print("🧠 LangGraph: LLM ile rapor yapılandırılıyor...")
        
        report_content = state.get("initial_report", "")
        topic = state.get("topic", "")
        
        from crewai import Task, Agent, Crew
        
        # LLM ile yapılandırma ajanı
        structure_agent = Agent(
            role='Rapor Yapılandırma Uzmanı',
            goal='Verilen raporu mantıklı alt başlıklara böler.',
            backstory="Karmaşık metinleri organize etme konusunda uzman.",
            verbose=False,
            allow_delegation=False,
            tools=[],
            llm=self.gemini_llm
        )
        
        structure_task = Task(
            description=(
                f"Aşağıdaki '{topic}' konulu raporu analiz et ve mantıklı alt başlıklara böl:\n\n"
                f"RAPOR:\n{report_content}\n\n"
                "GÖREV:\n"
                "1. Raporun ana konularını belirle\n"
                "2. Her ana konu için açık ve öz bir başlık oluştur\n"
                "3. Her başlık altındaki içeriği özetle\n"
                "4. Sonucu şu formatta yaz:\n\n"
                "BAŞLIK 1: [Başlık adı]\n"
                "İÇERİK: [Bu bölümün içeriği]\n\n"
                "BAŞLIK 2: [Başlık adı]\n"
                "İÇERİK: [Bu bölümün içeriği]\n\n"
                "Minimum 3, maksimum 8 başlık oluştur."
            ),
            expected_output="Alt başlıklara bölünmüş strukturlu rapor",
            agent=structure_agent
        )
        
        crew = Crew(
            agents=[structure_agent],
            tasks=[structure_task],
            verbose=False
        )
        
        result = crew.kickoff()
        state["structured_text"] = str(result)
        print("✅ Rapor LLM ile yapılandırıldı")
        
        return state
    
    def llm_convert_to_json(self, state: dict) -> dict:
        """LLM ile JSON'a dönüştür"""
        print("🔄 LangGraph: LLM ile JSON'a dönüştürülüyor...")
        
        structured_text = state.get("structured_text", "")
        retry_count = state.get("retry_count", 0)
        
        from crewai import Task, Agent, Crew
        
        # JSON dönüştürme ajanı
        json_agent = Agent(
            role='JSON Dönüştürme Uzmanı',
            goal='Yapılandırılmış metni geçerli JSON formatına dönüştürür.',
            backstory="JSON formatları konusunda mükemmel bir uzman.",
            verbose=False,
            allow_delegation=False,
            tools=[],
            llm=self.gemini_llm
        )
        
        retry_warning = ""
        if retry_count > 0:
            retry_warning = f"\n⚠️ BU {retry_count + 1}. DENEME! Önceki JSON geçersizdi, çok dikkatli ol!\n"
        
        json_task = Task(
            description=(
                f"{retry_warning}"
                "Aşağıdaki yapılandırılmış metni JSON array formatına dönüştür:\n\n"
                f"YAPILANDIRILMIŞ METİN:\n{structured_text}\n\n"
                "HEDEF JSON FORMAT:\n"
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
                "- SADECE JSON ARRAY çıktısı ver, hiç ek metin yok\n"
                "- Her obje 'alt_baslik' ve 'aciklama' anahtarlarına sahip olmalı\n"
                "- Türkçe karakterleri düzgün kullan\n"
                "- Tırnak işaretlerini doğru kullan\n"
                "- Virgülleri unutma\n"
                "- BAŞLIK: ve İÇERİK: kısımlarını çıkar, sadece içeriği al\n"
                f"- Bu {retry_count + 1}. deneme, hata yapma!"
            ),
            expected_output="Geçerli JSON array formatı",
            agent=json_agent
        )
        
        crew = Crew(
            agents=[json_agent],
            tasks=[json_task],
            verbose=False
        )
        
        result = crew.kickoff()
        state["json_output"] = str(result).strip()
        print(f"✅ JSON dönüştürme tamamlandı (deneme {retry_count + 1})")
        
        return state
    
    def _extract_sections_from_report(self, report: str) -> List[Dict]:
        """Raporden alt başlıkları çıkar (basit parsing)"""
        # Bu fonksiyon rapordaki başlıkları tanımlar
        # Gerçek implementasyonda daha sofistike parsing olabilir
        
        sections = []
        lines = report.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Başlık tespiti (çeşitli formatları destekle)
            if (line.startswith('#') or 
                line.isupper() or 
                (len(line) < 100 and ':' in line and line.endswith(':'))):
                
                # Önceki bölümü kaydet
                if current_section and current_content:
                    sections.append({
                        "alt_baslik": current_section,
                        "aciklama": ' '.join(current_content)
                    })
                
                # Yeni bölüm başlat
                current_section = line.replace('#', '').replace(':', '').strip()
                current_content = []
            else:
                if current_section:
                    current_content.append(line)
        
        # Son bölümü kaydet
        if current_section and current_content:
            sections.append({
                "alt_baslik": current_section,
                "aciklama": ' '.join(current_content)
            })
        
        # Eğer hiç bölüm bulunamazsa, tüm raporu tek bölüm yap
        if not sections:
            sections.append({
                "alt_baslik": "Genel Değerlendirme",
                "aciklama": report
            })
        
        return sections
    
    def validate_json_structure(self, state: dict) -> dict:
        """JSON yapısını doğrula"""
        print("✅ LangGraph: JSON yapısı doğrulanıyor...")
        
        json_output = state.get("json_output", "")
        
        try:
            # JSON temizleme
            cleaned_json = json_output.strip()
            if cleaned_json.startswith('```json'):
                cleaned_json = cleaned_json[7:]
            if cleaned_json.endswith('```'):
                cleaned_json = cleaned_json[:-3]
            cleaned_json = cleaned_json.strip()
            
            # Parse testi
            parsed_data = json.loads(cleaned_json)
            
            # Yapı doğrulaması
            if isinstance(parsed_data, list) and len(parsed_data) > 0:
                for item in parsed_data:
                    if not isinstance(item, dict):
                        raise ValueError("Liste elemanları dict olmalı")
                    if "alt_baslik" not in item or "aciklama" not in item:
                        raise ValueError("Eksik anahtarlar: alt_baslik veya aciklama")
                    if not item["alt_baslik"].strip() or not item["aciklama"].strip():
                        raise ValueError("Boş başlık veya açıklama")
                
                state["structured_data"] = parsed_data
                state["json_validation_passed"] = True
                state["json_string"] = json.dumps(parsed_data, ensure_ascii=False, indent=2)
                print(f"✅ JSON doğrulandı: {len(parsed_data)} bölüm")
            else:
                raise ValueError("JSON liste formatında değil veya boş")
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON parse hatası: {str(e)}")
            state["json_validation_passed"] = False
            state["last_error"] = f"JSON Parse Error: {str(e)}"
        except Exception as e:
            print(f"❌ JSON yapı hatası: {str(e)}")
            state["json_validation_passed"] = False
            state["last_error"] = f"Structure Error: {str(e)}"
        
        return state
    
    def should_retry_json(self, state: dict) -> str:
        """JSON'ın yeniden denenmesi gerekip gerekmediğini kontrol et"""
        if state.get("json_validation_passed", False):
            return "continue"
        elif state.get("retry_count", 0) < state.get("max_retries", 3):
            return "retry"
        else:
            return "error"
    
    def retry_json_creation(self, state: dict) -> dict:
        """JSON oluşturmayı yeniden dene"""
        retry_count = state.get("retry_count", 0) + 1
        state["retry_count"] = retry_count
        
        print(f"🔄 LangGraph: JSON yeniden oluşturuluyor (deneme {retry_count})")
        
        # Önceki hatayı göster
        last_error = state.get("last_error", "")
        print(f"❌ Önceki hata: {last_error}")
        
        # LLM ile yeniden dönüştür (retry_count state'e eklendi)
        return self.llm_convert_to_json(state)
    
    def _extract_sections_from_report_v2(self, report: str, retry_attempt: int) -> List[Dict]:
        """Alternatif parsing stratejisi"""
        # Her retry'da farklı parsing stratejisi kullan
        if retry_attempt == 2:
            # Paragraf tabanlı parsing
            paragraphs = report.split('\n\n')
            sections = []
            for i, para in enumerate(paragraphs):
                if len(para.strip()) > 50:  # Çok kısa paragrafları atla
                    sections.append({
                        "alt_baslik": f"Bölüm {i+1}",
                        "aciklama": para.strip()
                    })
            return sections
        
        elif retry_attempt == 3:
            # Cümle tabanlı parsing
            sentences = report.split('.')
            sections = []
            current_section = []
            
            for sentence in sentences:
                current_section.append(sentence.strip())
                if len(current_section) >= 3:  # Her 3 cümlede bir bölüm
                    sections.append({
                        "alt_baslik": f"Kısım {len(sections)+1}",
                        "aciklama": '. '.join(current_section) + '.'
                    })
                    current_section = []
            
            if current_section:  # Kalan cümleleri ekle
                sections.append({
                    "alt_baslik": f"Kısım {len(sections)+1}",
                    "aciklama": '. '.join(current_section) + '.'
                })
            
            return sections
        
        # Default strategy
        return self._extract_sections_from_report(report)
    
    def should_retry_json(self, state: dict) -> str:
        """JSON'ın yeniden denenmesi gerekip gerekmediğini kontrol et"""
        if state.get("json_validation_passed", False):
            return "continue"
        elif state.get("retry_count", 0) < state.get("max_retries", 3):
            return "retry"
        else:
            return "error"
    
    def check_retry_limit(self, state: dict) -> str:
        """Retry limitini kontrol et"""
        if state.get("retry_count", 0) < state.get("max_retries", 3):
            return "validate"
        else:
            return "error"
    
    def save_initial_structure(self, state: dict) -> dict:
        """İlk JSON yapısını kaydet"""
        print("💾 LangGraph: İlk JSON yapısı kaydediliyor...")
        
        json_string = state.get("json_string", "")
        topic = state.get("topic", "research")
        
        filename = f"{topic}_initial_structure.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(json_string)
            
            state["initial_structure_saved"] = True
            state["initial_filename"] = filename
            print(f"✅ İlk yapı kaydedildi: {filename}")
            
        except Exception as e:
            print(f"❌ Kaydetme hatası: {str(e)}")
            state["initial_structure_saved"] = False
            state["last_error"] = str(e)
        
        return state
    
    def process_detailed_sections(self, state: dict) -> dict:
        """Detaylandırılmış bölümleri işle"""
        print("🔍 LangGraph: Detaylandırılmış bölümler işleniyor...")
        
        # Bu aşamada CrewAI'dan gelen detaylandırılmış veriler işlenir
        detailed_sections = state.get("detailed_sections", [])
        
        if not detailed_sections:
            # Eğer henüz detaylandırma yapılmamışsa, mevcut yapıyı kullan
            detailed_sections = state.get("structured_data", [])
        
        state["processed_detailed_sections"] = detailed_sections
        state["current_section_index"] = len(detailed_sections)
        
        return state
    
    def save_final_json(self, state: dict) -> dict:
        """Son JSON dosyasını kaydet"""
        print("💾 LangGraph: Final JSON kaydediliyor...")
        
        detailed_sections = state.get("processed_detailed_sections", [])
        topic = state.get("topic", "research")
        
        final_filename = f"{topic}_final_report.json"
        
        try:
            final_json = json.dumps(detailed_sections, ensure_ascii=False, indent=2)
            
            with open(final_filename, 'w', encoding='utf-8') as f:
                f.write(final_json)
            
            state["final_filename"] = final_filename
            state["process_complete"] = True
            
            print(f"🎉 Final rapor kaydedildi: {final_filename}")
            print(f"📊 Toplam bölüm: {len(detailed_sections)}")
            
        except Exception as e:
            print(f"❌ Final kaydetme hatası: {str(e)}")
            state["last_error"] = str(e)
        
        return state
    
    def handle_error(self, state: dict) -> dict:
        """Hata durumunu işle"""
        error = state.get("last_error", "Bilinmeyen hata")
        print(f"💀 LangGraph: Hata işleniyor - {error}")
        
        state["process_complete"] = False
        state["final_error"] = error
        
        return state

class HybridResearchOrchestrator:
    """CrewAI ve LangGraph'ı koordine eden ana sistem"""
    
    def __init__(self):
        self.crew_system = CrewAIResearchSystem()
        self.langgraph_processor = LangGraphJSONProcessor()
        self.message_queue = asyncio.Queue()
        
    async def send_a2a_message(self, message: A2AMessage):
        """A2A mesajı gönder"""
        await self.message_queue.put(message)
        print(f"📤 A2A Mesaj: {message.sender} → {message.receiver} ({message.message_type.value})")
    
    async def receive_a2a_message(self) -> A2AMessage:
        """A2A mesajı al"""
        message = await self.message_queue.get()
        print(f"📥 A2A Mesaj alındı: {message.sender} → {message.receiver}")
        return message
    
    async def run_hybrid_research(self, topic: str):
        """Hybrid araştırma sürecini başlat"""
        print("🚀 HYBRID RESEARCH SYSTEM BAŞLATIYOR")
        print("="*60)
        
        # 1. AŞAMA: CrewAI ile ilk araştırma
        print("\n🔍 AŞAMA 1: CrewAI Initial Research")
        research_result = await self.crew_system.conduct_initial_research(topic)
        
        # A2A mesajı gönder
        await self.send_a2a_message(A2AMessage(
            message_type=MessageType.RESEARCH_COMPLETE,
            sender="CrewAI_Research",
            receiver="LangGraph_Processor",
            payload=research_result,
            message_id="research_001",
            timestamp=asyncio.get_event_loop().time()
        ))
        
        # 2. AŞAMA: LangGraph ile JSON işleme
        print("\n🔧 AŞAMA 2: LangGraph JSON Processing")
        
        # LangGraph state'i hazırla
        initial_state = {
            "topic": topic,
            "initial_report": research_result["report"],
            "max_retries": 3
        }
        
        # LangGraph workflow'unu çalıştır
        final_state = await asyncio.to_thread(
            self.langgraph_processor.graph.invoke,
            initial_state
        )
        
        # JSON işleme tamamlandı mesajı
        await self.send_a2a_message(A2AMessage(
            message_type=MessageType.JSON_PROCESS_COMPLETE,
            sender="LangGraph_Processor",
            receiver="CrewAI_Detailer",
            payload={"structured_data": final_state.get("structured_data", [])},
            message_id="json_001",
            timestamp=asyncio.get_event_loop().time()
        ))
        
        # 3. AŞAMA: CrewAI ile detaylandırma
        print("\n📖 AŞAMA 3: CrewAI Section Detailing")
        
        structured_sections = final_state.get("structured_data", [])
        detailed_sections = []
        
        for i, section in enumerate(structured_sections):
            print(f"🔍 Bölüm {i+1}/{len(structured_sections)}: {section['alt_baslik']}")
            
            detail_result = await self.crew_system.detail_section_research(
                section['alt_baslik'],
                section['aciklama'],
                topic
            )
            
            detailed_sections.append({
                "alt_baslik": section['alt_baslik'],
                "aciklama": detail_result["detailed_content"]
            })
        
        # 4. AŞAMA: LangGraph ile final kaydetme
        print("\n💾 AŞAMA 4: Final JSON Save")
        
        final_state["detailed_sections"] = detailed_sections
        final_state["processed_detailed_sections"] = detailed_sections
        
        # Final kaydetme
        final_result = await asyncio.to_thread(
            self.langgraph_processor.save_final_json,
            final_state
        )
        
        # Sonuç raporu
        print("\n" + "="*60)
        print("🎉 HYBRID RESEARCH TAMAMLANDI!")
        print("="*60)
        print(f"📄 Topic: {topic}")
        print(f"📊 Sections: {len(detailed_sections)}")
        print(f"💾 Final File: {final_result.get('final_filename', 'N/A')}")
        print("="*60)
        
        return final_result

# Ana çalıştırma fonksiyonu
async def main():
    """Ana async fonksiyon"""
    orchestrator = HybridResearchOrchestrator()
    
    # Kullanıcıdan topic al
    topic = input("🔍 Araştırma konusunu girin: ")
    
    # Hybrid research başlat
    result = await orchestrator.run_hybrid_research(topic)
    
    print(f"\n✅ Sistem tamamlandı! Sonuç: {result}")

if __name__ == "__main__":
    # Async main'i çalıştır
    asyncio.run(main())