// static/js/pdf-manager.js
// PDF yönetimi için gerekli fonksiyonlar

class PDFManager {
    constructor(app) {
        this.app = app; 
        this.isUploading = false;
        this.currentUpload = null;
        this.initializeEventListeners();
        this.loadPDFList();
    }

    initializeEventListeners() {
        // PDF file input change event
        const fileInput = document.getElementById('pdfFileInput');
        if (fileInput) {
            fileInput.addEventListener('change', this.handlePdfUpload.bind(this));
        }
    }

    async handlePdfUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        // Dosya doğrulama
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            this.showError('Sadece PDF dosyaları desteklenir.');
            return;
        }

        // Boyut kontrolü (50MB)
        const maxSize = 50 * 1024 * 1024;
        if (file.size > maxSize) {
            this.showError('Dosya boyutu 50MB\'tan büyük olamaz.');
            return;
        }

        // Upload sürecini başlat
        await this.uploadPDF(file);
        
        // Input'u temizle
        event.target.value = '';
    }

    async uploadPDF(file) {
        if (this.isUploading) {
            this.showError('Zaten bir dosya yükleniyor.');
            return;
        }

        this.isUploading = true;
        this.showUploadModal(file);

        try {
            const formData = new FormData();
            formData.append('file', file);

            // Progress göstergesi için XMLHttpRequest kullan
            const response = await this.uploadWithProgress(formData, file);

            if (response.success) {
                this.showUploadSuccess(response);
                await this.loadPDFList();
                
                // WebSocket üzerinden bildir
                if (window.app && window.app.ws) {
                    window.app.ws.send({
                        type: 'pdf_uploaded',
                        filename: response.filename,
                        stats: response.stats
                    });
                }
                
                // App'e PDF stats'ını güncelle
                if (window.app && response.stats) {
                    window.app.updatePDFStats(response.stats);
                }
            } else {
                throw new Error(response.message || 'Upload failed');
            }

        } catch (error) {
            console.error('❌ PDF Upload Error:', error);
            this.showError(`Upload hatası: ${error.message}`);
        } finally {
            this.isUploading = false;
            setTimeout(() => {
                this.hideUploadModal();
            }, 2000);
        }
    }

    uploadWithProgress(formData, file) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();

            // Progress event
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    this.updateUploadProgress(percentComplete, 'Yükleniyor...', 'Uploading');
                }
            });

            // Load event
            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        this.updateUploadProgress(100, 'Vektörleştiriliyor...', 'Processing');
                        setTimeout(() => {
                            resolve(response);
                        }, 1000);
                    } catch (e) {
                        reject(new Error('Invalid response format'));
                    }
                } else {
                    try {
                        const errorResponse = JSON.parse(xhr.responseText);
                        reject(new Error(errorResponse.detail || 'Upload failed'));
                    } catch (e) {
                        reject(new Error(`HTTP ${xhr.status}: ${xhr.statusText}`));
                    }
                }
            });

            // Error event
            xhr.addEventListener('error', () => {
                reject(new Error('Network error during upload'));
            });

            // Start upload
            xhr.open('POST', '/upload-pdf');
            xhr.send(formData);
        });
    }

    showUploadModal(file) {
        const modal = document.getElementById('uploadModal');
        const filename = document.getElementById('uploadFilename');
        const fileSize = document.getElementById('fileSize');
        const status = document.getElementById('uploadStatus');
        const processStatus = document.getElementById('processStatus');

        if (modal && filename && fileSize && status && processStatus) {
            filename.textContent = file.name;
            fileSize.textContent = this.formatFileSize(file.size);
            status.textContent = 'Hazırlanıyor...';
            processStatus.textContent = 'Başlatılıyor';
            
            modal.style.display = 'flex';
            this.updateUploadProgress(0, 'Başlatılıyor...', 'Initializing');
        }
    }

    hideUploadModal() {
        const modal = document.getElementById('uploadModal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    updateUploadProgress(percentage, statusText, processText) {
        const progressFill = document.getElementById('progressFill');
        const uploadStatus = document.getElementById('uploadStatus');
        const processStatus = document.getElementById('processStatus');

        if (progressFill) {
            progressFill.style.width = `${percentage}%`;
        }
        
        if (uploadStatus) {
            uploadStatus.textContent = statusText;
        }
        
        if (processStatus) {
            processStatus.textContent = processText;
        }
    }

    

    async loadPDFList() {
        try {
            const response = await fetch('/list-pdfs');
            const data = await response.json();

            if (data.success) {
                this.displayPDFList(data.documents);
                this.updatePDFStats(data.stats);
            } else {
                console.error('❌ PDF list load failed:', data);
            }
        } catch (error) {
            console.error('❌ Error loading PDF list:', error);
        }
    }

    displayPDFList(documents) {
        const pdfList = document.getElementById('pdfList');
        if (!pdfList) return;

        if (!documents || documents.length === 0) {
            pdfList.innerHTML = '<div class="no-pdfs">Henüz PDF yüklenmemiş</div>';
            return;
        }

        const html = documents.map(doc => `
            <div class="pdf-item" data-hash="${doc.file_hash}">
                <div class="pdf-info">
                    <div class="pdf-name">
                        <i class="fas fa-file-pdf"></i>
                        <span title="${doc.filename}">${this.truncateFilename(doc.filename)}</span>
                    </div>
                    <div class="pdf-meta">
                        <small>${doc.chunk_count || 0} parça • ${this.formatDate(doc.upload_date)}</small>
                    </div>
                </div>
                <button class="delete-pdf-btn" onclick="pdfManager.deletePDF('${doc.file_hash}', '${doc.filename}')" title="PDF'i Sil">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `).join('');

        pdfList.innerHTML = html;
    }

    updatePDFStats(stats) {
        const totalPdfs = document.getElementById('totalPdfs');
        const totalChunks = document.getElementById('totalChunks');

        if (totalPdfs) totalPdfs.textContent = stats.total_documents || 0;
        if (totalChunks) totalChunks.textContent = stats.total_chunks || 0;
    }

    async deletePDF(fileHash, filename) {
        if (!confirm(`'${filename}' dosyasını silmek istediğinizden emin misiniz?`)) {
            return;
        }

        try {
            const response = await fetch(`/delete-pdf/${fileHash}`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                // UI'yi güncelle
                await this.loadPDFList();
                
                // App stats'ını güncelle
                if (window.app && data.stats) {
                    window.app.updatePDFStats(data.stats);
                }

                // Success message
                if (window.app && window.app.ui) {
                    window.app.ui.addMessage(`🗑️ '${filename}' başarıyla silindi.`, 'system');
                }
            } else {
                throw new Error(data.message || 'Delete failed');
            }
        } catch (error) {
            console.error('❌ PDF Delete Error:', error);
            this.showError(`Silme hatası: ${error.message}`);
        }
    }

    // Utility functions
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    formatDate(dateString) {
        if (!dateString) return 'Bilinmiyor';
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('tr-TR', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return 'Geçersiz tarih';
        }
    }
    // pdf-manager.js dosyasının içinde
    initializeEventListeners() {
        // PDF file input change event
        const fileInput = document.getElementById('pdfFileInput');
        if (fileInput) {
            // 'change' olayını dinle ve sınıfın kendi handlePdfUpload metodunu çağır
            fileInput.addEventListener('change', this.handlePdfUpload.bind(this));
        }
    }

    truncateFilename(filename, maxLength = 25) {
        if (filename.length <= maxLength) return filename;
        const extension = filename.split('.').pop();
        const nameWithoutExt = filename.substring(0, filename.lastIndexOf('.'));
        const truncated = nameWithoutExt.substring(0, maxLength - extension.length - 4) + '...';
        return truncated + '.' + extension;
    }

    // showError fonksiyonunu güncelleyin
    showError(message) {
        console.error('❌ PDF Manager Error:', message);
        if (this.app && this.app.ui) {
            this.app.ui.addMessage(`❌ ${message}`, 'system');
        } else {
            alert(message);
        }
    }

    // showUploadSuccess fonksiyonunu güncelleyin
    showUploadSuccess(response) {
        this.updateUploadProgress(100, '✅ Başarıyla tamamlandı!', 'Completed');
        if (this.app && this.app.ui) {
            this.app.ui.addMessage(
                `📚 '${response.filename}' başarıyla yüklendi ve vektörleştirildi. Artık bu doküman hakkında sorular sorabilirsiniz!`, 
                'system'
            );
        }
    }
}




export default PDFManager;