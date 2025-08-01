// static/js/core/ChatHistoryManager.js

class ChatHistoryManager {
    constructor(app) {
        this.app = app;
        this.currentChatId = null;
        this.chats = [];
        this.isLoading = false;
        
        this.initializeEventListeners();
        this.loadChatHistory();
    }

    initializeEventListeners() {
        // Yeni sohbet butonu
        const newChatBtn = document.querySelector('.new-chat-btn');
        if (newChatBtn) {
            newChatBtn.addEventListener('click', () => this.createNewChat());
        }

        // Chat list event delegation
        const chatList = document.getElementById('chatList');
        if (chatList) {
            chatList.addEventListener('click', (e) => {
                const chatItem = e.target.closest('.chat-item');
                if (chatItem) {
                    const chatId = chatItem.dataset.chatId;
                    if (chatId) {
                        this.loadChat(chatId);
                    }
                }

                // Silme butonu
                if (e.target.classList.contains('delete-chat-btn')) {
                    e.stopPropagation();
                    const chatId = e.target.closest('.chat-item').dataset.chatId;
                    this.deleteChat(chatId);
                }
            });
        }
    }

    async loadChatHistory() {
        if (this.isLoading) return;
        
        try {
            this.isLoading = true;
            const response = await fetch('/chats');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.chats = data.chats;
                this.renderChatList();
                console.log(`✅ ${this.chats.length} sohbet yüklendi`);
            } else {
                console.error('❌ Sohbet yükleme başarısız:', data);
            }
            
        } catch (error) {
            console.error('❌ Sohbet geçmişi yükleme hatası:', error);
            this.showError('Sohbet geçmişi yüklenirken hata oluştu');
        } finally {
            this.isLoading = false;
        }
    }

    async createNewChat() {
        try {
            const response = await fetch('/chats/new', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                // Yeni sohbeti listeye ekle
                this.chats.unshift(data.chat);
                this.renderChatList();
                
                // Yeni sohbeti yükle
                await this.loadChat(data.chat.id);
                
                console.log('✅ Yeni sohbet oluşturuldu:', data.chat.id);
            } else {
                throw new Error(data.message || 'Sohbet oluşturulamadı');
            }
            
        } catch (error) {
            console.error('❌ Yeni sohbet oluşturma hatası:', error);
            this.showError('Yeni sohbet oluşturulurken hata oluştu');
        }
    }

    async loadChat(chatId) {
        if (this.currentChatId === chatId) {
            console.log('ℹ️ Aynı sohbet zaten açık:', chatId);
            return;
        }

        try {
            // UI'yi loading durumuna getir
            this.showLoadingState();
            
            const response = await fetch(`/chats/${chatId}`);
            
            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('Sohbet bulunamadı');
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.currentChatId = chatId;
                
                // Sohbet listesindeki aktif durumu güncelle
                this.updateActiveChatInList(chatId);
                
                // Mesajları temizle ve yükle
                this.clearMessages();
                this.loadMessages(data.messages);
                
                // PDF istatistiklerini güncelle
                if (data.vector_store_stats) {
                    this.app.updatePDFStats(data.vector_store_stats);
                }
                
                // WebSocket bağlantısını bu chat için yeniden kur
                this.app.ws.reconnectWithChatId(chatId);
                
                console.log('✅ Sohbet yüklendi:', chatId);
                console.log('📊 Mesaj sayısı:', data.messages.length);
                
            } else {
                throw new Error(data.message || 'Sohbet yüklenemedi');
            }
            
        } catch (error) {
            console.error('❌ Sohbet yükleme hatası:', error);
            this.showError(`Sohbet yüklenirken hata oluştu: ${error.message}`);
        } finally {
            this.hideLoadingState();
        }
    }

    async deleteChat(chatId) {
        if (!confirm('Bu sohbeti silmek istediğinizden emin misiniz? Bu işlem geri alınamaz.')) {
            return;
        }

        try {
            const response = await fetch(`/chats/${chatId}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                // Listeden kaldır
                this.chats = this.chats.filter(chat => chat.id !== chatId);
                this.renderChatList();
                
                // Eğer silinen sohbet aktif sohbet ise, yeni sohbet oluştur
                if (this.currentChatId === chatId) {
                    await this.createNewChat();
                }
                
                console.log('✅ Sohbet silindi:', chatId);
                this.showSuccess('Sohbet başarıyla silindi');
                
            } else {
                throw new Error(data.message || 'Sohbet silinemedi');
            }
            
        } catch (error) {
            console.error('❌ Sohbet silme hatası:', error);
            this.showError(`Sohbet silinirken hata oluştu: ${error.message}`);
        }
    }

    renderChatList() {
        const chatList = document.getElementById('chatList');
        if (!chatList) return;

        if (this.chats.length === 0) {
            chatList.innerHTML = `
                <div class="empty-chat-list">
                    <i class="fas fa-comments"></i>
                    <p>Henüz sohbet yok</p>
                    <small>Yeni sohbet başlatmak için yukarıdaki butona tıklayın</small>
                </div>
            `;
            return;
        }

        chatList.innerHTML = this.chats.map(chat => this.renderChatItem(chat)).join('');
    }

    renderChatItem(chat) {
        const isActive = chat.id === this.currentChatId;
        const updatedDate = new Date(chat.updated_at);
        const timeAgo = this.getTimeAgo(updatedDate);
        
        // Son mesajı kısalt
        const lastMessage = chat.last_message || 'Henüz mesaj yok';
        const truncatedMessage = lastMessage.length > 50 
            ? lastMessage.substring(0, 50) + '...' 
            : lastMessage;

        return `
            <div class="chat-item ${isActive ? 'active' : ''}" data-chat-id="${chat.id}">
                <div class="chat-item-header">
                    <div class="chat-item-title" title="${chat.title}">
                        ${this.escapeHtml(chat.title)}
                    </div>
                    <div class="chat-item-actions">
                        <span class="chat-item-time">${timeAgo}</span>
                        <button class="delete-chat-btn" title="Sohbeti Sil">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                <div class="chat-item-preview" title="${this.escapeHtml(lastMessage)}">
                    ${this.escapeHtml(truncatedMessage)}
                </div>
                <div class="chat-item-stats">
                    <span class="stat-item">
                        <i class="fas fa-comment"></i>
                        ${chat.message_count || 0}
                    </span>
                    <span class="stat-item">
                        <i class="fas fa-file-pdf"></i>
                        ${chat.pdf_count || 0}
                    </span>
                </div>
            </div>
        `;
    }

    updateActiveChatInList(chatId) {
        const chatItems = document.querySelectorAll('.chat-item');
        chatItems.forEach(item => {
            if (item.dataset.chatId === chatId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    loadMessages(messages) {
        if (!messages || messages.length === 0) {
            // Hoş geldin mesajını göster
            this.showWelcomeMessage();
            return;
        }

        // Hoş geldin mesajını gizle
        this.hideWelcomeMessage();

        // Mesajları yükle
        messages.forEach(message => {
            if (message.type === 'user') {
                this.app.ui.addMessage(message.content, 'user');
            } else if (message.type === 'ai') {
                this.app.ui.addMessage(message.content, 'ai');
            }
        });

        // En alta scroll et
        this.app.ui.scrollToBottom();
    }

    clearMessages() {
        const messagesContainer = document.getElementById('messagesContainer');
        if (messagesContainer) {
            messagesContainer.innerHTML = '';
        }
    }

    showWelcomeMessage() {
        const messagesContainer = document.getElementById('messagesContainer');
        if (messagesContainer && !messagesContainer.querySelector('.welcome-message')) {
            messagesContainer.innerHTML = `
                <div class="welcome-message">
                    <div class="welcome-icon">
                        <i class="fas fa-robot"></i>
                    </div>
                    <h2>Merhaba! 👋</h2>
                    <p>Size nasıl yardımcı olabilirim? Aşağıdaki konularda uzmanım:</p>
                    <div class="feature-list">
                        <div class="feature-item"><i class="fas fa-search"></i> Web araştırması</div>
                        <div class="feature-item"><i class="fas fa-file-pdf"></i> PDF doküman analizi</div>
                        <div class="feature-item"><i class="fas fa-brain"></i> Akıllı soru-cevap</div>
                        <div class="feature-item"><i class="fas fa-chart-line"></i> Veri analizi</div>
                    </div>
                </div>
            `;
        }
    }

    hideWelcomeMessage() {
        const welcomeMessage = document.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }
    }

    showLoadingState() {
        const messagesContainer = document.getElementById('messagesContainer');
        if (messagesContainer) {
            messagesContainer.innerHTML = `
                <div class="loading-chat">
                    <div class="loading-spinner"></div>
                    <p>Sohbet yükleniyor...</p>
                </div>
            `;
        }
    }

    hideLoadingState() {
        const loadingChat = document.querySelector('.loading-chat');
        if (loadingChat) {
            loadingChat.remove();
        }
    }

    // Utility methods
    getTimeAgo(date) {
        const now = new Date();
        const diffInSeconds = Math.floor((now - date) / 1000);
        
        if (diffInSeconds < 60) return 'Az önce';
        if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} dk önce`;
        if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} sa önce`;
        if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)} gün önce`;
        
        return date.toLocaleDateString('tr-TR');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showError(message) {
        // Basit error notification
        console.error('❌', message);
        // Gelecekte toast notification eklenebilir
    }

    showSuccess(message) {
        // Basit success notification  
        console.log('✅', message);
        // Gelecekte toast notification eklenebilir
    }

    // Public methods
    getCurrentChatId() {
        return this.currentChatId;
    }

    updateChatTitle(chatId, newTitle) {
        const chat = this.chats.find(c => c.id === chatId);
        if (chat) {
            chat.title = newTitle;
            this.renderChatList();
        }
    }

    updateChatStats(chatId, messageCount, pdfCount) {
        const chat = this.chats.find(c => c.id === chatId);
        if (chat) {
            chat.message_count = messageCount;
            chat.pdf_count = pdfCount;
            chat.updated_at = new Date().toISOString();
            this.renderChatList();
        }
    }
}

export default ChatHistoryManager;