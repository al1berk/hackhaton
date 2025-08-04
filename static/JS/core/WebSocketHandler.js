// static/js/core/WebSocketHandler.js

export default class WebSocketHandler {
    constructor(chatId, onMessage, onConnectionChange) {
        this.chatId = chatId;
        this.onMessage = onMessage;
        this.onConnectionChange = onConnectionChange;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.isConnecting = false;
        this.messageQueue = [];
        this.lastPingTime = null;
        this.pingInterval = null;
        
        // Test parametreleri için callback'ler
        this.onTestParametersRequest = null;
        this.onTestGenerated = null;
        this.onTestEvaluation = null;
        
        this.connect();
    }

    connect() {
        if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        this.isConnecting = true;
        
        // Chat ID yoksa varsayılan bir ID kullan
        const chatId = this.chatId || 'default';
        const wsUrl = `ws://${window.location.host}/ws/${chatId}`;
        
        console.log(`🔌 WebSocket bağlantısı kuruluyor: ${wsUrl}`);
        
        try {
            this.ws = new WebSocket(wsUrl);
            this.setupEventListeners();
        } catch (error) {
            console.error('❌ WebSocket oluşturma hatası:', error);
            this.handleConnectionError();
        }
    }

    setupEventListeners() {
        this.ws.onopen = () => {
            console.log('✅ WebSocket bağlantısı kuruldu');
            this.isConnecting = false;
            this.reconnectAttempts = 0;
            this.onConnectionChange('connected');
            
            // Kuyruktaki mesajları gönder
            this.processMessageQueue();
            
            // Ping başlat
            this.startPing();
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('❌ WebSocket mesaj parse hatası:', error);
            }
        };

        this.ws.onerror = (error) => {
            console.error('❌ WebSocket hatası:', error);
            this.handleConnectionError();
        };

