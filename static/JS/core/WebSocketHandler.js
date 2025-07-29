// static/js/core/WebSocketHandler.js
export class WebSocketHandler {
    constructor(callbacks) {
        this.ws = null;
        this.isConnected = false;
        this.callbacks = callbacks; // { onOpen, onMessage, onClose, onError }
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // Start with 1 second
        this.connect();
    }

    connect() {
        // WebSocket URL'sini daha güvenli şekilde oluştur
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname;
        const port = window.location.port;
        const wsUrl = `${protocol}//${host}${port ? ':' + port : ''}/ws`;
        
        console.log(`WebSocket bağlantı denemesi: ${wsUrl}`);
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('✅ WebSocket bağlantısı başarıyla kuruldu');
                this.isConnected = true;
                this.reconnectAttempts = 0; // Reset attempts on successful connection
                this.reconnectDelay = 1000; // Reset delay
                if (this.callbacks.onOpen) this.callbacks.onOpen();
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('📨 WebSocket mesaj alındı:', data);
                    if (this.callbacks.onMessage) this.callbacks.onMessage(data);
                } catch (error) {
                    console.error('❌ JSON parse hatası:', error, 'Raw data:', event.data);
                }
            };

            this.ws.onclose = (event) => {
                console.log(`🔌 WebSocket bağlantısı kapandı. Code: ${event.code}, Reason: ${event.reason}`);
                this.isConnected = false;
                if (this.callbacks.onClose) this.callbacks.onClose();
                
                // Reconnection logic with exponential backoff
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    console.log(`🔄 Yeniden bağlanma denemesi ${this.reconnectAttempts}/${this.maxReconnectAttempts} - ${this.reconnectDelay}ms sonra`);
                    setTimeout(() => this.connect(), this.reconnectDelay);
                    this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000); // Max 30 seconds
                } else {
                    console.error('❌ Maksimum yeniden bağlanma denemesi aşıldı');
                }
            };

            this.ws.onerror = (error) => {
                console.error('❌ WebSocket hatası:', error);
                if (this.callbacks.onError) this.callbacks.onError(error);
            };

        } catch (error) {
            console.error('❌ WebSocket oluşturma hatası:', error);
            if (this.callbacks.onError) this.callbacks.onError(error);
        }
    }

    send(data) {
        if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
            try {
                const jsonData = JSON.stringify(data);
                console.log('📤 WebSocket mesaj gönderiliyor:', data);
                this.ws.send(jsonData);
                return true;
            } catch (error) {
                console.error('❌ Mesaj gönderme hatası:', error);
                return false;
            }
        } else {
            console.error("❌ WebSocket bağlı değil veya hazır değil. ReadyState:", this.ws?.readyState);
            return false;
        }
    }

    // Manual reconnect method
    reconnect() {
        if (this.ws) {
            this.ws.close();
        }
        this.reconnectAttempts = 0;
        this.connect();
    }

    // Graceful disconnect
    disconnect() {
        this.reconnectAttempts = this.maxReconnectAttempts; // Prevent reconnection
        if (this.ws) {
            this.ws.close(1000, 'Manual disconnect');
        }
    }
}