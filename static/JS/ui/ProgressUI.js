// static/js/ui/ProgressUI.js
import { DOM } from './DOM.js';

export class ProgressUI {
    constructor() {
        this.mainSteps = [];
        this.subTopics = [];
        this.completedTopics = {};
        this.expandedTopics = new Set();
        this.currentResearchData = null;
    }
    
    // Ana Araştırma Adımlarını oluşturur
    createMainStepsUI(steps) {
        this.mainSteps = steps;
        const stepsContainer = document.createElement('div');
        stepsContainer.className = 'research-steps-container';
        stepsContainer.id = 'mainStepsContainer';
        
        stepsContainer.innerHTML = `
            <div class="steps-header">
                <div class="steps-title"><i class="fas fa-cogs"></i><span>CrewAI Araştırma Süreci</span></div>
                <div class="steps-status">Başlatılıyor...</div>
            </div>
            <div class="steps-list"></div>
        `;

        const stepsList = stepsContainer.querySelector('.steps-list');
        steps.forEach((step, index) => {
            const stepElement = document.createElement('div');
            stepElement.className = 'step-item pending';
            stepElement.id = `main-step-${step.id}`;
            stepElement.innerHTML = `
                <div class="step-indicator">
                    <div class="step-number">${index + 1}</div>
                    <div class="step-status-icon">
                        <i class="fas fa-circle pending-icon"></i>
                        <i class="fas fa-spinner fa-spin spinning-icon" style="display: none;"></i>
                        <i class="fas fa-check completed-icon" style="display: none;"></i>
                    </div>
                </div>
                <div class="step-content">
                    <div class="step-title">${step.title}</div>
                    <div class="step-agent">Agent: ${step.agent}</div>
                    <div class="step-status">Bekliyor...</div>
                    <div class="step-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: 0%"></div>
                        </div>
                    </div>
                </div>
            `;
            stepsList.appendChild(stepElement);
        });
        
        DOM.messagesContainer.appendChild(stepsContainer);
        this.scrollToBottom();
    }

    updateMainStepStatus(stepId, status, message = null) {
        const stepElement = document.getElementById(`main-step-${stepId}`);
        if (!stepElement) return;

        const icons = {
            pending: stepElement.querySelector('.pending-icon'),
            running: stepElement.querySelector('.spinning-icon'),
            completed: stepElement.querySelector('.completed-icon')
        };
        const statusText = stepElement.querySelector('.step-status');
        const progressFill = stepElement.querySelector('.progress-fill');
        const stepsStatus = document.querySelector('.steps-status');
        
        // Tüm iconları gizle
        Object.values(icons).forEach(icon => icon.style.display = 'none');
        stepElement.classList.remove('pending', 'running', 'completed');

        if (status === 'running') {
            icons.running.style.display = 'inline-block';
            statusText.textContent = message || 'İşlem devam ediyor...';
            stepElement.classList.add('running');
            progressFill.style.width = '50%';
            if (stepsStatus) stepsStatus.textContent = 'Araştırma devam ediyor...';
        } else if (status === 'completed') {
            icons.completed.style.display = 'inline-block';
            statusText.textContent = message || 'Tamamlandı ✓';
            stepElement.classList.add('completed');
            progressFill.style.width = '100%';
        } else {
            icons.pending.style.display = 'inline-block';
            statusText.textContent = message || 'Bekliyor...';
            stepElement.classList.add('pending');
            progressFill.style.width = '0%';
        }
    }

    // Workflow mesajlarını işler
    handleWorkflowMessage(agent, message) {
        console.log(`📡 Workflow Message: ${agent} -> ${message}`);
        
        // Agent'e göre step ID'sini belirle
        const agentStepMap = {
            'WebResearcher': 'web-research',
            'YouTubeAnalyst': 'youtube-analysis',
            'ReportProcessor': 'report-structure',
            'DetailResearcher': 'detail-research',
            'CrewAI-Manager': 'manager'
        };
        
        const stepId = agentStepMap[agent];
        if (!stepId) return;

        if (message.includes('başlatılıyor') || message.includes('başlat')) {
            this.updateMainStepStatus(stepId, 'running', message);
        } else if (message.includes('tamamland') || message.includes('✅')) {
            this.updateMainStepStatus(stepId, 'completed', message);
        }
    }

    // Alt Başlık UI'ını yönetir
    initializeSubTopics(subtopics) {
        // Varsa eski waiting elementini kaldır
        const waitingElement = document.getElementById('waitingSubTopics');
        if (waitingElement) waitingElement.remove();

        console.log('📋 Subtopics alındı:', subtopics);

        this.subTopics = subtopics.map((topic, index) => ({
            id: `subtopic-${index}`,
            title: typeof topic === 'string' ? topic : (topic.alt_baslik || topic.title || `Konu ${index + 1}`),
            status: 'pending',
            content: ''
        }));
        
        this.createSubTopicsUI();
        this.scrollToBottom();
    }

