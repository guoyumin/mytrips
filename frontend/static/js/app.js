// MyTrips Email Import Application

class EmailImportApp {
    constructor() {
        this.isImporting = false;
        this.isClassifying = false;
        this.isExtracting = false;
        this.progressInterval = null;
        this.classificationInterval = null;
        this.extractionInterval = null;
        this.currentSection = 'welcome';
        this.init();
    }

    init() {
        console.log('MyTrips Email Import App initialized');
        
        // Force layout fix
        setTimeout(() => {
            const mainContent = document.querySelector('.main-content');
            if (mainContent) {
                console.log('Forcing layout fix');
                mainContent.style.display = 'flex';
                mainContent.style.flexDirection = 'row';
                mainContent.style.height = 'calc(100vh - 120px)';
            }
        }, 100);
        
        // Check initial cache stats
        this.loadCacheStats();
        // Initialize sidebar navigation
        this.initSidebar();
        // Show default section
        this.switchFunction('status');
    }

    initSidebar() {
        // Add click handlers for function groups
        document.querySelectorAll('.function-group').forEach(group => {
            group.addEventListener('click', (e) => {
                const functionName = group.dataset.function;
                this.switchFunction(functionName);
            });
        });
    }

    switchFunction(functionName) {
        // Update active state in sidebar
        document.querySelectorAll('.function-group').forEach(group => {
            group.classList.remove('active');
        });
        document.querySelector(`[data-function="${functionName}"]`).classList.add('active');

        // Hide all content sections
        this.hideAllSections();

        // Show relevant content
        switch(functionName) {
            case 'import':
                this.showImportSection();
                break;
            case 'classify':
                this.showClassifySection();
                break;
            case 'extract':
                this.showExtractSection();
                break;
            case 'travel':
                this.showTravelEmails();
                break;
            case 'status':
                this.showStatusSection();
                break;
        }
        
        this.currentSection = functionName;
    }

    hideAllSections() {
        document.getElementById('import-section').style.display = 'none';
        document.getElementById('classify-section').style.display = 'none';
        document.getElementById('extract-section').style.display = 'none';
        document.getElementById('travel-emails-section').style.display = 'none';
        document.getElementById('status-section').style.display = 'none';
        document.getElementById('progress-section').style.display = 'none';
        document.getElementById('stats').style.display = 'none';
    }

    showImportSection() {
        document.getElementById('import-section').style.display = 'block';
    }

    showClassifySection() {
        document.getElementById('classify-section').style.display = 'block';
    }

    showExtractSection() {
        document.getElementById('extract-section').style.display = 'block';
    }

    showTravelEmails() {
        document.getElementById('travel-emails-section').style.display = 'block';
        this.loadTravelEmails();
    }

    showStatusSection() {
        document.getElementById('status-section').style.display = 'block';
        this.loadStatusData();
    }

    async importEmails() {
        if (this.isImporting) {
            console.log('Import already in progress, ignoring click');
            return;
        }

        this.isImporting = true;
        this.updateUIForImporting(true);

        try {
            // Get selected time range
            const timeRange = document.getElementById('timeRange').value;
            const days = parseInt(timeRange);
            
            // Update status to show selected range
            this.displayStatus(`Starting import for ${this.getTimeRangeLabel(days)}...`, 'loading');
            
            // Start import
            const response = await fetch('/api/emails/import', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ days: days })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to start import');
            }

            if (!data.started) {
                // Check if it's because import is already running
                if (data.message && data.message.includes('already')) {
                    this.displayStatus('⚠️ ' + data.message, 'loading');
                    this.startProgressMonitoring(); // Monitor existing progress
                    return;
                } else {
                    throw new Error(data.message || 'Import failed to start');
                }
            }

