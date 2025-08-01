// static/js/core/DocumentManager.js

export class DocumentManager {
    constructor() {
        this.documents = [];
    }

    async uploadFiles(chatId, files) {
        const formData = new FormData();
        
        Array.from(files).forEach(file => {
            formData.append('files', file);
        });

        try {
            const response = await fetch(`/api/chats/${chatId}/documents`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Dosya yükleme başarısız');
            }

            const data = await response.json();
            
            // UI'ya başarı mesajı göster
            this.showUploadSuccess(data.uploaded_files.length);
            
            // Döküman listesini yenile
            await this.loadDocuments(chatId);
            
            return data.uploaded_files;
        } catch (error) {
            console.error('Dosya yükleme hatası:', error);
            this.showUploadError(error.message);
            throw error;
        }
    }

    async loadDocuments(chatId) {
        try {
            const response = await fetch(`/api/chats/${chatId}/documents`);
            const data = await response.json();
            this.documents = data.documents;
            this.renderDocuments(data.documents);
            return data.documents;
        } catch (error) {
            console.error('Dökümanlar yüklenemedi:', error);
            return [];
        }
    }

    renderDocuments(documents) {
        const documentsList = document.getElementById('documentsList');
        const documentsItems = document.getElementById('documentsItems');
        
        if (documents.length === 0) {
            documentsList.style.display = 'none';
            return;
        }

        documentsList.style.display = 'block';
        documentsItems.innerHTML = '';

        documents.forEach(doc => {
            const docElement = document.createElement('div');
            docElement.className = 'document-item';
            docElement.innerHTML = `
                <div class="document-info">
                    <div class="document-icon">
                        <i class="fas ${this.getFileIcon(doc.file_type)}"></i>
                    </div>
                    <div class="document-details">
                        <div class="document-name">${doc.original_filename}</div>
                        <div class="document-meta">
                            ${this.formatFileSize(doc.file_size)} • ${this.formatDate(doc.uploaded_at)}
                        </div>
                    </div>
                </div>
                <div class="document-actions">
                    <button class="doc-action-btn" onclick="documentManager.deleteDocument(${doc.id})" title="Sil">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
            documentsItems.appendChild(docElement);
        });

        // Döküman listesini toggle etme
        document.getElementById('toggleDocs').onclick = () => {
            const isVisible = documentsItems.style.display !== 'none';
            documentsItems.style.display = isVisible ? 'none' : 'block';
            document.querySelector('#toggleDocs i').className = isVisible ? 'fas fa-eye' : 'fas fa-eye-slash';
        };
    }

    async deleteDocument(docId) {
        if (!confirm('Bu dökümanı silmek istediğinizden emin misiniz?')) {
            return;
        }

        try {
            const response = await fetch(`/api/documents/${docId}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                throw new Error('Döküman silinemedi');
            }

            // UI'dan kaldır
            this.documents = this.documents.filter(doc => doc.id !== docId);
            this.renderDocuments(this.documents);
            
            this.showDeleteSuccess();
        } catch (error) {
            console.error('Döküman silme hatası:', error);
            this.showDeleteError(error.message);
        }
    }

    getFileIcon(fileType) {
        const iconMap = {
            'application/pdf': 'fa-file-pdf',
            'text/plain': 'fa-file-text',
            'application/msword': 'fa-file-word',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'fa-file-word'
        };
        return iconMap[fileType] || 'fa-file';
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('tr-TR', {
            day: 'numeric',
            month: 'short',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    showUploadSuccess(count) {
        // Toast notification göster
        this.showToast(`${count} dosya başarıyla yüklendi!`, 'success');
    }

    showUploadError(message) {
        this.showToast(`Yükleme hatası: ${message}`, 'error');
    }

    showDeleteSuccess() {
        this.showToast('Döküman silindi', 'success');
    }

    showDeleteError(message) {
        this.showToast(`Silme hatası: ${message}`, 'error');
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 10000;
            animation: slideInRight 0.3s ease;
        `;

        if (type === 'success') toast.style.backgroundColor = '#10b981';
        else if (type === 'error') toast.style.backgroundColor = '#ef4444';
        else toast.style.backgroundColor = '#6b7280';

        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => document.body.removeChild(toast), 300);
        }, 3000);
    }
}

// Global instance for onclick handlers
window.documentManager = new DocumentManager();