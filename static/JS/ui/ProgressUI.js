// static/js/ui/ProgressUI.js
import { DOM } from './DOM.js';

export class ProgressUI {
    constructor() {
        this.mainSteps = [];
        this.subTopics = [];
        this.completedTopics = {};
        this.expandedTopics = new Set();
        this.currentResearchData = null;
    }
    
    // Ana Araştırma Adımlarını oluşturur
    createMainStepsUI(steps) {
        this.mainSteps = steps;
        const stepsContainer = document.createElement('div');
        stepsContainer.className = 'research-steps-container';
        stepsContainer.id = 'mainStepsContainer';
        
        stepsContainer.innerHTML = `
            <div class="steps-header">
                <div class="steps-title"><i class="fas fa-cogs"></i><span>CrewAI Araştırma Süreci</span></div>
                <div class="steps-status">Başlatılıyor...</div>
            </div>
            <div class="steps-list"></div>
        `;

        const stepsList = stepsContainer.querySelector('.steps-list');
        steps.forEach((step, index) => {
            const stepElement = document.createElement('div');
            stepElement.className = 'step-item pending';
            stepElement.id = `main-step-${step.id}`;
            stepElement.innerHTML = `
                <div class="step-indicator">
                    <div class="step-number">${index + 1}</div>
                    <div class="step-status-icon">
                        <i class="fas fa-circle pending-icon"></i>
                        <i class="fas fa-spinner fa-spin spinning-icon" style="display: none;"></i>
                        <i class="fas fa-check completed-icon" style="display: none;"></i>
                    </div>
                </div>
                <div class="step-content">
                    <div class="step-title">${step.title}</div>
                    <div class="step-agent">Agent: ${step.agent}</div>
                    <div class="step-status">Bekliyor...</div>
                    <div class="step-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: 0%"></div>
                        </div>
                    </div>
                </div>
            `;
            stepsList.appendChild(stepElement);
        });
        
        DOM.messagesContainer.appendChild(stepsContainer);
        this.scrollToBottom();
    }

    updateMainStepStatus(stepId, status, message = null) {
        const stepElement = document.getElementById(`main-step-${stepId}`);
        if (!stepElement) return;

        const icons = {
            pending: stepElement.querySelector('.pending-icon'),
            running: stepElement.querySelector('.spinning-icon'),
            completed: stepElement.querySelector('.completed-icon')
        };
        const statusText = stepElement.querySelector('.step-status');
        const progressFill = stepElement.querySelector('.progress-fill');
        const stepsStatus = document.querySelector('.steps-status');
        
        // Tüm iconları gizle
        Object.values(icons).forEach(icon => icon.style.display = 'none');
        stepElement.classList.remove('pending', 'running', 'completed');

        if (status === 'running') {
            icons.running.style.display = 'inline-block';
            statusText.textContent = message || 'İşlem devam ediyor...';
            stepElement.classList.add('running');
            progressFill.style.width = '50%';
            if (stepsStatus) stepsStatus.textContent = 'Araştırma devam ediyor...';
        } else if (status === 'completed') {
            icons.completed.style.display = 'inline-block';
            statusText.textContent = message || 'Tamamlandı ✓';
            stepElement.classList.add('completed');
            progressFill.style.width = '100%';
        } else {
            icons.pending.style.display = 'inline-block';
            statusText.textContent = message || 'Bekliyor...';
            stepElement.classList.add('pending');
            progressFill.style.width = '0%';
        }
    }

    // Workflow mesajlarını işler
    handleWorkflowMessage(agent, message) {
        console.log(`📡 Workflow Message: ${agent} -> ${message}`);
        
        // Agent'e göre step ID'sini belirle
        const agentStepMap = {
            'WebResearcher': 'web-research',
            'YouTubeAnalyst': 'youtube-analysis',
            'ReportProcessor': 'report-structure',
            'DetailResearcher': 'detail-research',
            'CrewAI-Manager': 'manager'
        };
        
        const stepId = agentStepMap[agent];
        if (!stepId) return;

        if (message.includes('başlatılıyor') || message.includes('başlat')) {
            this.updateMainStepStatus(stepId, 'running', message);
        } else if (message.includes('tamamland') || message.includes('✅')) {
            this.updateMainStepStatus(stepId, 'completed', message);
        }
    }

