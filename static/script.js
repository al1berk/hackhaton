class LangGraphChatWithProgress {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.currentChatId = null;
        this.chatHistory = [];
        this.researchProgress = {
            mainSteps: [],
            subTopics: [],
            currentStep: null,
            currentSubTopic: null
        };
        this.completedTopics = {};
        
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.messagesContainer = document.getElementById('messagesContainer');
        this.connectionStatus = document.getElementById('connectionStatus');
        this.charCount = document.getElementById('charCount');
        
        this.initializeEventListeners();
        this.connectWebSocket();
        this.loadChatHistory();
    }

    initializeEventListeners() {
        this.messageInput.addEventListener('input', (e) => {
            this.handleInputChange(e);
            this.autoResizeTextarea(e.target);
        });

        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        this.sendBtn.addEventListener('click', () => this.sendMessage());

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
        });
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.updateConnectionStatus('connecting', 'Bağlanıyor...');
        
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket bağlantısı kuruldu');
            this.isConnected = true;
            this.updateConnectionStatus('connected', 'Bağlı');
            this.hideWelcomeMessage();
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleIncomingMessage(data);
        };

        this.ws.onclose = () => {
            console.log('WebSocket bağlantısı kapandı');
            this.isConnected = false;
            this.updateConnectionStatus('disconnected', 'Bağlantı kesildi');
            
            setTimeout(() => {
                if (!this.isConnected) {
                    this.connectWebSocket();
                }
            }, 3000);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket hatası:', error);
            this.updateConnectionStatus('disconnected', 'Bağlantı hatası');
        };
    }

    handleIncomingMessage(data) {
        console.log('Incoming message:', data); // Debug için
        this.removeTypingIndicator();

        switch(data.type) {
            case 'message':
                if (data.content && data.content.trim() !== "") {
                    this.addMessage(data.content, 'ai');
                    this.saveToHistory(data.content, 'ai');
                }
                break;
            
            case 'confirmation_request':
                this.showConfirmationUI(data.content);
                break;
                
            case 'crew_research_start':
                this.initializeMainSteps();
                break;
                
            case 'crew_progress':
                this.handleCrewProgress(data);
                break;
                
            case 'workflow_message':
                this.handleWorkflowMessage(data);
                break;
                
            case 'a2a_message':
                this.handleA2AMessage(data);
                break;
                
            case 'subtopics_found':
                this.initializeSubTopics(data.subtopics);
                break;
                
            case 'subtopic_progress':
                this.updateSubTopicProgress(data);
                break;
                
            case 'system':
                this.addMessage(data.content, 'system');
                break;
                
            default:
                if (data.content && data.content.trim() !== "") {
                    this.addMessage(data.content, 'ai');
                }
        }
        
        if (this.getSetting('soundNotifications')) {
            this.playNotificationSound();
        }
    }

    showConfirmationUI(question) {
        this.addMessage(question, 'system');

        const confirmationContainer = document.createElement('div');
        confirmationContainer.className = 'confirmation-container';
        
        const yesButton = document.createElement('button');
        yesButton.textContent = 'Evet, Başlat';
        yesButton.className = 'confirmation-btn yes';
        
        const noButton = document.createElement('button');
        noButton.textContent = 'Hayır, Teşekkürler';
        noButton.className = 'confirmation-btn no';

        const sendConfirmation = (isConfirmed) => {
            const message = isConfirmed ? 'evet' : 'hayır';
            this.addMessage(isConfirmed ? 'Evet, onayla.' : 'Hayır, kalsın.', 'user');
            
            this.ws.send(JSON.stringify({ message: message }));
            
            confirmationContainer.remove();
            
            this.showTypingIndicator();
        };

        yesButton.onclick = () => sendConfirmation(true);
        noButton.onclick = () => sendConfirmation(false);

        confirmationContainer.appendChild(yesButton);
        confirmationContainer.appendChild(noButton);
        
        this.messagesContainer.appendChild(confirmationContainer);
        this.scrollToBottom();
    }

    initializeMainSteps() {
        this.researchProgress.mainSteps = [
            { id: 'step1', title: 'Kapsamlı Ön Web Araştırması', status: 'pending', agent: 'WebResearcher' },
            { id: 'step2', title: 'YouTube Video Analizi', status: 'pending', agent: 'YouTubeAnalyst' },
            { id: 'step3', title: 'Raporu Yapılandırma ve JSON Formatına Dönüştürme', status: 'pending', agent: 'ReportProcessor' }
        ];
        
        this.createMainStepsUI();
    }

    createMainStepsUI() {
        const stepsContainer = document.createElement('div');
        stepsContainer.className = 'research-steps-container';
        stepsContainer.id = 'mainStepsContainer';
        
        const headerDiv = document.createElement('div');
        headerDiv.className = 'steps-header';
        headerDiv.innerHTML = `
            <div class="steps-title">
                <i class="fas fa-cogs"></i>
                <span>CrewAI Araştırma Süreci</span>
            </div>
        `;
        
        const stepsDiv = document.createElement('div');
        stepsDiv.className = 'steps-list';
        
        this.researchProgress.mainSteps.forEach((step, index) => {
            const stepElement = document.createElement('div');
            stepElement.className = 'step-item';
            stepElement.id = `main-step-${step.id}`;
            
            stepElement.innerHTML = `
                <div class="step-indicator">
                    <div class="step-number">${index + 1}</div>
                    <div class="step-status-icon">
                        <i class="fas fa-circle pending-icon"></i>
                        <i class="fas fa-spinner spinning-icon" style="display: none;"></i>
                        <i class="fas fa-check completed-icon" style="display: none;"></i>
                    </div>
                </div>
                <div class="step-content">
                    <div class="step-title">${step.title}</div>
                    <div class="step-agent">Agent: ${step.agent}</div>
                    <div class="step-status">Bekliyor...</div>
                </div>
            `;
            
            stepsDiv.appendChild(stepElement);
        });
        
        stepsContainer.appendChild(headerDiv);
        stepsContainer.appendChild(stepsDiv);
        
        this.messagesContainer.appendChild(stepsContainer);
        this.scrollToBottom();
    }

    handleCrewProgress(data) {
        console.log('Crew Progress:', data); // Debug için
        
        // Main step güncelleme
        if (data.step_data && data.step_data.main_step) {
            this.updateMainStepStatus(data.step_data.main_step, data.step_data.status || 'running');
        }
        
        // Agent bazlı güncelleme
        if (data.agent) {
            this.updateStepStatusByAgent(data.agent, data.message);
        }
    }

    handleWorkflowMessage(data) {
        console.log('Workflow Message:', data); // Debug için
        
        // Agent-to-step mapping
        const agentToStep = {
            'WebResearcher': 'step1',
            'YouTubeAnalyst': 'step2', 
            'ReportProcessor': 'step3'
        };
        
        const stepId = agentToStep[data.agent];
        if (!stepId) {
            console.warn('Unknown agent:', data.agent);
            return;
        }

        // Status belirleme - daha kesin kontrol
        let status = 'running';
        if (data.message.includes('tamamlandı') || data.message.includes('✅')) {
            status = 'completed';
        } else if (data.message.includes('başlatılıyor') || data.message.includes('🔍') || data.message.includes('📹') || data.message.includes('📋')) {
            status = 'running';
        }
        
        console.log(`Updating step ${stepId} to ${status}`); // Debug için
        this.updateMainStepStatus(stepId, status);
        
        // Step 3 tamamlandığında alt konuları bekle
        if (stepId === 'step3' && status === 'completed') {
            setTimeout(() => {
                this.waitForSubTopics();
            }, 1000);
        }
    }

    updateStepStatusByAgent(agentName, message) {
        console.log(`updateStepStatusByAgent: ${agentName} -> ${message}`); // Debug için
        
        const agentToStep = {
            'WebResearcher': 'step1',
            'YouTubeAnalyst': 'step2',
            'ReportProcessor': 'step3',
            'DetailResearcher': null // Bu alt konular için
        };
        
        const stepId = agentToStep[agentName];
        if (!stepId) return;
        
        let status = 'running';
        if (message.includes('tamamlandı') || message.includes('✅')) {
            status = 'completed';
        }
        
        this.updateMainStepStatus(stepId, status);
    }

    handleA2AMessage(data) {
        console.log('A2A Message:', data); // Debug için
        
        if (data.message.includes('detaylandırılıyor')) {
            const topicMatch = data.message.match(/Alt başlık \d+\/\d+ detaylandırılıyor: (.+)/);
            if (topicMatch) this.updateSubTopicStatus(topicMatch[1], 'running');
        } else if (data.message.includes('detaylandırıldı')) {
            const topicMatch = data.message.match(/'(.+)' detaylandırıldı/);
            if (topicMatch) this.updateSubTopicStatus(topicMatch[1], 'completed');
        }
    }

    updateMainStepStatus(stepId, status) {
        console.log(`updateMainStepStatus called: ${stepId} -> ${status}`); // Debug için
        
        const stepElement = document.getElementById(`main-step-${stepId}`);
        if (!stepElement) {
            console.warn(`Step element not found: main-step-${stepId}`);
            return;
        }
        
        const icons = {
            pending: stepElement.querySelector('.pending-icon'),
            running: stepElement.querySelector('.spinning-icon'),
            completed: stepElement.querySelector('.completed-icon')
        };
        const statusText = stepElement.querySelector('.step-status');
        
        // Önce tüm ikonları gizle ve sınıfları kaldır
        Object.values(icons).forEach(icon => {
            if (icon) icon.style.display = 'none';
        });
        stepElement.classList.remove('pending', 'running', 'completed');

        // Yeni duruma göre ayarla
        switch(status) {
            case 'running':
                if (icons.running) {
                    icons.running.style.display = 'inline-block';
                    statusText.textContent = 'İşlem devam ediyor...';
                    stepElement.classList.add('running');
                }
                break;
            case 'completed':
                if (icons.completed) {
                    icons.completed.style.display = 'inline-block';
                    statusText.textContent = 'Tamamlandı ✓';
                    stepElement.classList.add('completed');
                }
                break;
            default: // pending
                if (icons.pending) {
                    icons.pending.style.display = 'inline-block';
                    statusText.textContent = 'Bekliyor...';
                    stepElement.classList.add('pending');
                }
        }
        
        // State'i güncelle
        const step = this.researchProgress.mainSteps.find(s => s.id === stepId);
        if (step) {
            step.status = status;
            console.log(`Step ${stepId} updated to ${status}`); // Debug için
        }
    }

    waitForSubTopics() {
        const waitingDiv = document.createElement('div');
        waitingDiv.className = 'waiting-subtopics';
        waitingDiv.id = 'waitingSubTopics';
        waitingDiv.innerHTML = `
            <div class="waiting-message">
                <i class="fas fa-search spinning"></i>
                <span>Alt konular belirleniyor...</span>
            </div>
        `;
        this.messagesContainer.appendChild(waitingDiv);
        this.scrollToBottom();
    }

    initializeSubTopics(subtopics) {
        const waitingElement = document.getElementById('waitingSubTopics');
        if (waitingElement) waitingElement.remove();
        
        this.researchProgress.subTopics = subtopics.map((topic, index) => ({
            id: `subtopic-${index}`,
            title: typeof topic === 'string' ? topic : topic.alt_baslik || topic.title,
            status: 'pending',
            content: ''
        }));
        
        this.createSubTopicsUI();
    }

    createSubTopicsUI() {
        const subTopicsContainer = document.createElement('div');
        subTopicsContainer.className = 'subtopics-container';
        subTopicsContainer.id = 'subTopicsContainer';
        
        subTopicsContainer.innerHTML = `
            <div class="subtopics-header">
                <div class="subtopics-title">
                    <i class="fas fa-list-ul"></i>
                    <span>Detay Araştırma Konuları</span>
                </div>
            </div>
            <div class="subtopics-list"></div>
        `;

        const topicsDiv = subTopicsContainer.querySelector('.subtopics-list');
        this.researchProgress.subTopics.forEach((topic, index) => {
            const topicElement = document.createElement('div');
            topicElement.className = 'subtopic-item';
            topicElement.id = `subtopic-${topic.id}`;
            
            topicElement.innerHTML = `
                <div class="subtopic-indicator">
                    <div class="subtopic-number">${index + 1}</div>
                    <div class="subtopic-status-icon">
                        <i class="fas fa-circle pending-icon"></i>
                        <i class="fas fa-spinner spinning-icon" style="display: none;"></i>
                        <i class="fas fa-check completed-icon" style="display: none;"></i>
                    </div>
                </div>
                <div class="subtopic-content">
                    <div class="subtopic-title">${topic.title}</div>
                    <div class="subtopic-status">Sırada bekliyor...</div>
                </div>
            `;
            
            topicElement.addEventListener('click', () => {
                if (topic.status === 'completed') {
                    this.openTopicDetailModal(topic);
                }
            });
            
            topicsDiv.appendChild(topicElement);
        });
        
        this.messagesContainer.appendChild(subTopicsContainer);
        this.scrollToBottom();
    }

    updateSubTopicStatus(topicTitle, status, content = '') {
        const topic = this.researchProgress.subTopics.find(t => t.title === topicTitle);
        if (!topic) return;
        
        const topicElement = document.getElementById(`subtopic-${topic.id}`);
        if (!topicElement) return;

        const icons = {
            pending: topicElement.querySelector('.pending-icon'),
            running: topicElement.querySelector('.spinning-icon'),
            completed: topicElement.querySelector('.completed-icon')
        };
        const statusText = topicElement.querySelector('.subtopic-status');
        
        Object.values(icons).forEach(icon => icon.style.display = 'none');
        topicElement.classList.remove('pending', 'running', 'completed', 'clickable');
        
        switch(status) {
            case 'running':
                icons.running.style.display = 'inline-block';
                statusText.textContent = 'Araştırılıyor...';
                topicElement.classList.add('running');
                break;
            case 'completed':
                icons.completed.style.display = 'inline-block';
                statusText.textContent = 'Tamamlandı - Detayları görüntüle';
                topicElement.classList.add('completed', 'clickable');
                topic.content = content;
                this.completedTopics[topic.id] = { title: topic.title, content: content };
                break;
            default:
                icons.pending.style.display = 'inline-block';
                statusText.textContent = 'Sırada bekliyor...';
                topicElement.classList.add('pending');
        }
        topic.status = status;
    }

    openTopicDetailModal(topic) {
        const modal = document.createElement('div');
        modal.className = 'topic-detail-modal-overlay';
        modal.id = 'topicDetailModal';
        
        const topicData = this.completedTopics[topic.id];
        const content = topicData ? topicData.content : 'İçerik bulunamadı.';
        
        modal.innerHTML = `
            <div class="topic-detail-modal">
                <div class="topic-detail-header">
                    <h2>${topic.title}</h2>
                    <button class="close-modal-btn" onclick="closeTopicModal()"><i class="fas fa-times"></i></button>
                </div>
                <div class="topic-detail-body">
                    <div class="topic-content">${this.formatTopicContent(content)}</div>
                    <div class="topic-meta">
                        <div class="meta-item"><i class="fas fa-robot"></i><span>CrewAI DetailResearcher tarafından araştırıldı</span></div>
                        <div class="meta-item"><i class="fas fa-clock"></i><span>${new Date().toLocaleString('tr-TR')}</span></div>
                    </div>
                </div>
                <div class="topic-detail-footer">
                    <button class="export-btn" onclick="exportTopicContent('${topic.id}')"><i class="fas fa-download"></i> İçeriği Dışa Aktar</button>
                    <button class="close-btn" onclick="closeTopicModal()">Kapat</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
    }

    formatTopicContent(content) {
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^/, '<p>').replace(/$/, '</p>');
    }

    updateConnectionStatus(status, text) {
        const indicator = this.connectionStatus.querySelector('.status-indicator');
        const statusText = this.connectionStatus.querySelector('span');
        
        indicator.className = `status-indicator ${status}`;
        statusText.textContent = text;
    }

    handleInputChange(e) {
        const length = e.target.value.length;
        this.sendBtn.disabled = length === 0 || !this.isConnected;
        this.charCount.textContent = `${length}/2000`;
    }

    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || !this.isConnected) return;

        this.addMessage(message, 'user');
        this.showTypingIndicator();
        this.ws.send(JSON.stringify({ message: message }));
        
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';
        this.handleInputChange({ target: this.messageInput });
        this.saveToHistory(message, 'user');
    }

    addMessage(content, sender) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${sender}`;
        
        messageElement.innerHTML = `
            <div class="message-avatar"><i class="fas ${sender === 'user' ? 'fa-user' : sender === 'ai' ? 'fa-robot' : 'fa-cog'}"></i></div>
            <div class="message-content">${this.formatMessage(content)}</div>
        `;
        
        this.messagesContainer.appendChild(messageElement);
        this.scrollToBottom();
    }

    formatMessage(content) {
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }

    showTypingIndicator() {
        if (document.getElementById('typingIndicator')) return;
        const typingElement = document.createElement('div');
        typingElement.className = 'typing-indicator';
        typingElement.id = 'typingIndicator';
        typingElement.innerHTML = `
            <div class="message-avatar"><i class="fas fa-robot"></i></div>
            <div class="message-content"><div class="typing-dots"><span></span><span></span><span></span></div></div>
        `;
        this.messagesContainer.appendChild(typingElement);
        this.scrollToBottom();
    }

    removeTypingIndicator() {
        const typingIndicator = document.getElementById('typingIndicator');
        if (typingIndicator) typingIndicator.remove();
    }

    hideWelcomeMessage() {
        const welcomeMessage = document.querySelector('.welcome-message');
        if (welcomeMessage) welcomeMessage.style.display = 'none';
    }

    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    saveToHistory(message, sender) { /* ... (Implementation needed) ... */ }
    loadChatHistory() { /* ... (Implementation needed) ... */ }
    getSetting(key) { return true; /* Default to true for notifications */ }
    playNotificationSound() { /* ... (Implementation needed) ... */ }
    closeModal() { /* ... (Implementation needed) ... */ }
}

function closeTopicModal() {
    const modal = document.getElementById('topicDetailModal');
    if (modal) modal.remove();
}

function exportTopicContent(topicId) {
    const topic = chat.completedTopics[topicId];
    if (!topic) return;
    
    const content = `# ${topic.title}\n\n${topic.content}`;
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${topic.title.replace(/[^a-z0-9]/gi, '_')}.md`;
    a.click();
    URL.revokeObjectURL(url);
}

let chat;
document.addEventListener('DOMContentLoaded', () => {
    chat = new LangGraphChatWithProgress();
});