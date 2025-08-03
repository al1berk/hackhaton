// static/js/ui/UIManager.js
import { DOM } from './DOM.js';
import { ProgressUI } from './ProgressUI.js';

export class UIManager {
    constructor() {
        this.progressUI = new ProgressUI();
    }
    
    // Mesajlaşma arayüzü
    addMessage(content, sender) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${sender}`;
        const formattedContent = this.progressUI.formatContent(content).replace(/<p>|<\/p>/g, ""); // p tag'leri mesaj kutusunda olmasın
        
        messageElement.innerHTML = `
            <div class="message-avatar"><i class="fas ${sender === 'user' ? 'fa-user' : sender === 'ai' ? 'fa-robot' : 'fa-cog'}"></i></div>
            <div class="message-content">${formattedContent}</div>
        `;
        
        DOM.messagesContainer.appendChild(messageElement);
        this.scrollToBottom();
    }

    showTypingIndicator() {
        if (document.getElementById('typingIndicator')) return;
        const typingElement = document.createElement('div');
        typingElement.className = 'message ai'; // Stil tutarlılığı için
        typingElement.id = 'typingIndicator';
        typingElement.innerHTML = `
            <div class="message-avatar"><i class="fas fa-robot"></i></div>
            <div class="message-content"><div class="typing-dots"><span></span><span></span><span></span></div></div>
        `;
        DOM.messagesContainer.appendChild(typingElement);
        this.scrollToBottom();
    }

    displayTestButton(data) {
        const messageElement = document.createElement('div');
        messageElement.className = 'message system'; // Sistem mesajı olarak gösterelim

        const content = data.content || 'Testin başarıyla oluşturuldu!';
        const questions = data.questions;

        // Butonun HTML içeriğini oluştur
        messageElement.innerHTML = `
            <div class="message-avatar"><i class="fas fa-clipboard-check"></i></div>
            <div class="message-content">
                <p>${content}</p>
                <div class="test-button-container">
                    <button class="solve-test-btn">
                        <i class="fas fa-pencil-alt"></i> Testi Çöz
                    </button>
                </div>
            </div>
        `;

        // Butonu bul ve olay dinleyicisi ekle
        const solveButton = messageElement.querySelector('.solve-test-btn');
        if (solveButton) {
            solveButton.onclick = () => {
                try {
                    // Soru verisini tarayıcının hafızasına kaydet
                    localStorage.setItem('currentTestQuestions', JSON.stringify(questions));
                    console.log('✅ Test soruları localStorage\'a kaydedildi.');

                    // Yeni bir sekmede test çözme sayfasını aç
                    window.open('test_solver.html', '_blank');
                } catch (error) {
                    console.error('❌ Test başlatılırken hata:', error);
                    alert('Test başlatılırken bir sorun oluştu. Lütfen konsolu kontrol edin.');
                }
            };
        }

        DOM.messagesContainer.appendChild(messageElement);
        this.scrollToBottom();
    }

    removeTypingIndicator() {
        const typingIndicator = document.getElementById('typingIndicator');
        if (typingIndicator) typingIndicator.remove();
    }

    showConfirmationUI(question, onConfirmCallback) {
        this.addMessage(question, 'system');
        const confirmationContainer = document.createElement('div');
        confirmationContainer.className = 'confirmation-container';
        
        const yesButton = document.createElement('button');
        yesButton.textContent = 'Evet, Başlat';
        yesButton.className = 'confirmation-btn yes';
        
        const noButton = document.createElement('button');
        noButton.textContent = 'Hayır, Teşekkürler';
        noButton.className = 'confirmation-btn no';

        yesButton.onclick = () => {
            onConfirmCallback(true);
            confirmationContainer.remove();
        };
        noButton.onclick = () => {
            onConfirmCallback(false);
            confirmationContainer.remove();
        };

        confirmationContainer.appendChild(yesButton);
        confirmationContainer.appendChild(noButton);
        DOM.messagesContainer.appendChild(confirmationContainer);
        this.scrollToBottom();
    }

    // Genel UI fonksiyonları
    updateConnectionStatus(status, text) {
        const indicator = DOM.connectionStatus.querySelector('.status-indicator');
        const statusText = DOM.connectionStatus.querySelector('span');
        indicator.className = `status-indicator ${status}`;
        statusText.textContent = text;
    }
    
    hideWelcomeMessage() {
        const welcomeMessage = document.querySelector('.welcome-message');
        if (welcomeMessage) welcomeMessage.style.display = 'none';
    }

    scrollToBottom() {
        DOM.messagesContainer.scrollTop = DOM.messagesContainer.scrollHeight;
    }

    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }
}