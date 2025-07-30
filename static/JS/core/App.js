// static/js/core/App.js
import { DOM } from '../ui/DOM.js';
import { UIManager } from '../ui/UIManager.js';
import { WebSocketHandler } from './WebSocketHandler.js';

class App {
    constructor() {
        this.ui = new UIManager();
        this.ws = new WebSocketHandler({
            onOpen: this.handleWsOpen.bind(this),
            onMessage: this.handleWsMessage.bind(this),
            onClose: this.handleWsClose.bind(this),
            onError: this.handleWsError.bind(this)
        });

        // Tüm uygulama durumu (state) burada yönetilir
        this.researchState = {
            mainSteps: [
                { id: 'step1', title: 'Kapsamlı Ön Web Araştırması', status: 'pending', agent: 'WebResearcher' },
                { id: 'step2', title: 'YouTube Video Analizi', status: 'pending', agent: 'YouTubeAnalyst' },
                { id: 'step3', title: 'Raporu Yapılandırma ve JSON Formatına Dönüştürme', status: 'pending', agent: 'ReportProcessor' }
            ],
            isResearchCompleted: false,
            currentState: 'idle', // idle, waiting_confirmation, researching, completed
            subTopics: [],
            isWaitingForConfirmation: false,
            pendingResearchTopic: null
        };
        
        this.initializeEventListeners();
    }

    // Event Listeners
    initializeEventListeners() {
        // Message input event listeners
        DOM.messageInput.addEventListener('input', (e) => {
            const length = e.target.value.length;
            DOM.charCount.textContent = `${length}/2000`;
            this.updateSendButton();
            this.ui.autoResizeTextarea(e.target);
        });

        DOM.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        DOM.sendBtn.addEventListener('click', () => this.sendMessage());

        // Event delegation for dynamically created buttons
        document.body.addEventListener('click', (e) => {
            // Detaylı rapor butonu
            if (e.target && (e.target.id === 'viewReportButton' || e.target.closest('#viewReportButton'))) {
                e.preventDefault();
                this.handleViewReportClick();
            }
            
            // PDF indirme butonu
            if (e.target && (e.target.id === 'downloadPdfButton' || e.target.closest('#downloadPdfButton'))) {
                e.preventDefault();
                this.handleDownloadPdfClick();
            }
        });

        // Initial state
        this.updateSendButton();
    }

    // Report button handlers
    handleViewReportClick() {
        console.log("🔍 Detaylı rapor görüntüleme talep edildi");
        if (this.ui.progressUI && typeof this.ui.progressUI.openDetailedReport === 'function') {
            this.ui.progressUI.openDetailedReport();
        } else {
            console.error("❌ openDetailedReport fonksiyonu bulunamadı");
            alert('Rapor görüntüleme özelliği şu anda kullanılamıyor.');
        }
    }

    handleDownloadPdfClick() {
        console.log("📄 PDF indirme talep edildi");
        if (this.ui.progressUI && typeof this.ui.progressUI.downloadPDF === 'function') {
            this.ui.progressUI.downloadPDF();
        } else {
            console.error("❌ downloadPDF fonksiyonu bulunamadı");
            alert('PDF indirme özelliği şu anda kullanılamıyor.');
        }
    }

    // UI Helper Methods
    updateSendButton() {
        const message = DOM.messageInput.value.trim();
        DOM.sendBtn.disabled = !message || !this.ws.isConnected;
    }

    updateCharCount() {
        const current = DOM.messageInput.value.length;
        const max = DOM.messageInput.maxLength;
        DOM.charCount.textContent = `${current}/${max}`;
    }

    // WebSocket Handlers
    handleWsOpen() {
        console.log('✅ WebSocket bağlantısı kuruldu');
        this.ui.updateConnectionStatus('connected', 'Bağlı');
        this.updateSendButton();
    }

    handleWsClose() {
        console.log('🔌 WebSocket bağlantısı kesildi');
        this.ui.updateConnectionStatus('disconnected', 'Bağlantı kesildi');
        DOM.sendBtn.disabled = true;
    }