    // Alt Başlık UI'ını yönetir
    initializeSubTopics(subtopics) {
        // Varsa eski waiting elementini kaldır
        const waitingElement = document.getElementById('waitingSubTopics');
        if (waitingElement) waitingElement.remove();

        console.log('📋 Subtopics alındı:', subtopics);

        this.subTopics = subtopics.map((topic, index) => ({
            id: `subtopic-${index}`,
            title: typeof topic === 'string' ? topic : (topic.alt_baslik || topic.title || `Konu ${index + 1}`),
            status: 'pending',
            content: ''
        }));
        
        this.createSubTopicsUI();
        this.scrollToBottom();
    }

    createSubTopicsUI() {
        const container = document.createElement('div');
        container.className = 'subtopics-container';
        container.id = 'subTopicsContainer';
        container.innerHTML = `
            <div class="subtopics-header">
                <div class="subtopics-title">
                    <i class="fas fa-list-ul"></i>
                    <span>Detay Araştırma Konuları (${this.subTopics.length})</span>
                </div>
                <div class="subtopics-progress">
                    <span class="progress-text">0/${this.subTopics.length} tamamlandı</span>
                    <div class="overall-progress-bar">
                        <div class="overall-progress-fill" style="width: 0%"></div>
                    </div>
                </div>
            </div>
            <div class="subtopics-list"></div>
        `;
        
        const list = container.querySelector('.subtopics-list');
        this.subTopics.forEach((topic, index) => {
            const topicElement = this.createSubTopicElement(topic, index);
            list.appendChild(topicElement);
        });
        
        DOM.messagesContainer.appendChild(container);
    }
    
    createSubTopicElement(topic, index) {
        const topicElement = document.createElement('div');
        topicElement.className = 'subtopic-item pending';
        topicElement.id = `subtopic-${topic.id}`;
        
        topicElement.innerHTML = `
            <div class="subtopic-main-row">
                <div class="subtopic-indicator">
                    <div class="subtopic-number">${index + 1}</div>
                    <div class="subtopic-status-icon">
                        <i class="fas fa-circle pending-icon"></i>
                        <i class="fas fa-spinner fa-spin spinning-icon" style="display: none;"></i>
                        <i class="fas fa-check completed-icon" style="display: none;"></i>
                    </div>
                </div>
                <div class="subtopic-content">
                    <div class="subtopic-title">${topic.title}</div>
                    <div class="subtopic-status">Sırada bekliyor...</div>
                    <div class="subtopic-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: 0%"></div>
                        </div>
                    </div>
                </div>
                <div class="expand-icon"><i class="fas fa-chevron-down"></i></div>
            </div>
            <div class="subtopic-details" style="display: none;">
                <div class="subtopic-content-text">İçerik henüz hazırlanmadı...</div>
                <div class="subtopic-timestamp"></div>
            </div>
        `;
        
        // Click handler'ı sadece completed durumda aktif olacak
        const mainRow = topicElement.querySelector('.subtopic-main-row');
        mainRow.addEventListener('click', () => {
            if (topic.status === 'completed') {
                this.toggleSubTopicDetails(topic.id);
            }
        });
        
        return topicElement;
    }

