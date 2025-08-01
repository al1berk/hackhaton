# src/core/conversation.py

from typing import TypedDict, List, Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
import asyncio
import json
from datetime import datetime

# --- GÜNCELLENMİŞ IMPORT YOLLARI ---
from core.config import Config
from agents.research_crew import AsyncCrewAIA2AHandler
# YENI SATIR 15: Vector store import'u eklendi
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
    # YENI SATIRLAR 27-28: RAG ile ilgili state alanları eklendi
    rag_context: str
    has_pdf_context: bool

class AsyncLangGraphDialog:
    def __init__(self, websocket_callback=None):
        self.llm = ChatGoogleGenerativeAI(
            model=Config.GEMINI_MODEL,
            google_api_key=Config.GOOGLE_API_KEY,
            temperature=Config.GEMINI_TEMPERATURE,
        )
        
        self.websocket_callback = websocket_callback
        self.crew_handler = AsyncCrewAIA2AHandler(websocket_callback)
        # YENI SATIRLAR 40-41: Vector store başlatılması
        self.vector_store = VectorStore(Config.VECTOR_STORE_PATH)
        
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
            # YENI SATIRLAR 54-55: RAG state başlangıç değerleri
            rag_context="",
            has_pdf_context=False
        )
    
    def create_conversation_graph(self):
        workflow = StateGraph(ConversationState)
        
        workflow.add_node("handle_confirmation", self.handle_confirmation_node)
        workflow.add_node("intent_analysis", self.intent_analysis_node)
        workflow.add_node("rag_search", self.rag_search_node)
        workflow.add_node("no_pdf_available", self.no_pdf_available_node)  # YENİ NODE
        workflow.add_node("crew_research_agent", self.crew_research_agent_node)
        workflow.add_node("research_presentation", self.research_presentation_node)
        workflow.add_node("gemini_response", self.gemini_response_node)
        workflow.add_node("ask_confirmation", self.ask_confirmation_node)
        workflow.add_node("research_followup", self.research_followup_node)
        
        workflow.set_conditional_entry_point(
            self.route_initial_input,
            {"continue_to_intent": "intent_analysis", "handle_confirmation": "handle_confirmation"}
        )
        
        # Güncellenmiş routing
        workflow.add_conditional_edges(
            "intent_analysis",
            self.should_call_crew_or_ask_or_rag_or_no_pdf,  # YENİ FUNCTION
            {
                "crew_research": "crew_research_agent", 
                "ask_confirmation": "ask_confirmation", 
                "rag_search": "rag_search", 
                "no_pdf_available": "no_pdf_available",  # YENİ ROUTE
                "gemini": "gemini_response"
            }
        )

        workflow.add_conditional_edges(
            "handle_confirmation",
            self.decide_after_confirmation,
            {"start_research": "crew_research_agent", "cancel": "gemini_response"}
        )
        
        workflow.add_edge("rag_search", "gemini_response")
        workflow.add_edge("no_pdf_available", END)  # YENİ EDGE
        workflow.add_edge("crew_research_agent", "research_presentation")
        workflow.add_edge("research_presentation", "research_followup")
        workflow.add_edge("research_followup", END)
        workflow.add_edge("gemini_response", END)
        workflow.add_edge("ask_confirmation", END)

        return workflow.compile()

