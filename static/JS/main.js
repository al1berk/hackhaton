// static/js/main.js
import App from './core/App.js';

// Global functions (HTML'den çağrılabilir)
window.startNewChat = function() {
    if (window.app && window.app.chatHistory) {
        window.app.chatHistory.createNewChat();
    }
};

window.sendMessage = function() {
    if (window.app) {
        window.app.sendMessage();
    }
};

window.toggleSettings = function() {
    const modal = document.getElementById('settingsModal');
    if (modal) {
        modal.style.display = modal.style.display === 'flex' ? 'none' : 'flex';
    }
};

window.cancelUpload = function() {
    if (window.app && window.app.pdfManager) {
        window.app.pdfManager.cancelUpload();
    }
};

// DOM ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 LangGraph AI Assistant başlatılıyor...');
    
    try {
        // Ana uygulamayı başlat
        window.app = new App();
        
        console.log('✅ Uygulama başarıyla başlatıldı');
        console.log('📊 App State:', window.app.getState());
        
        // Settings modal event listeners
        setupSettingsModal();
        
        // Global error handling
        window.addEventListener('error', (e) => {
            console.error('❌ Global error:', e.error);
        });
        
        window.addEventListener('unhandledrejection', (e) => {
            console.error('❌ Unhandled promise rejection:', e.reason);
        });
        
    } catch (error) {
        console.error('❌ Uygulama başlatma hatası:', error);
        
        // Fallback UI göster
        showErrorFallback(error.message);
    }
});

function setupSettingsModal() {
    // Settings modal kapama
    document.addEventListener('click', (e) => {
        const modal = document.getElementById('settingsModal');
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });
    
    // ESC ile modal kapama
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const modal = document.getElementById('settingsModal');
            if (modal && modal.style.display === 'flex') {
                modal.style.display = 'none';
            }
        }
    });
    
    // Settings form handling
    const themeSelect = document.getElementById('themeSelect');
    const fontSizeSelect = document.getElementById('fontSizeSelect');
    const soundNotifications = document.getElementById('soundNotifications');
    const ragEnabled = document.getElementById('ragEnabled');
    
    // Load saved settings
    loadSettings();
    
    // Save settings on change
    if (themeSelect) {
        themeSelect.addEventListener('change', saveSettings);
    }
    if (fontSizeSelect) {
        fontSizeSelect.addEventListener('change', saveSettings);
    }
    if (soundNotifications) {
        soundNotifications.addEventListener('change', saveSettings);
    }
    if (ragEnabled) {
        ragEnabled.addEventListener('change', saveSettings);
    }
}

function loadSettings() {
    try {
        const settings = JSON.parse(localStorage.getItem('aiAssistantSettings') || '{}');
        
        const themeSelect = document.getElementById('themeSelect');
        const fontSizeSelect = document.getElementById('fontSizeSelect');
        const soundNotifications = document.getElementById('soundNotifications');
        const ragEnabled = document.getElementById('ragEnabled');
        
        if (themeSelect && settings.theme) {
            themeSelect.value = settings.theme;
            applyTheme(settings.theme);
        }
        
        if (fontSizeSelect && settings.fontSize) {
            fontSizeSelect.value = settings.fontSize;
            applyFontSize(settings.fontSize);
        }
        
        if (soundNotifications && typeof settings.soundNotifications === 'boolean') {
            soundNotifications.checked = settings.soundNotifications;
        }
        
        if (ragEnabled && typeof settings.ragEnabled === 'boolean') {
            ragEnabled.checked = settings.ragEnabled;
        }
        
    } catch (error) {
        console.warn('⚠️ Settings yükleme hatası:', error);
    }
}

function saveSettings() {
    try {
        const themeSelect = document.getElementById('themeSelect');
        const fontSizeSelect = document.getElementById('fontSizeSelect');
        const soundNotifications = document.getElementById('soundNotifications');
        const ragEnabled = document.getElementById('ragEnabled');
        
        const settings = {
            theme: themeSelect?.value || 'light',
            fontSize: fontSizeSelect?.value || 'medium',
            soundNotifications: soundNotifications?.checked || false,
            ragEnabled: ragEnabled?.checked || true
        };
        
        localStorage.setItem('aiAssistantSettings', JSON.stringify(settings));
        
        // Apply settings
        applyTheme(settings.theme);
        applyFontSize(settings.fontSize);
        
        console.log('💾 Settings saved:', settings);
        
    } catch (error) {
        console.error('❌ Settings kaydetme hatası:', error);
    }
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    
    if (theme === 'auto') {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
    }
}

function applyFontSize(fontSize) {
    document.documentElement.setAttribute('data-font-size', fontSize);
}

function showErrorFallback(errorMessage) {
    const container = document.querySelector('.app-container');
    if (container) {
        container.innerHTML = `
            <div class="error-fallback">
                <div class="error-icon">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <h2>Uygulama Başlatılamadı</h2>
                <p>Bir hata oluştu ve uygulama başlatılamadı.</p>
                <div class="error-details">
                    <strong>Hata:</strong> ${errorMessage}
                </div>
                <button onclick="window.location.reload()" class="retry-btn">
                    <i class="fas fa-redo"></i>
                    Sayfayı Yenile
                </button>
            </div>
        `;
    }
}

// Media query listener for auto theme
if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        const currentTheme = document.getElementById('themeSelect')?.value;
        if (currentTheme === 'auto') {
            document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
        }
    });
}

// Debug functions (development only)
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    window.debugApp = function() {
        if (window.app) {
            console.log('🐛 App Debug Info:');
            console.log('State:', window.app.getState());
            console.log('WebSocket:', window.app.ws.getConnectionState());
            console.log('PDF State:', window.app.getPDFState());
            console.log('Chat History:', window.app.getChatHistory());
        }
    };
    
    window.clearLocalStorage = function() {
        localStorage.clear();
        console.log('🧹 LocalStorage temizlendi');
    };
    
    console.log('🔧 Debug mode aktif. Komutlar: debugApp(), clearLocalStorage()');
}