    handleWsError(error) {
        console.error("❌ WebSocket Hatası:", error);
        this.ui.updateConnectionStatus('error', 'Bağlantı hatası');
        DOM.sendBtn.disabled = true;
    }

    handleWsMessage(data) {
        console.log('📨 Gelen Mesaj:', data);
        this.ui.removeTypingIndicator();

        switch(data.type) {
            case 'connection_established':
                console.log('✅ Server bağlantısı onaylandı');
                break;

            case 'message':
                if (data.content?.trim()) {
                    this.ui.addMessage(data.content, 'ai');
                }
                break;

            case 'system':
                if (data.content?.trim()) {
                    this.ui.addMessage(data.content, 'system');
                }
                break;

            case 'confirmation_request':
                this.handleConfirmationRequest(data);
                break;

            case 'crew_research_start':
                this.handleResearchStart(data);
                break;

            case 'workflow_message':
                this.handleWorkflowMessage(data);
                break;

            case 'a2a_message':
                this.handleA2AMessage(data);
                break;

            case 'subtopics_found':
                this.handleSubTopicsFound(data);
                break;

            case 'subtopic_progress':
                this.ui.progressUI.updateSubTopicStatus(data.subtopic, data.status, data.content);
                break;

            case 'research_completed':
                this.handleResearchCompleted(data);
                break;

            case 'main_steps':
                this.ui.progressUI.createMainStepsUI(data.steps || this.researchState.mainSteps);
                break;

            case 'main_step_update':
                this.ui.progressUI.updateMainStepStatus(data.step_id, data.status);
                break;

            case 'subtopics_initialized':
                this.handleSubTopicsInitialized(data);
                break;

            case 'subtopic_update':
                this.ui.progressUI.updateSubTopicStatus(data.topic_title, data.status, data.content);
                break;

            case 'error':
                this.ui.addMessage(`❌ Hata: ${data.message || data.content}`, 'system');
                break;

            default:
                console.warn("⚠️ Bilinmeyen mesaj tipi:", data.type);
                // Fallback - show content if available
                if (data.content && typeof data.content === 'string') {
                    this.ui.addMessage(data.content, 'ai');
                }
        }
    }

    // Specialized Message Handlers
    handleConfirmationRequest(data) {
        this.researchState.isWaitingForConfirmation = true;
        this.researchState.pendingResearchTopic = data.topic || data.content;
        this.researchState.currentState = 'waiting_confirmation';

        this.ui.showConfirmationUI(data.content || data.message, (isConfirmed) => {
            this.handleConfirmationResponse(isConfirmed);
        });
    }

    handleConfirmationResponse(confirmed) {
        this.researchState.isWaitingForConfirmation = false;
        
        const userResponse = confirmed ? 'Evet, başlat.' : 'Hayır, teşekkürler.';
        this.ui.addMessage(userResponse, 'user');

        const response = {
            type: 'confirmation_response',
            confirmed: confirmed,
            topic: this.researchState.pendingResearchTopic,
            message: confirmed ? 'evet' : 'hayır'
        };

        this.ws.send(response);

        if (confirmed) {
            this.ui.addMessage('🔍 CrewAI araştırması başlatılıyor...', 'system');
            this.ui.showTypingIndicator();
            this.researchState.currentState = 'researching';
        } else {
            this.ui.addMessage('Araştırma iptal edildi. Başka bir konuda yardımcı olabilirim.', 'ai');
            this.researchState.currentState = 'idle';
        }
    }

    handleResearchStart(data) {
        this.researchState.currentState = 'researching';
        this.ui.progressUI.createMainStepsUI(this.researchState.mainSteps);
        if (data.message) {
            this.ui.addMessage(data.message, 'system');
        }
    }

