from typing import TypedDict, List, Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
import asyncio
import json
from datetime import datetime
from config import Config
from crew_research_tool import AsyncCrewAIA2AHandler

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

class AsyncLangGraphDialog:
    def __init__(self, websocket_callback=None):
        self.llm = ChatGoogleGenerativeAI(
            model=Config.GEMINI_MODEL,
            google_api_key=Config.GOOGLE_API_KEY,
            temperature=Config.GEMINI_TEMPERATURE,
            max_tokens=Config.GEMINI_MAX_TOKENS
        )
        
        self.websocket_callback = websocket_callback
        self.crew_handler = AsyncCrewAIA2AHandler(websocket_callback)
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
            pending_action=""
        )
    
    def create_conversation_graph(self):
        workflow = StateGraph(ConversationState)
        
        workflow.add_node("handle_confirmation", self.handle_confirmation_node)
        workflow.add_node("intent_analysis", self.intent_analysis_node)
        workflow.add_node("crew_research_agent", self.crew_research_agent_node)
        workflow.add_node("research_presentation", self.research_presentation_node)
        workflow.add_node("gemini_response", self.gemini_response_node)
        workflow.add_node("ask_confirmation", self.ask_confirmation_node)
        
        workflow.set_conditional_entry_point(
            self.route_initial_input,
            {"continue_to_intent": "intent_analysis", "handle_confirmation": "handle_confirmation"}
        )
        
        workflow.add_conditional_edges(
            "intent_analysis",
            self.should_call_crew_or_ask,
            {"crew_research": "crew_research_agent", "ask_confirmation": "ask_confirmation", "gemini": "gemini_response"}
        )

        workflow.add_conditional_edges(
            "handle_confirmation",
            self.decide_after_confirmation,
            {"start_research": "crew_research_agent", "cancel": "gemini_response"}
        )
        
        workflow.add_edge("crew_research_agent", "research_presentation")
        workflow.add_edge("research_presentation", END)
        workflow.add_edge("gemini_response", END)
        workflow.add_edge("ask_confirmation", END)

        return workflow.compile()

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

    def intent_analysis_node(self, state: ConversationState) -> ConversationState:
        last_message = state["messages"][-1].content.strip().lower()
        original_message = state["messages"][-1].content.strip()
        
        research_keywords_strong = ["araştır", "araştırma yap", "incele", "analiz et"]
        research_keywords_weak = ["hakkında bilgi", "nedir", "kimdir", "nasıl çalışır", "son gelişmeler"]
        
        detected_intent = "general_chat"
        task_topic = original_message
        
        for keyword in research_keywords_strong:
            if last_message.startswith(keyword) or last_message.endswith(keyword):
                detected_intent = "web_research"
                task_topic = original_message.replace(keyword, "", 1).strip()
                break
        
        if detected_intent != "web_research":
            if len(last_message.split()) > 3 or any(keyword in last_message for keyword in research_keywords_weak):
                 detected_intent = "ask_confirmation"

        state["current_intent"] = detected_intent
        state["crew_ai_task"] = task_topic
        state["needs_crew_ai"] = detected_intent == "web_research"
        
        return state

    def should_call_crew_or_ask(self, state: ConversationState) -> Literal["crew_research", "ask_confirmation", "gemini"]:
        return state["current_intent"] if state["current_intent"] in ["web_research", "ask_confirmation"] else "gemini"

    async def crew_research_agent_node(self, state: ConversationState) -> ConversationState:
        try:
            research_query = state['crew_ai_task']
            if self.websocket_callback:
                await self.websocket_callback(json.dumps({
                    "type": "crew_research_start", 
                    "message": f"🤖 CrewAI Asenkron Multi-Agent sistemi '{research_query}' konusunu araştırıyor...", 
                    "timestamp": datetime.utcnow().isoformat()
                }))
            
            research_result = await self.crew_handler.research_workflow(research_query)
            state["research_data"] = research_result
            
        except Exception as e:
            error_msg = f"CrewAI araştırma hatası: {str(e)}"
            state["research_data"] = {"error": error_msg}
            if self.websocket_callback:
                await self.websocket_callback(json.dumps({
                    "type": "crew_research_error", 
                    "message": f"❌ {error_msg}", 
                    "timestamp": datetime.utcnow().isoformat()
                }))
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
            if messages_for_llm and "araştırma başlatılmadı" in messages_for_llm[-1].content:
                 messages_for_llm = messages_for_llm[:-1]
            
            response = await self.llm.ainvoke(messages_for_llm)
            state["messages"].append(AIMessage(content=response.content))
            
        except Exception as e:
            error_message = f"Üzgünüm, bir hata oluştu: {str(e)}"
            state["messages"].append(AIMessage(content=error_message))
        
        return state
    
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
        
        return {
            "total_messages": len(messages),
            "user_messages": user_messages,
            "ai_messages": ai_messages,
            "current_intent": self.conversation_state.get("current_intent", "N/A"),
            "has_research_data": bool(self.conversation_state.get("research_data")),
            "last_research": self.conversation_state.get("research_data", {}).get("topic", ""),
            "crew_ai_enabled": True,
            "async_mode": True
        }