# Güncellenmiş routing function
    def should_call_crew_or_ask_or_rag_or_no_pdf(self, state: ConversationState) -> Literal["crew_research", "ask_confirmation", "rag_search", "no_pdf_available", "gemini"]:
        intent = state["current_intent"]
        if intent in ["web_research", "ask_confirmation", "rag_search", "no_pdf_available"]:
            return intent
        return "gemini"

    def route_initial_input(self, state: ConversationState) -> Literal["continue_to_intent", "handle_confirmation"]:
        if state.get("pending_action"):
            return "handle_confirmation"
        return "continue_to_intent"

    def handle_confirmation_node(self, state: ConversationState) -> ConversationState:
        last_message = state["messages"][-1].content.lower()
        
        if any(keyword in last_message for keyword in ["evet", "onayla", "başlat", "yap"]):
            state["current_intent"] = state["pending_action"]
            state["needs_crew_ai"] = True
        else:
            state["current_intent"] = "general_chat"
            state["needs_crew_ai"] = False
            state["messages"].append(AIMessage(content="Anlaşıldı, araştırma başlatılmadı. Size başka nasıl yardımcı olabilirim?"))

        state["pending_action"] = ""
        return state

    def decide_after_confirmation(self, state: ConversationState) -> Literal["start_research", "cancel"]:
        if state["needs_crew_ai"]:
            return "start_research"
        return "cancel"

    async def ask_confirmation_node(self, state: ConversationState) -> ConversationState:
        topic = state["crew_ai_task"]
        message_content = f"'{topic}' konusu hakkında kapsamlı bir web araştırması başlatmamı onaylıyor musunuz?"
        
        if self.websocket_callback:
            await self.websocket_callback(json.dumps({
                "type": "confirmation_request", 
                "content": message_content, 
                "timestamp": datetime.utcnow().isoformat()
            }))
        
        state["pending_action"] = "web_research"
        return state

    # YENI FONKSIYON: RAG search node'u (SATIRLAR 127-154)
    async def rag_search_node(self, state: ConversationState) -> ConversationState:
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
                            "message": f"📚 {len(relevant_results)} ilgili doküman parçası bulundu",
                            "timestamp": datetime.utcnow().isoformat()
                        }))
                else:
                    state["rag_context"] = ""
                    state["has_pdf_context"] = False
            else:
                state["rag_context"] = ""
                state["has_pdf_context"] = False
                
        except Exception as e:
            print(f"❌ RAG search error: {e}")
            state["rag_context"] = ""
            state["has_pdf_context"] = False
        
        return state

    def intent_analysis_node(self, state: ConversationState) -> ConversationState:
        last_message = state["messages"][-1].content.strip().lower()
        original_message = state["messages"][-1].content.strip()
        
        # Araştırma tamamlandıysa ve research data varsa
        if state.get("research_completed", False) and state.get("research_data"):
            research_keywords = ["araştırma", "rapor", "bulgu", "sonuç", "detay", "açıkla", "anlatır mısın", 
                            "nedir", "nasıl", "ne demek", "anlat", "açıklayabilir", "daha fazla bilgi"]
            
            if any(keyword in last_message for keyword in research_keywords):
                state["current_intent"] = "research_question"
                state["needs_crew_ai"] = False
                return state
        
        # **ÖNCE RAG KONTROL ET** - PDF dosyası referansları
        if Config.RAG_ENABLED:
            # PDF dosyası mevcut mu kontrol et
            vector_stats = self.vector_store.get_stats()
            has_documents = vector_stats.get("total_documents", 0) > 0
            
            # PDF referans kelimeleri
            pdf_reference_keywords = [
                "doküman", "dokuman", "dosya", "pdf", "rapor", "belge", 
                "metin", "kitap", "makale", "döküman", "dökuman"
            ]
            
            # Dosya ismi referansları (yüklenen PDF'leri kontrol et)
            uploaded_files = vector_stats.get("documents", [])
            file_references = []
            for doc in uploaded_files:
                filename = doc.get("filename", "").lower()
                if filename:
                    # Dosya adının parçalarını ekle
                    name_parts = filename.replace(".pdf", "").replace("-", " ").replace("_", " ").split()
                    file_references.extend(name_parts)
            
            # PDF içeriği ile ilgili sorular
            pdf_content_keywords = [
                "içinde", "neler var", "özet", "özetle", "içerik", "bahsediyor", 
                "yaziyor", "yazıyor", "anlatıyor", "gösteriyor", "içeriği nedir",
                "hakkında bilgi", "ne diyor", "nasıl açıklıyor", "hangi konular"
            ]
            
            # Bu doküman, bu dosya gibi direkt referanslar
            direct_references = [
                "bu doküman", "bu dokuman", "bu dosya", "bu pdf", "bu rapor",
                "bu belge", "yüklediğim", "yukledıgım", "gönderdiğim", "gonderdigim"
            ]
            
            # RAG için uygun mu kontrol et
            should_use_rag = False
            
            # 1. Direkt PDF referansı var mı?
            if any(ref in last_message for ref in direct_references):
                should_use_rag = True
            
            # 2. PDF dosya ismi referansı var mı?
            elif any(file_ref in last_message for file_ref in file_references if len(file_ref) > 2):
                should_use_rag = True
            
            # 3. PDF referans kelimesi + içerik sorusu kombinasyonu
            elif (any(pdf_ref in last_message for pdf_ref in pdf_reference_keywords) and 
                any(content_q in last_message for content_q in pdf_content_keywords)):
                should_use_rag = True
            
            # 4. Genel sorular ama PDF mevcut
            elif has_documents:
                general_question_keywords = [
                    "nedir", "nasıl", "ne demek", "açıkla", "anlat", "bilgi ver",
                    "kimdir", "hangi", "neden", "niçin", "ne zaman", "nerede",
                    "özet", "özetle", "içerik", "hakkında"
                ]
                
                # Genel soru + PDF mevcut = RAG'a yönlendir
                if any(keyword in last_message for keyword in general_question_keywords):
                    should_use_rag = True
            
            # RAG kullanılacaksa
            if should_use_rag and has_documents:
                state["current_intent"] = "rag_search"
                state["crew_ai_task"] = original_message
                state["needs_crew_ai"] = False
                return state
            
            # PDF mevcut değilse ve PDF referansı yapıldıysa uyar
            elif should_use_rag and not has_documents:
                state["current_intent"] = "no_pdf_available"
                state["needs_crew_ai"] = False
                return state
    
        # Web araştırması kontrolleri
        research_keywords_strong = ["araştır", "araştırma yap", "incele", "analiz et", "web'de ara", "internette ara"]
        research_keywords_weak = ["hakkında bilgi", "son gelişmeler", "güncel", "haberler"]
        
        detected_intent = "general_chat"
        task_topic = original_message
        
        # Güçlü araştırma ifadeleri
        for keyword in research_keywords_strong:
            if keyword in last_message:
                detected_intent = "web_research"
                task_topic = original_message.replace(keyword, "", 1).strip()
                break
        
        # Zayıf araştırma ifadeleri - onay iste
        if detected_intent != "web_research":
            if len(last_message.split()) > 5 and any(keyword in last_message for keyword in research_keywords_weak):
                # Ama PDF referansı yoksa onay iste
                if not any(pdf_ref in last_message for pdf_ref in ["doküman", "dokuman", "dosya", "pdf"]):
                    detected_intent = "ask_confirmation"

        state["current_intent"] = detected_intent
        state["crew_ai_task"] = task_topic
        state["needs_crew_ai"] = detected_intent == "web_research"
        
        return state

    # GÜNCELLENEN FONKSIYON: should_call_crew_or_ask fonksiyonu genişletildi (SATIRLAR 207-209)
    def should_call_crew_or_ask_or_rag(self, state: ConversationState) -> Literal["crew_research", "ask_confirmation", "rag_search", "gemini"]:
        intent = state["current_intent"]
        if intent in ["web_research", "ask_confirmation", "rag_search"]:
            return intent
        return "gemini"
    async def no_pdf_available_node(self, state: ConversationState) -> ConversationState:
        """PDF referansı yapıldı ama hiç PDF yüklenmemiş"""
        
        response = ("📄 Henüz herhangi bir PDF dokümanı yüklenmemiş. "
                "Bir doküman hakkında soru sorabilmem için önce PDF dosyanızı yüklemeniz gerekiyor.\n\n"
                "💡 **Nasıl PDF yükleyebilirim?**\n"
                "• Ekranın sol üstündeki **'PDF Yükle'** butonuna tıklayın\n"
                "• Dosyanızı seçin ve yükleme işlemini bekleyin\n"
                "• Yükleme tamamlandıktan sonra doküman içeriği hakkında sorular sorabilirsiniz!\n\n"
                "🔍 **PDF yükledikten sonra neler yapabilirim?**\n"
                "• Dokümanın özetini isteyebilirsiniz\n"
                "• Belirli konular hakkında sorular sorabilirsiniz\n"
                "• İçerikten alıntılar ve detaylar alabilirsiniz")
        
        state["messages"].append(AIMessage(content=response))
        return state

    async def crew_research_agent_node(self, state: ConversationState) -> ConversationState:
        try:
            research_query = state['crew_ai_task']
            if self.websocket_callback:
                await self.websocket_callback(json.dumps({
                    "type": "crew_research_start", 
                    "message": f"🤖 CrewAI Asenkron Multi-Agent sistemi '{research_query}' konusunu araştırıyor...", 
                    "timestamp": datetime.utcnow().isoformat()
                }))
            
            # Araştırma başlangıcında kısa bir bekleme
            await asyncio.sleep(0.5)
            
            # CrewAI araştırmasını başlat
            research_result = await self.crew_handler.research_workflow(research_query)
            
            # Sonuçları kontrol et
            if research_result and not research_result.get("error"):
                state["research_data"] = research_result
                state["research_completed"] = True
                
                if self.websocket_callback:
                    await self.websocket_callback(json.dumps({
                        "type": "crew_research_success", 
                        "message": f"✅ '{research_query}' araştırması başarıyla tamamlandı!", 
                        "timestamp": datetime.utcnow().isoformat(),
                        "research_data": {
                            "topic": research_result.get("topic", research_query),
                            "subtopics_count": len(research_result.get("detailed_research", [])),
                            "has_detailed_data": bool(research_result.get("detailed_research"))
                        }
                    }))
            else:
                # Hata durumu
                error_msg = research_result.get("error", "Bilinmeyen araştırma hatası") if research_result else "Araştırma sonucu alınamadı"
                state["research_data"] = {"error": error_msg}
                
                if self.websocket_callback:
                    await self.websocket_callback(json.dumps({
                        "type": "crew_research_error", 
                        "message": f"❌ Araştırma hatası: {error_msg}", 
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                
        except Exception as e:
            error_msg = f"CrewAI araştırma hatası: {str(e)}"
            state["research_data"] = {"error": error_msg}
            if self.websocket_callback:
                await self.websocket_callback(json.dumps({
                    "type": "crew_research_error", 
                    "message": f"❌ {error_msg}", 
                    "timestamp": datetime.utcnow().isoformat()
                }))
            print(f"❌ Crew research node error: {e}")
            
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

    async def research_followup_node(self, state: ConversationState) -> ConversationState:
        """Araştırma tamamlandığında takip mesajı gönder"""
        if state.get("research_completed", False) and not "error" in state.get("research_data", {}):
            if self.websocket_callback:
                await self.websocket_callback(json.dumps({
                    "type": "research_completed", 
                    "message": "Araştırma başarıyla tamamlandı!", 
                    "timestamp": datetime.utcnow().isoformat(),
                    "research_data": state["research_data"]
                }))
            
            await asyncio.sleep(1)
            
            followup_message = ("🎯 Harika! Araştırma raporunuz hazır. Yukarıdaki **'Detaylı Raporu Görüntüle'** butonuna "
                              "tıklayarak tüm bulgularımızı inceleyebilirsiniz.\n\n"
                              "💡 Takıldığınız yerler olursa benimle birlikte raporu inceleyelim! Herhangi bir konuyu "
                              "daha detayına inmek isterseniz, sadece sorun - birlikte çalışabiliriz! 🤝")
            
            state["messages"].append(AIMessage(content=followup_message))
        
        return state

    async def gemini_response_node(self, state: ConversationState) -> ConversationState:
        try:
            messages_for_llm = state["messages"]
            
            # GÜNCELLENEN SATIRLAR 304-329: RAG context desteği eklendi
            if state.get("has_pdf_context") and state.get("rag_context"):
                # RAG context'i kullan
                user_question = messages_for_llm[-1].content
                rag_context = state["rag_context"]
                
                contextual_prompt = f"""
Kullanıcının sorusu: {user_question}

Aşağıda yüklenmiş PDF dokümanlarından bulunan ilgili bilgiler var. 
Bu bilgileri kullanarak kullanıcının sorusuna doğru ve detaylı bir şekilde cevap ver.

PDF DOKÜMANLARINDAN BULUNAN BİLGİLER:
{rag_context}

Cevabında:
1. PDF dokümanlarından elde edilen bilgileri kullan
2. Hangi dokümanlardan geldiğini belirt
3. Spesifik detayları vurgula
4. Eğer PDF'lerde olmayan bir şey soruyorsa, web araştırması önerebilirsin
5. Kullanıcı dostu ve bilgilendirici bir ton kullan

NOT: Bu bilgiler kullanıcının yüklediği PDF dokümanlarından geliyor.
"""
                
                contextual_messages = messages_for_llm[:-1] + [HumanMessage(content=contextual_prompt)]
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
                if messages_for_llm and "araştırma başlatılmadı" in messages_for_llm[-1].content:
                    messages_for_llm = messages_for_llm[:-1]
                response = await self.llm.ainvoke(messages_for_llm)
            
            state["messages"].append(AIMessage(content=response.content))
            
        except Exception as e:
            error_message = f"Üzgünüm, bir hata oluştu: {str(e)}"
            state["messages"].append(AIMessage(content=error_message))
        
        return state

    # YENI FONKSIYON: RAG context formatı (SATIRLAR 366-385)
    def format_rag_context(self, search_results: List[dict]) -> str:
        """RAG arama sonuçlarını LLM için uygun formatta hazırla"""
        context = "YÜKLENEN PDF DOKÜMANLARINDAN BULUNAN BİLGİLER:\n\n"
        
        for i, result in enumerate(search_results, 1):
            filename = result['metadata'].get('filename', 'Bilinmeyen dosya')
            chunk_index = result['metadata'].get('chunk_index', 0)
            similarity = result.get('similarity', 0)
            content = result['content']
            
            context += f"{i}. KAYNAK: {filename} (Bölüm {chunk_index + 1}, Benzerlik: %{similarity*100:.1f})\n"
            context += f"İÇERİK: {content}\n\n"
        
        context += f"TOPLAM KAYNAK: {len(search_results)} doküman parçası\n"
        context += f"ARAMA TARİHİ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
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
            self.conversation_state["messages"].append(HumanMessage(content=user_message))
            self.conversation_state["websocket_callback"] = self.websocket_callback
            
            final_state = await self.graph.ainvoke(self.conversation_state)
            self.conversation_state = final_state
            
            if final_state.get('pending_action'):
                 return ""
            
            ai_messages = [msg for msg in final_state["messages"] if isinstance(msg, AIMessage)]
            if ai_messages:
                return ai_messages[-1].content
            return ""
            
        except Exception as e:
            error_response = f"Bir hata oluştu: {str(e)}"
            print(f"Process message error: {e}")
            self.conversation_state["pending_action"] = ""
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
        
        # GÜNCELLENEN SATIRLAR 442-454: Vector store istatistikleri eklendi
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
            "vector_store_stats": vector_stats
        }