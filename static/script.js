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
        this.expandedTopics = new Set(); // Açık olan alt başlıkları takip etmek için
        this.researchCompleted = false; // Araştırma tamamlandı mı?
        
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
        console.log('Incoming message:', data);
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
                this.researchCompleted = false;
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
                console.log('Subtopics found:', data.subtopics);
                this.initializeSubTopics(data.subtopics);
                break;
            
            case 'subtopic_progress':
                console.log('Subtopic progress:', data);
                this.updateSubTopicProgress(data);
                break;
            
            case 'system':
                this.addMessage(data.content, 'system');
                break;
            
            default:
                if (data.content && data.content.trim() !== "") {
                    this.addMessage(data.content, 'ai');
                    
                    // Araştırma tamamlandı mı kontrol et
                    if (data.content.includes('Araştırması Tamamlandı') || data.content.includes('araştırma workflow\'u tamamlandı')) {
                        this.researchCompleted = true;
                        this.showViewReportButton();
                        this.sendFollowUpMessage();
                    }
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
            
            if (isConfirmed) {
                this.showTypingIndicator();
            }
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
        console.log('Crew Progress:', data);
        
        if (data.step_data && data.step_data.main_step) {
            this.updateMainStepStatus(data.step_data.main_step, data.step_data.status || 'running');
        }
        
        if (data.agent) {
            this.updateStepStatusByAgent(data.agent, data.message);
        }
    }

    handleWorkflowMessage(data) {
        console.log('Workflow Message:', data);
        
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

        let status = 'running';
        if (data.message.includes('tamamlandı') || data.message.includes('✅')) {
            status = 'completed';
        } else if (data.message.includes('başlatılıyor') || data.message.includes('🔍') || data.message.includes('📹') || data.message.includes('📋')) {
            status = 'running';
        }
        
        console.log(`Updating step ${stepId} to ${status}`);
        this.updateMainStepStatus(stepId, status);
        
        if (stepId === 'step3' && status === 'completed') {
            setTimeout(() => {
                this.waitForSubTopics();
            }, 1000);
        }
    }

    updateStepStatusByAgent(agentName, message) {
        console.log(`updateStepStatusByAgent: ${agentName} -> ${message}`);
        
        const agentToStep = {
            'WebResearcher': 'step1',
            'YouTubeAnalyst': 'step2',
            'ReportProcessor': 'step3',
            'DetailResearcher': null
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
        console.log('A2A Message:', data);
        
        if (data.message.includes('detaylandırılıyor')) {
            const topicMatch = data.message.match(/Alt başlık \d+\/\d+ detaylandırılıyor: (.+)/);
            if (topicMatch) this.updateSubTopicStatus(topicMatch[1], 'running');
        } else if (data.message.includes('detaylandırıldı')) {
            const topicMatch = data.message.match(/'(.+)' detaylandırıldı/);
            if (topicMatch) this.updateSubTopicStatus(topicMatch[1], 'completed');
        }
    }

    updateMainStepStatus(stepId, status) {
        console.log(`updateMainStepStatus called: ${stepId} -> ${status}`);
        
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
        
        Object.values(icons).forEach(icon => {
            if (icon) icon.style.display = 'none';
        });
        stepElement.classList.remove('pending', 'running', 'completed');

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
            default:
                if (icons.pending) {
                    icons.pending.style.display = 'inline-block';
                    statusText.textContent = 'Bekliyor...';
                    stepElement.classList.add('pending');
                }
        }
        
        const step = this.researchProgress.mainSteps.find(s => s.id === stepId);
        if (step) {
            step.status = status;
            console.log(`Step ${stepId} updated to ${status}`);
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
        console.log('Initializing subtopics:', subtopics);
        
        const waitingElement = document.getElementById('waitingSubTopics');
        if (waitingElement) waitingElement.remove();
        
        this.researchProgress.subTopics = subtopics.map((topic, index) => ({
            id: `subtopic-${index}`,
            title: typeof topic === 'string' ? topic : (topic.alt_baslik || topic.title || `Konu ${index + 1}`),
            status: 'pending',
            content: ''
        }));
        
        console.log('SubTopics array created:', this.researchProgress.subTopics);
        
        this.createSubTopicsUI();
    }

    // *** DÜZELTİLMİŞ FONKSİYONLAR ***

createSubTopicsUI() {
    console.log('Creating SubTopics UI for:', this.researchProgress.subTopics);
    
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
            <div class="subtopic-header" data-topic-id="${topic.id}">
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
                <div class="expand-icon">
                    <i class="fas fa-chevron-down"></i>
                </div>
            </div>
            <div class="subtopic-details" style="display: none;">
                <div class="subtopic-content-text">İçerik henüz hazırlanmadı...</div>
            </div>
        `;
        
        // Click event'i header'a ekle - sadece tamamlanmış olanlar için
        const headerElement = topicElement.querySelector('.subtopic-header');
        headerElement.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const topicId = headerElement.getAttribute('data-topic-id');
            const topic = this.researchProgress.subTopics.find(t => t.id === topicId);
            
            console.log('Topic clicked:', topic?.title, 'Status:', topic?.status);
            console.log('Topic object:', topic);
            
            if (topic && topic.status === 'completed') {
                this.toggleSubTopicDetails(topicId);
            } else {
                console.log('Topic not completed yet or not found');
            }
        });
        
        topicsDiv.appendChild(topicElement);
    });
    
    this.messagesContainer.appendChild(subTopicsContainer);
    this.scrollToBottom();
}

updateSubTopicStatus(topicTitle, status, content = '') {
    console.log('updateSubTopicStatus called:', { 
        topicTitle, 
        status, 
        contentLength: content.length,
        contentPreview: content.substring(0, 100) + '...' 
    });
    
    const topic = this.researchProgress.subTopics.find(t => t.title === topicTitle);
    if (!topic) {
        console.warn('Topic not found for title:', topicTitle);
        console.log('Available topics:', this.researchProgress.subTopics.map(t => t.title));
        return;
    }
    
    console.log('Found topic:', topic.id, topic.title);
    
    const topicElement = document.getElementById(`subtopic-${topic.id}`);
    if (!topicElement) {
        console.warn('Topic element not found:', `subtopic-${topic.id}`);
        return;
    }

    const icons = {
        pending: topicElement.querySelector('.pending-icon'),
        running: topicElement.querySelector('.spinning-icon'),
        completed: topicElement.querySelector('.completed-icon')
    };
    const statusText = topicElement.querySelector('.subtopic-status');
    const contentText = topicElement.querySelector('.subtopic-content-text');
    const headerElement = topicElement.querySelector('.subtopic-header');
    
    // Tüm iconları gizle
    Object.values(icons).forEach(icon => {
        if (icon) icon.style.display = 'none';
    });
    
    // CSS sınıflarını temizle
    topicElement.classList.remove('pending', 'running', 'completed', 'clickable');
    if (headerElement) {
        headerElement.classList.remove('clickable');
    }
    
    switch(status) {
        case 'running':
            if (icons.running) icons.running.style.display = 'inline-block';
            if (statusText) statusText.textContent = 'Araştırılıyor...';
            topicElement.classList.add('running');
            break;
            
        case 'completed':
            if (icons.completed) icons.completed.style.display = 'inline-block';
            if (statusText) statusText.textContent = 'Tamamlandı - Tıkla ve detayları gör';
            
            // Topic nesnesini güncelle
            topic.status = 'completed';
            topic.content = content;
            
            // Completed topic'i kaydet
            this.completedTopics[topic.id] = { 
                title: topic.title, 
                content: content 
            };
            
            // CSS sınıflarını ekle
            topicElement.classList.add('completed', 'clickable');
            if (headerElement) {
                headerElement.classList.add('clickable');
                headerElement.style.cursor = 'pointer';
            }
            
            // İçeriği DOM'a yükle
            if (contentText && content) {
                const formattedContent = this.formatTopicContent(content);
                contentText.innerHTML = formattedContent;
                console.log('Content loaded to DOM for topic:', topic.title);
                console.log('Formatted content length:', formattedContent.length);
            }
            
            console.log('Topic completed and ready for click:', topic.title);
            console.log('CompletedTopics updated:', Object.keys(this.completedTopics));
            break;
            
        default:
            if (icons.pending) icons.pending.style.display = 'inline-block';
            if (statusText) statusText.textContent = 'Sırada bekliyor...';
            topicElement.classList.add('pending');
    }
}

toggleSubTopicDetails(topicId) {
    console.log('toggleSubTopicDetails called for:', topicId);
    
    const topicElement = document.getElementById(`subtopic-${topicId}`);
    if (!topicElement) {
        console.error('Topic element not found:', `subtopic-${topicId}`);
        return;
    }

    const detailsDiv = topicElement.querySelector('.subtopic-details');
    const expandIcon = topicElement.querySelector('.expand-icon i');
    const contentText = topicElement.querySelector('.subtopic-content-text');
    
    if (!detailsDiv || !expandIcon) {
        console.error('Required elements not found for topic:', topicId);
        return;
    }
    
    // Topic nesnesini bul
    const topic = this.researchProgress.subTopics.find(t => t.id === topicId);
    const completedTopic = this.completedTopics[topicId];
    
    console.log('Topic object:', topic);
    console.log('Completed topic data:', completedTopic);
    console.log('Current display style:', detailsDiv.style.display);
    
    if (this.expandedTopics.has(topicId)) {
        // Kapat
        detailsDiv.style.display = 'none';
        expandIcon.className = 'fas fa-chevron-down';
        this.expandedTopics.delete(topicId);
        topicElement.classList.remove('expanded');
        console.log('✅ Topic closed:', topicId);
    } else {
        // Aç - içerik kontrolü yap
        let contentToShow = "İçerik mevcut değil.";
        
        if (completedTopic && completedTopic.content) {
            contentToShow = this.formatTopicContent(completedTopic.content);
        } else if (topic && topic.content) {
            contentToShow = this.formatTopicContent(topic.content);
        }
        
        // İçeriği güncelle
        if (contentText) {
            contentText.innerHTML = contentToShow;
        }
        
        // Göster
        detailsDiv.style.display = 'block';
        expandIcon.className = 'fas fa-chevron-up';
        this.expandedTopics.add(topicId);
        topicElement.classList.add('expanded');
        
        console.log('✅ Topic opened:', topicId);
        console.log('Content shown length:', contentToShow.length);
    }
}

// İçerik formatlamada da küçük bir düzeltme
formatTopicContent(content) {
    if (!content || typeof content !== 'string') {
        return '<p>İçerik mevcut değil.</p>';
    }
    
    return content
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/^(.*)$/, '<p>$1</p>');
}

// Debugging için yardımcı fonksiyon
debugSubTopicStatus(topicId = null) {
    if (topicId) {
        const topic = this.researchProgress.subTopics.find(t => t.id === topicId);
        const completed = this.completedTopics[topicId];
        console.log(`Debug for ${topicId}:`, {
            topic: topic,
            completed: completed,
            expanded: this.expandedTopics.has(topicId)
        });
    } else {
        console.log('All topics debug:', {
            subTopics: this.researchProgress.subTopics,
            completedTopics: this.completedTopics,
            expandedTopics: Array.from(this.expandedTopics)
        });
    }
}

    showViewReportButton() {
        // Daha önce eklenmiş butonu kontrol et
        if (document.getElementById('viewReportButton')) return;

        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'view-report-container';
        buttonContainer.id = 'viewReportContainer';
        
        buttonContainer.innerHTML = `
            <div class="report-ready-message">
                <i class="fas fa-check-circle"></i>
                <span>Araştırma raporu hazır!</span>
            </div>
            <button class="view-report-btn" id="viewReportButton">
                <i class="fas fa-external-link-alt"></i>
                Detaylı Raporu Görüntüle
            </button>
        `;
        
        const button = buttonContainer.querySelector('#viewReportButton');
        button.addEventListener('click', () => {
            this.openDetailedReport();
        });
        
        this.messagesContainer.appendChild(buttonContainer);
        this.scrollToBottom();
    }

    sendFollowUpMessage() {
        // Biraz bekleme süresi ekle
        setTimeout(() => {
            const followUpMessage = "🎯 Harika! Araştırma raporunuz hazır. Yukarıdaki **'Detaylı Raporu Görüntüle'** butonuna tıklayarak tüm bulgularımızı inceleyebilirsiniz. \n\n💡 Takıldığınız yerler olursa benimle birlikte raporu inceleyelim! Herhangi bir konuyu daha detayına inmek isterseniz, sadece sorun - birlikte çalışabiliriz! 🤝";
            
            this.addMessage(followUpMessage, 'ai');
        }, 1500);
    }

    openDetailedReport() {
        const reportWindow = window.open('', '_blank', 'width=1200,height=800,scrollbars=yes,resizable=yes');
        
        const reportHTML = this.generateReportHTML();
        reportWindow.document.write(reportHTML);
        reportWindow.document.close();
        
        // PDF export fonksiyonunu yeni pencereye ekle
        reportWindow.exportToPDF = () => {
            reportWindow.print();
        };
    }

    generateReportHTML() {
        const currentDate = new Date().toLocaleDateString('tr-TR');
        const currentTime = new Date().toLocaleTimeString('tr-TR');
        
        let topicsHTML = '';
        this.researchProgress.subTopics.forEach((topic, index) => {
            const topicData = this.completedTopics[topic.id];
            const content = topicData ? this.formatTopicContent(topicData.content) : 
                           topic.content ? this.formatTopicContent(topic.content) : 'İçerik mevcut değil.';
            
            topicsHTML += `
                <div class="report-section">
                    <div class="section-header">
                        <span class="section-number">${index + 1}</span>
                        <h2 class="section-title">${topic.title}</h2>
                    </div>
                    <div class="section-content">
                        ${content}
                    </div>
                </div>
            `;
        });

        return `
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Araştırma Raporu - CrewAI Multi-Agent</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f8f9fa;
        }
        
        .report-container {
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
            min-height: 100vh;
        }
        
        .report-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 3rem 2rem;
            text-align: center;
        }
        
        .report-title {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 1rem;
        }
        
        .report-subtitle {
            font-size: 1.2rem;
            opacity: 0.9;
            margin-bottom: 2rem;
        }
        
        .report-meta {
            display: flex;
            justify-content: center;
            gap: 2rem;
            font-size: 0.9rem;
        }
        
        .meta-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .report-content {
            padding: 2rem;
        }
        
        .report-section {
            margin-bottom: 3rem;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        
        .section-header {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 1.5rem 2rem;
            border-bottom: 3px solid #667eea;
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .section-number {
            background: #667eea;
            color: white;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 1.2rem;
        }
        
        .section-title {
            color: #495057;
            font-size: 1.5rem;
            font-weight: 600;
        }
        
        .section-content {
            padding: 2rem;
            background: white;
        }
        
        .section-content p {
            margin-bottom: 1rem;
            text-align: justify;
        }
        
        .section-content strong {
            color: #667eea;
            font-weight: 600;
        }
        
        .section-content em {
            font-style: italic;
            color: #6c757d;
        }
        
        .section-content code {
            background: #f8f9fa;
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
        }
        
        .export-controls {
            position: fixed;
            top: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
            z-index: 1000;
        }
        
        .export-btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(40,167,69,0.3);
        }
        
        .export-btn:hover {
            background: #218838;
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(40,167,69,0.4);
        }
        
        .close-btn {
            background: #6c757d;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.3s ease;
        }
        
        .close-btn:hover {
            background: #545b62;
            transform: translateY(-2px);
        }
        
        @media print {
            .export-controls {
                display: none;
            }
            
            .report-container {
                box-shadow: none;
            }
            
            .report-section {
                break-inside: avoid;
                page-break-inside: avoid;
            }
        }
        
        @media (max-width: 768px) {
            .report-header {
                padding: 2rem 1rem;
            }
            
            .report-title {
                font-size: 2rem;
            }
            
            .report-content {
                padding: 1rem;
            }
            
            .section-header {
                padding: 1rem;
                flex-direction: column;
                text-align: center;
                gap: 0.5rem;
            }
            
            .section-content {
                padding: 1rem;
            }
            
            .export-controls {
                position: static;
                justify-content: center;
                margin: 1rem;
            }
        }
    </style>
</head>
<body>
    <div class="export-controls">
        <button class="export-btn" onclick="exportToPDF()">
            📄 PDF Olarak Kaydet
        </button>
        <button class="close-btn" onclick="window.close()">
            ✕ Kapat
        </button>
    </div>
    
    <div class="report-container">
        <div class="report-header">
            <h1 class="report-title">🔍 Araştırma Raporu</h1>
            <p class="report-subtitle">CrewAI Multi-Agent Sistemi ile Hazırlanmıştır</p>
            <div class="report-meta">
                <div class="meta-item">
                    <span>📅</span>
                    <span>${currentDate}</span>
                </div>
                <div class="meta-item">
                    <span>🕐</span>
                    <span>${currentTime}</span>
                </div>
                <div class="meta-item">
                    <span>🤖</span>
                    <span>${this.researchProgress.subTopics.length} Alt Başlık</span>
                </div>
            </div>
        </div>
        
        <div class="report-content">
            ${topicsHTML}
        </div>
    </div>
</body>
</html>
        `;
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

    saveToHistory(message, sender) { /* Implementation needed */ }
    loadChatHistory() { /* Implementation needed */ }
    getSetting(key) { return true; }
    playNotificationSound() { /* Implementation needed */ }
    closeModal() { /* Implementation needed */ }
}

let chat;
document.addEventListener('DOMContentLoaded', () => {
    chat = new LangGraphChatWithProgress();
});