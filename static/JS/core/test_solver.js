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
            const questions = testData.questions;

            // Tüm soru türlerini tek bir listeye topla
            if (questions.coktan_secmeli) allQuestions.push(...questions.coktan_secmeli.map(q => ({...q, type: 'coktan_secmeli'})));
            if (questions.klasik) allQuestions.push(...questions.klasik.map(q => ({...q, type: 'klasik'})));
            if (questions.bosluk_doldurma) allQuestions.push(...questions.bosluk_doldurma.map(q => ({...q, type: 'bosluk_doldurma'})));

            totalQuestions = allQuestions.length;
            if (totalQuestions === 0) {
                showError("Bu testte hiç soru bulunmuyor.");
                return;
            }

            renderTest();
        } catch (error) {
            console.error("Test yüklenirken hata:", error);
            showError("Test yüklenirken bir hata oluştu. Lütfen konsolu kontrol edin.");
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
            }
            
            questionHTML += `<div class="answer-feedback" id="feedback-${index}"></div>`;
            questionCard.innerHTML = questionHTML;
            testBody.appendChild(questionCard);
        });

        attachEventListeners();
        updateProgress();
    }

    function renderMultipleChoice(question, index) {
        let optionsHTML = '<ul class="options-list">';
        for (const [key, value] of Object.entries(question.secenekler)) {
            optionsHTML += `
                <li class="option-item" data-question-index="${index}" data-answer-key="${key}">
                    <span class="option-letter">${key}</span>
                    <span class="option-text">${value}</span>
                </li>
            `;
        }
        optionsHTML += '</ul>';
        return optionsHTML;
    }
    
    // Diğer soru tipleri için render fonksiyonları (klasik, boşluk doldurma) benzer şekilde eklenebilir.
    function renderClassic(question, index) { return `<div class="classic-answer-area"><textarea placeholder="Cevabınızı buraya yazın..."></textarea><button data-question-index="${index}">Cevapla</button></div>`; }
    function renderFillBlank(question, index) { return `<div class="classic-answer-area"><input type="text" placeholder="Boşluğu doldurun..." /><button data-question-index="${index}">Cevapla</button></div>`; }


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

        if (answeredQuestions === totalQuestions) {
            finishTestBtn.style.display = 'block';
            finishTestBtn.onclick = showFinalResults;
        }
    }
    
    function showFinalResults() {
        finalScoreEl.textContent = `${score} / ${totalQuestions}`;
        resultSummary.style.display = 'block';
        finishTestBtn.style.display = 'none';
        // TODO: Sonuçları ana sunucuya göndererek zayıf konuları analiz et.
    }

    function finishTest() {
        if (answeredQuestions < totalQuestions) {
            if (!confirm('Testi henüz bitirmediniz. Yine de sonuçları görmek istiyor musunuz?')) {
                return;
            }
        }

        // Test sonuçlarını hesapla
        const results = calculateTestResults();
        
        // Sonuçları göster
        showTestResults(results);
        
        // Ana pencereye sonuçları gönder
        sendResultsToMainWindow(results);
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
                        <h3>🎯 Eksik Olduğun Konular</h3>
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
                ` : '<div class="perfect-score">🎉 Mükemmel! Hiç hata yapmadın!</div>'}

                <div class="results-actions">
                    <button class="review-btn" onclick="showDetailedReview()">
                        📋 Detaylı İnceleme
                    </button>
                    <button class="close-btn" onclick="window.close()">
                        🏠 Ana Sayfaya Dön
                    </button>
                </div>

                <div class="detailed-review" id="detailedReview" style="display: none;">
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
});
