// static/js/ui/DOM.js

// 'export' kelimesi, bu DOM nesnesini diğer dosyalarda import edebilmemizi sağlar.
export const DOM = {
    // Ana Sohbet Alanı
    messagesContainer: document.getElementById('messagesContainer'),
    
    // Bağlantı Durumu
    connectionStatus: document.getElementById('connectionStatus'),
    
    // Mesaj Giriş Alanı
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    charCount: document.getElementById('charCount'),
    
    // Kenar Çubuğu (Sidebar)
    chatList: document.getElementById('chatList'),
    
    // Ayarlar Modalı
    settingsModal: document.getElementById('settingsModal'),
    themeSelect: document.getElementById('themeSelect'),
    fontSizeSelect: document.getElementById('fontSizeSelect'),
    soundNotifications: document.getElementById('soundNotifications'),
};