    updateSubTopicStatus(topicTitle, status, content = '') {
        console.log(`🔄 Subtopic güncelleniyor: ${topicTitle} -> ${status}`);
        
        const topic = this.subTopics.find(t => t.title === topicTitle);
        if (!topic) {
            console.warn(`⚠️ Subtopic bulunamadı: ${topicTitle}`);
            return;
        }

        topic.status = status;
        if (content) topic.content = content;

        const topicElement = document.getElementById(`subtopic-${topic.id}`);
        if (!topicElement) {
            console.warn(`⚠️ Subtopic element bulunamadı: subtopic-${topic.id}`);
            return;
        }

        const icons = {
            pending: topicElement.querySelector('.pending-icon'),
            running: topicElement.querySelector('.spinning-icon'),
            completed: topicElement.querySelector('.completed-icon')
        };
        const statusText = topicElement.querySelector('.subtopic-status');
        const headerRow = topicElement.querySelector('.subtopic-main-row');
        const progressFill = topicElement.querySelector('.progress-fill');

        // Tüm iconları gizle ve class'ları temizle
        Object.values(icons).forEach(icon => icon.style.display = 'none');
        topicElement.classList.remove('pending', 'running', 'completed', 'clickable');
        
        if (status === 'running') {
            icons.running.style.display = 'inline-block';
            statusText.textContent = 'Araştırılıyor...';
            topicElement.classList.add('running');
            progressFill.style.width = '50%';
            headerRow.style.cursor = 'default';
        } else if (status === 'completed') {
            icons.completed.style.display = 'inline-block';
            statusText.textContent = 'Tamamlandı - Detaylar için tıkla';
            topicElement.classList.add('completed', 'clickable');
            headerRow.style.cursor = 'pointer';
            progressFill.style.width = '100%';
            
            // Timestamp ekle
            const timestampDiv = topicElement.querySelector('.subtopic-timestamp');
            if (timestampDiv) {
                timestampDiv.textContent = `Tamamlandı: ${new Date().toLocaleTimeString()}`;
            }
        } else {
            icons.pending.style.display = 'inline-block';
            statusText.textContent = 'Sırada bekliyor...';
            topicElement.classList.add('pending');
            progressFill.style.width = '0%';
            headerRow.style.cursor = 'default';
        }
        
        // Genel progress'i güncelle
        this.updateOverallProgress();
    }

    updateOverallProgress() {
        const completedCount = this.subTopics.filter(t => t.status === 'completed').length;
        const totalCount = this.subTopics.length;
        const percentage = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;
        
        const progressText = document.querySelector('.progress-text');
        const progressFill = document.querySelector('.overall-progress-fill');
        
        if (progressText) {
            progressText.textContent = `${completedCount}/${totalCount} tamamlandı`;
        }
        
        if (progressFill) {
            progressFill.style.width = `${percentage}%`;
        }
        
        // Tüm konular tamamlandıysa rapor butonunu göster
        if (completedCount === totalCount && totalCount > 0) {
            setTimeout(() => this.showViewReportButton(), 1000);
        }
    }

    toggleSubTopicDetails(topicId) {
        const topic = this.subTopics.find(t => t.id === topicId);
        if (!topic || topic.status !== 'completed') return;

        const topicElement = document.getElementById(`subtopic-${topicId}`);
        const detailsDiv = topicElement.querySelector('.subtopic-details');
        const expandIcon = topicElement.querySelector('.expand-icon i');

        if (this.expandedTopics.has(topicId)) {
            // Kapat
            detailsDiv.style.display = 'none';
            expandIcon.className = 'fas fa-chevron-down';
            this.expandedTopics.delete(topicId);
            topicElement.classList.remove('expanded');
        } else {
            // Aç
            const contentText = topicElement.querySelector('.subtopic-content-text');
            contentText.innerHTML = this.formatContent(topic.content);
            detailsDiv.style.display = 'block';
            expandIcon.className = 'fas fa-chevron-up';
            this.expandedTopics.add(topicId);
            topicElement.classList.add('expanded');
            
            // Açılan bölüme scroll
            setTimeout(() => {
                detailsDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }, 100);
        }
    }