    handleWorkflowMessage(data) {
        const agentToStep = { 
            'WebResearcher': 'step1', 
            'YouTubeAnalyst': 'step2', 
            'ReportProcessor': 'step3' 
        };
        
        const stepId = agentToStep[data.agent];
        if (!stepId) return;

        let status = 'running';
        if (data.message.includes('tamamlandı') || data.message.includes('✅')) {
            status = 'completed';
        }
        
        this.ui.progressUI.updateMainStepStatus(stepId, status);
        
        // Add message to chat if needed
        if (data.show_in_chat !== false) {
            this.ui.addMessage(data.message, 'system');
        }
    }

    handleA2AMessage(data) {
        if (data.message.includes('detaylandırılıyor')) {
            const topicMatch = data.message.match(/Alt başlık \d+\/\d+ detaylandırılıyor: (.+)/);
            if (topicMatch) {
                this.ui.progressUI.updateSubTopicStatus(topicMatch[1], 'running');
            }
        } else if (data.message.includes('detaylandırıldı')) {
            const topicMatch = data.message.match(/'(.+)' detaylandırıldı/);
            if (topicMatch) {
                this.ui.progressUI.updateSubTopicStatus(topicMatch[1], 'completed');
            }
        }
        
        // Add message to chat if needed
        if (data.show_in_chat !== false) {
            this.ui.addMessage(data.message, 'system');
        }
    }

    handleSubTopicsFound(data) {
        this.researchState.subTopics = data.subtopics || [];
        this.ui.progressUI.initializeSubTopics(this.researchState.subTopics);
        
        if (data.message) {
            this.ui.addMessage(data.message, 'system');
        }
    }

    handleSubTopicsInitialized(data) {
        this.researchState.subTopics = data.subtopics || [];
        this.ui.progressUI.initializeSubTopics(this.researchState.subTopics);
    }

    handleResearchCompleted(data) {
        this.researchState.isResearchCompleted = true;
        this.researchState.currentState = 'completed';
        
        // Research data'yı ProgressUI'ye aktar
        if (data.research_data) {
            this.ui.progressUI.setResearchData(data.research_data);
        }
        
        // Update final step status
        this.ui.progressUI.updateMainStepStatus('step3', 'completed');
        
        // Show report button
        this.ui.progressUI.showViewReportButton();
        
        // Show completion message
        if (data.message) {
            this.ui.addMessage(data.message, 'system');
        }
        
        // Send follow-up message
        this.sendFollowUpMessage();
    }

    // User Actions
    sendMessage() {
        const message = DOM.messageInput.value.trim();
        if (!message || !this.ws.isConnected) {
            console.warn('⚠️ Mesaj boş veya WebSocket bağlı değil');
            return;
        }

        console.log('📤 Mesaj gönderiliyor:', message);

        // Add user message to UI
        this.ui.addMessage(message, 'user');
        this.ui.hideWelcomeMessage();
        
        // Show typing indicator
        this.ui.showTypingIndicator();

        // Send to WebSocket
        const success = this.ws.send({ message: message });
        if (!success) {
            this.ui.removeTypingIndicator();
            this.ui.addMessage('❌ Mesaj gönderilemedi. Lütfen tekrar deneyin.', 'system');
            return;
        }
        
        // Clear input
        DOM.messageInput.value = '';
        this.ui.autoResizeTextarea(DOM.messageInput);
        this.updateCharCount();
        this.updateSendButton();
    }

    sendFollowUpMessage() {
        setTimeout(() => {
            const followUpMessage = "🎯 Harika! Araştırma raporunuz hazır. Yukarıdaki **'Detaylı Raporu Görüntüle'** butonuna tıklayarak tüm bulgularımızı inceleyebilirsiniz. \n\n💡 Takıldığınız yerler olursa benimle birlikte raporu inceleyelim! Herhangi bir konuyu daha detayına inmek isterseniz, sadece sorun - birlikte çalışabiliriz! 🤝";
            this.ui.addMessage(followUpMessage, 'ai');
        }, 1500);
    }

    // Manual reconnect method
    reconnect() {
        if (this.ws) {
            this.ws.reconnect();
        }
    }

    // Get current state for debugging
    getState() {
        return {
            researchState: this.researchState,
            isConnected: this.ws.isConnected,
            subTopics: this.ui.progressUI.subTopics
        };
    }
}

export default App;