    createSubTopicsUI() {
        const container = document.createElement('div');
        container.className = 'subtopics-container';
        container.id = 'subTopicsContainer';
        container.innerHTML = `
            <div class="subtopics-header">
                <div class="subtopics-title">
                    <i class="fas fa-list-ul"></i>
                    <span>Detay Araştırma Konuları (${this.subTopics.length})</span>
                </div>
                <div class="subtopics-progress">
                    <span class="progress-text">0/${this.subTopics.length} tamamlandı</span>
                    <div class="overall-progress-bar">
                        <div class="overall-progress-fill" style="width: 0%"></div>
                    </div>
                </div>
            </div>
            <div class="subtopics-list"></div>
        `;
        
        const list = container.querySelector('.subtopics-list');
        this.subTopics.forEach((topic, index) => {
            const topicElement = this.createSubTopicElement(topic, index);
            list.appendChild(topicElement);
        });
        
        DOM.messagesContainer.appendChild(container);
    }
    
    createSubTopicElement(topic, index) {
        const topicElement = document.createElement('div');
        topicElement.className = 'subtopic-item pending';
        topicElement.id = `subtopic-${topic.id}`;
        
        topicElement.innerHTML = `
            <div class="subtopic-main-row">
                <div class="subtopic-indicator">
                    <div class="subtopic-number">${index + 1}</div>
                    <div class="subtopic-status-icon">
                        <i class="fas fa-circle pending-icon"></i>
                        <i class="fas fa-spinner fa-spin spinning-icon" style="display: none;"></i>
                        <i class="fas fa-check completed-icon" style="display: none;"></i>
                    </div>
                </div>
                <div class="subtopic-content">
                    <div class="subtopic-title">${topic.title}</div>
                    <div class="subtopic-status">Sırada bekliyor...</div>
                    <div class="subtopic-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: 0%"></div>
                        </div>
                    </div>
                </div>
                <div class="expand-icon"><i class="fas fa-chevron-down"></i></div>
            </div>
            <div class="subtopic-details" style="display: none;">
                <div class="subtopic-content-text">İçerik henüz hazırlanmadı...</div>
                <div class="subtopic-timestamp"></div>
            </div>
        `;
        
        // Click handler'ı sadece completed durumda aktif olacak
        const mainRow = topicElement.querySelector('.subtopic-main-row');
        mainRow.addEventListener('click', () => {
            if (topic.status === 'completed') {
                this.toggleSubTopicDetails(topic.id);
            }
        });
        
        return topicElement;
    }

    updateSubTopicStatus(topicTitle, status, content = '') {
        console.log(`🔄 Subtopic güncelleniyor: ${topicTitle} -> ${status}`);
        
        const topic = this.subTopics.find(t => t.title === topicTitle);
        if (!topic) {
            console.warn(`⚠️ Subtopic bulunamadı: ${topicTitle}`);
            return;
        }

        topic.status = status;
        if (content) topic.content = content;

        const topicElement = document.getElementById(`subtopic-${topic.id}`);
        if (!topicElement) {
            console.warn(`⚠️ Subtopic element bulunamadı: subtopic-${topic.id}`);
            return;
        }

        const icons = {
            pending: topicElement.querySelector('.pending-icon'),
            running: topicElement.querySelector('.spinning-icon'),
            completed: topicElement.querySelector('.completed-icon')
        };
        const statusText = topicElement.querySelector('.subtopic-status');
        const headerRow = topicElement.querySelector('.subtopic-main-row');
        const progressFill = topicElement.querySelector('.progress-fill');

        // Tüm iconları gizle ve class'ları temizle
        Object.values(icons).forEach(icon => icon.style.display = 'none');
        topicElement.classList.remove('pending', 'running', 'completed', 'clickable');
        
        if (status === 'running') {
            icons.running.style.display = 'inline-block';
            statusText.textContent = 'Araştırılıyor...';
            topicElement.classList.add('running');
            progressFill.style.width = '50%';
            headerRow.style.cursor = 'default';
        } else if (status === 'completed') {
            icons.completed.style.display = 'inline-block';
            statusText.textContent = 'Tamamlandı - Detaylar için tıkla';
            topicElement.classList.add('completed', 'clickable');
            headerRow.style.cursor = 'pointer';
            progressFill.style.width = '100%';
            
            // Timestamp ekle
            const timestampDiv = topicElement.querySelector('.subtopic-timestamp');
            if (timestampDiv) {
                timestampDiv.textContent = `Tamamlandı: ${new Date().toLocaleTimeString()}`;
            }
        } else {
            icons.pending.style.display = 'inline-block';
            statusText.textContent = 'Sırada bekliyor...';
            topicElement.classList.add('pending');
            progressFill.style.width = '0%';
            headerRow.style.cursor = 'default';
        }
        
        // Genel progress'i güncelle
        this.updateOverallProgress();
    }

