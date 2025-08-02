// static/js/core/App.js
import { DOM } from '../ui/DOM.js';
import { UIManager } from '../ui/UIManager.js';
import { WebSocketHandler } from './WebSocketHandler.js';
import PDFManager from '../pdf-manager.js';
import ChatHistoryManager from './ChatHistoryManager.js';

class App {
    constructor() {
        this.ui = new UIManager();
        this.ws = new WebSocketHandler({
            onOpen: this.handleWsOpen.bind(this),
            onMessage: this.handleWsMessage.bind(this),
            onClose: this.handleWsClose.bind(this),
            onError: this.handleWsError.bind(this)
        });
        this.pdfManager = new PDFManager(this);
        this.chatHistory = new ChatHistoryManager(this);

        // Tüm uygulama durumu (state) burada yönetilir
        this.researchState = {
            mainSteps: [
                { id: 'step1', title: 'Kapsamlı Ön Web Araştırması', status: 'pending', agent: 'WebResearcher' },
                { id: 'step2', title: 'YouTube Video Analizi', status: 'pending', agent: 'YouTubeAnalyst' },
                { id: 'step3', title: 'Raporu Yapılandırma ve JSON Formatına Dönüştürme', status: 'pending', agent: 'ReportProcessor' }
            ],
            isResearchCompleted: false,
            currentState: 'idle',
            subTopics: [],
            isWaitingForConfirmation: false,
            pendingResearchTopic: null
        };
        
        this.pdfState = {
            totalDocuments: 0,
            totalChunks: 0,
            ragEnabled: true,
            isProcessingPdf: false,
            currentChatId: null
        };
        
        // YENİ: İlk açılış durumu
        this.isFirstLoad = true;
        
        this.initializeEventListeners();
        
        // Global erişim için window'a ekle
        window.app = this;
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
                
                // YENİ: Chat ID'yi güncelle
                if (data.chat_id) {
                    this.pdfState.currentChatId = data.chat_id;
                    console.log(`📝 Aktif sohbet: ${data.chat_id}`);
                    
                    // İlk yüklemede hoş geldin mesajını göster, sonrasında gizle
                    if (!this.isFirstLoad) {
                        this.ui.hideWelcomeMessage();
                    }
                }
                
                // Vector store istatistiklerini güncelle
                if (data.vector_store_stats) {
                    this.updatePDFStats(data.vector_store_stats);
                }
                
                // Chat bilgilerini güncelle
                if (data.chat_info) {
                    console.log('💬 Chat bilgileri:', data.chat_info);
                }
                break;

            case 'message':
                if (data.content?.trim()) {
                    this.ui.addMessage(data.content, 'ai');
                    // İlk AI mesajından sonra hoş geldin mesajını gizle
                    this.ui.hideWelcomeMessage();
                }
                break;

            case 'system':
                if (data.content?.trim()) {
                    this.ui.addMessage(data.content, 'system');
                }
                break;

            case 'rag_found':
                if (data.message) {
                    this.ui.addMessage(data.message, 'system');
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

    // PDF Stats Güncelleme
    updatePDFStats(stats) {
        this.pdfState.totalDocuments = stats.total_documents || 0;
        this.pdfState.totalChunks = stats.total_chunks || 0;
        this.pdfState.currentChatId = stats.chat_id || this.pdfState.currentChatId;
        
        // Sidebar'daki istatistikleri güncelle
        const totalPdfsElement = document.getElementById('totalPdfs');
        const totalChunksElement = document.getElementById('totalChunks');
        
        if (totalPdfsElement) totalPdfsElement.textContent = this.pdfState.totalDocuments;
        if (totalChunksElement) totalChunksElement.textContent = this.pdfState.totalChunks;
        
        // Chat history'deki PDF sayısını güncelle
        if (this.pdfState.currentChatId) {
            this.chatHistory.updateChatStats(
                this.pdfState.currentChatId, 
                null, // message count - burada güncellenmeyecek
                this.pdfState.totalDocuments
            );
        }
        
        console.log(`📚 PDF Stats güncellendi: ${this.pdfState.totalDocuments} PDF, ${this.pdfState.totalChunks} parça (Chat: ${this.pdfState.currentChatId})`);
    }

    // YENİ FONKSIYON: PDF yükleme başarısı
    onPDFUploadSuccess(uploadData) {
        // PDF stats'i güncelle
        if (uploadData.stats) {
            this.updatePDFStats(uploadData.stats);
        }
        
        // Chat history güncelle
        if (uploadData.chat_id) {
            this.chatHistory.updateChatStats(
                uploadData.chat_id,
                null, // message count değişmedi
                uploadData.stats?.total_documents || 0
            );
        }
        
        // YENİ: İlk yüklemeden sonra artık mesaj gönderebilir
        if (this.isFirstLoad && uploadData.chat_id) {
            this.isFirstLoad = false;
            this.pdfState.currentChatId = uploadData.chat_id;
            console.log('✅ PDF yüklendikten sonra chat hazır:', uploadData.chat_id);
        }
        
        // WebSocket'e bilgi gönder
        if (this.ws.isConnected) {
            this.ws.send({
                type: 'pdf_uploaded',
                filename: uploadData.filename,
                chat_id: uploadData.chat_id
            });
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
        if (!message) {
            console.warn('⚠️ Mesaj boş');
            return;
        }

        // Aktif sohbet varsa ve bağlıysa direkt gönder
        if (this.pdfState.currentChatId && this.ws.isConnected) {
            this.sendMessageToServer(message);
            return;
        }

        // İlk mesajsa veya aktif sohbet yoksa yeni chat oluştur
        if (this.isFirstLoad || !this.pdfState.currentChatId) {
            this.createNewChatAndSendMessage(message);
            return;
        }

        // WebSocket bağlı değilse hata mesajı
        if (!this.ws.isConnected) {
            console.warn('⚠️ WebSocket bağlı değil');
            this.ui.addMessage('❌ Bağlantı yok. Lütfen bekleyin...', 'system');
            return;
        }

        this.sendMessageToServer(message);
    }

    // YENİ FONKSIYON: Yeni chat oluştur ve mesaj gönder
    async createNewChatAndSendMessage(message) {
        try {
            console.log('🆕 İlk mesaj - yeni chat oluşturuluyor...');
            
            // Loading state göster
            this.ui.addMessage('🔄 Sohbet oluşturuluyor...', 'system');
            
            // Yeni chat oluştur
            const chatId = await this.chatHistory.createNewChatForFirstMessage();
            
            // System mesajını temizle
            const systemMessages = document.querySelectorAll('.message.system');
            systemMessages.forEach(msg => {
                if (msg.textContent.includes('Sohbet oluşturuluyor')) {
                    msg.remove();
                }
            });
            
            // WebSocket bağlantısının kurulmasını bekle
            let retryCount = 0;
            const maxRetries = 10;
            
            while (!this.ws.isConnected && retryCount < maxRetries) {
                await new Promise(resolve => setTimeout(resolve, 300));
                retryCount++;
            }
            
            if (this.ws.isConnected) {
                this.sendMessageToServer(message);
                this.isFirstLoad = false;
            } else {
                console.error('❌ WebSocket bağlantısı kurulamadı');
                this.ui.addMessage('❌ Bağlantı kurulamadı. Sayfayı yenileyin.', 'system');
            }
            
        } catch (error) {
            console.error('❌ Yeni chat oluşturma hatası:', error);
            this.ui.addMessage('❌ Sohbet oluşturulamadı. Lütfen tekrar deneyin.', 'system');
        }
    }

    // YENİ FONKSIYON: Mesajı sunucuya gönder
    sendMessageToServer(message) {
        console.log('📤 Mesaj gönderiliyor:', message);

        // Web araştırması checkbox'ını kontrol et
        const webResearchEnabled = document.getElementById('webResearchEnabled');
        const forceWebResearch = webResearchEnabled && webResearchEnabled.checked;

        // Add user message to UI
        this.ui.addMessage(message, 'user');
        this.ui.hideWelcomeMessage();
        
        // Show typing indicator
        this.ui.showTypingIndicator();

        // Send to WebSocket with research flag
        const messageData = { 
            message: message,
            force_web_research: forceWebResearch
        };

        const success = this.ws.send(messageData);
        if (!success) {
            this.ui.removeTypingIndicator();
            this.ui.addMessage('❌ Mesaj gönderilemedi. Lütfen tekrar deneyin.', 'system');
            return;
        }
        
        // Clear input and research checkbox
        DOM.messageInput.value = '';
        if (webResearchEnabled) {
            webResearchEnabled.checked = false;
        }
        
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

    // YENİ FONKSIYON: Chat değiştirme
    switchToChat(chatId) {
        console.log(`🔄 Sohbet değiştiriliyor: ${chatId}`);
        
        // Mevcut state'i temizle
        this.researchState.currentState = 'idle';
        this.researchState.isResearchCompleted = false;
        this.researchState.research_data = {};
        
        // PDF state'i güncelle
        this.pdfState.currentChatId = chatId;
        
        // WebSocket'i yeni chat ile yeniden bağla
        this.ws.reconnectWithChatId(chatId);
    }

    // PDF durumunu al
    getPDFState() {
        return {
            ...this.pdfState,
            hasDocuments: this.pdfState.totalDocuments > 0,
            averageChunksPerDoc: this.pdfState.totalDocuments > 0 
                ? Math.round(this.pdfState.totalChunks / this.pdfState.totalDocuments)
                : 0
        };
    }

    // Get current state for debugging
    getState() {
        return {
            researchState: this.researchState,
            pdfState: this.pdfState,
            isConnected: this.ws.isConnected,
            subTopics: this.ui.progressUI.subTopics,
            currentChatId: this.pdfState.currentChatId
        };
    }

    // YENİ FONKSIYON: Chat history manager'a erişim
    getChatHistory() {
        return this.chatHistory;
    }
}

export default App;