    // Rapor ve içerik formatlama
    showViewReportButton() {
        if (document.getElementById('viewReportButton')) return;
        
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'view-report-container';
        buttonContainer.innerHTML = `
            <div class="report-ready-message">
                <i class="fas fa-check-circle"></i>
                <span>🎉 Araştırma raporu hazır!</span>
            </div>
            <div class="report-buttons">
                <button class="view-report-btn" id="viewReportButton">
                    <i class="fas fa-external-link-alt"></i>
                    Detaylı Raporu Görüntüle
                </button>
                <button class="download-pdf-btn" id="downloadPdfButton">
                    <i class="fas fa-file-pdf"></i>
                    PDF İndir
                </button>
            </div>
            <div class="report-stats">
                <span>📊 ${this.subTopics.length} konu detaylandırıldı</span>
                <span>⏰ ${new Date().toLocaleTimeString()} tarihinde tamamlandı</span>
            </div>
        `;
        
        // Event listeners
        const viewButton = buttonContainer.querySelector('#viewReportButton');
        const pdfButton = buttonContainer.querySelector('#downloadPdfButton');
        
        viewButton.addEventListener('click', () => this.openDetailedReport());
        pdfButton.addEventListener('click', () => this.downloadPDF());
        
        DOM.messagesContainer.appendChild(buttonContainer);
        this.scrollToBottom();
        
        // Button animasyonu
        setTimeout(() => buttonContainer.classList.add('animate-in'), 100);
    }

    // Detaylı raporu yeni sekmede açar
    openDetailedReport() {
        console.log("🔍 Rapor görüntüleme talep edildi");
        
        if (!this.subTopics || this.subTopics.length === 0) {
            alert('Henüz görüntülenecek rapor verisi yok.');
            return;
        }

        // Yeni pencere aç
        const reportWindow = window.open('', '_blank', 'width=1200,height=800,scrollbars=yes');
        
        if (!reportWindow) {
            alert('Pop-up engelleyici aktif olabilir. Lütfen pop-up\'lara izin verin.');
            return;
        }

        // Rapor HTML'ini oluştur
        const reportHTML = this.generateReportHTML();
        
        reportWindow.document.write(reportHTML);
        reportWindow.document.close();
    }

    // PDF indirme fonksiyonu - Gelişmiş ve düzenli format
    async downloadPDF() {
        console.log("📄 PDF indirme talep edildi");
        
        if (!this.subTopics || this.subTopics.length === 0) {
            alert('Henüz indirilecek rapor verisi yok.');
            return;
        }

        try {
            // PDF butonuna loading efekti ekle
            const pdfButton = document.getElementById('downloadPdfButton');
            if (pdfButton) {
                pdfButton.classList.add('loading');
                pdfButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> PDF Hazırlanıyor...';
            }

            // jsPDF kütüphanesini dinamik olarak yükle
            if (!window.jsPDF) {
                await this.loadScript('https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js');
            }

            const { jsPDF } = window.jspdf;
            const doc = new jsPDF('p', 'mm', 'a4');
            
            // PDF içeriğini oluştur
            this.generatePDFContentImproved(doc);
            
            // PDF'i indir
            const fileName = `arastirma-raporu-${new Date().toISOString().slice(0, 10)}.pdf`;
            doc.save(fileName);
            
            // Buton durumunu sıfırla
            if (pdfButton) {
                pdfButton.classList.remove('loading');
                pdfButton.innerHTML = '<i class="fas fa-file-pdf"></i> PDF İndir';
            }
            
        } catch (error) {
            console.error('PDF oluşturma hatası:', error);
            alert('PDF oluşturulurken bir hata oluştu. Lütfen tekrar deneyin.');
            
            // Hata durumunda buton durumunu sıfırla
            const pdfButton = document.getElementById('downloadPdfButton');
            if (pdfButton) {
                pdfButton.classList.remove('loading');
                pdfButton.innerHTML = '<i class="fas fa-file-pdf"></i> PDF İndir';
            }
        }
    }