    updateOverallProgress() {
        const completedCount = this.subTopics.filter(t => t.status === 'completed').length;
        const totalCount = this.subTopics.length;
        const percentage = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;
        
        const progressText = document.querySelector('.progress-text');
        const progressFill = document.querySelector('.overall-progress-fill');
        
        if (progressText) {
            progressText.textContent = `${completedCount}/${totalCount} tamamlandı`;
        }
        
        if (progressFill) {
            progressFill.style.width = `${percentage}%`;
        }
        
        // Tüm konular tamamlandıysa rapor butonunu göster
        if (completedCount === totalCount && totalCount > 0) {
            setTimeout(() => this.showViewReportButton(), 1000);
        }
    }

    toggleSubTopicDetails(topicId) {
        const topic = this.subTopics.find(t => t.id === topicId);
        if (!topic || topic.status !== 'completed') return;

        const topicElement = document.getElementById(`subtopic-${topicId}`);
        const detailsDiv = topicElement.querySelector('.subtopic-details');
        const expandIcon = topicElement.querySelector('.expand-icon i');

        if (this.expandedTopics.has(topicId)) {
            // Kapat
            detailsDiv.style.display = 'none';
            expandIcon.className = 'fas fa-chevron-down';
            this.expandedTopics.delete(topicId);
            topicElement.classList.remove('expanded');
        } else {
            // Aç
            const contentText = topicElement.querySelector('.subtopic-content-text');
            contentText.innerHTML = this.formatContent(topic.content);
            detailsDiv.style.display = 'block';
            expandIcon.className = 'fas fa-chevron-up';
            this.expandedTopics.add(topicId);
            topicElement.classList.add('expanded');
            
            // Açılan bölüme scroll
            setTimeout(() => {
                detailsDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }, 100);
        }
    }

    // Rapor ve içerik formatlama
    showViewReportButton() {
        if (document.getElementById('viewReportButton')) return;
        
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'view-report-container';
        buttonContainer.innerHTML = `
            <div class="report-ready-message">
                <i class="fas fa-check-circle"></i>
                <span>🎉 Araştırma raporu hazır!</span>
            </div>
            <button class="view-report-btn" id="viewReportButton">
                <i class="fas fa-external-link-alt"></i>
                Detaylı Raporu Görüntüle
            </button>
            <div class="report-stats">
                <span>📊 ${this.subTopics.length} konu detaylandırıldı</span>
                <span>⏰ ${new Date().toLocaleTimeString()} tarihinde tamamlandı</span>
            </div>
        `;
        
        const button = buttonContainer.querySelector('#viewReportButton');
        button.addEventListener('click', () => this.triggerReportView());
        
        DOM.messagesContainer.appendChild(buttonContainer);
        this.scrollToBottom();
        
        // Button animasyonu
        setTimeout(() => buttonContainer.classList.add('animate-in'), 100);
    }
    
    // Bu fonksiyon App.js tarafından override edilecek
    triggerReportView() {
        console.log("🔍 Rapor görüntüleme talep edildi");
        // App.js'ten bu fonksiyon override edilecek
        if (window.openDetailedReport) {
            window.openDetailedReport(this.currentResearchData);
        }
    }
    
    // Araştırma verilerini kaydet
    setResearchData(data) {
        this.currentResearchData = data;
    }
    
    formatContent(content) {
        if (!content || typeof content !== 'string') return '<p>İçerik mevcut değil.</p>';
        
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^(.*)$/, '<p>$1</p>');
    }
    
    // Utility functions
    scrollToBottom() {
        setTimeout(() => {
            DOM.messagesContainer.scrollTop = DOM.messagesContainer.scrollHeight;
        }, 100);
    }
    
    // Temizlik fonksiyonu
    cleanup() {
        const containers = ['mainStepsContainer', 'subTopicsContainer', 'viewReportButton'];
        containers.forEach(id => {
            const element = document.getElementById(id);
            if (element) element.remove();
        });
        
        this.mainSteps = [];
        this.subTopics = [];
        this.completedTopics = {};
        this.expandedTopics.clear();
        this.currentResearchData = null;
    }
    
    // Debugging için
    getStatus() {
        return {
            mainSteps: this.mainSteps.length,
            subTopics: this.subTopics.length,
            completed: this.subTopics.filter(t => t.status === 'completed').length,
            expanded: this.expandedTopics.size,
            hasResearchData: !!this.currentResearchData
        };
    }
}