        this.ws.onclose = (event) => {
            console.log(`🔌 WebSocket bağlantısı kapandı. Code: ${event.code}, Reason: ${event.reason}`);
            this.isConnecting = false;
            this.stopPing();
            
            if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
                this.handleReconnect();
            } else {
                this.onConnectionChange('disconnected');
            }
        };
    }

    handleMessage(data) {
        console.log('📨 WebSocket mesaj alındı:', data.type);
        
        switch (data.type) {
            case 'ai_response':
                this.onMessage(data);
                break;
                
            case 'crew_research_start':
            case 'crew_research_success':
            case 'crew_research_error':
            case 'crew_progress':
            case 'workflow_message':
                this.onMessage(data);
                break;
                
            case 'test_parameters_request':
                this.handleTestParametersRequest(data);
                break;
                
            case 'test_parameters_error':
                this.handleTestParametersError(data);
                break;
                
            case 'test_parameters_complete':
                this.handleTestParametersComplete(data);
                break;
                
            case 'test_generated':
                this.handleTestGenerated(data);
                break;
                
            case 'test_evaluation_complete':
                this.handleTestEvaluation(data);
                break;
                
            case 'topic_explanation':
                this.handleTopicExplanation(data);
                break;
                
            case 'error':
                console.error('❌ Server error:', data.message);
                this.onMessage({
                    type: 'error',
                    content: data.message,
                    timestamp: new Date().toISOString()
                });
                break;
                
            case 'pong':
                this.lastPingTime = Date.now();
                break;
                
            default:
                console.warn('⚠️ Bilinmeyen mesaj türü:', data.type);
                this.onMessage(data);
        }
    }

    handleTestParametersRequest(data) {
        console.log('🎯 Test parametreleri isteniyor:', data.stage);
        
        // Test parametreleri UI'sini göster
        this.showTestParametersUI(data);
    }

    handleTestParametersError(data) {
        console.log('❌ Test parametreleri hatası:', data.content);
        
        // Hata mesajını göster
        this.showTestParametersError(data.content);
    }

    handleTestParametersComplete(data) {
        console.log('✅ Test parametreleri tamamlandı:', data.parameters);
        
        // Parametreler tamamlandı mesajını göster
        this.onMessage({
            type: 'ai_response',
            message: data.content,
            timestamp: data.timestamp || new Date().toISOString()
        });
    }

    handleTestGenerated(data) {
        console.log('🧠 Test oluşturuldu:', data);
        
        // Test sonuçlarını göster ve çözme butonunu ekle
        this.showTestResults(data);
    }

    handleTestEvaluation(data) {
        console.log('📊 Test değerlendirmesi:', data.evaluation);
        
        // Test sonuçlarını chat'e ekle
        this.onMessage({
            type: 'test_evaluation',
            evaluation: data.evaluation,
            timestamp: data.timestamp || new Date().toISOString()
        });
    }

    handleTopicExplanation(data) {
        console.log('📖 Konu açıklaması:', data.topic);
        
        // Konu açıklamasını göster
        this.onMessage({
            type: 'ai_response',
            message: data.explanation,
            timestamp: data.timestamp || new Date().toISOString(),
            metadata: {
                topic: data.topic,
                explanation_type: 'topic_detail'
            }
        });
    }

    showTestParametersUI(data) {
        const messagesContainer = document.getElementById('messagesContainer');
        if (!messagesContainer) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai-message test-parameters-message';
        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="test-parameters-content">
                    <div class="parameters-header">
                        <i class="fas fa-cog"></i>
                        <h3>Test Ayarları</h3>
                    </div>
                    <p>${data.content}</p>
                    
                    <div class="parameters-form" id="parametersForm-${data.stage}">
                        ${this.renderParametersForm(data)}
                    </div>
                </div>
            </div>
            <div class="message-time">${new Date().toLocaleTimeString('tr-TR')}</div>
        `;

        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        // Form event listener'larını ekle
        this.setupParametersFormEvents(data.stage);
    }

    renderParametersForm(data) {
        switch (data.stage) {
            case 'question_types':
                return `
                    <div class="question-types-grid">
                        ${data.options.map(option => `
                            <div class="question-type-card ${option.selected ? 'selected' : ''}">
                                <div class="card-header">
                                    <input type="checkbox" 
                                           id="type_${option.id}"
                                           value="${option.id}" 
                                           ${option.selected ? 'checked' : ''}
                                           onchange="toggleQuestionType('${option.id}')">
                                    <label for="type_${option.id}" class="type-label">
                                        <strong>${option.label}</strong>
                                    </label>
                                </div>
                                <div class="card-description">
                                    <small>${option.description}</small>
                                </div>
                                <div class="card-counter">
                                    <label for="count_${option.id}">Soru Sayısı:</label>
                                    <div class="counter-controls">
                                        <button type="button" onclick="adjustCount('${option.id}', -1)" ${option.selected ? '' : 'disabled'}>-</button>
                                        <input type="number" 
                                               id="count_${option.id}"
                                               min="0" 
                                               max="${option.max_count}" 
                                               value="${option.selected ? option.default_count : 0}"
                                               ${option.selected ? '' : 'disabled'}
                                               onchange="validateCount('${option.id}')">
                                        <button type="button" onclick="adjustCount('${option.id}', 1)" ${option.selected ? '' : 'disabled'}>+</button>
                                    </div>
                                    <small>Max: ${option.max_count}</small>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                    <div class="parameters-summary">
                        <div class="total-questions">
                            <strong>Toplam Soru: <span id="totalQuestions">8</span></strong>
                        </div>
                    </div>
                    <button class="parameters-next-btn" onclick="window.submitParametersForm('${data.stage}')">
                        ${data.next_button_text}
                    </button>
                `;

            case 'difficulty':
                return `
                    <div class="difficulty-options">
                        ${data.options.map(option => `
                            <div class="difficulty-card ${option.selected ? 'selected' : ''}">
                                <input type="radio" 
                                       id="diff_${option.id}"
                                       name="difficulty" 
                                       value="${option.id}" 
                                       ${option.selected ? 'checked' : ''}>
                                <label for="diff_${option.id}" class="difficulty-label">
                                    <div class="difficulty-title">${option.label}</div>
                                    <div class="difficulty-desc">${option.description}</div>
                                </label>
                            </div>
                        `).join('')}
                    </div>
                    <button class="parameters-next-btn" onclick="window.submitParametersForm('${data.stage}')">
                        ${data.next_button_text}
                    </button>
                `;

            case 'student_level':
                return `
                    <div class="level-options">
                        ${data.options.map(option => `
                            <div class="level-card ${option.selected ? 'selected' : ''}">
                                <input type="radio" 
                                       id="level_${option.id}"
                                       name="student_level" 
                                       value="${option.id}" 
                                       ${option.selected ? 'checked' : ''}>
                                <label for="level_${option.id}" class="level-label">
                                    <div class="level-title">${option.label}</div>
                                    <div class="level-desc">${option.description}</div>
                                </label>
                            </div>
                        `).join('')}
                    </div>
                    <button class="parameters-next-btn" onclick="window.submitParametersForm('${data.stage}')">
                        ${data.next_button_text}
                    </button>
                `;

            default:
                return '<p>Bilinmeyen parametre türü</p>';
        }
    }

    setupParametersFormEvents(stage) {
        // Global fonksiyonları oluştur
        window.submitParametersForm = (formStage) => {
            this.submitParametersForm(formStage);
        };

        // Soru türü toggle fonksiyonu
        window.toggleQuestionType = (typeId) => {
            const checkbox = document.getElementById(`type_${typeId}`);
            const countInput = document.getElementById(`count_${typeId}`);
            const card = checkbox.closest('.question-type-card');
            const buttons = card.querySelectorAll('.counter-controls button');
            
            if (checkbox.checked) {
                card.classList.add('selected');
                countInput.disabled = false;
                buttons.forEach(btn => btn.disabled = false);
                if (countInput.value === '0') {
                    countInput.value = '5'; // varsayılan değer
                }
            } else {
                card.classList.remove('selected');
                countInput.disabled = true;
                countInput.value = '0';
                buttons.forEach(btn => btn.disabled = true);
            }
            this.updateTotalQuestions();
        };

        // Soru sayısı ayarlama fonksiyonu
        window.adjustCount = (typeId, change) => {
            const countInput = document.getElementById(`count_${typeId}`);
            const currentValue = parseInt(countInput.value) || 0;
            const newValue = Math.max(0, Math.min(parseInt(countInput.max), currentValue + change));
            countInput.value = newValue;
            this.updateTotalQuestions();
        };

        // Soru sayısı doğrulama fonksiyonu
        window.validateCount = (typeId) => {
            const countInput = document.getElementById(`count_${typeId}`);
            const value = parseInt(countInput.value) || 0;
            const max = parseInt(countInput.max) || 20;
            
            if (value > max) {
                countInput.value = max;
            } else if (value < 0) {
                countInput.value = 0;
            }
            
            this.updateTotalQuestions();
        };

        // İlk yüklemede toplam soruları hesapla
        if (stage === 'question_types') {
            setTimeout(() => this.updateTotalQuestions(), 100);
        }
    }

    updateTotalQuestions() {
        const totalElement = document.getElementById('totalQuestions');
        if (!totalElement) return;

        let total = 0;
        document.querySelectorAll('[id^="count_"]').forEach(input => {
            const checkbox = document.getElementById(input.id.replace('count_', 'type_'));
            if (checkbox && checkbox.checked) {
                total += parseInt(input.value) || 0;
            }
        });

        totalElement.textContent = total;
        
        // Total'a göre buton durumunu güncelle
        const nextBtn = document.querySelector('.parameters-next-btn');
        if (nextBtn) {
            if (total === 0) {
                nextBtn.disabled = true;
                nextBtn.textContent = 'En az 1 soru seçmelisiniz';
            } else {
                nextBtn.disabled = false;
                nextBtn.textContent = 'Devam Et';
            }
        }
    }

    submitParametersForm(stage) {
        let response = '';

        switch (stage) {
            case 'question_types':
                const selectedTypes = [];
                document.querySelectorAll(`#parametersForm-${stage} input[type="checkbox"]:checked`).forEach(cb => {
                    selectedTypes.push(cb.nextElementSibling.textContent);
                });
                response = selectedTypes.join(', ');
                break;

            case 'difficulty':
                const selectedDifficulty = document.querySelector(`#parametersForm-${stage} input[type="radio"]:checked`);
                response = selectedDifficulty ? selectedDifficulty.nextElementSibling.textContent : 'orta';
                break;

            case 'count':
                const countInput = document.getElementById('questionCount');
                response = countInput ? countInput.value : '5';
                break;
        }

        // Formu devre dışı bırak
        const form = document.getElementById(`parametersForm-${stage}`);
        if (form) {
            form.style.opacity = '0.5';
            form.style.pointerEvents = 'none';
        }

        // Parametreleri sunucuya gönder
        this.sendMessage({
            type: 'test_parameters_response',
            stage: stage,
            response: response
        });
    }

    showTestParametersError(message) {
        const messagesContainer = document.getElementById('messagesContainer');
        if (!messagesContainer) return;

        const errorDiv = document.createElement('div');
        errorDiv.className = 'message ai-message error-message';
        errorDiv.innerHTML = `
            <div class="message-content">
                <div class="error-content">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>${message}</p>
                </div>
            </div>
            <div class="message-time">${new Date().toLocaleTimeString('tr-TR')}</div>
        `;

        messagesContainer.appendChild(errorDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    showTestResults(data) {
        const messagesContainer = document.getElementById('messagesContainer');
        if (!messagesContainer) return;

        // Test verilerini kontrol et ve güvenli bir şekilde parse et
        let testQuestions = null;
        let questionCount = 0;
        let questionTypes = [];

        try {
            if (data.questions) {
                testQuestions = data.questions;
                
                // Question count'u güvenli şekilde al
                if (testQuestions.document_info) {
                    questionCount = testQuestions.document_info.question_count || 0;
                    
                    // Question types'ı güvenli şekilde al
                    const qTypes = testQuestions.document_info.question_types;
                    if (qTypes && typeof qTypes === 'object') {
                        // Eğer object ise, değerleri topla veya anahtarları al
                        if (Array.isArray(qTypes)) {
                            questionTypes = qTypes;
                        } else {
                            // Object ise anahtarları al ve Türkçe'ye çevir
                            const typeLabels = {
                                "coktan_secmeli": "Çoktan Seçmeli",
                                "klasik": "Klasik",
                                "bosluk_doldurma": "Boşluk Doldurma",
                                "dogru_yanlis": "Doğru-Yanlış"
                            };
                            
                            questionTypes = Object.keys(qTypes)
                                .filter(key => qTypes[key] > 0)
                                .map(key => typeLabels[key] || key);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('❌ Test verilerini parse ederken hata:', error);
            questionCount = 'N/A';
            questionTypes = ['Karışık'];
        }

        const testDiv = document.createElement('div');
        testDiv.className = 'message ai-message test-results-message';
        testDiv.innerHTML = `
            <div class="message-content">
                <div class="test-results-content">
                    <div class="test-header">
                        <i class="fas fa-brain"></i>
                        <h3>Test Hazır!</h3>
                    </div>
                    <p>${data.content}</p>
                    
                    <div class="test-actions">
                        <button class="solve-test-btn" onclick="window.startTest('${this.escapeForAttribute(JSON.stringify(testQuestions))}')">
                            <i class="fas fa-play"></i>
                            Testi Çöz
                        </button>
                        <button class="preview-test-btn" onclick="window.previewTest('${this.escapeForAttribute(JSON.stringify(testQuestions))}')">
                            <i class="fas fa-eye"></i>
                            Önizleme
                        </button>
                    </div>
                    
                    <div class="test-info">
                        <div class="info-item">
                            <span>Soru Sayısı:</span>
                            <strong>${questionCount}</strong>
                        </div>
                        <div class="info-item">
                            <span>Soru Türleri:</span>
                            <strong>${questionTypes.join(', ') || 'Karışık'}</strong>
                        </div>
                    </div>
                </div>
            </div>
            <div class="message-time">${new Date().toLocaleTimeString('tr-TR')}</div>
        `;

        messagesContainer.appendChild(testDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        // Global fonksiyonları tanımla
        window.startTest = (questionsData) => {
            this.startTest(questionsData);
        };

        window.previewTest = (questionsData) => {
            this.previewTest(questionsData);
        };
    }

    // HTML attribute'lar için string escape fonksiyonu
    escapeForAttribute(str) {
        if (!str) return '';
        return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    startTest(questionsData) {
        // Test verilerini localStorage'a kaydet
        const testData = typeof questionsData === 'string' ? 
            JSON.parse(questionsData) : questionsData;
        
        localStorage.setItem('currentTestQuestions', JSON.stringify(testData));
        
        // Yeni sekmede test sayfasını aç
        window.open('/static/test_solver.html', '_blank');
    }

    previewTest(questionsData) {
        // Önizleme modal'ını göster (isteğe bağlı)
        console.log('Test önizlemesi:', questionsData);
    }

    sendMessage(message) {
        if (this.isConnected()) {
            try {
                this.ws.send(JSON.stringify(message));
                console.log('📤 Mesaj gönderildi:', message.type);
            } catch (error) {
                console.error('❌ Mesaj gönderim hatası:', error);
                this.messageQueue.push(message);
            }
        } else {
            console.log('📋 Mesaj kuyruğa eklendi:', message.type);
            this.messageQueue.push(message);
            
            if (!this.isConnecting) {
                this.connect();
            }
        }
    }

    send(messageData) {
        if (this.isConnected()) {
            try {
                const message = {
                    type: 'user_message',
                    message: messageData.message || messageData,
                    force_web_research: messageData.force_web_research || false
                };
                this.ws.send(JSON.stringify(message));
                console.log('📤 Mesaj gönderildi:', message.type);
                return true;
            } catch (error) {
                console.error('❌ Mesaj gönderim hatası:', error);
                this.messageQueue.push(messageData);
                return false;
            }
        } else {
            console.log('📋 Mesaj kuyruğa eklendi');
            this.messageQueue.push(messageData);
            
            if (!this.isConnecting) {
                this.connect();
            }
            return false;
        }
    }

    reconnectWithChatId(chatId) {
        console.log(`🔄 WebSocket yeniden bağlanıyor (Chat ID: ${chatId})`);
        
        // Mevcut bağlantıyı kapat
        if (this.ws) {
            this.ws.close();
        }
        
        // Yeni chat ID ile bağlan
        this.connect(chatId);
    }
    
    handleConnectionError() {
        this.isConnecting = false;
        this.onConnectionChange('error');
        
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.handleReconnect();
        }
    }

    handleReconnect() {
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        
        console.log(`🔄 Yeniden bağlanma denemesi ${this.reconnectAttempts}/${this.maxReconnectAttempts} - ${delay}ms sonra`);
        
        this.onConnectionChange('reconnecting');
        
        setTimeout(() => {
            if (!this.isConnected()) {
                this.connect();
            }
        }, delay);
    }

    processMessageQueue() {
        while (this.messageQueue.length > 0) {
            const message = this.messageQueue.shift();
            this.sendMessage(message);
        }
    }

    startPing() {
        this.pingInterval = setInterval(() => {
            if (this.isConnected()) {
                this.sendMessage({ type: 'ping' });
            }
        }, 30000); // Her 30 saniyede ping
    }

    stopPing() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }

    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }

    reconnect() {
        console.log('🔄 Manuel yeniden bağlanma başlatılıyor...');
        this.reconnectAttempts = 0;
        
        if (this.ws) {
            this.ws.close();
        }
        
        setTimeout(() => {
            this.connect(this.currentChatId);
        }, 1000);
    }
    
    close() {
        console.log('🔌 WebSocket bağlantısı kapatılıyor...');
        if (this.ws) {
            this.ws.close();
        }
        this.isConnected = false;
    }
    
    // Getter methods
    getConnectionState() {
        if (!this.ws) return 'CLOSED';
        
        const states = {
            [WebSocket.CONNECTING]: 'CONNECTING',
            [WebSocket.OPEN]: 'OPEN', 
            [WebSocket.CLOSING]: 'CLOSING',
            [WebSocket.CLOSED]: 'CLOSED'
        };
        
        return states[this.ws.readyState] || 'UNKNOWN';
    }
    
    getCurrentChatId() {
        return this.currentChatId;
    }
}