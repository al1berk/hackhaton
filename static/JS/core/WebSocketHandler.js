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
                
            case 'llm_evaluation_response':
                this.handleLLMEvaluationResponse(data);
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
        
        // Test verilerini localStorage'a kaydet (fallback için)
        if (data.questions) {
            try {
                localStorage.setItem('lastGeneratedTest', JSON.stringify(data.questions));
                console.log('✅ Test verileri localStorage\'a kaydedildi');
            } catch (error) {
                console.error('❌ Test verileri localStorage\'a kaydedilemedi:', error);
            }
        }
        
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

    handleLLMEvaluationResponse(data) {
        try {
            console.log('🤖 LLM değerlendirme yanıtı alındı:', data);
            
            const { questionIndex, evaluation, metadata } = data;
            
            if (metadata && metadata.evaluationType === 'classic_question') {
                // LLM yanıtını parse et
                const result = this.parseLLMEvaluationResponse(evaluation);
                
                // Test penceresine sonucu gönder
                this.sendEvaluationToTestWindow(questionIndex, result);
                
                console.log('✅ Klasik soru değerlendirmesi tamamlandı:', result);
            }
            
        } catch (error) {
            console.error('❌ LLM değerlendirme yanıtı işleme hatası:', error);
            
            // Hata durumunda fallback sonuç gönder
            this.sendEvaluationToTestWindow(data.questionIndex, {
                isCorrect: true,
                feedback: 'Değerlendirme hatası oluştu, cevabınız kaydedildi.',
                score: 70
            });
        }
    }

    parseLLMEvaluationResponse(evaluation) {
        try {
            // LLM yanıtından bilgileri çıkar
            const lines = evaluation.split('\n');
            let isCorrect = true;
            let score = 70;
            let feedback = 'Değerlendirme tamamlandı.';
            
            for (const line of lines) {
                const cleanLine = line.trim().toUpperCase();
                
                // DOĞRU/YANLIŞ kontrolü
                if (cleanLine.includes('DOĞRU/YANLIŞ:') || cleanLine.includes('DOGRU/YANLIS:')) {
                    isCorrect = cleanLine.includes('DOĞRU') && !cleanLine.includes('YANLIŞ');
                }
                
                // PUAN kontrolü
                if (cleanLine.includes('PUAN:')) {
                    const scoreMatch = line.match(/(\d+)/);
                    if (scoreMatch) {
                        score = parseInt(scoreMatch[1]);
                        // %60 altı yanlış kabul edilir
                        if (score < 60) {
                            isCorrect = false;
                        }
                    }
                }
                
                // GERİ BİLDİRİM kontrolü
                if (line.trim().toUpperCase().includes('GERİ BİLDİRİM:') || 
                    line.trim().toUpperCase().includes('GERI BILDIRIM:')) {
                    feedback = line.split(':').slice(1).join(':').trim();
                }
            }
            
            // Eğer hiçbir bilgi bulunamazsa, tüm metni feedback olarak kullan
            if (feedback === 'Değerlendirme tamamlandı.' && evaluation.length > 50) {
                feedback = evaluation.substring(0, 200) + '...';
            }
            
            return {
                isCorrect: isCorrect,
                feedback: feedback,
                score: score
            };
            
        } catch (error) {
            console.error('❌ LLM yanıtı parse hatası:', error);
            return {
                isCorrect: true, // Hata durumunda doğru kabul et
                feedback: 'Değerlendirme tamamlandı ancak detaylı analiz yapılamadı.',
                score: 70
            };
        }
    }

    sendEvaluationToTestWindow(questionIndex, result) {
        try {
            console.log(`🔍 Test penceresine sonuç göndermeye çalışıyor (Soru ${questionIndex}):`, result);
            
            // Ana pencere referansları
            let testWindowFound = false;
            let attempts = 0;
            const maxAttempts = 3;
            
            // 1. window.testWindow referansını kontrol et
            if (window.testWindow && !window.testWindow.closed) {
                console.log('✅ window.testWindow bulundu ve açık');
                try {
                    window.testWindow.postMessage({
                        type: 'classic_evaluation_result',
                        questionIndex: questionIndex,
                        isCorrect: result.isCorrect,
                        feedback: result.feedback,
                        score: result.score || 0
                    }, window.location.origin);
                    
                    console.log(`📤 Test penceresine değerlendirme sonucu gönderildi (window.testWindow) (Soru ${questionIndex})`);
                    testWindowFound = true;
                } catch (msgError) {
                    console.error('❌ window.testWindow ile mesaj gönderme hatası:', msgError);
                }
            } else {
                console.warn('⚠️ window.testWindow bulunamadı veya kapatılmış');
            }
            
            // 2. Tüm açık pencereleri kontrol et (fallback)
            if (!testWindowFound) {
                console.log('🔍 Alternatif yöntemlerle test penceresi aranıyor...');
                
                // Chrome/modern browsers için
                if (typeof window.chrome !== 'undefined' && window.chrome.runtime) {
                    // Chrome extension context - farklı yaklaşım gerekebilir
                    console.log('Chrome ortamı tespit edildi');
                }
                
                // Tüm açık sekmelere mesaj göndermeye çalış
                try {
                    // localStorage üzerinden iletişim kurmayı dene
                    const messageData = {
                        type: 'classic_evaluation_result',
                        questionIndex: questionIndex,
                        isCorrect: result.isCorrect,
                        feedback: result.feedback,
                        score: result.score || 0,
                        timestamp: Date.now()
                    };
                    
                    localStorage.setItem('test_evaluation_message', JSON.stringify(messageData));
                    console.log('📦 Test sonucu localStorage\'a kaydedildi');
                    
                    // localStorage event'i tetiklemek için hemen sil ve tekrar yaz
                    setTimeout(() => {
                        localStorage.removeItem('test_evaluation_message');
                        localStorage.setItem('test_evaluation_message', JSON.stringify(messageData));
                    }, 50);
                    
                } catch (storageError) {
                    console.error('❌ localStorage ile iletişim hatası:', storageError);
                }
            }
            
            // 3. Son çare: Global window objesi üzerinden
            if (!testWindowFound) {
                try {
                    // Diğer sekmelerde dinlenebilecek global event
                    const customEvent = new CustomEvent('testEvaluationResult', {
                        detail: {
                            type: 'classic_evaluation_result',
                            questionIndex: questionIndex,
                            isCorrect: result.isCorrect,
                            feedback: result.feedback,
                            score: result.score || 0
                        }
                    });
                    window.dispatchEvent(customEvent);
                    console.log('📡 Global custom event gönderildi');
                } catch (eventError) {
                    console.error('❌ Custom event gönderme hatası:', eventError);
                }
            }
            
            // Debug bilgisi
            console.log(`🔍 Test penceresi durumu raporu:
                - window.testWindow var mı: ${!!window.testWindow}
                - window.testWindow kapalı mı: ${window.testWindow ? window.testWindow.closed : 'N/A'}
                - Mesaj gönderildi mi: ${testWindowFound}
                - localStorage fallback kullanıldı: ${!testWindowFound}
            `);
            
        } catch (error) {
            console.error('❌ Test penceresine sonuç gönderme hatası:', error);
            
            // Son çare: Konsola yazdır (geliştirme için)
            console.log(`🆘 FALLBACK - Test sonucu (Soru ${questionIndex}):`, {
                isCorrect: result.isCorrect,
                feedback: result.feedback,
                score: result.score
            });
        }
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
        let response = {};

        switch (stage) {
            case 'question_types':
                // Seçili soru türlerini ve sayılarını topla
                const questionTypes = {};
                document.querySelectorAll(`#parametersForm-${stage} input[type="checkbox"]:checked`).forEach(cb => {
                    const typeId = cb.value;
                    const countInput = document.getElementById(`count_${typeId}`);
                    const count = parseInt(countInput.value) || 0;
                    
                    if (count > 0) {
                        questionTypes[typeId] = count;
                    }
                });
                
                response = {
                    soru_turleri: questionTypes
                };
                break;

            case 'difficulty':
                const selectedDifficulty = document.querySelector(`#parametersForm-${stage} input[type="radio"]:checked`);
                response = {
                    zorluk_seviyesi: selectedDifficulty ? selectedDifficulty.value : 'orta'
                };
                break;

            case 'student_level':
                const selectedLevel = document.querySelector(`#parametersForm-${stage} input[type="radio"]:checked`);
                response = {
                    ogrenci_seviyesi: selectedLevel ? selectedLevel.value : 'lise'
                };
                break;

            default:
                response = { response: 'bilinmeyen_stage' };
        }

        // Formu devre dışı bırak
        const form = document.getElementById(`parametersForm-${stage}`);
        if (form) {
            form.style.opacity = '0.5';
            form.style.pointerEvents = 'none';
        }

        console.log(`📤 Parametre yanıtı gönderiliyor (${stage}):`, response);

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
                
                // Test verilerini localStorage'a kaydet
                localStorage.setItem('lastGeneratedTest', JSON.stringify(testQuestions));
                
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

        // Benzersiz ID oluştur
        const testId = `test_${Date.now()}`;

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
                        <button class="solve-test-btn" data-test-id="${testId}" onclick="window.startTestById('${testId}')">
                            <i class="fas fa-play"></i>
                            Testi Çöz
                        </button>
                        <button class="preview-test-btn" data-test-id="${testId}" onclick="window.previewTestById('${testId}')">
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

        // Test verilerini ID ile eşleştirerek sakla
        if (testQuestions) {
            localStorage.setItem(`testData_${testId}`, JSON.stringify(testQuestions));
        }

        // Global fonksiyonları tanımla
        window.startTestById = (testId) => {
            this.startTestById(testId);
        };

        window.previewTestById = (testId) => {
            this.previewTestById(testId);
        };
    }

    // HTML attribute'lar için string escape fonksiyonu
    escapeForAttribute(str) {
        if (!str) return '';
        return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    startTest(questionsData) {
        try {
            console.log('🚀 Test başlatılıyor...', typeof questionsData);
            
            // Test verilerini güvenli şekilde parse et
            let testData;
            if (typeof questionsData === 'string') {
                // HTML attribute'undan gelen string'i decode et
                const decodedString = questionsData
                    .replace(/&quot;/g, '"')
                    .replace(/&#39;/g, "'");
                
                try {
                    testData = JSON.parse(decodedString);
                } catch (parseError) {
                    console.error('❌ JSON parse hatası:', parseError);
                    console.log('Raw string:', questionsData);
                    console.log('Decoded string:', decodedString);
                    
                    // Fallback: localStorage'dan test verilerini al
                    const existingData = localStorage.getItem('lastGeneratedTest');
                    if (existingData) {
                        console.log('📋 Mevcut test verilerini kullanıyor...');
                        testData = JSON.parse(existingData);
                    } else {
                        throw new Error('Test verileri bulunamadı. Lütfen testi tekrar oluşturun.');
                    }
                }
            } else if (typeof questionsData === 'object') {
                testData = questionsData;
            } else {
                throw new Error('Geçersiz test veri formatı');
            }
            
            // Test verilerini kontrol et
            if (!testData || typeof testData !== 'object') {
                throw new Error('Test verileri geçersiz');
            }
            
            console.log('✅ Test verileri başarıyla yüklendi:', testData);
            
            // Test verilerini localStorage'a kaydet
            localStorage.setItem('currentTestQuestions', JSON.stringify(testData));
            localStorage.setItem('lastGeneratedTest', JSON.stringify(testData));
            
            // Yeni sekmede test sayfasını aç
            const testWindow = window.open('/static/test_solver.html', '_blank');
            
            if (!testWindow) {
                throw new Error('Pop-up engellendi. Lütfen pop-up engelleyicisini devre dışı bırakın.');
            }
            
        } catch (error) {
            console.error('❌ Test başlatma hatası:', error);
            
            // Kullanıcıya hata mesajı göster
            const errorMessage = `Test başlatılamadı: ${error.message}`;
            this.onMessage({
                type: 'error',
                content: errorMessage,
                timestamp: new Date().toISOString()
            });
        }
    }

    startTestById(testId) {
        try {
            console.log('🚀 Test ID ile başlatılıyor:', testId);
            
            // Test verilerini ID ile localStorage'dan al
            const testDataString = localStorage.getItem(`testData_${testId}`);
            if (!testDataString) {
                // Fallback: son oluşturulan testi kullan
                const fallbackData = localStorage.getItem('lastGeneratedTest');
                if (fallbackData) {
                    console.log('📋 Fallback test verilerini kullanıyor...');
                    localStorage.setItem('currentTestQuestions', fallbackData);
                } else {
                    throw new Error('Test verileri bulunamadı. Lütfen testi tekrar oluşturun.');
                }
            } else {
                // Test verilerini currentTestQuestions olarak kaydet
                localStorage.setItem('currentTestQuestions', testDataString);
            }
            
            // Yeni sekmede test sayfasını aç
            window.testWindow = window.open('/static/test_solver.html', '_blank');

            
            if (!window.testWindow) {
                throw new Error('Pop-up engellendi. Lütfen pop-up engelleyicisini devre dışı bırakın.');
            }
            
            console.log('✅ Test başarıyla başlatıldı');
            
        } catch (error) {
            console.error('❌ Test başlatma hatası:', error);
            
            // Kullanıcıya hata mesajı göster
            const errorMessage = `Test başlatılamadı: ${error.message}`;
            this.onMessage({
                type: 'error',
                content: errorMessage,
                timestamp: new Date().toISOString()
            });
        }
    }

    previewTestById(testId) {
        try {
            console.log('👁️ Test ID ile önizleme:', testId);
            
            // Test verilerini ID ile localStorage'dan al
            const testDataString = localStorage.getItem(`testData_${testId}`);
            if (!testDataString) {
                throw new Error('Test verileri bulunamadı');
            }
            
            const testData = JSON.parse(testDataString);
            
            // Önizleme modal'ı veya yeni sekme açabilirsiniz
            console.log('📋 Test önizlemesi:', testData);
            
            // Basit önizleme için console'da göster
            let previewText = '📋 Test Önizlemesi:\n\n';
            
            if (testData.document_info) {
                previewText += `📊 Toplam Soru: ${testData.document_info.question_count}\n`;
                previewText += `🎯 Soru Türleri: ${JSON.stringify(testData.document_info.question_types)}\n\n`;
            }
            
            // İlk birkaç soruyu göster
            if (testData.coktan_secmeli && testData.coktan_secmeli.length > 0) {
                previewText += `🔸 Çoktan Seçmeli Sorular (${testData.coktan_secmeli.length} adet):\n`;
                previewText += `1. ${testData.coktan_secmeli[0].question}\n\n`;
            }
            
            if (testData.klasik && testData.klasik.length > 0) {
                previewText += `🔸 Klasik Sorular (${testData.klasik.length} adet):\n`;
                previewText += `1. ${testData.klasik[0].question}\n\n`;
            }
            
            // Kullanıcıya önizleme mesajı göster
            this.onMessage({
                type: 'ai_response',
                message: previewText,
                timestamp: new Date().toISOString(),
                metadata: {
                    message_type: 'test_preview'
                }
            });
            
        } catch (error) {
            console.error('❌ Test önizleme hatası:', error);
            
            const errorMessage = `Test önizlenemiyor: ${error.message}`;
            this.onMessage({
                type: 'error',
                content: errorMessage,
                timestamp: new Date().toISOString()
            });
        }
    }

    previewTest(questionsData) {
        // Eski fonksiyon - geriye dönük uyumluluk için
        console.log('Test önizlemesi (eski yöntem):', questionsData);
        
        try {
            let testData;
            if (typeof questionsData === 'string') {
                testData = JSON.parse(questionsData.replace(/&quot;/g, '"').replace(/&#39;/g, "'"));
            } else {
                testData = questionsData;
            }
            
            // startTestById'daki ile aynı önizleme mantığını kullan
            const tempId = `temp_${Date.now()}`;
            localStorage.setItem(`testData_${tempId}`, JSON.stringify(testData));
            this.previewTestById(tempId);
            
            // Geçici veriyi temizle
            setTimeout(() => {
                localStorage.removeItem(`testData_${tempId}`);
            }, 5000);
            
        } catch (error) {
            console.error('❌ Test önizleme hatası:', error);
        }
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