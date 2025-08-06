# src/core/conversation.py

from typing import TypedDict, List, Literal
from chromadb import logger
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
import asyncio
import json
from datetime import datetime
import re

from .config import Config
from agents.research_crew import AsyncCrewAIA2AHandler
from agents.crew_agents import CrewAISystem # YENİ: CrewAI sistemini import et

from core.vector_store import VectorStore

class ConversationState(TypedDict):
    messages: List[BaseMessage]
    current_intent: str
    needs_crew_ai: bool
    crew_ai_task: str
    user_context: dict
    conversation_summary: str
    research_data: dict
    websocket_callback: object
    pending_action: str
    research_completed: bool
    rag_context: str
    has_pdf_context: bool
    chat_id: str
    chat_manager: object  # Chat manager referansı
    test_generation_requested: bool
    test_parameters: dict
    generated_questions: dict
    full_document_text: str # Dökümanın tam metnini tutmak için
    # DÜZELTİLMİŞ TEST ALANLARI
    awaiting_test_params: bool
    test_param_stage: str  # "start", "question_types", "difficulty", "student_level", "complete"
    partial_test_params: dict
    test_params_ready: bool  # Test parametrelerinin hazır olup olmadığını belirler
    ui_message_sent: bool  # UI mesajının gönderilip gönderilmediğini takip eder - YENİ
    