    // Script dinamik yükleme yardımcı fonksiyonu
    loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    // HTML rapor oluşturma
    generateReportHTML() {
        const completedTopics = this.subTopics.filter(t => t.status === 'completed');
        const reportDate = new Date().toLocaleDateString('tr-TR');
        const reportTime = new Date().toLocaleTimeString('tr-TR');

        return `
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Araştırma Raporu - ${reportDate}</title>
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }
                .container {
                    max-width: 900px;
                    margin: 0 auto;
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                }
                .header {
                    text-align: center;
                    border-bottom: 3px solid #2196F3;
                    padding-bottom: 20px;
                    margin-bottom: 30px;
                }
                .header h1 {
                    color: #1976D2;
                    margin: 0;
                    font-size: 2.5em;
                }
                .header .date {
                    color: #666;
                    font-size: 1.1em;
                    margin-top: 10px;
                }
                .summary {
                    background: #E3F2FD;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 30px;
                    border-left: 4px solid #2196F3;
                }
                .topic {
                    margin-bottom: 40px;
                    padding: 25px;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    background: #fafafa;
                }
                .topic h2 {
                    color: #1976D2;
                    border-bottom: 2px solid #2196F3;
                    padding-bottom: 10px;
                    margin-top: 0;
                }
                .topic-content {
                    background: white;
                    padding: 20px;
                    border-radius: 6px;
                    margin-top: 15px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                .topic-number {
                    background: #2196F3;
                    color: white;
                    padding: 5px 12px;
                    border-radius: 20px;
                    font-weight: bold;
                    font-size: 0.9em;
                    display: inline-block;
                    margin-bottom: 10px;
                }
                .footer {
                    text-align: center;
                    margin-top: 50px;
                    padding-top: 20px;
                    border-top: 1px solid #e0e0e0;
                    color: #666;
                }
                @media print {
                    body { background: white; }
                    .container { box-shadow: none; }
                    .topic { break-inside: avoid; }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔍 Araştırma Raporu</h1>
                    <div class="date">${reportDate} - ${reportTime}</div>
                </div>
                
                <div class="summary">
                    <h3>📊 Rapor Özeti</h3>
                    <p><strong>Toplam Konu:</strong> ${completedTopics.length}</p>
                    <p><strong>Araştırma Tarihi:</strong> ${reportDate}</p>
                    <p><strong>Durum:</strong> ✅ Tamamlandı</p>
                </div>

                ${completedTopics.map((topic, index) => `
                    <div class="topic">
                        <span class="topic-number">Konu ${index + 1}</span>
                        <h2>${topic.title}</h2>
                        <div class="topic-content">
                            ${this.formatContent(topic.content)}
                        </div>
                    </div>
                `).join('')}

                <div class="footer">
                    <p>Bu rapor CrewAI tarafından otomatik olarak oluşturulmuştur.</p>
                    <p>Oluşturulma Zamanı: ${reportDate} ${reportTime}</p>
                </div>
            </div>
        </body>
        </html>
        `;
    }

    // Gelişmiş PDF içerik oluşturma - Türkçe destekli ve düzenli
    generatePDFContentImproved(doc) {
        const completedTopics = this.subTopics.filter(t => t.status === 'completed');
        const pageWidth = doc.internal.pageSize.width;
        const pageHeight = doc.internal.pageSize.height;
        const margin = 20;
        const contentWidth = pageWidth - 2 * margin;
        let yPosition = margin;

        // UTF-8 desteği için font ayarı
        doc.addFont('https://fonts.gstatic.com/s/opensans/v18/mem8YaGs126MiZpBA-UFVZ0bf8pkAg.ttf', 'OpenSans', 'normal');
        doc.setFont('helvetica');

        // Başlık sayfası
        this.addPDFHeader(doc, margin, yPosition, contentWidth);
        yPosition += 40;

        // Özet kutusu
        yPosition = this.addPDFSummary(doc, margin, yPosition, contentWidth, completedTopics.length);
        yPosition += 20;

        // İçindekiler
        yPosition = this.addPDFTableOfContents(doc, margin, yPosition, contentWidth, completedTopics);
        
        // Yeni sayfa
        doc.addPage();
        yPosition = margin;

        // Ana içerik
        completedTopics.forEach((topic, index) => {
            yPosition = this.addPDFTopic(doc, topic, index + 1, margin, yPosition, contentWidth, pageHeight);
        });

        // Footer ekleme
        this.addPDFFooters(doc);
    }

