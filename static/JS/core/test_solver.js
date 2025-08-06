document.addEventListener('DOMContentLoaded', () => {
    const testBody = document.getElementById('testBody');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const finishTestBtn = document.getElementById('finishTestBtn');
    const resultSummary = document.getElementById('resultSummary');
    const finalScoreEl = document.getElementById('finalScore');

    let allQuestions = [];
    let totalQuestions = 0;
    let answeredQuestions = 0;
    let score = 0;
    let userAnswers = [];

    function loadTest() {
        try {
            const questionsDataString = localStorage.getItem('currentTestQuestions');
            if (!questionsDataString) {
                showError("Test verisi bulunamadı. Lütfen ana sayfadan testi tekrar başlatın.");
                return;
            }

            const testData = JSON.parse(questionsDataString);
            
            // Test verilerini doğrula
            if (!testData || typeof testData !== 'object') {
                showError("Test verisi geçersiz format.");
                return;
            }

            let questions = null;
            
            // Test verisinin yapısını kontrol et
            if (testData.questions) {
                questions = testData.questions;
            } else if (testData.coktan_secmeli || testData.klasik || testData.bosluk_doldurma) {
                // Direkt soru türleri varsa
                questions = testData;
            } else {
                showError("Test verilerinde soru bulunamadı.");
                return;
            }

            // Güvenli soru ekleme fonksiyonu
            const addQuestionsToArray = (questionArray, type) => {
                if (Array.isArray(questionArray)) {
                    questionArray.forEach(q => {
                        // Her soruyu doğrula
                        if (q && typeof q === 'object' && q.soru) {
                            allQuestions.push({...q, type: type});
                        } else {
                            console.warn(`Geçersiz ${type} sorusu atlandı:`, q);
                        }
                    });
                }
            };

            // Tüm soru türlerini güvenli şekilde ekle
            addQuestionsToArray(questions.coktan_secmeli, 'coktan_secmeli');
            addQuestionsToArray(questions.klasik, 'klasik');
            addQuestionsToArray(questions.bosluk_doldurma, 'bosluk_doldurma');
            addQuestionsToArray(questions.dogru_yanlis, 'dogru_yanlis');

            totalQuestions = allQuestions.length;
            if (totalQuestions === 0) {
                showError("Bu testte hiç geçerli soru bulunmuyor.");
                return;
            }

            console.log(`✅ ${totalQuestions} soru yüklendi:`, allQuestions);
            renderTest();
        } catch (error) {
            console.error("Test yüklenirken hata:", error);
            showError(`Test yüklenirken bir hata oluştu: ${error.message}`);
        }
    }

    function renderTest() {
        testBody.innerHTML = ''; // Temizle
        allQuestions.forEach((question, index) => {
            const questionCard = document.createElement('div');
            questionCard.className = 'question-card';
            questionCard.id = `question-${index}`;

            let questionHTML = `
                <div class="question-header">
                    <div class="question-title">Soru ${index + 1}</div>
                    <div class="question-difficulty">${question.zorluk || 'Belirtilmemiş'}</div>
                </div>
                <p class="question-text">${question.soru}</p>
            `;

            if (question.type === 'coktan_secmeli') {
                questionHTML += renderMultipleChoice(question, index);
            } else if (question.type === 'klasik') {
                questionHTML += renderClassic(question, index);
            } else if (question.type === 'bosluk_doldurma') {
                questionHTML += renderFillBlank(question, index);
            } else if (question.type === 'dogru_yanlis') {
                questionHTML += renderTrueFalse(question, index);
            }
            
            questionHTML += `<div class="answer-feedback" id="feedback-${index}"></div>`;
            questionCard.innerHTML = questionHTML;
            testBody.appendChild(questionCard);
        });

        attachEventListeners();
        updateProgress();
    }

    function renderMultipleChoice(question, index) {
        // Seçenekleri güvenli şekilde kontrol et
        const options = question.secenekler;
        
        if (!options || typeof options !== 'object') {
            console.error(`Geçersiz seçenekler (Soru ${index + 1}):`, options);
            return `
                <div class="error-message">
                    <p>⚠️ Bu soruda seçenekler eksik veya hatalı</p>
                    <small>Soru ${index + 1} için seçenekler yüklenemedi</small>
                </div>
            `;
        }

        let optionsHTML = '<ul class="options-list">';
        
        try {
            const entries = Object.entries(options);
            
            if (entries.length === 0) {
                console.warn(`Boş seçenekler listesi (Soru ${index + 1})`);
                return `
                    <div class="error-message">
                        <p>⚠️ Bu soruda hiç seçenek bulunamadı</p>
                    </div>
                `;
            }
            
            entries.forEach(([key, value]) => {
                if (key && value !== null && value !== undefined) {
                    optionsHTML += `
                        <li class="option-item" data-question-index="${index}" data-answer-key="${key}">
                            <span class="option-letter">${key}</span>
                            <span class="option-text">${value}</span>
                        </li>
                    `;
                }
            });
            
        } catch (error) {
            console.error(`Seçenekler işlenirken hata (Soru ${index + 1}):`, error);
            return `
                <div class="error-message">
                    <p>⚠️ Seçenekler işlenirken hata oluştu</p>
                    <small>${error.message}</small>
                </div>
            `;
        }
        
        optionsHTML += '</ul>';
        return optionsHTML;
    }
    
    function renderClassic(question, index) { 
        return `
            <div class="classic-answer-area">
                <textarea 
                    id="classic-answer-${index}" 
                    placeholder="Cevabınızı buraya yazın..." 
                    rows="4" 
                    data-question-index="${index}">
                </textarea>
                <button 
                    class="answer-btn classic-answer-btn" 
                    data-question-index="${index}" 
                    onclick="handleClassicAnswer(${index})">
                    Cevapla
                </button>
            </div>
        `;
    }
    
    function renderFillBlank(question, index) { 
        return `
            <div class="fill-blank-answer-area">
                <input 
                    type="text" 
                    id="fill-blank-answer-${index}" 
                    placeholder="Boşluğu doldurun..." 
                    data-question-index="${index}" 
                />
                <button 
                    class="answer-btn fill-blank-answer-btn" 
                    data-question-index="${index}" 
                    onclick="handleFillBlankAnswer(${index})">
                    Cevapla
                </button>
            </div>
        `;
    }

    function renderTrueFalse(question, index) {
        return `
            <div class="true-false-options">
                <div class="true-false-option" data-question-index="${index}" data-answer="true" onclick="handleTrueFalseAnswer(${index}, true)">
                    <span class="option-letter">D</span>
                    <span class="option-text">Doğru</span>
                </div>
                <div class="true-false-option" data-question-index="${index}" data-answer="false" onclick="handleTrueFalseAnswer(${index}, false)">
                    <span class="option-letter">Y</span>
                    <span class="option-text">Yanlış</span>
                </div>
            </div>
        `;
    }

    function attachEventListeners() {
        document.querySelectorAll('.option-item').forEach(item => {
            item.addEventListener('click', handleMultipleChoiceAnswer);
        });
        // Diğer soru tipleri için event listenerlar buraya eklenecek
    }

    function handleMultipleChoiceAnswer(event) {
        const selectedOption = event.currentTarget;
        const questionIndex = parseInt(selectedOption.dataset.questionIndex, 10);
        const selectedAnswerKey = selectedOption.dataset.answerKey;
        
        const question = allQuestions[questionIndex];
        const isCorrect = selectedAnswerKey === question.dogru_cevap;

        const options = document.querySelectorAll(`.option-item[data-question-index="${questionIndex}"]`);
        options.forEach(opt => {
            opt.classList.add('answered');
            if(opt.dataset.answerKey === question.dogru_cevap) {
                opt.classList.add('correct');
            }
        });

        if (isCorrect) {
            score++;
            showFeedback(questionIndex, `Doğru! ${question.aciklama || ''}`, true);
        } else {
            selectedOption.classList.add('incorrect');
            showFeedback(questionIndex, `Yanlış. Doğru cevap: ${question.dogru_cevap}. ${question.aciklama || ''}`, false);
        }

        // Kullanıcı cevabını kaydet
        userAnswers[questionIndex] = selectedAnswerKey;

        answeredQuestions++;
        updateProgress();
    }

    function showFeedback(index, message, isCorrect) {
        const feedbackEl = document.getElementById(`feedback-${index}`);
        feedbackEl.innerHTML = `<p>${isCorrect ? '✅' : '❌'} ${message}</p>`;
        feedbackEl.className = `answer-feedback ${isCorrect ? 'correct' : 'incorrect'}`;
    }

    function updateProgress() {
        const percentage = totalQuestions > 0 ? (answeredQuestions / totalQuestions) * 100 : 0;
        progressBar.style.width = `${percentage}%`;
        progressText.textContent = `${answeredQuestions}/${totalQuestions}`;

        // Testi Bitir butonunu göster - hem tamamlandığında hem de en az yarısı cevaplandığında
        if (answeredQuestions >= Math.ceil(totalQuestions / 2) || answeredQuestions === totalQuestions) {
            finishTestBtn.style.display = 'flex'; // flex olarak göster
            finishTestBtn.onclick = finishTest;
        }

        // Test tamamlandığında butonu vurgula
        if (answeredQuestions === totalQuestions) {
            finishTestBtn.classList.add('pulse-animation');
            finishTestBtn.innerHTML = `
                <i class="fas fa-check-circle"></i>
                <span>Test Tamamlandı - Sonuçları Gör</span>
            `;
        }
    }
    
    function showFinalResults() {
        // DÜZELTME: Bu fonksiyonu finishTest() ile birleştir
        const results = calculateTestResults();
        showTestResults(results);
        sendResultsToMainWindow(results);
    }

    function finishTest() {
        if (answeredQuestions < totalQuestions) {
            if (!confirm('Testi henüz bitirmediniz. Yine de sonuçları görmek istiyor musunuz?')) {
                return;
            }
        }

        // Test sonuçlarını hesapla
        const results = calculateTestResults();
        
        // Sonuçları göster (sadece test sayfasında)
        showTestResults(results);
        
        // Ana pencereye gönderme işlevi KALDIRILDI
        console.log('✅ Test tamamlandı, sonuçlar test sayfasında gösteriliyor');
    }

    function calculateTestResults() {
        let correctAnswers = 0;
        let wrongAnswers = 0;
        const detailedResults = [];
        const topicErrors = {};

        allQuestions.forEach((question, index) => {
            const userAnswer = userAnswers[index];
            let isCorrect = false;
            let correctAnswer = '';

            // Doğru cevabı belirle
            if (question.type === 'coktan_secmeli') {
                correctAnswer = question.dogru_cevap;
                isCorrect = userAnswer === correctAnswer;
            } else if (question.type === 'bosluk_doldurma') {
                correctAnswer = question.dogru_cevap;
                // Boşluk doldurma için basit string karşılaştırması
                isCorrect = userAnswer && 
                           userAnswer.toLowerCase().trim() === correctAnswer.toLowerCase().trim();
            } else if (question.type === 'klasik') {
                // Klasik sorular için manuel değerlendirme gerekir
                // Şimdilik otomatik "doğru" kabul ediyoruz
                isCorrect = userAnswer && userAnswer.trim().length > 10;
                correctAnswer = "Manuel değerlendirme gerekli";
            } else if (question.type === 'dogru_yanlis') {
                correctAnswer = question.dogru_cevap === 'true' ? 'Doğru' : 'Yanlış';
                isCorrect = userAnswer === correctAnswer;
            }

            if (isCorrect) {
                correctAnswers++;
            } else {
                wrongAnswers++;
                
                // Konuya göre hata sayısını artır
                const topic = question.konu_basligi || question.konu || 'Genel';
                topicErrors[topic] = (topicErrors[topic] || 0) + 1;
            }

            detailedResults.push({
                question_index: index,
                question_text: question.soru,
                question_type: question.type,
                user_answer: userAnswer,
                correct_answer: correctAnswer,
                is_correct: isCorrect,
                topic: question.konu_basligi || question.konu || 'Genel',
                explanation: question.aciklama || ''
            });
        });

        const successRate = totalQuestions > 0 ? (correctAnswers / totalQuestions) * 100 : 0;

        return {
            test_id: Date.now().toString(),
            completed_at: new Date().toISOString(),
            statistics: {
                total_questions: totalQuestions,
                correct_answers: correctAnswers,
                wrong_answers: wrongAnswers,
                success_rate: Math.round(successRate * 100) / 100
            },
            topic_errors: topicErrors,
            detailed_results: detailedResults,
            performance_level: getPerformanceLevel(successRate)
        };
    }

    function getPerformanceLevel(successRate) {
        if (successRate >= 90) return 'excellent';
        if (successRate >= 70) return 'good';
        if (successRate >= 50) return 'fair';
        return 'needs_improvement';
    }

    function showTestResults(results) {
        const testBody = document.getElementById('testBody');
        const controls = document.querySelector('.test-controls');
        
        if (controls) controls.style.display = 'none';

        testBody.innerHTML = `
            <div class="test-results">
                <div class="results-header">
                    <div class="results-icon ${results.performance_level}">
                        ${getPerformanceIcon(results.performance_level)}
                    </div>
                    <h2>Test Tamamlandı!</h2>
                    <div class="success-rate">
                        <span class="rate-value">${results.statistics.success_rate}%</span>
                        <span class="rate-label">Başarı Oranı</span>
                    </div>
                </div>

                <div class="results-stats">
                    <div class="stat-card correct">
                        <div class="stat-icon">✅</div>
                        <div class="stat-value">${results.statistics.correct_answers}</div>
                        <div class="stat-label">Doğru</div>
                    </div>
                    <div class="stat-card wrong">
                        <div class="stat-icon">❌</div>
                        <div class="stat-value">${results.statistics.wrong_answers}</div>
                        <div class="stat-label">Yanlış</div>
                    </div>
                    <div class="stat-card total">
                        <div class="stat-icon">📊</div>
                        <div class="stat-value">${results.statistics.total_questions}</div>
                        <div class="stat-label">Toplam</div>
                    </div>
                </div>

                ${Object.keys(results.topic_errors).length > 0 ? `
                    <div class="weak-topics">
                        <h3>⚠️ Eksik Olduğun Konular</h3>
                        <div class="topic-list">
                            ${Object.entries(results.topic_errors).map(([topic, errorCount]) => `
                                <div class="topic-item">
                                    <span class="topic-name">${topic}</span>
                                    <span class="error-count">${errorCount} hata</span>
                                    <button class="explain-btn" onclick="requestTopicExplanation('${topic}')">
                                        📖 Açıkla
                                    </button>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : `
                    <div class="weak-topics">
                        <h3>🎉 Harika Performans!</h3>
                        <p style="text-align: center; color: var(--test-success); font-size: 1.125rem; font-weight: 600;">
                            Tüm konularda başarılısın! Böyle devam et! 👏
                        </p>
                    </div>
                `}

                <div class="results-actions">
                    <button class="close-btn" onclick="window.close()">
                        🏠 Ana Sayfaya Dön
                    </button>
                </div>

                <div class="detailed-review">
                    <h3>📋 Detaylı Soru İncelemesi</h3>
                    <div class="question-review-list">
                        ${results.detailed_results.map((result, index) => `
                            <div class="question-review ${result.is_correct ? 'correct' : 'wrong'}">
                                <div class="question-header">
                                    <span class="question-number">Soru ${index + 1}</span>
                                    <span class="question-status">
                                        ${result.is_correct ? '✅ Doğru' : '❌ Yanlış'}
                                    </span>
                                </div>
                                <div class="question-text">${result.question_text}</div>
                                <div class="answer-comparison">
                                    <div class="user-answer">
                                        <strong>Senin Cevabın:</strong> 
                                        ${result.user_answer || 'Cevaplamadın'}
                                    </div>
                                    <div class="correct-answer">
                                        <strong>Doğru Cevap:</strong> 
                                        ${result.correct_answer}
                                    </div>
                                </div>
                                ${result.explanation ? `
                                    <div class="explanation">
                                        <strong>Açıklama:</strong> ${result.explanation}
                                    </div>
                                ` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;

        // Sayfayı en üste scroll et
        window.scrollTo(0, 0);
        
        // Animasyonları tetikle
        setTimeout(() => {
            const elements = document.querySelectorAll('.stat-card, .question-review, .topic-item');
            elements.forEach((el, index) => {
                setTimeout(() => {
                    el.style.opacity = '0';
                    el.style.transform = 'translateY(20px)';
                    el.style.transition = 'all 0.6s ease-out';
                    
                    setTimeout(() => {
                        el.style.opacity = '1';
                        el.style.transform = 'translateY(0)';
                    }, 50);
                }, index * 100);
            });
        }, 300);
    }
    
    function getPerformanceIcon(level) {
        const icons = {
            'excellent': '🏆',
            'good': '👍',
            'fair': '📚',
            'needs_improvement': '💪'
        };
        return icons[level] || '📊';
    }

    function sendResultsToMainWindow(results) {
        try {
            // Ana pencereye mesaj gönder
            if (window.opener && !window.opener.closed) {
                window.opener.postMessage({
                    type: 'test_completed',
                    results: results
                }, window.location.origin);
            }

            // localStorage'a da kaydet (backup)
            localStorage.setItem('lastTestResults', JSON.stringify(results));
            
            console.log('✅ Test sonuçları ana pencereye gönderildi:', results);
        } catch (error) {
            console.error('❌ Sonuç gönderme hatası:', error);
        }
    }

    window.showDetailedReview = function() {
        const detailedReview = document.getElementById('detailedReview');
        if (detailedReview) {
            detailedReview.style.display = detailedReview.style.display === 'none' ? 'block' : 'none';
        }
    };

    window.requestTopicExplanation = function(topic) {
        try {
            if (window.opener && !window.opener.closed) {
                window.opener.postMessage({
                    type: 'explain_topic',
                    topic: topic
                }, window.location.origin);
                
                // Kullanıcıya feedback ver
                const button = event.target;
                const originalText = button.textContent;
                button.textContent = '✅ İstek Gönderildi';
                button.disabled = true;
                
                setTimeout(() => {
                    button.textContent = originalText;
                    button.disabled = false;
                }, 2000);
            } else {
                alert('Ana pencere bulunamadı. Lütfen ana sayfadan konuyu sorun.');
            }
        } catch (error) {
            console.error('❌ Konu açıklama isteği hatası:', error);
        }
    };

    function showError(message) {
        testBody.innerHTML = `<div class="error-state"><h3>Hata!</h3><p>${message}</p></div>`;
    }

    // Testi başlat
    loadTest();

    // WebSocket ile klasik soru değerlendirme fonksiyonu
    async function evaluateClassicAnswer(questionIndex, userAnswer) {
        const question = allQuestions[questionIndex];
        
        try {
            // LLM değerlendirme prompt'unu oluştur
            const evaluationPrompt = createEvaluationPrompt(question, userAnswer);
            
            // WebSocket üzerinden LLM değerlendirme isteği gönder
            if (window.testWebSocket && window.testWebSocket.readyState === WebSocket.OPEN) {
                // Promise ile LLM yanıtını bekle
                const evaluationResult = await requestLLMEvaluation(evaluationPrompt, questionIndex);
                
                // LLM yanıtını parse et
                const parsedResult = parseLLMEvaluation(evaluationResult);
                
                if (parsedResult.isCorrect) {
                    score++;
                }
                
                // YENİ: Özel klasik soru feedback fonksiyonunu kullan
                showClassicAnswerFeedback(questionIndex, parsedResult.isCorrect, parsedResult.feedback);
                
                console.log(`✅ LLM Değerlendirme tamamlandı (Soru ${questionIndex + 1}):`, parsedResult);
                
            } else {
                // WebSocket yoksa manuel değerlendirme
                console.warn('⚠️ WebSocket bağlantısı yok, manuel değerlendirme yapılıyor');
                const manualEvaluation = evaluateClassicManually(question, userAnswer);
                
                if (manualEvaluation.isCorrect) {
                    score++;
                }
                
                // Yanlış cevap ise doğru cevabı göster
                showClassicAnswerFeedback(questionIndex, manualEvaluation.isCorrect, manualEvaluation.feedback);
            }
            
        } catch (error) {
            console.error('❌ LLM değerlendirme hatası, manuel değerlendirmeye geçiliyor:', error);
            
            // Hata durumunda manuel değerlendirme yap
            const manualEvaluation = evaluateClassicManually(question, userAnswer);
            
            if (manualEvaluation.isCorrect) {
                score++;
            }
            
            showClassicAnswerFeedback(questionIndex, manualEvaluation.isCorrect, manualEvaluation.feedback);
            
        } finally {
            // Butonu normale döndür
            const button = document.querySelector(`button[data-question-index="${questionIndex}"]`);
            if(button) {
                button.disabled = true;
                button.textContent = 'Cevaplandı';
            }
            
            answeredQuestions++;
            updateProgress();
        }
    }

    // LLM değerlendirme prompt'u oluştur
    function createEvaluationPrompt(question, userAnswer) {
        const sampleAnswer = question.ornek_cevap || question.cevap || '';
        const criteria = question.degerlendirme_kriterleri || '';
        
        return `
Sen bir eğitim uzmanısın. Aşağıdaki açık uçlu soruya verilen cevabı değerlendirmen gerekiyor.

**SORU:**
${question.soru}

**ÖĞRENCİNİN CEVABI:**
${userAnswer}

**ÖRNEK CEVAP (Referans):**
${sampleAnswer || 'Örnek cevap belirtilmemiş'}

**DEĞERLENDİRME KRİTERLERİ:**
${criteria || 'Genel değerlendirme kriterleri kullanılacak'}

**GÖREV:**
Öğrencinin cevabını değerlendirip aşağıdaki formatta yanıt ver:

DOĞRU/YANLIŞ: [Doğru/Yanlış]
PUAN: [0-100 arası puan]
GERİ BİLDİRİM: [Detaylı açıklama - öğrencinin nerde doğru yaptığı, nerede eksik kaldığı, nasıl geliştirebileceği]

**DEĞERLENDİRME KURALLARI:**
- Eğer cevap temel kavramları doğru içeriyorsa "Doğru" ver
- Tamamen yanlış veya ilgisiz cevaplar "Yanlış"
- Puan verirken: İçerik doğruluğu (%60), detay seviyesi (%25), açıklık (%15)
- Geri bildirimde yapıcı ve teşvik edici ol
- Öğrencinin doğru yaptığı kısımları da belirt`;
    }

    // WebSocket üzerinden LLM değerlendirme isteği gönder
    async function requestLLMEvaluation(prompt, questionIndex) {
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('LLM değerlendirmesi zaman aşımına uğradı'));
            }, 30000); // 30 saniye timeout

            // Yanıt dinleyicisi
            const messageHandler = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'llm_evaluation_response' && 
                        data.questionIndex === questionIndex) {
                        clearTimeout(timeout);
                        window.testWebSocket.removeEventListener('message', messageHandler);
                        resolve(data.evaluation);
                    }
                } catch (error) {
                    console.error('LLM yanıt parse hatası:', error);
                }
            };

            window.testWebSocket.addEventListener('message', messageHandler);

            // İsteği gönder
            window.testWebSocket.send(JSON.stringify({
                type: 'llm_evaluation_request',
                prompt: prompt,
                questionIndex: questionIndex,
                metadata: {
                    questionText: allQuestions[questionIndex].soru,
                    timestamp: new Date().toISOString()
                }
            }));

            console.log(`📤 LLM değerlendirme isteği gönderildi (Soru ${questionIndex + 1})`);
        });
    }

    // LLM değerlendirme yanıtını parse et
    function parseLLMEvaluation(evaluation) {
        try {
            console.log('🔍 LLM Yanıtı:', evaluation); // Debug için
            
            // LLM yanıtından DOĞRU/YANLIŞ, PUAN ve GERİ BİLDİRİM çıkar
            const lines = evaluation.split('\n');
            let isCorrect = false;
            let score = 0;
            let feedback = '';
            let rawFeedback = '';

            // Tüm satırları işle
            for (const line of lines) {
                const trimmedLine = line.trim();
                
                if (trimmedLine.startsWith('DOĞRU/YANLIŞ:') || trimmedLine.startsWith('DOGRU/YANLIS:')) {
                    const result = trimmedLine.split(':')[1]?.trim().toLowerCase();
                    isCorrect = result === 'doğru' || result === 'dogru';
                    console.log('✓ Doğru/Yanlış:', result, '- İsCorrect:', isCorrect);
                }
                
                if (trimmedLine.startsWith('PUAN:')) {
                    const scoreMatch = trimmedLine.match(/\d+/);
                    if (scoreMatch) {
                        score = parseInt(scoreMatch[0]);
                        console.log('✓ Puan:', score);
                        // 70+ puan alırsa doğru kabul et
                        if (score >= 70) {
                            isCorrect = true;
                        }
                    }
                }
                
                if (trimmedLine.startsWith('GERİ BİLDİRİM:') || trimmedLine.startsWith('GERI BILDIRIM:')) {
                    // Geri bildirim kısmından sonrasını al
                    const feedbackIndex = evaluation.indexOf(trimmedLine);
                    if (feedbackIndex !== -1) {
                        rawFeedback = evaluation.substring(feedbackIndex + trimmedLine.length).trim();
                        // İlk satırdaki ':' işaretinden sonrasını al
                        const colonIndex = rawFeedback.indexOf(':');
                        if (colonIndex !== -1) {
                            rawFeedback = rawFeedback.substring(colonIndex + 1).trim();
                        }
                    }
                }
            }

            // Eğer geri bildirim bulunamazsa, tüm metni geri bildirim olarak kullan
            if (!rawFeedback) {
                rawFeedback = evaluation;
            }

            // Feedback'i temizle ve kullanıcı dostu hale getir
            feedback = formatFeedbackMessage(rawFeedback, isCorrect, score);

            const result = {
                isCorrect: isCorrect,
                score: score,
                feedback: feedback
            };

            console.log('✅ Parse Sonucu:', result);
            return result;

        } catch (error) {
            console.error('❌ LLM yanıt parse hatası:', error);
            // Hata durumunda güvenli fallback
            return {
                isCorrect: true, // Hata durumunda lehte karar
                score: 70,
                feedback: 'Değerlendirme sırasında bir sorun oluştu, cevabınız kabul edildi.'
            };
        }
    }

    // Feedback mesajını kullanıcı dostu hale getir
    function formatFeedbackMessage(rawFeedback, isCorrect, score) {
        let formattedMessage = '';
        
        // Başlık ekle
        if (isCorrect) {
            formattedMessage += `🎉 **Tebrikler!** (${score}/100 puan)\n\n`;
        } else {
            formattedMessage += `📚 **Gelişme Fırsatı** (${score}/100 puan)\n\n`;
        }
        
        // Ana geri bildirimi ekle
        if (rawFeedback && rawFeedback.length > 0) {
            // Gereksiz tekrarları temizle
            let cleanFeedback = rawFeedback
                .replace(/DOĞRU\/YANLIŞ:.*?\n/gi, '')
                .replace(/PUAN:.*?\n/gi, '')
                .replace(/GERİ BİLDİRİM:.*?\n/gi, '')
                .replace(/GERI BILDIRIM:.*?\n/gi, '')
                .trim();
            
            if (cleanFeedback) {
                formattedMessage += cleanFeedback;
            } else {
                // Fallback mesaj
                if (isCorrect) {
                    formattedMessage += 'Cevabınız başarılı! Konuyu iyi anlamışsınız.';
                } else {
                    formattedMessage += 'Cevabınızda eksiklikler var. Konuyu tekrar gözden geçirmenizi öneririm.';
                }
            }
        } else {
            // Geri bildirim yoksa genel mesaj
            if (isCorrect) {
                formattedMessage += 'Cevabınız doğru değerlendirildi!';
            } else {
                formattedMessage += 'Cevabınızda iyileştirme alanları var.';
            }
        }
        
        return formattedMessage;
    }

    // Klasik soru için doğru cevabı gösterme fonksiyonu
    function showClassicAnswerFeedback(questionIndex, isCorrect, feedback) {
        const question = allQuestions[questionIndex];
        let fullFeedback = feedback;
        
        // Yanlış cevap ise doğru cevabı da göster
        if (!isCorrect) {
            const correctAnswer = question.ornek_cevap || question.cevap;
            if (correctAnswer) {
                fullFeedback += `\n\n📋 **Örnek Doğru Cevap:**\n${correctAnswer}`;
            }
            
            // Açıklama varsa ekle
            if (question.aciklama) {
                fullFeedback += `\n\n💡 **Açıklama:**\n${question.aciklama}`;
            }
        }
        
        showFeedback(questionIndex, fullFeedback, isCorrect);
    }

    // Klasik soru cevaplama fonksiyonu
    window.handleClassicAnswer = function(questionIndex) {
        const textarea = document.getElementById(`classic-answer-${questionIndex}`);
        const userAnswer = textarea.value.trim();
        
        if (!userAnswer) {
            alert('Lütfen bir cevap yazın.');
            return;
        }
        
        // Butonu devre dışı bırak
        const button = document.querySelector(`button[data-question-index="${questionIndex}"]`);
        button.disabled = true;
        button.textContent = 'Değerlendiriliyor...';
        
        // Kullanıcı cevabını kaydet
        userAnswers[questionIndex] = userAnswer;
        
        // LLM ile değerlendirme yap
        evaluateClassicAnswer(questionIndex, userAnswer);
    };

    // Boşluk doldurma cevaplama fonksiyonu
    window.handleFillBlankAnswer = function(questionIndex) {
        const input = document.getElementById(`fill-blank-answer-${questionIndex}`);
        const userAnswer = input.value.trim();
        
        if (!userAnswer) {
            alert('Lütfen boşluğu doldurun.');
            return;
        }
        
        const question = allQuestions[questionIndex];
        const correctAnswer = question.dogru_cevap;
        
        // Alternatif cevapları kontrol et
        let isCorrect = false;
        const alternatives = question.alternatif_cevaplar || [correctAnswer];
        
        for (const alt of alternatives) {
            if (userAnswer.toLowerCase().trim() === alt.toLowerCase().trim()) {
                isCorrect = true;
                break;
            }
        }
        
        // Benzerlik kontrolü (yakın cevaplar için)
        if (!isCorrect) {
            const similarity = calculateStringSimilarity(userAnswer.toLowerCase(), correctAnswer.toLowerCase());
            if (similarity > 0.8) {
                isCorrect = true;
            }
        }
        
        // Butonu devre dışı bırak
        const button = document.querySelector(`button[data-question-index="${questionIndex}"]`);
        button.disabled = true;
        input.disabled = true;
        
        // Stil güncellemeleri
        if (isCorrect) {
            input.classList.add('correct');
            score++;
            showFeedback(questionIndex, `Doğru! ${question.aciklama || ''}`, true);
        } else {
            input.classList.add('incorrect');
            showFeedback(questionIndex, `Yanlış. Doğru cevap: "${correctAnswer}". ${question.aciklama || ''}`, false);
        }
        
        // Kullanıcı cevabını kaydet
        userAnswers[questionIndex] = userAnswer;
        
        answeredQuestions++;
        updateProgress();
    };

    // Doğru-Yanlış cevaplama fonksiyonu
    window.handleTrueFalseAnswer = function(questionIndex, userAnswer) {
        const question = allQuestions[questionIndex];
        const correctAnswer = question.dogru_cevap;
        
        // String olarak karşılaştır
        const userAnswerStr = userAnswer ? 'true' : 'false';
        const isCorrect = userAnswerStr === correctAnswer;
        
        // Tüm seçenekleri devre dışı bırak
        const options = document.querySelectorAll(`.true-false-option[data-question-index="${questionIndex}"]`);
        options.forEach(opt => {
            opt.classList.add('answered');
            if (opt.dataset.answer === correctAnswer) {
                opt.classList.add('correct');
            }
        });
        
        // Seçilen seçeneği işaretle
        const selectedOption = document.querySelector(`.true-false-option[data-question-index="${questionIndex}"][data-answer="${userAnswerStr}"]`);
        if (selectedOption && !isCorrect) {
            selectedOption.classList.add('incorrect');
        }
        
        if (isCorrect) {
            score++;
            showFeedback(questionIndex, `Doğru! ${question.aciklama || ''}`, true);
        } else {
            const correctText = correctAnswer === 'true' ? 'Doğru' : 'Yanlış';
            showFeedback(questionIndex, `Yanlış. Doğru cevap: ${correctText}. ${question.aciklama || ''}`, false);
        }
        
        // Kullanıcı cevabını kaydet
        userAnswers[questionIndex] = userAnswer ? 'Doğru' : 'Yanlış';
        
        answeredQuestions++;
        updateProgress();
    };

    // Manuel klasik soru değerlendirme fonksiyonu (fallback)
    function evaluateClassicManually(question, userAnswer) {
        const answer = userAnswer.toLowerCase().trim();
        const sampleAnswer = (question.ornek_cevap || question.cevap || '').toLowerCase().trim();
        
        // Minimum uzunluk kontrolü
        if (answer.length < 10) {
            return {
                isCorrect: false,
                feedback: 'Cevabınız çok kısa. Lütfen daha detaylı açıklama yapın.'
            };
        }
        
        // Maksimum uzunluk kontrolü
        if (answer.length > 1000) {
            return {
                isCorrect: false,
                feedback: 'Cevabınız çok uzun. Lütfen daha öz bir açıklama yapın.'
            };
        }
        
        // Anahtar kelime kontrolü (örnek cevap varsa)
        if (sampleAnswer) {
            const sampleWords = sampleAnswer.split(/\s+/).filter(word => word.length > 3);
            const userWords = answer.split(/\s+/);
            let matchCount = 0;
            
            sampleWords.forEach(sampleWord => {
                if (userWords.some(userWord => 
                    userWord.includes(sampleWord) || 
                    sampleWord.includes(userWord) ||
                    calculateStringSimilarity(userWord, sampleWord) > 0.7
                )) {
                    matchCount++;
                }
            });
            
            const matchPercentage = matchCount / sampleWords.length;
            
            if (matchPercentage >= 0.4) { // %40 eşleşme
                return {
                    isCorrect: true,
                    feedback: `Cevabınız kabul edilebilir seviyede. Anahtar kavramların %${Math.round(matchPercentage * 100)}'ini kullandınız.`
                };
            } else if (matchPercentage >= 0.2) { // %20 eşleşme
                return {
                    isCorrect: false,
                    feedback: `Cevabınızda bazı doğru kavramlar var ama eksik. Örnek cevabı inceleyerek geliştirebilirsiniz.`
                };
            } else {
                return {
                    isCorrect: false,
                    feedback: 'Cevabınız beklenen içerikle uyuşmuyor. Örnek cevabı kontrol edin.'
                };
            }
        }
        
        // Örnek cevap yoksa genel değerlendirme
        const meaningfulWords = answer.split(/\s+/).filter(word => word.length > 3).length;
        
        if (meaningfulWords >= 5) {
            return {
                isCorrect: true,
                feedback: 'Cevabınız yeterli detayda yazılmış. Manuel olarak kabul edildi.'
            };
        } else {
            return {
                isCorrect: false,
                feedback: 'Cevabınızda daha fazla detay ve açıklama bekleniyor.'
            };
        }
    }

    // String benzerlik hesaplama fonksiyonu
    function calculateStringSimilarity(str1, str2) {
        const longer = str1.length > str2.length ? str1 : str2;
        const shorter = str1.length > str2.length ? str2 : str1;
        
        if (longer.length === 0) return 1.0;
        
        const editDistance = levenshteinDistance(longer, shorter);
        return (longer.length - editDistance) / longer.length;
    }

    // Levenshtein distance hesaplama
    function levenshteinDistance(str1, str2) {
        const matrix = [];
        
        for (let i = 0; i <= str2.length; i++) {
            matrix[i] = [i];
        }
        
        for (let j = 0; j <= str1.length; j++) {
            matrix[0][j] = j;
        }
        
        for (let i = 1; i <= str2.length; i++) {
            for (let j = 1; j <= str1.length; j++) {
                if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
                    matrix[i][j] = matrix[i - 1][j - 1];
                } else {
                    matrix[i][j] = Math.min(
                        matrix[i - 1][j - 1] + 1,
                        matrix[i][j - 1] + 1,
                        matrix[i - 1][j] + 1
                    );
                }
            }
        }
        
        return matrix[str2.length][str1.length];
    }

    // WebSocket bağlantısı kur
    function initWebSocketConnection() {
        try {
            // Chat ID'yi localStorage'dan al
            const chatId = localStorage.getItem('currentChatId') || 'default';
            const wsUrl = `ws://localhost:8000/ws/${chatId}`;
            
            window.testWebSocket = new WebSocket(wsUrl);
            
            window.testWebSocket.onopen = function(event) {
                console.log('✅ Test WebSocket bağlantısı kuruldu');
            };
            
            window.testWebSocket.onmessage = function(event) {
                // Mesajlar requestLLMEvaluation fonksiyonunda dinleniyor
            };
            
            window.testWebSocket.onclose = function(event) {
                console.log('🔌 Test WebSocket bağlantısı kapandı');
            };
            
            window.testWebSocket.onerror = function(error) {
                console.error('❌ Test WebSocket hatası:', error);
            };
            
        } catch (error) {
            console.error('❌ WebSocket bağlantı hatası:', error);
        }
    }

    // Test bilgisi gösterme fonksiyonu
    window.showTestInfo = function() {
        const totalTime = answeredQuestions > 0 ? 
            ((Date.now() - window.testStartTime) / 1000 / 60).toFixed(1) : 0;
        
        const infoMessage = `
📊 **Test Bilgileri**

🔢 **Toplam Soru:** ${totalQuestions}
✅ **Cevaplanan:** ${answeredQuestions}
⏳ **Kalan:** ${totalQuestions - answeredQuestions}
📈 **İlerleme:** %${Math.round((answeredQuestions / totalQuestions) * 100)}
⌚ **Geçen Süre:** ${totalTime} dakika

💡 **İpucu:** Test tamamlanmadan da sonuçları görüntüleyebilirsiniz!
        `;

        alert(infoMessage);
    };

    // Test başlangıç zamanını kaydet
    window.testStartTime = Date.now();

    // Testi başlat ve WebSocket bağlantısı kur
    initWebSocketConnection();
});