class AsyncLangGraphDialog:
    def __init__(self, websocket_callback=None, chat_id=None, chat_manager=None):
        self.llm = ChatGoogleGenerativeAI(
            model=Config.GEMINI_MODEL,
            google_api_key=Config.GOOGLE_API_KEY,
            temperature=Config.GEMINI_TEMPERATURE,
        )
        
        self.websocket_callback = websocket_callback
        self.chat_id = chat_id
        self.chat_manager = chat_manager
        self.crew_handler = AsyncCrewAIA2AHandler(websocket_callback)
        self.test_crew = CrewAISystem(api_key=Config.GOOGLE_API_KEY, websocket_callback=websocket_callback)

        
        # Chat-specific vector store oluştur
        self.vector_store = VectorStore(Config.VECTOR_STORE_PATH, chat_id=chat_id)
        
        self.graph = self.create_conversation_graph()
        
        self.conversation_state = ConversationState(
            messages=[SystemMessage(content=Config.SYSTEM_PROMPT)],
            current_intent="",
            needs_crew_ai=False,
            crew_ai_task="",
            user_context={},
            conversation_summary="",
            research_data={},
            websocket_callback=websocket_callback,
            pending_action="",
            research_completed=False,
            rag_context="",
            has_pdf_context=False,
            chat_id=chat_id or "",
            chat_manager=chat_manager,
            test_generation_requested=False,
            test_parameters={},
            generated_questions={},
            full_document_text="",
            awaiting_test_params=False,
            test_param_stage="start",
            partial_test_params={},
            test_params_ready=False,
            ui_message_sent=False  # YENİ: UI mesaj takibi
        )
    
    def create_conversation_graph(self):
        workflow = StateGraph(ConversationState)
        
        # Düğümleri tanımla
        workflow.add_node("intent_analysis", self.intent_analysis_node)
        workflow.add_node("rag_search", self.rag_search_node)
        workflow.add_node("no_pdf_available", self.no_pdf_available_node)
        workflow.add_node("crew_research_agent", self.crew_research_agent_node)
        workflow.add_node("research_presentation", self.research_presentation_node)
        workflow.add_node("gemini_response", self.gemini_response_node)
        workflow.add_node("check_document_for_test", self.check_document_for_test_node)
        workflow.add_node("ask_test_parameters", self.ask_test_parameters_node)
        workflow.add_node("process_test_parameters", self.process_test_parameters_node)
        workflow.add_node("generate_test_questions", self.generate_test_questions_node)
        workflow.add_node("present_test_results", self.present_test_results_node)
        
        # Giriş noktasını belirle
        workflow.set_entry_point("intent_analysis")
        
        # Intent analysis'ten sonraki yönlendirmeler
        workflow.add_conditional_edges(
            "intent_analysis",
            self.route_intent,
            {
                "web_research": "crew_research_agent",
                "rag_search": "rag_search",
                "no_pdf_available": "no_pdf_available",
                "generate_test": "check_document_for_test",
                "process_test_params": "process_test_parameters",
                "gemini": "gemini_response"
            }
        )

        # Test kontrolü sonrası yönlendirmeler
        workflow.add_conditional_edges(
            "check_document_for_test",
            self.route_test_document_check,
            {
                "ask_test_parameters": "ask_test_parameters",
                "gemini_response": "gemini_response"
            }
        )
        
        # Test parametreleri işleme sonrası
        workflow.add_conditional_edges(
            "process_test_parameters",
            self.route_test_parameters,
            {
                "ask_test_parameters": "ask_test_parameters",
                "generate_test_questions": "generate_test_questions",
                "gemini_response": "gemini_response"
            }
        )
        
        # Test parametreleri alma sonrası
        workflow.add_edge("ask_test_parameters", END)
        
        # Diğer bağlantılar
        workflow.add_edge("rag_search", "gemini_response")
        workflow.add_edge("no_pdf_available", END)
        workflow.add_edge("crew_research_agent", "research_presentation")
        workflow.add_edge("research_presentation", END)
        workflow.add_edge("generate_test_questions", "present_test_results")
        workflow.add_edge("present_test_results", END)
        workflow.add_edge("gemini_response", END)

        return workflow.compile()

    def route_intent(self, state: ConversationState) -> str:
        """Intent'e göre yönlendirme - DÜZELTİLMİŞ"""
        intent = state.get("current_intent", "gemini")
        
        # Eğer test parametreleri işlenmeyi bekliyorsa
        if state.get("awaiting_test_params") and intent != "generate_test":
            return "process_test_params"
        
        if intent in ["web_research", "rag_search", "no_pdf_available", "generate_test", "process_test_params"]:
            return intent
        return "gemini"

    def route_test_document_check(self, state: ConversationState) -> str:
        """Test için doküman kontrolü sonrası yönlendirme"""
        if state.get("full_document_text"):
            return "ask_test_parameters"
        return "gemini_response"
    
    def route_test_parameters(self, state: ConversationState) -> str:
        """Test parametrelerini işleme sonrası yönlendirme"""
        if state.get("test_params_ready"):
            return "generate_test_questions"
        elif state.get("awaiting_test_params"):
            return "ask_test_parameters"
        return "gemini_response"

    async def rag_search_node(self, state: ConversationState):
        """PDF dokümanlarında arama yapar"""
        try:
            last_message = state["messages"][-1].content
            
            # Vektör deposunda ara
            search_results = self.vector_store.search_similar(
                query=last_message,
                n_results=Config.RAG_TOP_K
            )
            
            if search_results:
                # Benzerlik skoruna göre filtrele
                relevant_results = [
                    result for result in search_results 
                    if result['similarity'] >= Config.RAG_SIMILARITY_THRESHOLD
                ]
                
                if relevant_results:
                    # RAG context'i oluştur
                    rag_context = self.format_rag_context(relevant_results)
                    state["rag_context"] = rag_context
                    state["has_pdf_context"] = True
                    
                    if self.websocket_callback:
                        await self.websocket_callback(json.dumps({
                            "type": "rag_found",
                            "message": f"📚 {len(relevant_results)} ilgili doküman parçası bulundu (Sohbet: {self.chat_id})",
                            "timestamp": datetime.utcnow().isoformat(),
                            "chat_id": self.chat_id
                        }))
                else:
                    state["rag_context"] = ""
                    state["has_pdf_context"] = False
            else:
                state["rag_context"] = ""
                state["has_pdf_context"] = False
                
        except Exception as e:
            print(f"❌ RAG search error (Chat: {self.chat_id}): {e}")
            state["rag_context"] = ""
            state["has_pdf_context"] = False
        
        # KRİTİK DÜZELTME: State'i return et!
        return state
    
    def format_rag_context(self, search_results: List[dict]) -> str:
        """RAG arama sonuçlarını LLM için uygun formatta hazırla"""
        context = f"===== YÜKLENEN PDF DOKÜMANLARINDAN BULUNAN BİLGİLER =====\n"
        context += f"Sohbet ID: {self.chat_id}\n"
        context += f"Bulunan parça sayısı: {len(search_results)}\n\n"
        
        for i, result in enumerate(search_results, 1):
            filename = result['metadata'].get('filename', 'Bilinmeyen dosya')
            chunk_index = result['metadata'].get('chunk_index', 0)
            similarity = result.get('similarity', 0)
            content = result['content']
            
            context += f"KAYNAK {i}:\n"
            context += f"📄 Dosya: {filename}\n"
            context += f"📍 Bölüm: {chunk_index + 1}\n"
            context += f"🎯 Benzerlik: %{similarity*100:.1f}\n"
            context += f"📝 İÇERİK:\n{content}\n"
            context += f"{'='*50}\n\n"
        
        context += f"ÖNEMLİ: Bu bilgiler kullanıcının bu sohbete yüklediği PDF dokümanlarından geliyor.\n"
        context += f"Kullanıcının sorusunu bu PDF içeriğine dayanarak yanıtla.\n"
        context += f"Arama tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        context += "=" * 60
        
        return context

    def format_research_context(self, research_data: dict) -> str:
        """Araştırma verilerini LLM için uygun formatta hazırla"""
        context = f"KONU: {research_data.get('topic', 'Belirtilmemiş')}\n\n"
        
        detailed_research = research_data.get('detailed_research', [])
        if detailed_research:
            context += "ALT BAŞLIKLAR VE DETAYLAR:\n"
            for i, section in enumerate(detailed_research, 1):
                title = section.get('alt_baslik', f'Konu {i}')
                content = section.get('aciklama', 'İçerik mevcut değil')
                context += f"\n{i}. {title}:\n{content}\n"
        
        context += f"\nARAŞTIRMA TARİHİ: {research_data.get('timestamp', 'Belirtilmemiş')}"
        return context
    
    async def process_user_message(self, user_message: str) -> str:
        try:
            # Kullanıcı mesajını conversation state'e ekle
            self.conversation_state["messages"].append(HumanMessage(content=user_message))
            self.conversation_state["websocket_callback"] = self.websocket_callback
            
            # Mesajı chat manager'a kaydet
            if self.chat_manager and self.chat_id:
                self.chat_manager.save_message(self.chat_id, {
                    "type": "user",
                    "content": user_message
                })
                
                # İlk mesajsa otomatik başlık oluştur
                chat_info = self.chat_manager.get_chat_info(self.chat_id)
                if chat_info and chat_info.get("message_count", 0) == 1:
                    self.chat_manager.auto_generate_title(self.chat_id, user_message)
            
            # Graph'ı çalıştır
            final_state = await self.graph.ainvoke(self.conversation_state)
            self.conversation_state = final_state
            
            # Pending action varsa mesaj döndürme
            if final_state.get('pending_action'):
                return ""
            
            # AI mesajlarını al
            ai_messages = [msg for msg in final_state["messages"] if isinstance(msg, AIMessage)]
            if ai_messages:
                ai_response = ai_messages[-1].content
                
                # AI mesajını da chat manager'a kaydet
                if self.chat_manager and self.chat_id and ai_response:
                    self.chat_manager.save_message(self.chat_id, {
                        "type": "ai",
                        "content": ai_response
                    })
                
                return ai_response
            return ""
            
        except Exception as e:
            error_response = f"Bir hata oluştu: {str(e)}"
            print(f"❌ Process message error (Chat: {self.chat_id}): {e}")
            self.conversation_state["pending_action"] = ""
            
            # Hata mesajını da kaydet
            if self.chat_manager and self.chat_id:
                self.chat_manager.save_message(self.chat_id, {
                    "type": "system",
                    "content": error_response
                })
            
            return error_response

    def get_conversation_history(self) -> List[dict]:
        """Konuşma geçmişini döner"""
        history = []
        for message in self.conversation_state["messages"]:
            if isinstance(message, HumanMessage):
                history.append({"type": "human", "content": message.content})
            elif isinstance(message, AIMessage):
                history.append({"type": "ai", "content": message.content})
        return history
    
    def get_conversation_stats(self) -> dict:
        """Konuşma istatistiklerini döner"""
        messages = self.conversation_state["messages"]
        user_messages = sum(1 for msg in messages if isinstance(msg, HumanMessage))
        ai_messages = sum(1 for msg in messages if isinstance(msg, AIMessage))
        
        vector_stats = self.vector_store.get_stats()
        
        return {
            "total_messages": len(messages),
            "user_messages": user_messages,
            "ai_messages": ai_messages,
            "current_intent": self.conversation_state.get("current_intent", "N/A"),
            "has_research_data": bool(self.conversation_state.get("research_data")),
            "last_research": self.conversation_state.get("research_data", {}).get("topic", ""),
            "crew_ai_enabled": True,
            "async_mode": True,
            "research_completed": self.conversation_state.get("research_completed", False),
            "rag_enabled": Config.RAG_ENABLED,
            "vector_store_stats": vector_stats,
            "chat_id": self.chat_id or "default",
            # Test durumu istatistikleri - DÜZELTİLMİŞ
            "test_stats": {
                "awaiting_params": self.conversation_state.get("awaiting_test_params", False),
                "param_stage": self.conversation_state.get("test_param_stage", "start"),
                "params_ready": self.conversation_state.get("test_params_ready", False),
                "has_generated_test": bool(self.conversation_state.get("generated_questions")),
                "ui_message_sent": self.conversation_state.get("ui_message_sent", False)
            }
        }

    def load_conversation_from_messages(self, messages: List[dict]):
        """Daha önce kaydedilmiş mesajları yükle"""
        try:
            # SystemMessage'ı koru, diğerlerini temizle
            system_messages = [msg for msg in self.conversation_state["messages"] if isinstance(msg, SystemMessage)]
            self.conversation_state["messages"] = system_messages
            
            # Kaydedilmiş mesajları ekle
            for msg in messages:
                if msg.get("type") == "user":
                    self.conversation_state["messages"].append(HumanMessage(content=msg["content"]))
                elif msg.get("type") == "ai":
                    self.conversation_state["messages"].append(AIMessage(content=msg["content"]))
                    
        except Exception as e:
            print(f"❌ Load conversation error (Chat: {self.chat_id}): {e}")

    def reset_conversation(self):
        """Konuşmayı sıfırla"""
        self.conversation_state = ConversationState(
            messages=[SystemMessage(content=Config.SYSTEM_PROMPT)],
            current_intent="",
            needs_crew_ai=False,
            crew_ai_task="",
            user_context={},
            conversation_summary="",
            research_data={},
            websocket_callback=self.websocket_callback,
            pending_action="",
            research_completed=False,
            rag_context="",
            has_pdf_context=False,
            chat_id=self.chat_id or "",
            chat_manager=self.chat_manager,
            test_generation_requested=False,
            test_parameters={},
            generated_questions={},
            full_document_text="",
            awaiting_test_params=False,
            test_param_stage="start",
            partial_test_params={},
            test_params_ready=False,
            ui_message_sent=False  # YENİ: UI mesaj takibi sıfırla
        )

    def update_chat_manager(self, chat_manager):
        """Chat manager referansını güncelle"""
        self.chat_manager = chat_manager
        self.conversation_state["chat_manager"] = chat_manager

    def get_chat_id(self) -> str:
        """Mevcut chat ID'yi döner"""
        return self.chat_id or ""

    def set_chat_id(self, chat_id: str):
        """Chat ID'yi güncelle ve vector store'u yeniden başlat"""
        self.chat_id = chat_id
        self.conversation_state["chat_id"] = chat_id
        
        # Vector store'u yeni chat ID ile yeniden başlat
        self.vector_store = VectorStore(Config.VECTOR_STORE_PATH, chat_id=chat_id)
    
    def intent_analysis_node(self, state: ConversationState) -> ConversationState:
        last_message = state["messages"][-1].content.strip().lower()
        original_message = state["messages"][-1].content.strip()
        
        # Force web research flag'ini kontrol et
        force_web_research = state.get("force_web_research", False)
        
        print(f"🔍 Intent Analysis - Message: '{last_message[:50]}...', Force Web Research: {force_web_research}")
        
        # ÖNCE test parametresi bekleme durumunu kontrol et
        if state.get("awaiting_test_params"):
            # Test parametresi bekleniyor
            state["current_intent"] = "process_test_params"
            logger.info("✅ Intent detected: process_test_params (awaiting parameters)")
            return state
        
        # Test oluşturma komutları - GENİŞLETİLMİŞ LİSTE
        test_keywords = [
            "test oluştur", "test olustur", "soru hazırla", "sınav yap", "test yap", 
            "soru üret", "soru uret", "test hazırla", "quiz oluştur",
            "quiz olustur", "sınav oluştur", "sinav olustur", "test üret", "test uret",
            "sorular oluştur", "sorular olustur", "değerlendirme yap", "degerlendirme yap"
        ]
        
        if any(keyword in last_message for keyword in test_keywords):
            state["current_intent"] = "generate_test"
            state["test_generation_requested"] = True
            logger.info("✅ Intent detected: generate_test")
            return state

        # Araştırma tamamlandıysa ve research data varsa
        if state.get("research_completed", False) and state.get("research_data"):
            research_keywords = ["araştırma", "rapor", "bulgu", "sonuç", "detay", "açıkla", "anlatır mısın", 
                            "nedir", "nasıl", "ne demek", "anlat", "açıklayabilir", "daha fazla bilgi"]
            
            if any(keyword in last_message for keyword in research_keywords):
                state["current_intent"] = "research_question"
                state["needs_crew_ai"] = False
                print(f"✅ Intent: research_question")
                return state
        
        # ÖNCE web araştırması flag'ini kontrol et
        if force_web_research:
            state["current_intent"] = "web_research"
            state["crew_ai_task"] = original_message
            state["needs_crew_ai"] = True
            print(f"✅ Intent: web_research (forced)")
            return state
        
        # RAG kontrolü - DAHA SPESIFIK KRITERLER
        if Config.RAG_ENABLED:
            vector_stats = self.vector_store.get_stats()
            has_documents = vector_stats.get("total_documents", 0) > 0
            print(f"📚 PDF Documents: {has_documents}, Total: {vector_stats.get('total_documents', 0)}")
            
            if has_documents:
                # Direkt PDF referansları
                direct_pdf_references = [
                    "bu doküman", "bu dokuman", "bu dosya", "bu pdf", "bu rapor",
                    "bu belge", "yüklediğim", "yukledıgım", "gönderdiğim", "gonderdigim",
                    "dokümanı", "dokumanı", "dosyayı", "pdf'i", "raporu", "belgeyi",
                    "dosyada", "dosyadan", "pdf'te", "pdf'de", "belgede", "dökümanı", "dokumanı"
                ]
                
                # PDF içerik soruları
                pdf_content_questions = [
                    "özet", "özetle", "içerik", "içinde", "neler var", "ne diyor",
                    "bahsediyor", "yaziyor", "yazıyor", "anlatıyor", "gösteriyor",
                    "açıklıyor", "hangi konular", "nasıl açıklıyor", "konu başlıkları",
                    "başlıklar", "konular", "bölümler", "detaylar", "bilgiler", "içindekiler"
                ]
                
                # Dosya ismi referansları
                uploaded_files = vector_stats.get("documents", [])
                file_name_matches = []
                for doc in uploaded_files:
                    filename = doc.get("filename", "").lower()
                    if filename:
                        # Dosya adının ana kısmını al (uzantısız)
                        name_without_ext = filename.replace(".pdf", "").replace("-", " ").replace("_", " ")
                        name_parts = [part for part in name_without_ext.split() if len(part) > 3]
                        
                        # Bu dosya isminin parçaları mesajda geçiyor mu?
                        for part in name_parts:
                            if part in last_message:
                                file_name_matches.append(part)
                
                # RAG kullanım kriterleri
                should_use_rag = False
                reason = ""
                
                # 1. Direkt PDF referansı
                if any(ref in last_message for ref in direct_pdf_references):
                    should_use_rag = True
                    reason = "Direct PDF reference"
                
                # 2. **KONU BAŞLIĞI SORGUSU - GÜÇLENDİRİLMİŞ**
                elif any(kw in last_message for kw in ["konu başlıkları", "başlıklar", "konular", "bölümler", "içindekiler", "pdf deki", "pdfdeki", "pdf in", "pdfin", "başlık", "konu", "içerik"]):
                    should_use_rag = True
                    reason = "Table of contents/content request"
                
                # 3. Dosya ismi + içerik sorusu
                elif file_name_matches and any(q in last_message for q in pdf_content_questions):
                    should_use_rag = True
                    reason = f"File name match ({file_name_matches}) + content question"
                
                # 4. PDF kelimesi + içerik sorusu 
                elif ("pdf" in last_message or "doküman" in last_message or "dokuman" in last_message) and \
                     any(q in last_message for q in pdf_content_questions):
                    should_use_rag = True
                    reason = "PDF keyword + content question"
                
                print(f"🎯 RAG Analysis: should_use={should_use_rag}, reason='{reason}'")
                
                if should_use_rag:
                    state["current_intent"] = "rag_search"
                    state["crew_ai_task"] = original_message
                    state["needs_crew_ai"] = False
                    print(f"✅ Intent: rag_search")
                    return state
            
            # PDF mevcut değilse ve PDF referansı yapıldıysa uyar
            elif not has_documents and any(ref in last_message for ref in ["pdf", "doküman", "dokuman", "dosya", "belge"]):
                state["current_intent"] = "no_pdf_available"
                state["needs_crew_ai"] = False
                print(f"✅ Intent: no_pdf_available")
                return state
    
        # Web araştırması otomatik algılama - SADECE kesin durumlar
        research_keywords_explicit = ["araştır", "araştırma yap", "incele", "analiz et", "web'de ara", "internette ara"]
        
        detected_intent = "gemini"  # Varsayılan olarak gemini response
        task_topic = original_message
        
        # Açık araştırma talepleri
        for keyword in research_keywords_explicit:
            if keyword in last_message:
                detected_intent = "web_research"
                task_topic = original_message.replace(keyword, "", 1).strip()
                break
        
        state["current_intent"] = detected_intent
        state["crew_ai_task"] = task_topic
        state["needs_crew_ai"] = detected_intent == "web_research"
        
        print(f"✅ Final Intent: {detected_intent}")
        return state

    async def no_pdf_available_node(self, state: ConversationState) -> ConversationState:
        """PDF referansı yapıldı ama hiç PDF yüklenmemiş"""
        
        response = ("📄 Bu sohbette henüz herhangi bir PDF dokümanı yüklenmemiş. "
                "Bir doküman hakkında soru sorabilmem için önce PDF dosyanızı yüklemeniz gerekiyor.\n\n"
                "💡 **Nasıl PDF yükleyebilirim?**\n"
                "• Ekranın sol üstündeki **'PDF Yükle'** butonuna tıklayın\n"
                "• Dosyanızı seçin ve yükleme işlemini bekleyin\n"
                "• Yükleme tamamlandıktan sonra doküman içeriği hakkında sorular sorabilirsiniz!\n\n"
                "🔍 **PDF yükledikten sonra neler yapabilirim?**\n"
                "• Dokümanın özetini isteyebilirsiniz\n"
                "• Belirli konular hakkında sorular sorabilirsiniz\n"
                "• İçerikten alıntılar ve detaylar alabilirsiniz\n\n"
                f"📝 **Not:** Bu PDF'ler sadece bu sohbete ({self.chat_id}) özeldir.")
        
        state["messages"].append(AIMessage(content=response))
        return state

    async def crew_research_agent_node(self, state: ConversationState) -> ConversationState:
        try:
            research_query = state['crew_ai_task']
            if self.websocket_callback:
                await self.websocket_callback(json.dumps({
                    "type": "crew_research_start", 
                    "message": f"🤖 CrewAI Asenkron Multi-Agent sistemi '{research_query}' konusunu araştırıyor...", 
                    "timestamp": datetime.utcnow().isoformat(),
                    "chat_id": self.chat_id
                }))
            
            await asyncio.sleep(0.5)
            
            research_result = await self.crew_handler.research_workflow(research_query)
            
            if research_result and not research_result.get("error"):
                state["research_data"] = research_result
                state["research_completed"] = True
                
                if self.websocket_callback:
                    await self.websocket_callback(json.dumps({
                        "type": "crew_research_success", 
                        "message": f"✅ '{research_query}' araştırması başarıyla tamamlandı!", 
                        "timestamp": datetime.utcnow().isoformat(),
                        "chat_id": self.chat_id,
                        "research_data": {
                            "topic": research_result.get("topic", research_query),
                            "subtopics_count": len(research_result.get("detailed_research", [])),
                            "has_detailed_data": bool(research_result.get("detailed_research"))
                        }
                    }))
            else:
                error_msg = research_result.get("error", "Bilinmeyen araştırma hatası") if research_result else "Araştırma sonucu alınamadı"
                state["research_data"] = {"error": error_msg}
                
                if self.websocket_callback:
                    await self.websocket_callback(json.dumps({
                        "type": "crew_research_error", 
                        "message": f"❌ Araştırma hatası: {error_msg}", 
                        "timestamp": datetime.utcnow().isoformat(),
                        "chat_id": self.chat_id
                    }))
                
        except Exception as e:
            error_msg = f"CrewAI araştırma hatası: {str(e)}"
            state["research_data"] = {"error": error_msg}
            if self.websocket_callback:
                await self.websocket_callback(json.dumps({
                    "type": "crew_research_error", 
                    "message": f"❌ {error_msg}", 
                    "timestamp": datetime.utcnow().isoformat(),
                    "chat_id": self.chat_id
                }))
            print(f"❌ Crew research node error (Chat: {self.chat_id}): {e}")
            
        return state

    async def research_presentation_node(self, state: ConversationState) -> ConversationState:
        research_data = state.get("research_data", {})
        if "error" in research_data:
            response = f"Üzgünüm, araştırma sırasında bir hata oluştu: {research_data['error']}"
        else:
            final_report = research_data.get("final_report", "")
            response = final_report if final_report else "Araştırma tamamlandı, ancak bir sunum özeti oluşturulamadı."
        
        state["messages"].append(AIMessage(content=response))
        return state

    async def gemini_response_node(self, state: ConversationState) -> ConversationState:
        try:
            messages_for_llm = state["messages"]
            
            if state.get("has_pdf_context") and state.get("rag_context"):
                # RAG context'i kullan - GÜÇLENDİRİLMİŞ VE KEMİK GIBI SERT PROMPT
                user_question = messages_for_llm[-1].content
                rag_context = state["rag_context"]
                
                # Çok daha güçlü ve net bir prompt oluştur
                enhanced_prompt = f"""SEN BİR PDF ANALİZ ASİSTANISIN VE SAKİN GENEL BİLGİNİ KULLANMA!

KULLANICININ SORUSU: "{user_question}"

YÜKLENEN PDF DOKÜMANLARINDAN BULUNAN BİLGİLER:
{rag_context}

ZORUNLU CEVAPLAMA KURALLARI:
1. Yukarıdaki PDF dokümanlarından bulduğun bilgileri kullanarak cevap ver
2. "Yüklediğiniz PDF'te şu bilgiler var:" diye başla
3. Hangi dosyadan hangi bilgiyi aldığını belirt
4. Konu başlıkları soruluyorsa, PDF'ten çıkan başlıkları listele
5. PDF'te olmayan bilgiler hakkında "Bu konuda PDF'te bilgi yok" de
6. Asla "hangi PDF" diye sorma, zaten PDF'lerin listesi yukarıda var
7. Kesinlikle genel internet bilgisi kullanma, sadece PDF içeriği kullan

ÖRNEK YANIT FORMATI:
"📄 Yüklediğiniz PDF dokümanlarından şu bilgileri buldum:

• [Dosya adı]'nda şu konular var: [listele]
• [Belirli konu] hakkında: [PDF'ten alıntı]

Kaynak: [Dosya adı], Bölüm [X]"

ŞİMDİ BU KURALLARA UYARAK CEVAP VER:"""
                
                # Sadece system message + yeni prompt gönder
                contextual_messages = [
                    SystemMessage(content="Sen PDF analiz asistanısın. Sadece yüklenen dokümanlardan bilgi ver."),
                    HumanMessage(content=enhanced_prompt)
                ]
                
                response = await self.llm.ainvoke(contextual_messages)
                
            elif state.get("current_intent") == "research_question" and state.get("research_data"):
                research_context = self.format_research_context(state["research_data"])
                
                user_question = messages_for_llm[-1].content
                
                contextual_prompt = f"""
Kullanıcının sorusu: {user_question}

Aşağıda CrewAI Multi-Agent sistemi ile yapılan bir araştırmanın sonuçları var. 
Bu araştırma verilerini kullanarak kullanıcının sorusuna doğru ve detaylı bir şekilde cevap ver.

ARAŞTIRMA VERİLERİ:
{research_context}

Cevabında:
1. Araştırma verilerinden elde edilen bilgileri kullan
2. Spesifik detayları belirt
3. Kaynaklı bilgiler ver
4. Eğer araştırmada olmayan bir şey soruyorsa, bunu belirt
5. Gerekirse daha detaylı açıklama öner

Kullanıcı dostu ve bilgilendirici bir ton kullan.
"""
                
                contextual_messages = messages_for_llm[:-1] + [HumanMessage(content=contextual_prompt)]
                response = await self.llm.ainvoke(contextual_messages)
                
            else:
                # Normal Gemini response
                if messages_for_llm and "araştırma başlatılmadı" in messages_for_llm[-1].content:
                    messages_for_llm = messages_for_llm[:-1]
                response = await self.llm.ainvoke(messages_for_llm)
            
            state["messages"].append(AIMessage(content=response.content))
            
        except Exception as e:
            error_message = f"Üzgünüm, bir hata oluştu: {str(e)}"
            state["messages"].append(AIMessage(content=error_message))
            print(f"❌ Gemini response error (Chat: {self.chat_id}): {e}")
        
        return state
    
    def _get_full_text_from_vector_store(self) -> str:
        """Vektör veritabanındaki tüm parçaları birleştirerek tam metni alır."""
        try:
            all_docs = self.vector_store.collection.get(include=["documents"])
            if not all_docs or not all_docs.get('documents'):
                return ""
            full_text = "\n\n".join(all_docs['documents'])
            logger.info(f"📄 Vektör deposundan {len(full_text)} karakterlik tam metin alındı.")
            return full_text
        except Exception as e:
            logger.error(f"❌ Vektör deposundan tam metin alınamadı: {e}")
            return ""

    async def check_document_for_test_node(self, state: ConversationState) -> ConversationState:
        """Test üretimi için döküman olup olmadığını kontrol eder."""
        logger.info("STEP: Checking for document to generate test...")
        
        # Chat ID'yi kullanarak vektör deposunda arama yap
        chat_id = state.get("chat_id") or self.chat_id
        if not chat_id:
            logger.warning("Chat ID bulunamadı, test üretimi yapılamaz.")
            state["messages"].append(AIMessage(content="Üzgünüm, chat oturumu bulunamadı. Lütfen sayfayı yenileyin."))
            state["full_document_text"] = ""
            return state
        
        # Vektör deposundan tam metni al
        full_text = self._get_full_text_from_vector_store()
        
        if not full_text:
            # Vector store boşsa, kullanıcıya doküman yüklemesini söyle
            logger.warning(f"Chat {chat_id} için hiç doküman bulunamadı.")
            
            # Vector store stats'ını kontrol et
            vector_stats = self.vector_store.get_stats()
            logger.info(f"Vector store stats: {vector_stats}")
            
            error_message = ("📚 Test oluşturmak için önce bir doküman yüklemeniz gerekiyor.\n\n"
                           "💡 **Nasıl doküman yükleyebilirim?**\n"
                           "• Sol üstteki **'PDF Yükle'** butonuna tıklayın\n"
                           "• PDF dosyanızı seçin (metin, resim, el yazısı desteklenir)\n"
                           "• Yükleme tamamlandıktan sonra 'test oluştur' yazabilirsiniz\n\n"
                           f"📊 **Mevcut durum:** {vector_stats.get('total_documents', 0)} doküman, "
                           f"{vector_stats.get('total_chunks', 0)} metin parçası")
            
            state["messages"].append(AIMessage(content=error_message))
            state["full_document_text"] = ""
        else:
            logger.info(f"✅ Test için doküman bulundu: {len(full_text)} karakter")
            state["full_document_text"] = full_text
            
        return state

    async def ask_test_parameters_node(self, state: ConversationState) -> ConversationState:
        """Kullanıcıdan test parametrelerini almak için etkileşimli düğüm - TEK SEFERDE UI GÖNDERİM"""
        try:
            current_stage = state.get("test_param_stage", "question_types")
            
            # SORUN 1: Çoklu UI mesajları önlemek için kontrol ekle
            if state.get("ui_message_sent"):
                logger.info("⚠️ UI mesajı zaten gönderildi, tekrar gönderilmiyor")
                return state
            
            # İlk kez çağrılıyorsa, parametreleri sıfırla
            if not state.get("awaiting_test_params"):
                state["awaiting_test_params"] = True
                state["test_param_stage"] = "question_types"
                state["partial_test_params"] = {}
                state["test_params_ready"] = False
                current_stage = "question_types"
                
                logger.info("🎯 Test parametreleri isteniyor - ilk aşama başlatılıyor")
            
            # UI mesajını sadece bir kez gönder
            state["ui_message_sent"] = True
            
            if current_stage == "question_types":
                # Soru türleri seçim mesajı gönder
                question_types_message = {
                    "type": "test_parameters_request",
                    "stage": "question_types",
                    "content": "🎯 **Test Oluşturma Ayarları**\n\n**1. Hangi soru türlerini ve kaçar tane istiyorsunuz?**\n\nHer soru türü için 0-20 arası sayı belirleyebilirsiniz:",
                    "options": [
                        {
                            "id": "coktan_secmeli", 
                            "label": "Çoktan Seçmeli Sorular", 
                            "description": "A, B, C, D şıklı sorular",
                            "selected": True,
                            "default_count": 5,
                            "max_count": 20
                        },
                        {
                            "id": "klasik", 
                            "label": "Klasik (Açık Uçlu) Sorular", 
                            "description": "Uzun cevap gerektiren sorular",
                            "selected": True,
                            "default_count": 3,
                            "max_count": 10
                        },
                        {
                            "id": "bosluk_doldurma", 
                            "label": "Boşluk Doldurma Soruları", 
                            "description": "Eksik kelime/kavram tamamlama",
                            "selected": False,
                            "default_count": 2,
                            "max_count": 15
                        },
                        {
                            "id": "dogru_yanlis", 
                            "label": "Doğru-Yanlış Soruları", 
                            "description": "İki seçenekli doğruluk soruları",
                            "selected": False,
                            "default_count": 5,
                            "max_count": 20
                        }
                    ],
                    "next_button_text": "Devam Et",
                    "chat_id": self.chat_id
                }
                
                # AI mesajı ekle (kullanıcıya görünür olan kısım)
                ui_message = ("🎯 **Test Ayarları**\n\n"
                            "Test oluşturmak için önce birkaç ayar yapalım:\n\n"
                            "**1. Soru Türleri:** Hangi türde sorular istiyorsunuz?\n"
                            "**2. Zorluk Seviyesi:** Kolay, Orta veya Zor?\n"
                            "**3. Öğrenci Seviyesi:** Hedef kitle hangi seviyede?\n\n"
                            "Yukarıdaki menüden seçimlerinizi yapın ⬆️")
                
                state["messages"].append(AIMessage(content=ui_message))
                
            elif current_stage == "difficulty":
                # Zorluk seviyesi mesajı gönder
                question_types_message = {
                    "type": "test_parameters_request",
                    "stage": "difficulty",
                    "content": "**2. Testin zorluk seviyesini seçin:**",
                    "options": [
                        {"id": "kolay", "label": "Kolay", "description": "Temel kavramlar ve basit uygulamalar", "selected": False},
                        {"id": "orta", "label": "Orta", "description": "Orta seviye analiz ve uygulama", "selected": True},
                        {"id": "zor", "label": "Zor", "description": "İleri seviye analiz ve sentez", "selected": False}
                    ],
                    "next_button_text": "Devam Et",
                    "chat_id": self.chat_id
                }
                
            elif current_stage == "student_level":
                # Öğrenci seviyesi mesajı gönder
                question_types_message = {
                    "type": "test_parameters_request",
                    "stage": "student_level",
                    "content": "**3. Hedef öğrenci seviyesini seçin:**",
                    "options": [
                        {"id": "ortaokul", "label": "Ortaokul (5-8. Sınıf)", "description": "Temel kavramlar ve basit açıklamalar", "selected": False},
                        {"id": "lise", "label": "Lise (9-12. Sınıf)", "description": "Detaylı analiz ve kavramsal bağlantılar", "selected": True},
                        {"id": "universite", "label": "Üniversite", "description": "İleri seviye akademik içerik", "selected": False},
                        {"id": "yetiskin", "label": "Yetişkin Eğitimi", "description": "Pratik odaklı öğrenme", "selected": False}
                    ],
                    "next_button_text": "Testi Oluştur",
                    "chat_id": self.chat_id
                }
            
            # WebSocket mesajını gönder
            if self.websocket_callback:
                await self.websocket_callback(json.dumps(question_types_message))
                logger.info(f"📤 Test parametreleri UI mesajı gönderildi - Stage: {current_stage}")
                
        except Exception as e:
            error_message = f"Üzgünüm, test parametreleri alınırken bir hata oluştu: {str(e)}"
            state["messages"].append(AIMessage(content=error_message))
            logger.error(f"❌ Ask test parameters error (Chat: {self.chat_id}): {e}")
        
        return state

    async def process_test_parameters_node(self, state: ConversationState) -> ConversationState:
        """Kullanıcıdan gelen test parametrelerini işler - SORUN 2 DÜZELTİLMİŞ"""
        try:
            # Eğer test parametresi beklemiyorsak, bu düğümün çalışmaması gerekir.
            if not state.get("awaiting_test_params"):
                logger.info("❌ Test parametreleri beklenmiyor, normal sohbete devam ediliyor.")
                state["current_intent"] = "gemini" 
                return state

            # Mevcut aşamayı ve önceden doldurulmuş parametreleri state'ten al.
            current_stage = state.get("test_param_stage", "question_types")
            all_params = state.get("partial_test_params", {})
            
            logger.info(f"🔄 Parametreler işleniyor - Aşama: {current_stage}, Mevcut Params: {all_params}")

            # SORUN 2: UI mesaj flag'ini sıfırla ki bir sonraki aşamada UI gönderilebilsin
            state["ui_message_sent"] = False

            # Gelen parametrelere göre bir sonraki aşamayı belirle
            if current_stage == "question_types":
                # Arayüzden "soru_turleri" verisi geldi mi diye kontrol et.
                if "soru_turleri" in all_params:
                    state["test_param_stage"] = "difficulty"
                    logger.info(f"✅ Soru türleri işlendi: {all_params['soru_turleri']}, bir sonraki aşama: 'difficulty'")
                else:
                    # Gerekli parametre yoksa, bir hata olduğunu varsay ve döngüyü kır.
                    logger.warning("⚠️ 'soru_turleri' parametresi state içinde bulunamadı.")
                    state["awaiting_test_params"] = False
                    state["messages"].append(AIMessage(content="Test parametreleri alınırken bir sorun oluştu. Lütfen tekrar deneyin."))
                    return state

            elif current_stage == "difficulty":
                # Arayüzden "zorluk_seviyesi" verisi geldi mi diye kontrol et.
                if "zorluk_seviyesi" in all_params:
                    state["test_param_stage"] = "student_level"
                    logger.info(f"✅ Zorluk seviyesi işlendi: {all_params['zorluk_seviyesi']}, bir sonraki aşama: 'student_level'")
                else:
                    logger.warning("⚠️ 'zorluk_seviyesi' parametresi state içinde bulunamadı.")
                    state["awaiting_test_params"] = False
                    state["messages"].append(AIMessage(content="Test parametreleri alınırken bir sorun oluştu. Lütfen tekrar deneyin."))
                    return state
                    
            elif current_stage == "student_level":
                # Arayüzden "ogrenci_seviyesi" verisi geldi mi diye kontrol et.
                if "ogrenci_seviyesi" in all_params:
                    # Tüm parametreler tamamlandı. Test üretimine geçilebilir.
                    state["test_param_stage"] = "complete"
                    state["test_params_ready"] = True
                    state["awaiting_test_params"] = False
                    
                    # SORUN 2: Parametreleri doğru formatta kaydet
                    final_params = {
                        "soru_turleri": all_params.get("soru_turleri", {}),
                        "zorluk_seviyesi": all_params.get("zorluk_seviyesi", "orta"),
                        "ogrenci_seviyesi": all_params.get("ogrenci_seviyesi", "lise")
                    }
                    
                    state["test_parameters"] = final_params
                    state["partial_test_params"] = final_params  # İkisini de güncelle
                    
                    logger.info(f"🎯 Tüm test parametreleri tamamlandı ve kaydedildi: {final_params}")
                    
                    # Kullanıcıya parametrelerin alındığını bildiren mesaj
                    total_questions = sum(final_params["soru_turleri"].values()) if final_params["soru_turleri"] else 8
                    
                    confirmation_message = (
                        f"✅ **Test parametreleri ayarlandı!**\n\n"
                        f"🎯 **Soru türleri:** "
                    )
                    
                    # Soru türlerini güzel formatta göster
                    soru_turleri_text = []
                    for tur, sayi in final_params["soru_turleri"].items():
                        if sayi > 0:
                            tur_adi = {
                                "coktan_secmeli": "Çoktan Seçmeli",
                                "klasik": "Klasik (Açık Uçlu)", 
                                "bosluk_doldurma": "Boşluk Doldurma",
                                "dogru_yanlis": "Doğru-Yanlış"
                            }.get(tur, tur)
                            soru_turleri_text.append(f"{tur_adi}: {sayi}")
                    
                    confirmation_message += ", ".join(soru_turleri_text)
                    confirmation_message += (
                        f"\n📊 **Zorluk:** {final_params['zorluk_seviyesi'].title()}"
                        f"\n🎓 **Seviye:** {final_params['ogrenci_seviyesi'].title()}"
                        f"\n🔢 **Toplam soru:** {total_questions}\n\n"
                        f"🔄 Test sorularını oluşturuyorum, bu işlem 3-5 dakika sürebilir..."
                    )
                    
                    state["messages"].append(AIMessage(content=confirmation_message))
                    
                else:
                    logger.warning("⚠️ 'ogrenci_seviyesi' parametresi state içinde bulunamadı.")
                    state["awaiting_test_params"] = False
                    state["messages"].append(AIMessage(content="Test parametreleri alınırken bir sorun oluştu. Lütfen tekrar deneyin."))
                    return state
            
            # Bu düğüm artık UI göndermez. Sadece state'i günceller.
            # Yönlendirme (routing) işlemi, grafikteki bir sonraki kenar tarafından yapılır.
            return state
        
        except Exception as e:
            error_message = f"Test parametreleri işlenirken kritik bir hata oluştu: {str(e)}"
            logger.error(f"❌ Process test parameters error: {e}", exc_info=True)
            state["messages"].append(AIMessage(content=error_message))
            state["awaiting_test_params"] = False
            state["test_params_ready"] = False
            return state

    async def generate_test_questions_node(self, state: ConversationState) -> ConversationState:
        """CrewAI kullanarak test sorularını üretir - SORUN 2 DÜZELTİLMİŞ"""
        logger.info("🚀 STEP: Generating test questions with CrewAI...")
        document_content = state["full_document_text"]
        
        if not document_content:
            error_msg = "Doküman içeriği bulunamadı, test oluşturulamıyor."
            logger.error(f"❌ {error_msg}")
            state["messages"].append(AIMessage(content=error_msg))
            return state
        
        logger.info(f"📄 Doküman uzunluğu: {len(document_content)} karakter")
        
        test_params = state.get("test_parameters", {})
        
        if not test_params:
            error_msg = "Test parametreleri bulunamadı. Lütfen tekrar 'test oluştur' yazın."
            logger.error(f"❌ {error_msg}")
            state["messages"].append(AIMessage(content=error_msg))
            return state
        
        # Parametreleri doğru şekilde çıkar
        question_types = test_params.get("soru_turleri", {'coktan_secmeli': 5, 'klasik': 3})
        difficulty_level = test_params.get("zorluk_seviyesi", "orta")
        student_level = test_params.get("ogrenci_seviyesi", "lise")
        
        # SORUN 2: Toplam soru sayısını doğru hesapla
        total_questions = sum(question_types.values()) if isinstance(question_types, dict) else 8
        
        preferences = {
            "soru_turleri": question_types,
            "zorluk_seviyesi": difficulty_level,
            "ogrenci_seviyesi": student_level,
            "toplam_soru": total_questions
        }
        
        logger.info(f"🎯 DOĞRU Test Parametreleri: {preferences}")
        
        if self.websocket_callback:
            await self.websocket_callback(json.dumps({
                "type": "system",
                "content": f"🧠 {total_questions} soruluk test hazırlıyorum... CrewAI sistemini başlatıyorum.",
                "timestamp": datetime.utcnow().isoformat(),
                "chat_id": self.chat_id
            }))
        
        try:
            # CrewAI'yi asenkron olarak çalıştır
            logger.info("🤖 CrewAI test sistemi başlatılıyor...")
            
            generated_data = await self.test_crew.generate_questions(document_content, preferences)
            logger.info(f"✅ CrewAI test sistemi tamamlandı. Sonuç: {type(generated_data)}")
            
            # Sonuç kontrolü ve hata yönetimi
            if generated_data and not generated_data.get("error"):
                state["generated_questions"] = generated_data
                logger.info("✅ Test soruları başarıyla oluşturuldu")
                
                # Başarı mesajı gönder
                if self.websocket_callback:
                    await self.websocket_callback(json.dumps({
                        "type": "crew_progress",
                        "message": "🎉 Test soruları başarıyla oluşturuldu!",
                        "timestamp": datetime.utcnow().isoformat(),
                        "chat_id": self.chat_id
                    }))
            else:
                error_msg = generated_data.get("error", "Test oluşturma sırasında bilinmeyen hata") if generated_data else "CrewAI'den yanıt alınamadı"
                logger.error(f"❌ CrewAI hatası: {error_msg}")
                state["generated_questions"] = {"error": error_msg}
                
                # Hata mesajı gönder
                if self.websocket_callback:
                    await self.websocket_callback(json.dumps({
                        "type": "error",
                        "message": f"❌ Test oluşturma hatası: {error_msg}",
                        "timestamp": datetime.utcnow().isoformat(),
                        "chat_id": self.chat_id
                    }))
                
        except Exception as e:
            error_msg = f"CrewAI test oluşturma hatası: {str(e)}"
            logger.error(f"❌ {error_msg}")
            state["generated_questions"] = {"error": error_msg}
            
            # Detaylı hata bilgisi gönder
            if self.websocket_callback:
                await self.websocket_callback(json.dumps({
                    "type": "error",
                    "message": f"Test oluşturma hatası: {error_msg}",
                    "timestamp": datetime.utcnow().isoformat(),
                    "chat_id": self.chat_id
                }))
        
        # Her durumda state'i güncelle - bu kritik!
        logger.info("📋 Test oluşturma node'u tamamlandı, present_test_results'a geçiliyor...")
        return state

    async def present_test_results_node(self, state: ConversationState) -> ConversationState:
        """Test sonuçlarını kullanıcıya sunar"""
        logger.info("🎯 STEP: Presenting test results...")
        
        generated_questions = state.get("generated_questions", {})
        
        if "error" in generated_questions:
            error_msg = f"❌ Test oluşturma hatası: {generated_questions['error']}"
            logger.error(error_msg)
            state["messages"].append(AIMessage(content=error_msg))
            return state
        
        if not generated_questions:
            error_msg = "❌ Test soruları oluşturulamadı - boş sonuç."
            logger.error(error_msg)
            state["messages"].append(AIMessage(content=error_msg))
            return state
        
        try:
            # Test parametrelerinden bilgileri al - DOĞRU KAYNAK
            test_params = state.get("partial_test_params", {})
            if not test_params:
                test_params = state.get("test_parameters", {})
                
            question_types = test_params.get("soru_turleri", {})
            total_questions = sum(question_types.values()) if question_types else 0
            
            # Test başarı mesajı oluştur
            success_message = f"🎉 **Test Başarıyla Oluşturuldu!**\n\n"
            success_message += f"📊 **Test Detayları:**\n"
            success_message += f"• **Toplam Soru:** {total_questions}\n"
            success_message += f"• **Zorluk:** {test_params.get('zorluk_seviyesi', 'orta').title()}\n"
            success_message += f"• **Seviye:** {test_params.get('ogrenci_seviyesi', 'lise').title()}\n\n"
            
            # Soru türleri detayı
            if question_types:
                success_message += f"🎯 **Soru Dağılımı:**\n"
                type_labels = {
                    "coktan_secmeli": "Çoktan Seçmeli",
                    "klasik": "Klasik (Açık Uçlu)",
                    "bosluk_doldurma": "Boşluk Doldurma",
                    "dogru_yanlis": "Doğru-Yanlış"
                }
                
                for type_id, count in question_types.items():
                    if count > 0:
                        type_name = type_labels.get(type_id, type_id)
                        success_message += f"• **{type_name}:** {count} soru\n"
                
                success_message += "\n"
            
            success_message += f"🚀 **Hazır!** Aşağıdaki **'Testi Çöz'** butonuna tıklayarak testinizi başlatabilirsiniz.\n"
            success_message += f"📝 Test sonuçlarınız otomatik olarak değerlendirilecek ve eksik konularınız belirlenecek."
            
            # Test sonuçlarını WebSocket üzerinden gönder
            if self.websocket_callback:
                test_message = {
                    "type": "test_generated",
                    "content": success_message,
                    "questions": generated_questions,
                    "test_parameters": test_params,
                    "timestamp": datetime.utcnow().isoformat(),
                    "chat_id": self.chat_id
                }
                
                await self.websocket_callback(json.dumps(test_message))
                logger.info("✅ Test sonuçları WebSocket üzerinden gönderildi")
            
            # State'e de mesajı ekle
            state["messages"].append(AIMessage(content=success_message))
            
            # Test tamamlandıktan sonra state'i temizle
            state["awaiting_test_params"] = False
            state["test_param_stage"] = "start"
            state["test_params_ready"] = False
            state["partial_test_params"] = {}
            state["ui_message_sent"] = False  # UI mesaj flag'ini temizle
            
        except Exception as e:
            error_msg = f"Test sonuçları sunulurken hata oluştu: {str(e)}"
            logger.error(f"❌ {error_msg}")
            state["messages"].append(AIMessage(content=error_msg))
        
        return state