    // PDF başlık ekleme
    addPDFHeader(doc, margin, yPosition, contentWidth) {
        const date = new Date().toLocaleDateString('tr-TR');
        const time = new Date().toLocaleTimeString('tr-TR');
        
        // Ana başlık
        doc.setFontSize(28);
        doc.setFont('helvetica', 'bold');
        doc.text('ARAŞTIRMA RAPORU', pageWidth/2, yPosition, { align: 'center' });
        
        // Alt çizgi
        doc.setLineWidth(1);
        doc.line(margin, yPosition + 5, pageWidth - margin, yPosition + 5);
        
        // Tarih bilgisi
        doc.setFontSize(12);
        doc.setFont('helvetica', 'normal');
        doc.text(`${date} - ${time}`, pageWidth/2, yPosition + 15, { align: 'center' });
    }

    // PDF özet kutusu
    addPDFSummary(doc, margin, yPosition, contentWidth, topicCount) {
        // Özet kutusu arka planı
        doc.setFillColor(240, 248, 255);
        doc.roundedRect(margin, yPosition, contentWidth, 35, 3, 3, 'F');
        
        // Özet başlığı
        doc.setFontSize(16);
        doc.setFont('helvetica', 'bold');
        doc.text('RAPOR ÖZETİ', margin + 10, yPosition + 12);
        
        // Özet içeriği
        doc.setFontSize(11);
        doc.setFont('helvetica', 'normal');
        doc.text(`• Toplam Konu: ${topicCount}`, margin + 10, yPosition + 22);
        doc.text(`• Araştırma Tarihi: ${new Date().toLocaleDateString('tr-TR')}`, margin + 10, yPosition + 28);
        doc.text(`• Durum: Tamamlandı`, margin + 10, yPosition + 34);
        
        return yPosition + 35;
    }

    // PDF içindekiler
    addPDFTableOfContents(doc, margin, yPosition, contentWidth, topics) {
        doc.setFontSize(16);
        doc.setFont('helvetica', 'bold');
        doc.text('İÇİNDEKİLER', margin, yPosition);
        yPosition += 15;
        
        doc.setFontSize(11);
        doc.setFont('helvetica', 'normal');
        
        topics.forEach((topic, index) => {
            const topicNumber = index + 1;
            const title = this.truncateText(topic.title, 60);
            doc.text(`${topicNumber}. ${title}`, margin + 5, yPosition);
            yPosition += 6;
        });
        
        return yPosition;
    }

    // PDF konu ekleme
    addPDFTopic(doc, topic, topicNumber, margin, yPosition, contentWidth, pageHeight) {
        // Sayfa kontrolü
        if (yPosition > pageHeight - 80) {
            doc.addPage();
            yPosition = margin;
        }

        // Konu başlığı kutusu
        doc.setFillColor(33, 150, 243);
        doc.roundedRect(margin, yPosition, contentWidth, 12, 2, 2, 'F');
        
        // Konu numarası ve başlığı
        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(255, 255, 255);
        doc.text(`${topicNumber}. ${this.truncateText(topic.title, 50)}`, margin + 5, yPosition + 8);
        
        yPosition += 20;

        // İçerik
        doc.setTextColor(0, 0, 0);
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        
        // HTML taglerini temizle ve düzenle
        const cleanContent = this.cleanContentForPDF(topic.content);
        const lines = doc.splitTextToSize(cleanContent, contentWidth - 10);
        
        lines.forEach(line => {
            if (yPosition > pageHeight - 20) {
                doc.addPage();
                yPosition = margin;
            }
            doc.text(line, margin + 5, yPosition);
            yPosition += 5;
        });
        
        yPosition += 15; // Konular arası boşluk
        
        // Ayırıcı çizgi
        doc.setLineWidth(0.3);
        doc.setDrawColor(200, 200, 200);
        doc.line(margin, yPosition - 10, pageWidth - margin, yPosition - 10);
        
        return yPosition;
    }

