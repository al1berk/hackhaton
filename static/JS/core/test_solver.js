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

    function showError(message) {
        testBody.innerHTML = `<div class="error-state"><h3>Hata!</h3><p>${message}</p></div>`;
    }

    // Testi başlat
    loadTest();
});
