// static/JS/ui/DOM.js
export const DOM = {
    // Message elements
    messagesContainer: null,
    messageInput: null,
    sendBtn: null,
    charCount: null,
    
    // Chat history elements
    chatList: null,
    
    // PDF elements
    pdfList: null,
    pdfFileInput: null,
    totalPdfs: null,
    totalChunks: null,
    
    // Connection status
    connectionStatus: null,
    
    // Modals
    settingsModal: null,
    uploadModal: null,
    
    // Upload modal elements
    uploadFilename: null,
    uploadStatus: null,
    progressFill: null,
    fileSize: null,
    processStatus: null,
    
    // Settings elements
    webResearchEnabled: null,
    ragEnabled: null,
    themeSelect: null,
    fontSizeSelect: null,
    soundNotifications: null,
    
    // Utility method to get elements with fallback
    get(id) {
        const element = document.getElementById(id);
        if (!element) {
            console.warn(`⚠️ Element bulunamadı: ${id}`);
        }
        return element;
    },
    
    // Initialize all DOM references
    init() {
        this.messagesContainer = this.get('messagesContainer');
        this.messageInput = this.get('messageInput');
        this.sendBtn = this.get('sendBtn');
        this.charCount = this.get('charCount');
        this.chatList = this.get('chatList');
        this.pdfList = this.get('pdfList');
        this.pdfFileInput = this.get('pdfFileInput');
        this.totalPdfs = this.get('totalPdfs');
        this.totalChunks = this.get('totalChunks');
        this.connectionStatus = this.get('connectionStatus');
        this.settingsModal = this.get('settingsModal');
        this.uploadModal = this.get('uploadModal');
        this.uploadFilename = this.get('uploadFilename');
        this.uploadStatus = this.get('uploadStatus');
        this.progressFill = this.get('progressFill');
        this.fileSize = this.get('fileSize');
        this.processStatus = this.get('processStatus');
        this.webResearchEnabled = this.get('webResearchEnabled');
        this.ragEnabled = this.get('ragEnabled');
        this.themeSelect = this.get('themeSelect');
        this.fontSizeSelect = this.get('fontSizeSelect');
        this.soundNotifications = this.get('soundNotifications');
        
        console.log('✅ DOM references initialized');
    }
};

// Initialize when the DOM is loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => DOM.init());
} else {
    DOM.init();
}

export default DOM;