            // Start progress monitoring - this will handle completion automatically
            this.startProgressMonitoring();

        } catch (error) {
            this.displayError(error.message);
            this.isImporting = false;
            this.updateUIForImporting(false);
            this.stopProgressMonitoring();
        }
    }

    async stopImport() {
        if (!this.isImporting) return;

        try {
            const response = await fetch('/api/emails/import/stop', {
                method: 'POST'
            });

            const data = await response.json();

            if (response.ok) {
                this.displayStatus('⏹️ Import stopped by user', 'status');
            }
        } catch (error) {
            console.error('Error stopping import:', error);
        }
    }

    async viewCacheStats() {
        try {
            const response = await fetch('/api/emails/cache/stats');
            const stats = await response.json();

            if (response.ok) {
                this.displayCacheStats(stats);
            } else {
                throw new Error('Failed to load cache stats');
            }
        } catch (error) {
            this.displayError('Failed to load cache statistics');
        }
    }

    async loadCacheStats() {
        try {
            const response = await fetch('/api/emails/cache/stats');
            const stats = await response.json();

            if (response.ok && stats.total_emails > 0) {
                document.getElementById('totalCached').textContent = stats.total_emails;
                
                if (stats.date_range) {
                    document.getElementById('dateRange').style.display = 'block';
                    document.getElementById('dateRangeText').textContent = 
                        `${stats.date_range.oldest} to ${stats.date_range.newest}`;
                }
            }
        } catch (error) {
            console.log('No existing cache found');
        }
    }

    startProgressMonitoring() {
        this.progressInterval = setInterval(async () => {
            await this.updateProgress();
        }, 1000);
    }

    stopProgressMonitoring() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
    }

    async updateProgress() {
        if (!this.isImporting) return;

        try {
            const response = await fetch('/api/emails/import/progress');
            const data = await response.json();

            if (response.ok) {
                this.displayProgress(data);
                
                // Check if finished
                if (data.finished) {
                    this.isImporting = false;
                    this.stopProgressMonitoring();
                    
                    if (data.final_results) {
                        this.displayResults(data.final_results);
                    }
                    
                    this.updateUIForImporting(false);
                }
            }
        } catch (error) {
            console.error('Progress update error:', error);
        }
    }

    async waitForCompletion() {
        return new Promise((resolve) => {
            const checkCompletion = async () => {
                try {
                    const response = await fetch('/api/emails/import/progress');
                    const data = await response.json();

                    if (data.finished) {
                        if (data.error) {
                            throw new Error(data.error);
                        }
                        resolve(data.final_results || null);
                        return;
                    }

                    // Continue checking if still importing
                    setTimeout(checkCompletion, 2000);
                } catch (error) {
                    this.displayError(error.message);
                    resolve(null);
                }
            };

            // Start checking immediately
            checkCompletion();
        });
    }

    updateUIForImporting(importing) {
        const importBtn = document.getElementById('importBtn');
        const stopBtn = document.getElementById('stopBtn');
        const progressSection = document.getElementById('progress-section');

        if (importing) {
            importBtn.disabled = true;
            importBtn.textContent = 'Importing...';
            stopBtn.style.display = 'inline-block';
            
            // Hide other sections and show progress
            this.hideAllSections();
            progressSection.style.display = 'block';
        } else {
            importBtn.disabled = false;
            importBtn.textContent = 'Import Emails';
            stopBtn.style.display = 'none';
            
            setTimeout(() => {
                if (this.currentSection === 'import') {
                    progressSection.style.display = 'none';
                    this.showImportSection();
                }
                document.getElementById('progressBar').style.width = '0%';
                document.getElementById('progressCount').textContent = '0/0';
            }, 2000);
        }
    }

    displayProgress(data) {
        const progressBar = document.getElementById('progressBar');
        const progressCount = document.getElementById('progressCount');
        const status = document.getElementById('status');

        if (data.progress !== undefined) {
            progressBar.style.width = data.progress + '%';
            progressCount.textContent = `${data.processed || 0}/${data.total || 0}`;
            
            this.displayStatus(
                `Processing emails... (${data.new_count || 0} new, ${data.skip_count || 0} skipped)`,
                'loading'
            );
        }
    }

    displayResults(results) {
        // Update stats
        document.getElementById('stats').style.display = 'grid';
        document.getElementById('newEmails').textContent = results.new_emails;
        document.getElementById('skippedEmails').textContent = results.skipped_emails;
        document.getElementById('totalCached').textContent = results.total_cached;

        // Update date range
        if (results.date_range) {
            document.getElementById('dateRange').style.display = 'block';
            document.getElementById('dateRangeText').textContent = 
                `${results.date_range.oldest} to ${results.date_range.newest}`;
        }

        // Update status
        this.displayStatus(
            `✅ Import completed! Imported ${results.new_emails} new emails, skipped ${results.skipped_emails} duplicates.`,
            'success'
        );

        // Update progress bar to 100%
        document.getElementById('progressBar').style.width = '100%';
    }

    displayCacheStats(stats) {
        alert(`Cache Statistics:\n\nTotal emails: ${stats.total_emails}\nClassified emails: ${stats.classified_emails}\nDate range: ${stats.date_range ? `${stats.date_range.oldest} to ${stats.date_range.newest}` : 'N/A'}`);
    }

    displayStatus(message, type = 'status') {
        const status = document.getElementById('status');
        status.style.display = 'block';
        status.className = `status ${type}`;
        status.innerHTML = message;
    }

    displayError(message) {
        this.displayStatus(`❌ Error: ${message}`, 'error');
    }
    
    getTimeRangeLabel(days) {
        const ranges = {
            1: 'last 1 day',
            3: 'last 3 days',
            10: 'last 10 days',
            30: 'last month',
            90: 'last 3 months', 
            180: 'last 6 months',
            365: 'last 1 year',
            730: 'last 2 years',
            1095: 'last 3 years'
        };
        return ranges[days] || `last ${days} days`;
    }

    // Classification methods
    async testClassification() {
        if (this.isClassifying) {
            console.log('Classification already in progress, ignoring click');
            return;
        }

        this.isClassifying = true;
        this.updateUIForClassification(true);

        try {
            const response = await fetch('/api/emails/classify/test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({})
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to start classification');
            }

            if (!data.started) {
                throw new Error(data.message || 'Classification failed to start');
            }

            this.displayStatus('🤖 Starting AI classification of emails...', 'loading');
            this.startClassificationMonitoring();

        } catch (error) {
            this.displayError(`Classification failed: ${error.message}`);
            this.isClassifying = false;
            this.updateUIForClassification(false);
        }
    }

    async stopClassification() {
        if (!this.isClassifying) return;

        try {
            const response = await fetch('/api/emails/classify/stop', {
                method: 'POST'
            });

            if (response.ok) {
                this.displayStatus('⏹️ Classification stopped by user', 'status');
                // Update UI immediately
                this.isClassifying = false;
                this.stopClassificationMonitoring();
                this.updateUIForClassification(false);
            }
        } catch (error) {
            console.error('Error stopping classification:', error);
        }
    }

    startClassificationMonitoring() {
        // Clear any existing global timer first
        if (window.globalClassificationInterval) {
            clearInterval(window.globalClassificationInterval);
        }
        
        window.globalClassificationInterval = setInterval(async () => {
            await this.updateClassificationProgress();
        }, 2000);
        this.classificationInterval = window.globalClassificationInterval;
    }

    stopClassificationMonitoring() {
        if (window.globalClassificationInterval) {
            clearInterval(window.globalClassificationInterval);
            window.globalClassificationInterval = null;
            this.classificationInterval = null;
        }
    }

    async updateClassificationProgress() {
        if (!this.isClassifying) {
            return;
        }

        try {
            const response = await fetch('/api/emails/classify/progress');
            const data = await response.json();

            if (response.ok) {
                this.displayClassificationProgress(data);
                
                if (data.finished) {
                    this.isClassifying = false;
                    this.stopClassificationMonitoring();
                    
                    // Display completion message
                    this.displayStatus(
                        `✅ ${data.message || 'Classification completed!'}`,
                        'success'
                    );
                    
                    this.updateUIForClassification(false);
                }
            }
        } catch (error) {
            console.error('Classification progress update error:', error);
        }
    }

    updateUIForClassification(classifying) {
        const classifyBtn = document.getElementById('classifyBtn');
        const stopClassifyBtn = document.getElementById('stopClassifyBtn');
        const progressSection = document.getElementById('progress-section');

        if (classifying) {
            classifyBtn.disabled = true;
            classifyBtn.textContent = 'Classifying...';
            stopClassifyBtn.style.display = 'inline-block';
            
            // Hide other sections and show progress
            this.hideAllSections();
            progressSection.style.display = 'block';
        } else {
            classifyBtn.disabled = false;
            classifyBtn.textContent = 'Classify Emails';
            stopClassifyBtn.style.display = 'none';
            
            setTimeout(() => {
                if (this.currentSection === 'classify') {
                    progressSection.style.display = 'none';
                    this.showClassifySection();
                }
                document.getElementById('progressBar').style.width = '0%';
                document.getElementById('progressCount').textContent = '0/0';
            }, 2000);
        }
    }

    displayClassificationProgress(data) {
        const progressBar = document.getElementById('progressBar');
        const progressCount = document.getElementById('progressCount');

        if (data.progress !== undefined) {
            progressBar.style.width = data.progress + '%';
            progressCount.textContent = `${data.processed || 0}/${data.total || 0}`;
            
            let statusText = `🤖 AI classifying emails...`;
            
            // Show batch progress if available
            if (data.current_batch && data.total_batches) {
                statusText += ` Batch ${data.current_batch}/${data.total_batches}`;
            }
            
            statusText += ` (${data.classified_count || 0} processed)`;
            
            if (data.estimated_cost) {
                statusText += ` • Est. cost: $${data.estimated_cost.toFixed(6)}`;
            }
            
            this.displayStatus(statusText, 'loading');
        }
    }

    displayClassificationResults(results) {
        this.displayStatus(
            `✅ Classification completed! Classified ${results.total_classified} emails. ` +
            `${results.travel_related} travel-related, ${results.not_travel_related} not travel-related.`,
            'success'
        );

        // Show additional info about test file
        setTimeout(() => {
            alert(`Classification test completed!\n\n` +
                  `Total classified: ${results.total_classified}\n` +
                  `Travel-related: ${results.travel_related}\n` +
                  `Not travel-related: ${results.not_travel_related}\n\n` +
                  `Results saved to: ${results.test_file.split('/').pop()}`);
        }, 1000);
    }

    // Content extraction methods
    async extractTravelContent() {
        if (this.isExtracting) {
            console.log('Extraction already in progress, ignoring click');
            return;
        }

        this.isExtracting = true;
        this.updateUIForExtraction(true);

        try {
            const response = await fetch('/api/content/extract', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({})
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to start content extraction');
            }

            if (!data.started) {
                // Check if it's because extraction is already running
                if (data.message && data.message.includes('already')) {
                    this.displayStatus('⚠️ ' + data.message, 'loading');
                    this.startExtractionMonitoring(); // Monitor existing progress
                    return;
                } else {
                    throw new Error(data.message || 'Content extraction failed to start');
                }
            }

            this.displayStatus('📄 Starting travel email content extraction...', 'loading');
            this.startExtractionMonitoring();

        } catch (error) {
            this.displayError(`Content extraction failed: ${error.message}`);
            this.isExtracting = false;
            this.updateUIForExtraction(false);
        }
    }

    async stopExtraction() {
        if (!this.isExtracting) return;

        try {
            const response = await fetch('/api/content/extract/stop', {
                method: 'POST'
            });

            if (response.ok) {
                this.displayStatus('⏹️ Content extraction stopped by user', 'status');
                this.isExtracting = false;
                this.stopExtractionMonitoring();
                this.updateUIForExtraction(false);
            }
        } catch (error) {
            console.error('Error stopping extraction:', error);
        }
    }

    startExtractionMonitoring() {
        if (window.globalExtractionInterval) {
            clearInterval(window.globalExtractionInterval);
        }
        
        window.globalExtractionInterval = setInterval(async () => {
            await this.updateExtractionProgress();
        }, 2000);
        this.extractionInterval = window.globalExtractionInterval;
    }

    stopExtractionMonitoring() {
        if (window.globalExtractionInterval) {
            clearInterval(window.globalExtractionInterval);
            window.globalExtractionInterval = null;
            this.extractionInterval = null;
        }
    }

    async updateExtractionProgress() {
        if (!this.isExtracting) {
            return;
        }

        try {
            const response = await fetch('/api/content/extract/progress');
            const data = await response.json();

            if (response.ok) {
                this.displayExtractionProgress(data);
                
                if (data.finished) {
                    this.isExtracting = false;
                    this.stopExtractionMonitoring();
                    
                    this.displayStatus(
                        `✅ ${data.message || 'Content extraction completed!'}`,
                        'success'
                    );
                    
                    this.updateUIForExtraction(false);
                }
            }
        } catch (error) {
            console.error('Extraction progress update error:', error);
        }
    }

    updateUIForExtraction(extracting) {
        const extractBtn = document.getElementById('extractBtn');
        const stopExtractBtn = document.getElementById('stopExtractBtn');
        const progressSection = document.getElementById('progress-section');

        if (extracting) {
            extractBtn.disabled = true;
            extractBtn.textContent = 'Extracting...';
            stopExtractBtn.style.display = 'inline-block';
            
            // Hide other sections and show progress
            this.hideAllSections();
            progressSection.style.display = 'block';
        } else {
            extractBtn.disabled = false;
            extractBtn.textContent = 'Extract Travel Content';
            stopExtractBtn.style.display = 'none';
            
            setTimeout(() => {
                if (this.currentSection === 'extract') {
                    progressSection.style.display = 'none';
                    this.showExtractSection();
                }
                document.getElementById('progressBar').style.width = '0%';
                document.getElementById('progressCount').textContent = '0/0';
            }, 2000);
        }
    }

    displayExtractionProgress(data) {
        const progressBar = document.getElementById('progressBar');
        const progressCount = document.getElementById('progressCount');

        if (data.progress !== undefined) {
            progressBar.style.width = data.progress + '%';
            progressCount.textContent = `${data.current || 0}/${data.total || 0}`;
            
            let statusText = `📄 Extracting travel email content...`;
            
            if (data.message) {
                statusText = `📄 ${data.message}`;
            }
            
            if (data.extracted_count !== undefined) {
                statusText += ` (${data.extracted_count} extracted, ${data.failed_count || 0} failed)`;
            }
            
            this.displayStatus(statusText, 'loading');
        }
    }

    // Travel Emails functionality
    async loadTravelEmails() {
        try {
            const response = await fetch('/api/emails/cache/stats');
            const stats = await response.json();

            if (!response.ok) {
                throw new Error('Failed to load travel emails');
            }

            // Get travel emails from the API
            const travelResponse = await fetch('/api/emails/list?classification=travel');
            const travelEmails = await travelResponse.json();

            if (travelResponse.ok) {
                this.displayTravelEmails(travelEmails);
            } else {
                // Fallback: create mock data from stats for now
                this.displayNoTravelEmails();
            }

        } catch (error) {
            console.error('Error loading travel emails:', error);
            this.displayNoTravelEmails();
        }
    }

    async displayTravelEmails(emails) {
        const emailsList = document.getElementById('travel-emails-list');
        
        if (!emails || emails.length === 0) {
            this.displayNoTravelEmails();
            return;
        }

        emailsList.innerHTML = emails.map(email => this.createEmailItem(email)).join('');
    }

    displayNoTravelEmails() {
        const emailsList = document.getElementById('travel-emails-list');
        emailsList.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #666;">
                <h3>No Travel Emails Found</h3>
                <p>Import and classify emails first to see travel-related emails here.</p>
            </div>
        `;
    }

    createEmailItem(email) {
        // Format date
        const date = new Date(email.date || email.timestamp).toLocaleDateString();
        
        // Determine if content is available (from EmailContent table)
        const hasContent = email.content_extracted || false;
        const hasAttachments = email.has_attachments || false;
        
        // Content link
        const contentLink = hasContent 
            ? `<a href="/api/content/${email.email_id}/view" target="_blank" class="action-link content-link">Content</a>`
            : `<span class="action-link content-link disabled">Content</span>`;
            
        // Attachment link
        const attachmentLink = hasAttachments
            ? `<a href="/api/content/${email.email_id}/attachments" target="_blank" class="action-link attachment-link">Attachments</a>`
            : `<span class="action-link attachment-link disabled">No Attachments</span>`;

        return `
            <div class="email-item">
                <div class="email-details">
                    <div class="email-subject">${this.escapeHtml(email.subject || 'No Subject')}</div>
                    <div class="email-meta">
                        <span class="email-sender">${this.escapeHtml(email.sender || 'Unknown Sender')}</span>
                        <span class="email-date">${date}</span>
                    </div>
                    <span class="email-classification">${email.classification || 'unclassified'}</span>
                </div>
                <div class="email-actions">
                    ${contentLink}
                    ${attachmentLink}
                </div>
            </div>
        `;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async refreshTravelEmails() {
        this.loadTravelEmails();
    }

    // Status functionality
    async loadStatusData() {
        try {
            this.displayStatus('📊 Loading email statistics...', 'loading');
            
            const response = await fetch('/api/emails/stats/detailed');
            const stats = await response.json();

            if (response.ok) {
                this.displayStatusData(stats);
                this.displayStatus('✅ Statistics loaded successfully', 'success');
            } else {
                throw new Error('Failed to load statistics');
            }
        } catch (error) {
            console.error('Error loading status data:', error);
            this.displayError('Failed to load email statistics');
        }
    }

    displayStatusData(stats) {
        const statusContent = document.getElementById('status-content');
        
        // Create classification details HTML
        const classificationHTML = this.createClassificationStatsHTML(stats.classification_details);
        const travelStatsHTML = this.createTravelStatsHTML(stats.travel_summary.travel_categories);
        
        statusContent.innerHTML = `
            <div class="status-overview">
                <!-- Basic Stats -->
                <div class="stats-grid">
                    <div class="stat-card primary">
                        <div class="stat-number">${stats.total_emails}</div>
                        <div class="stat-label">Total Emails</div>
                    </div>
                    <div class="stat-card success">
                        <div class="stat-number">${stats.classification_summary.classified}</div>
                        <div class="stat-label">Classified (${stats.classification_summary.classification_rate}%)</div>
                    </div>
                    <div class="stat-card warning">
                        <div class="stat-number">${stats.classification_summary.unclassified}</div>
                        <div class="stat-label">Unclassified</div>
                    </div>
                    <div class="stat-card info">
                        <div class="stat-number">${stats.travel_summary.total_travel_emails}</div>
                        <div class="stat-label">Travel Emails</div>
                    </div>
                </div>

                <!-- Date Range -->
                ${stats.date_range ? `
                <div class="date-range-card">
                    <h3>📅 Date Range</h3>
                    <p><strong>From:</strong> ${stats.date_range.oldest}</p>
                    <p><strong>To:</strong> ${stats.date_range.newest}</p>
                </div>
                ` : '<div class="date-range-card"><h3>📅 No Date Range Available</h3></div>'}

                <!-- Content Extraction Stats -->
                <div class="extraction-stats-card">
                    <h3>📄 Content Extraction Status</h3>
                    <div class="extraction-grid">
                        <div class="extraction-item success">
                            <span class="extraction-number">${stats.content_extraction.extracted}</span>
                            <span class="extraction-label">Extracted (${stats.content_extraction.extraction_rate}%)</span>
                        </div>
                        <div class="extraction-item error">
                            <span class="extraction-number">${stats.content_extraction.failed}</span>
                            <span class="extraction-label">Failed</span>
                        </div>
                        <div class="extraction-item extracting">
                            <span class="extraction-number">${stats.content_extraction.extracting || 0}</span>
                            <span class="extraction-label">Extracting</span>
                        </div>
                        <div class="extraction-item pending">
                            <span class="extraction-number">${stats.content_extraction.pending}</span>
                            <span class="extraction-label">Pending</span>
                        </div>
                    </div>
                </div>

                <!-- Classification Breakdown -->
                <div class="classification-breakdown">
                    <h3>🏷️ Classification Breakdown</h3>
                    <div class="classification-grid">
                        ${classificationHTML}
                    </div>
                </div>

                <!-- Travel Categories -->
                ${stats.travel_summary.total_travel_emails > 0 ? `
                <div class="travel-breakdown">
                    <h3>✈️ Travel Categories</h3>
                    <div class="travel-grid">
                        ${travelStatsHTML}
                    </div>
                </div>
                ` : ''}
            </div>
        `;
    }

    createClassificationStatsHTML(classificationDetails) {
        const classificationNames = {
            'unclassified': 'Unclassified',
            'flight': 'Flight',
            'hotel': 'Hotel',
            'car_rental': 'Car Rental',
            'train': 'Train',
            'cruise': 'Cruise',
            'tour': 'Tour',
            'travel_insurance': 'Travel Insurance',
            'flight_change': 'Flight Change',
            'hotel_change': 'Hotel Change',
            'other_travel': 'Other Travel',
            'not_travel_related': 'Not Travel Related'
        };

        return Object.entries(classificationDetails)
            .sort(([,a], [,b]) => b - a)
            .map(([classification, count]) => {
                const displayName = classificationNames[classification] || classification;
                const isTravel = !['unclassified', 'not_travel_related'].includes(classification);
                const cssClass = isTravel ? 'travel' : (classification === 'unclassified' ? 'unclassified' : 'non-travel');
                
                return `
                <div class="classification-item ${cssClass}">
                    <span class="classification-count">${count}</span>
                    <span class="classification-name">${displayName}</span>
                </div>
                `;
            }).join('');
    }

    createTravelStatsHTML(travelCategories) {
        const categoryNames = {
            'flight': '✈️ Flight',
            'hotel': '🏨 Hotel', 
            'car_rental': '🚗 Car Rental',
            'train': '🚂 Train',
            'cruise': '🚢 Cruise',
            'tour': '🗺️ Tour',
            'travel_insurance': '🛡️ Insurance',
            'flight_change': '✈️ Flight Change',
            'hotel_change': '🏨 Hotel Change',
            'other_travel': '🌍 Other Travel'
        };

        return Object.entries(travelCategories)
            .filter(([, count]) => count > 0)
            .sort(([,a], [,b]) => b - a)
            .map(([category, count]) => {
                const displayName = categoryNames[category] || category;
                return `
                <div class="travel-category-item">
                    <span class="travel-count">${count}</span>
                    <span class="travel-name">${displayName}</span>
                </div>
                `;
            }).join('');
    }

    async refreshStatus() {
        this.loadStatusData();
    }
}

// Global functions for button clicks
let app;

// Clear any existing classification timers globally
if (window.globalClassificationInterval) {
    clearInterval(window.globalClassificationInterval);
    window.globalClassificationInterval = null;
}

function importEmails() {
    app.importEmails();
}

function stopImport() {
    app.stopImport();
}

function viewCacheStats() {
    app.viewCacheStats();
}

function testClassification() {
    app.testClassification();
}

function stopClassification() {
    app.stopClassification();
}

function extractTravelContent() {
    app.extractTravelContent();
}

function stopExtraction() {
    app.stopExtraction();
}

function showTravelEmails() {
    app.switchFunction('travel');
}

function refreshTravelEmails() {
    app.refreshTravelEmails();
}

function refreshStatus() {
    app.refreshStatus();
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    app = new EmailImportApp();
});