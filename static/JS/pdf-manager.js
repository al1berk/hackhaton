// static/js/pdf-manager.js

class PDFManager {
    constructor(app) {
        this.app = app;
        this.isUploading = false;
        this.uploadModal = null;
        this.currentUpload = null;
        
        this.initializeElements();
        this.setupEventListeners();
        this.loadPDFList();
    }

    initializeElements() {
        this.fileInput = document.getElementById('pdfFileInput');
        this.uploadModal = document.getElementById('uploadModal');
        this.pdfList = document.getElementById('pdfList');
        this.pdfStats = document.getElementById('pdfStats');
        
        // Upload modal elements
        this.uploadFilename = document.getElementById('uploadFilename');
        this.uploadStatus = document.getElementById('uploadStatus');
        this.progressFill = document.getElementById('progressFill');
        this.fileSize = document.getElementById('fileSize');
        this.processStatus = document.getElementById('processStatus');
    }

    setupEventListeners() {
        // File input change event
        if (this.fileInput) {
            this.fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    this.handleFileSelect(e.target.files[0]);
                }
            });
        }

        // Cancel upload button
        const cancelBtn = document.querySelector('.cancel-upload-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.cancelUpload());
        }

        // PDF list event delegation
        if (this.pdfList) {
            this.pdfList.addEventListener('click', (e) => {
                if (e.target.classList.contains('delete-pdf-btn')) {
                    const fileHash = e.target.dataset.hash;
                    if (fileHash) {
                        this.deletePDF(fileHash);
                    }
                }
            });
        }
    }

    async handleFileSelect(file) {
        if (this.isUploading) {
            alert('Şu anda başka bir dosya yükleniyor. Lütfen bekleyin.');
            return;
        }

        // Dosya doğrulaması
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            alert('Sadece PDF dosyaları desteklenir.');
            return;
        }

        const maxSize = 50 * 1024 * 1024; // 50MB
        if (file.size > maxSize) {
            alert('Dosya boyutu 50MB\'tan büyük olamaz.');
            return;
        }

        // Aktif chat ID'yi al
        const currentChatId = this.app.chatHistory.getCurrentChatId();
        if (!currentChatId) {
            alert('Aktif bir sohbet bulunamadı. Lütfen önce bir sohbet başlatın.');
            return;
        }

        this.startUpload(file, currentChatId);
    }

    async startUpload(file, chatId) {
        this.isUploading = true;
        this.showUploadModal();
        this.updateUploadUI(file, 'Yükleme başlıyor...');

        try {
            const formData = new FormData();
            formData.append('file', file);

            // XMLHttpRequest kullan (progress tracking için)
            const xhr = new XMLHttpRequest();
            
            // Progress tracking
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    this.updateProgress(percentComplete, 'Yükleniyor...');
                }
            });

            // Response handling
            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        this.handleUploadSuccess(response);
                    } catch (error) {
                        this.handleUploadError('Sunucu yanıtı işlenemedi');
                    }
                } else {
                    this.handleUploadError(`HTTP ${xhr.status}: ${xhr.statusText}`);
                }
            });

            xhr.addEventListener('error', () => {
                this.handleUploadError('Ağ hatası oluştu');
            });

            // Chat-specific endpoint kullan
            xhr.open('POST', `/chats/${chatId}/upload-pdf`);
            this.currentUpload = xhr;
            xhr.send(formData);

        } catch (error) {
            console.error('❌ Upload error:', error);
            this.handleUploadError(error.message);
        }
    }

    handleUploadSuccess(response) {
        console.log('✅ PDF upload success:', response);
        
        this.updateProgress(100, 'Tamamlandı!');
        
        setTimeout(() => {
            this.hideUploadModal();
            
            // App'e bilgi ver
            this.app.onPDFUploadSuccess(response);
            
            // PDF listesini yenile
            this.loadPDFList();
            
            // Success message göster
            this.showSuccessMessage(`"${response.filename}" başarıyla yüklendi!`);
            
            this.resetUpload();
        }, 1000);
    }

    handleUploadError(errorMessage) {
        console.error('❌ PDF upload error:', errorMessage);
        
        this.updateProgress(0, `Hata: ${errorMessage}`);
        
        setTimeout(() => {
            this.hideUploadModal();
            this.showErrorMessage(`PDF yükleme hatası: ${errorMessage}`);
            this.resetUpload();
        }, 2000);
    }

    cancelUpload() {
        if (this.currentUpload) {
            this.currentUpload.abort();
            this.currentUpload = null;
        }
        
        this.hideUploadModal();
        this.resetUpload();
        console.log('🚫 PDF upload cancelled');
    }

    resetUpload() {
        this.isUploading = false;
        this.currentUpload = null;
        if (this.fileInput) {
            this.fileInput.value = '';
        }
    }

    // UI Methods
    showUploadModal() {
        if (this.uploadModal) {
            this.uploadModal.style.display = 'flex';
        }
    }

    hideUploadModal() {
        if (this.uploadModal) {
            this.uploadModal.style.display = 'none';
        }
    }

    updateUploadUI(file, status) {
        if (this.uploadFilename) {
            this.uploadFilename.textContent = file.name;
        }
        if (this.uploadStatus) {
            this.uploadStatus.textContent = status;
        }
        if (this.fileSize) {
            this.fileSize.textContent = this.formatFileSize(file.size);
        }
        if (this.processStatus) {
            this.processStatus.textContent = 'İşleniyor';
        }
    }

    updateProgress(percent, status) {
        if (this.progressFill) {
            this.progressFill.style.width = `${percent}%`;
        }
        if (this.uploadStatus) {
            this.uploadStatus.textContent = status;
        }
        if (this.processStatus) {
            if (percent === 100) {
                this.processStatus.textContent = 'Tamamlandı';
            } else if (percent > 0) {
                this.processStatus.textContent = `%${Math.round(percent)}`;
            }
        }
    }

    async loadPDFList() {
        try {
            const currentChatId = this.app.chatHistory.getCurrentChatId();
            if (!currentChatId) {
                this.renderEmptyPDFList();
                return;
            }

            const response = await fetch(`/chats/${currentChatId}/pdfs`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.renderPDFList(data.documents);
                
                // Stats'i güncelle
                if (data.stats) {
                    this.app.updatePDFStats(data.stats);
                }
                
                console.log(`📚 ${data.documents.length} PDF yüklendi`);
            } else {
                throw new Error(data.message || 'PDF listesi alınamadı');
            }
            
        } catch (error) {
            console.error('❌ PDF list loading error:', error);
            this.renderErrorPDFList(error.message);
        }
    }

    renderPDFList(documents) {
        if (!this.pdfList) return;

        if (documents.length === 0) {
            this.renderEmptyPDFList();
            return;
        }

        this.pdfList.innerHTML = documents.map(doc => this.renderPDFItem(doc)).join('');
    }

    renderPDFItem(doc) {
        const uploadDate = new Date(doc.upload_date);
        const timeAgo = this.getTimeAgo(uploadDate);
        
        return `
            <div class="pdf-item">
                <div class="pdf-icon">
                    <i class="fas fa-file-pdf"></i>
                </div>
                <div class="pdf-details">
                    <div class="pdf-name" title="${this.escapeHtml(doc.filename)}">
                        ${this.escapeHtml(this.truncateFilename(doc.filename))}
                    </div>
                    <div class="pdf-meta">
                        <span class="pdf-chunks">${doc.chunk_count} parça</span>
                        <span class="pdf-date">${timeAgo}</span>
                    </div>
                </div>
                <div class="pdf-actions">
                    <button class="delete-pdf-btn" data-hash="${doc.file_hash}" title="PDF'i Sil">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
    }

    renderEmptyPDFList() {
        if (this.pdfList) {
            this.pdfList.innerHTML = `
                <div class="empty-pdf-list">
                    <i class="fas fa-file-pdf"></i>
                    <p>Henüz PDF yok</p>
                    <small>PDF yüklemek için yukarıdaki butona tıklayın</small>
                </div>
            `;
        }
    }

    renderErrorPDFList(errorMessage) {
        if (this.pdfList) {
            this.pdfList.innerHTML = `
                <div class="pdf-error">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>PDF listesi yüklenemedi</p>
                    <small>${this.escapeHtml(errorMessage)}</small>
                </div>
            `;
        }
    }

    async deletePDF(fileHash) {
        if (!confirm('Bu PDF\'i silmek istediğinizden emin misiniz?')) {
            return;
        }

        try {
            const currentChatId = this.app.chatHistory.getCurrentChatId();
            if (!currentChatId) {
                throw new Error('Aktif sohbet bulunamadı');
            }

            const response = await fetch(`/chats/${currentChatId}/pdfs/${fileHash}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                // PDF listesini yenile
                this.loadPDFList();
                
                // Stats'i güncelle
                if (data.stats) {
                    this.app.updatePDFStats(data.stats);
                }
                
                this.showSuccessMessage('PDF başarıyla silindi');
                console.log('✅ PDF deleted:', fileHash);
            } else {
                throw new Error(data.message || 'PDF silinemedi');
            }

        } catch (error) {
            console.error('❌ PDF delete error:', error);
            this.showErrorMessage(`PDF silme hatası: ${error.message}`);
        }
    }

    // Utility Methods
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    truncateFilename(filename, maxLength = 25) {
        if (filename.length <= maxLength) return filename;
        const extension = filename.split('.').pop();
        const nameWithoutExtension = filename.substring(0, filename.lastIndexOf('.'));
        const truncatedName = nameWithoutExtension.substring(0, maxLength - extension.length - 4) + '...';
        return truncatedName + '.' + extension;
    }

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

    showSuccessMessage(message) {
        console.log('✅', message);
        // Gelecekte toast notification eklenebilir
        this.showToast(message, 'success');
    }

    showErrorMessage(message) {
        console.error('❌', message);
        // Gelecekte toast notification eklenebilir
        this.showToast(message, 'error');
    }

    showToast(message, type = 'info') {
        // Basit toast notification
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${this.escapeHtml(message)}</span>
        `;
        
        document.body.appendChild(toast);
        
        // Animation
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Auto remove
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => document.body.removeChild(toast), 300);
        }, 3000);
    }

    // Public methods
    refreshPDFList() {
        this.loadPDFList();
    }

    getCurrentPDFCount() {
        return this.app.pdfState.totalDocuments;
    }

    isUploadInProgress() {
        return this.isUploading;
    }
}

export default PDFManager;