    // PDF footer ekleme
    addPDFFooters(doc) {
        const totalPages = doc.internal.getNumberOfPages();
        const pageWidth = doc.internal.pageSize.width;
        const pageHeight = doc.internal.pageSize.height;
        
        for (let i = 1; i <= totalPages; i++) {
            doc.setPage(i);
            doc.setFontSize(9);
            doc.setFont('helvetica', 'normal');
            doc.setTextColor(128, 128, 128);
            
            // Sayfa numarası
            doc.text(`Sayfa ${i} / ${totalPages}`, 
                pageWidth - 30, 
                pageHeight - 10, 
                { align: 'center' }
            );
            
            // Alt çizgi
            doc.setLineWidth(0.3);
            doc.setDrawColor(200, 200, 200);
            doc.line(20, pageHeight - 15, pageWidth - 20, pageHeight - 15);
            
            // Footer metni
            doc.text('Bu rapor CrewAI tarafından otomatik olarak oluşturulmuştur.', 
                pageWidth/2, 
                pageHeight - 5, 
                { align: 'center' }
            );
        }
    }

    // PDF için içerik temizleme
    cleanContentForPDF(content) {
        if (!content || typeof content !== 'string') return 'İçerik mevcut değil.';
        
        return content
            // HTML taglerini kaldır
            .replace(/<[^>]*>/g, '')
            // HTML entity'lerini dönüştür
            .replace(/&nbsp;/g, ' ')
            .replace(/&amp;/g, '&')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&quot;/g, '"')
            .replace(/&#39;/g, "'")
            // Çoklu boşlukları tek boşluğa çevir
            .replace(/\s+/g, ' ')
            // Başlangıç ve bitiş boşluklarını kaldır
            .trim()
            // Markdown işaretlerini temizle
            .replace(/\*\*(.*?)\*\*/g, '$1')
            .replace(/\*(.*?)\*/g, '$1')
            .replace(/`(.*?)`/g, '$1')
            // Satır sonlarını düzenle
            .replace(/\n\s*\n/g, '\n\n')
            .replace(/\n/g, ' ');
    }

    // Metin kısaltma yardımcı fonksiyonu
    truncateText(text, maxLength) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength - 3) + '...';
    }

    // HTML taglerini temizleme yardımcı fonksiyonu
    stripHtmlTags(html) {
        const tmp = document.createElement('div');
        tmp.innerHTML = html;
        return tmp.textContent || tmp.innerText || '';
    }
    
    // Araştırma verilerini kaydet
    setResearchData(data) {
        this.currentResearchData = data;
    }
    
    formatContent(content) {
        if (!content || typeof content !== 'string') return '<p>İçerik mevcut değil.</p>';
        
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^(.*)$/, '<p>$1</p>');
    }
    
    // Utility functions
    scrollToBottom() {
        setTimeout(() => {
            DOM.messagesContainer.scrollTop = DOM.messagesContainer.scrollHeight;
        }, 100);
    }
    
    // Temizlik fonksiyonu
    cleanup() {
        const containers = ['mainStepsContainer', 'subTopicsContainer', 'viewReportButton'];
        containers.forEach(id => {
            const element = document.getElementById(id);
            if (element) element.remove();
        });
        
        this.mainSteps = [];
        this.subTopics = [];
        this.completedTopics = {};
        this.expandedTopics.clear();
        this.currentResearchData = null;
    }
    
    // Debugging için
    getStatus() {
        return {
            mainSteps: this.mainSteps.length,
            subTopics: this.subTopics.length,
            completed: this.subTopics.filter(t => t.status === 'completed').length,
            expanded: this.expandedTopics.size,
            hasResearchData: !!this.currentResearchData
        };
    }
}