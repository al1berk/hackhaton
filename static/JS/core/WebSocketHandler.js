// static/js/core/WebSocketHandler.js

export class WebSocketHandler {
    constructor(callbacks = {}) {
        this.callbacks = {
            onOpen: callbacks.onOpen || (() => {}),
            onMessage: callbacks.onMessage || (() => {}),
            onClose: callbacks.onClose || (() => {}),
            onError: callbacks.onError || (() => {})
        };
        
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.currentChatId = null; // YENİ: Mevcut chat ID
        
        this.connect();
    }
    
    connect(chatId = null) {
        try {
            // Chat ID'yi güncelle
            this.currentChatId = chatId;
            
            // WebSocket URL'sini belirle
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;
            
            let wsUrl;
            if (chatId) {
                wsUrl = `${protocol}//${host}/ws/${chatId}`;
            } else {
                wsUrl = `${protocol}//${host}/ws`;
            }
            
            console.log(`🔌 WebSocket bağlantısı kuruluyor: ${wsUrl}`);
            
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = (event) => {
                console.log('✅ WebSocket bağlantısı açıldı');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.callbacks.onOpen(event);
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.callbacks.onMessage(data);
                } catch (error) {
                    console.error('❌ WebSocket mesaj parse hatası:', error);
                    console.log('Raw message:', event.data);
                }
            };
            
            this.ws.onclose = (event) => {
                console.log('🔌 WebSocket bağlantısı kapandı:', event.code, event.reason);
                this.isConnected = false;
                this.callbacks.onClose(event);
                
                // Otomatik yeniden bağlanma
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.scheduleReconnect();
                }
            };
            
            this.ws.onerror = (error) => {
                console.error('❌ WebSocket hatası:', error);
                this.callbacks.onError(error);
            };
            
        } catch (error) {
            console.error('❌ WebSocket bağlantı hatası:', error);
            this.callbacks.onError(error);
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
    
    scheduleReconnect() {
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff
        
        console.log(`🔄 Yeniden bağlanma denemesi ${this.reconnectAttempts}/${this.maxReconnectAttempts} - ${delay}ms sonra`);
        
        setTimeout(() => {
            if (!this.isConnected) {
                this.connect(this.currentChatId);
            }
        }, delay);
    }
    
    send(data) {
        if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.warn('⚠️ WebSocket bağlı değil, mesaj gönderilemedi');
            return false;
        }
        
        try {
            const jsonData = typeof data === 'string' ? data : JSON.stringify(data);
            this.ws.send(jsonData);
            return true;
        } catch (error) {
            console.error('❌ WebSocket mesaj gönderme hatası:', error);
            return false;
        }
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