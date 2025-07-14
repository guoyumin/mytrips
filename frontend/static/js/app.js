// MyTrips Email Import Application

class EmailImportApp {
    constructor() {
        this.isImporting = false;
        this.isClassifying = false;
        this.isExtracting = false;
        this.isExtractingBookings = false;
        this.isDetectingTrips = false;
        this.progressInterval = null;
        this.classificationInterval = null;
        this.extractionInterval = null;
        this.bookingExtractionInterval = null;
        this.detectionInterval = null;
        this.currentSection = 'welcome';
        this.currentTripId = null;
        this.allTravelEmails = []; // Store all travel emails for filtering
        this.isLoadingTravelEmails = false; // Prevent duplicate loading
        this.currentPage = 1;
        this.pageSize = 50;
        this.totalEmails = 0;
        this.totalPages = 0;
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
            case 'booking-extraction':
                this.showBookingExtractionSection();
                break;
            case 'trip-detection':
                this.showTripDetectionSection();
                break;
            case 'my-trips':
                this.showMyTripsSection();
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
        // Removed gemini-usage-section as it no longer exists
        document.getElementById('booking-extraction-section').style.display = 'none';
        document.getElementById('trip-detection-section').style.display = 'none';
        document.getElementById('my-trips-section').style.display = 'none';
        document.getElementById('trip-detail-section').style.display = 'none';
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
        // Reset filters to 'all' when first showing the page
        const bookingFilterEl = document.getElementById('bookingFilter');
        const tripDetectionFilterEl = document.getElementById('tripDetectionFilter');
        const searchTextEl = document.getElementById('searchText');
        
        if (bookingFilterEl) {
            bookingFilterEl.value = 'all';
        }
        if (tripDetectionFilterEl) {
            tripDetectionFilterEl.value = 'all';
        }
        if (searchTextEl) {
            searchTextEl.value = '';
        }
        this.loadTravelEmails();
    }

    showStatusSection() {
        document.getElementById('status-section').style.display = 'block';
        // Removed Gemini usage section display
        this.loadStatusData();
        // Removed loadGeminiUsageData call
    }

    showBookingExtractionSection() {
        document.getElementById('booking-extraction-section').style.display = 'block';
    }

    async importEmails() {
        if (this.isImporting) {
            console.log('Import already in progress, ignoring click');
            return;
        }

        this.isImporting = true;
        this.updateUIForImporting(true);

        try {
            // Check if we have specific date range
            const startDateInput = document.getElementById('startDate');
            const endDateInput = document.getElementById('endDate');
            const startDate = startDateInput.value;
            const endDate = endDateInput.value;
            
            let endpoint, body, statusMessage;
            
            if (startDate && endDate) {
                // Use date range endpoint
                endpoint = '/api/emails/import/date-range';
                body = JSON.stringify({ 
                    start_date: startDate,
                    end_date: endDate 
                });
                statusMessage = `Starting import for ${startDate} to ${endDate}...`;
            } else {
                // Fall back to days-based import
                const timeRange = document.getElementById('timeRange').value;
                const days = parseInt(timeRange) || 30; // Default to 30 days
                
                endpoint = '/api/emails/import/days';
                body = JSON.stringify({ days: days });
                statusMessage = `Starting import for ${this.getTimeRangeLabel(days)}...`;
            }
            
            // Update status to show selected range
            this.displayStatus(statusMessage, 'loading');
            
            // Start import
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: body
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
            
            // Add cost information if available  
            if (data.cost_estimate) {
                statusText += ` | Est. cost: $${data.cost_estimate.estimated_cost_usd.toFixed(4)} (${data.cost_estimate.model})`;
            }
            
            this.displayStatus(statusText, 'loading');
        }
    }

    // Travel Emails functionality
    async loadTravelEmails(page = 1) {
        // Prevent duplicate loading
        if (this.isLoadingTravelEmails) {
            console.log('Already loading travel emails, skipping duplicate call');
            return;
        }

        this.isLoadingTravelEmails = true;
        
        try {
            // Get current filter values
            const bookingFilter = document.getElementById('bookingFilter')?.value || 'all';
            const tripDetectionFilter = document.getElementById('tripDetectionFilter')?.value || 'all';
            const searchText = document.getElementById('searchText')?.value || '';
            
            // Calculate offset
            const offset = (page - 1) * this.pageSize;
            
            // Build API URL based on filters
            let apiUrl = `/api/emails/list?classification=travel&limit=${this.pageSize}&offset=${offset}`;
            
            // Add booking filter
            if (bookingFilter === 'booking_completed') {
                apiUrl += '&booking_status=completed';
            } else if (bookingFilter === 'has_booking') {
                apiUrl += '&booking_status=has_booking';
            }
            
            // Add trip detection filter
            if (tripDetectionFilter !== 'all') {
                apiUrl += `&trip_detection_status=${tripDetectionFilter}`;
            }
            
            // Add search text
            if (searchText.trim()) {
                apiUrl += `&search=${encodeURIComponent(searchText.trim())}`;
            }
            
            console.log('Loading travel emails with URL:', apiUrl);

            // Get travel emails from the API
            const travelResponse = await fetch(apiUrl);
            const data = await travelResponse.json();

            if (travelResponse.ok) {
                console.log('API response:', data);
                this.currentPage = page;
                this.totalEmails = data.total_count;
                this.totalPages = Math.ceil(data.total_count / this.pageSize);
                this.displayTravelEmails(data.emails);
                this.updatePaginationControls();
            } else {
                console.error('API error:', travelResponse.status, data);
                this.displayNoTravelEmails();
            }

        } catch (error) {
            console.error('Error loading travel emails:', error);
            this.displayNoTravelEmails();
        } finally {
            this.isLoadingTravelEmails = false;
        }
    }

    async displayTravelEmails(emails) {
        // Get current filter values
        const bookingFilter = document.getElementById('bookingFilter')?.value || 'all';
        const tripDetectionFilter = document.getElementById('tripDetectionFilter')?.value || 'all';
        const searchText = document.getElementById('searchText')?.value || '';
        
        // Check if any server-side filters are active
        const hasServerSideFilters = bookingFilter === 'booking_completed' || 
                                   bookingFilter === 'has_booking' || 
                                   tripDetectionFilter !== 'all' || 
                                   searchText.trim() !== '';
        
        // Only update allTravelEmails if we're not using server-side filters
        if (!hasServerSideFilters) {
            this.allTravelEmails = emails || [];
        }
        
        if (!emails || emails.length === 0) {
            this.displayNoTravelEmails();
            return;
        }

        // For server-side filtered emails, display directly
        // For client-side filters (only 'extracted'), apply filtering
        let displayEmails = emails;
        
        if (!hasServerSideFilters && bookingFilter === 'extracted') {
            displayEmails = emails.filter(email => email.content_extracted);
        }

        const emailsList = document.getElementById('travel-emails-list');
        if (displayEmails.length === 0) {
            emailsList.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #666;">
                    <h3>No Emails Match Filter</h3>
                    <p>Try adjusting the filter or processing more emails first.</p>
                </div>
            `;
        } else {
            emailsList.innerHTML = displayEmails.map(email => this.createEmailItem(email)).join('');
        }
    }

    applyTravelEmailFilter() {
        // Check if elements exist
        const bookingFilterEl = document.getElementById('bookingFilter');
        const tripDetectionFilterEl = document.getElementById('tripDetectionFilter');
        const searchTextEl = document.getElementById('searchText');
        
        if (!bookingFilterEl || !tripDetectionFilterEl || !searchTextEl) {
            console.error('Filter elements not found in DOM');
            return;
        }
        
        const bookingFilter = bookingFilterEl.value;
        const tripDetectionFilter = tripDetectionFilterEl.value;
        const searchText = searchTextEl.value.toLowerCase().trim();
        
        console.log('Applying filters:', { bookingFilter, tripDetectionFilter, searchText }, 'Current emails count:', this.allTravelEmails.length);
        
        // For server-side filters, we need to reload data from API
        if (bookingFilter === 'booking_completed' || bookingFilter === 'has_booking' || 
            tripDetectionFilter !== 'all' || searchText !== '') {
            // Reset to page 1 when filters change
            this.currentPage = 1;
            this.loadTravelEmails(1);
            return;
        }
        
        // Check if we need to reload all emails (when switching from server-side filters to client-side filters)
        // Check if allTravelEmails is empty or if it only contains filtered emails
        if ((bookingFilter === 'all' || bookingFilter === 'extracted') && 
            (this.allTravelEmails.length === 0 || 
             (this.allTravelEmails.length > 0 && 
              this.allTravelEmails.every(email => email.booking_extraction_status === 'completed')))) {
            console.log('Need to reload all emails for client-side filtering');
            this.loadTravelEmails();
            return;
        }
        
        const emailsList = document.getElementById('travel-emails-list');
        let filteredEmails = this.allTravelEmails;
        
        // Apply booking filter
        switch (bookingFilter) {
            case 'extracted':
                filteredEmails = this.allTravelEmails.filter(email => email.content_extracted);
                break;
            case 'all':
            default:
                // For 'all' filter, show all emails (no filtering needed)
                filteredEmails = this.allTravelEmails;
                break;
        }
        
        if (filteredEmails.length === 0) {
            emailsList.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #666;">
                    <h3>No Emails Match Filter</h3>
                    <p>Try adjusting the filter or processing more emails first.</p>
                </div>
            `;
            return;
        }

        emailsList.innerHTML = filteredEmails.map(email => this.createEmailItem(email)).join('');
    }

    displayNoTravelEmails() {
        const emailsList = document.getElementById('travel-emails-list');
        emailsList.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #666;">
                <h3>No Travel Emails Found</h3>
                <p>Import and classify emails first to see travel-related emails here.</p>
            </div>
        `;
        // Hide pagination when no emails
        document.getElementById('pagination-controls').style.display = 'none';
    }

    updatePaginationControls() {
        const paginationControls = document.getElementById('pagination-controls');
        
        if (this.totalPages <= 1) {
            paginationControls.style.display = 'none';
            return;
        }
        
        paginationControls.style.display = 'block';
        
        let html = `
            <div class="pagination-info">
                Page ${this.currentPage} of ${this.totalPages} (${this.totalEmails.toLocaleString()} total emails)
            </div>
            <div class="pagination-buttons">
        `;
        
        // Previous button
        if (this.currentPage > 1) {
            html += `<button onclick="app.goToPage(1)" class="pagination-btn first-btn">First</button>`;
            html += `<button onclick="app.goToPage(${this.currentPage - 1})" class="pagination-btn prev-btn">Previous</button>`;
        }
        
        // Page numbers (show current and surrounding pages)
        const startPage = Math.max(1, this.currentPage - 2);
        const endPage = Math.min(this.totalPages, this.currentPage + 2);
        
        if (startPage > 1) {
            html += `<button onclick="app.goToPage(1)" class="pagination-btn page-btn">1</button>`;
            if (startPage > 2) {
                html += `<span class="pagination-dots">...</span>`;
            }
        }
        
        for (let i = startPage; i <= endPage; i++) {
            const activeClass = i === this.currentPage ? ' active' : '';
            html += `<button onclick="app.goToPage(${i})" class="pagination-btn page-btn${activeClass}">${i}</button>`;
        }
        
        if (endPage < this.totalPages) {
            if (endPage < this.totalPages - 1) {
                html += `<span class="pagination-dots">...</span>`;
            }
            html += `<button onclick="app.goToPage(${this.totalPages})" class="pagination-btn page-btn">${this.totalPages}</button>`;
        }
        
        // Next button
        if (this.currentPage < this.totalPages) {
            html += `<button onclick="app.goToPage(${this.currentPage + 1})" class="pagination-btn next-btn">Next</button>`;
            html += `<button onclick="app.goToPage(${this.totalPages})" class="pagination-btn last-btn">Last</button>`;
        }
        
        html += `</div>`;
        
        paginationControls.innerHTML = html;
    }

    goToPage(page) {
        if (page >= 1 && page <= this.totalPages && page !== this.currentPage) {
            this.loadTravelEmails(page);
        }
    }

    createEmailItem(email) {
        // Format date
        const date = new Date(email.date || email.timestamp).toLocaleDateString();
        
        // Determine if content is available (from EmailContent table)
        const hasContent = email.content_extracted || false;
        const hasAttachments = email.has_attachments || false;
        const hasBookingInfo = email.has_booking_info || false;
        
        // Content link
        const contentLink = hasContent 
            ? `<a href="/api/content/${email.email_id}/view" target="_blank" class="action-link content-link">Content</a>`
            : `<span class="action-link content-link disabled">Content</span>`;
            
        // Attachment link
        const attachmentLink = hasAttachments
            ? `<a href="/api/content/${email.email_id}/attachments" target="_blank" class="action-link attachment-link">Attachments</a>`
            : `<span class="action-link attachment-link disabled">No Attachments</span>`;

        // Booking info link - enable for all emails that completed booking extraction (regardless of whether booking info was found)
        const bookingExtractionCompleted = email.booking_extraction_status === 'completed';
        const bookingLink = bookingExtractionCompleted
            ? `<button onclick="viewBookingInfo('${email.email_id}')" class="action-link booking-link">Booking Info</button>`
            : `<span class="action-link booking-link disabled">No Booking</span>`;

        // Create booking summary display
        let bookingSummaryHtml = '';
        if (email.booking_summary) {
            const summary = email.booking_summary;
            
            // Handle non-booking emails
            if (summary.booking_type === null) {
                const nonBookingIcons = {
                    'reminder': '⏰',
                    'marketing': '📧',
                    'status_update': '🔄',
                    'check_in': '✈️',
                    'general_info': 'ℹ️',
                    'survey': '📋',
                    'program_enrollment': '🎫'
                };
                const icon = nonBookingIcons[summary.non_booking_type] || '📄';
                
                bookingSummaryHtml = `
                    <div class="non-booking-summary">
                        <div class="non-booking-header">
                            <span class="non-booking-type">${icon} ${summary.non_booking_type ? summary.non_booking_type.replace('_', ' ').toUpperCase() : 'NON-BOOKING'}</span>
                        </div>
                        <div class="non-booking-reason">${summary.reason || 'Not a booking email'}</div>
                    </div>
                `;
            } else {
                // Handle regular booking emails
                const statusIcon = summary.status === 'confirmed' ? '✅' : summary.status === 'cancelled' ? '❌' : '⚠️';
                const confirmations = summary.confirmation_numbers && summary.confirmation_numbers.length > 0 
                    ? `Conf: ${summary.confirmation_numbers.join(', ')}` 
                    : '';
                
                bookingSummaryHtml = `
                    <div class="booking-summary">
                        <div class="booking-header">
                            <span class="booking-type">${statusIcon} ${summary.booking_type ? summary.booking_type.replace('_', ' ').toUpperCase() : 'BOOKING'}</span>
                            <span class="booking-status">${summary.status}</span>
                        </div>
                        ${summary.key_details && summary.key_details.length > 0 ? summary.key_details.map(detail => `<div class="booking-detail">${detail}</div>`).join('') : ''}
                        ${confirmations ? `<div class="booking-confirmation">${confirmations}</div>` : ''}
                        ${summary.total_cost ? `<div class="booking-cost">Cost: ${summary.total_cost}</div>` : ''}
                    </div>
                `;
            }
        } else if (email.booking_extraction_status === 'failed') {
            bookingSummaryHtml = '<div class="booking-error">❌ Booking extraction failed</div>';
        } else if (email.booking_extraction_status === 'completed') {
            bookingSummaryHtml = '<div class="booking-completed">✅ Booking extraction completed - No booking information found</div>';
        } else if (email.booking_extraction_status === 'pending') {
            bookingSummaryHtml = '<div class="booking-pending">⏳ Booking extraction pending</div>';
        }

        return `
            <div class="email-item">
                <div class="email-details">
                    <div class="email-subject">${this.escapeHtml(email.subject || 'No Subject')}</div>
                    <div class="email-meta">
                        <span class="email-sender">${this.escapeHtml(email.sender || 'Unknown Sender')}</span>
                        <span class="email-date">${date}</span>
                        <span class="email-id">ID: ${email.email_id}</span>
                    </div>
                    <span class="email-classification">${email.classification || 'unclassified'}</span>
                    <span class="trip-detection-status ${email.trip_detection_status || 'pending'}">${this.getTripDetectionStatusLabel(email.trip_detection_status)}</span>
                    ${bookingSummaryHtml}
                </div>
                <div class="email-actions">
                    ${contentLink}
                    ${attachmentLink}
                    ${bookingLink}
                </div>
            </div>
        `;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    getTripDetectionStatusLabel(status) {
        const statusLabels = {
            'pending': '⏳ Pending',
            'processing': '🔄 Processing',
            'completed': '✅ Completed',
            'failed': '❌ Failed'
        };
        return statusLabels[status] || '⏳ Pending';
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
                <!-- Date Range (moved to top) -->
                ${stats.date_range ? `
                <div class="date-range-card">
                    <h3>📅 Date Range</h3>
                    <p><strong>From:</strong> ${stats.date_range.oldest}</p>
                    <p><strong>To:</strong> ${stats.date_range.newest}</p>
                </div>
                ` : '<div class="date-range-card"><h3>📅 No Date Range Available</h3></div>'}

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

                <!-- Content Extraction Stats (with not_required added) -->
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
                        <div class="extraction-item not-required">
                            <span class="extraction-number">${stats.content_extraction.not_required || 0}</span>
                            <span class="extraction-label">Not Required</span>
                        </div>
                    </div>
                </div>

                <!-- Booking Extraction Stats (with not_travel and no_booking added) -->
                ${stats.booking_extraction ? `
                <div class="extraction-stats-card">
                    <h3>🔍 Booking Extraction Status</h3>
                    <div class="extraction-grid">
                        <div class="extraction-item success">
                            <span class="extraction-number">${stats.booking_extraction.completed || 0}</span>
                            <span class="extraction-label">Completed (${stats.booking_extraction.completion_rate || 0}%)</span>
                        </div>
                        <div class="extraction-item error">
                            <span class="extraction-number">${stats.booking_extraction.failed || 0}</span>
                            <span class="extraction-label">Failed</span>
                        </div>
                        <div class="extraction-item extracting">
                            <span class="extraction-number">${stats.booking_extraction.extracting || 0}</span>
                            <span class="extraction-label">Extracting</span>
                        </div>
                        <div class="extraction-item pending">
                            <span class="extraction-number">${stats.booking_extraction.pending || 0}</span>
                            <span class="extraction-label">Pending</span>
                        </div>
                        <div class="extraction-item not-travel">
                            <span class="extraction-number">${stats.booking_extraction.not_travel || 0}</span>
                            <span class="extraction-label">Not Travel</span>
                        </div>
                        <div class="extraction-item no-booking">
                            <span class="extraction-number">${stats.booking_extraction.no_booking || 0}</span>
                            <span class="extraction-label">No Booking</span>
                        </div>
                    </div>
                </div>
                ` : ''}

                <!-- Trip Detection Stats -->
                <div class="extraction-stats-card">
                    <h3>🗺️ Trip Detection Progress</h3>
                    <div class="trip-detection-summary">
                        <div class="trip-stat">
                            <span class="trip-stat-number">${(stats.trip_detection && stats.trip_detection.total_trips_detected) || 0}</span>
                            <span class="trip-stat-label">已检测到的行程数量</span>
                        </div>
                        <div class="trip-stat">
                            <span class="trip-stat-number">${(stats.trip_detection && stats.trip_detection.completed) || 0}</span>
                            <span class="trip-stat-label">已完成Trip Detection的邮件数量</span>
                        </div>
                        <div class="trip-stat">
                            <span class="trip-stat-number">${(stats.trip_detection && stats.trip_detection.booking_emails_count) || 0}</span>
                            <span class="trip-stat-label">包含booking信息的邮件总数</span>
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

    async refreshGeminiUsage() {
        await this.loadGeminiUsageData();
    }

    async loadGeminiUsageData() {
        try {
            const response = await fetch('/api/emails/gemini-usage');
            const data = await response.json();

            if (response.ok) {
                this.displayGeminiUsage(data);
            } else {
                throw new Error(data.detail || 'Failed to load Gemini usage data');
            }
        } catch (error) {
            console.error('Error loading Gemini usage:', error);
            document.getElementById('gemini-usage-content').innerHTML = `
                <p class="error">Error loading Gemini usage: ${error.message}</p>
            `;
        }
    }

    displayGeminiUsage(data) {
        const usageContent = document.getElementById('gemini-usage-content');
        
        let html = `
            <div class="usage-summary">
                <h3>📊 Current Usage Summary</h3>
                <div class="usage-stats">
                    <div class="usage-stat">
                        <div class="stat-number">${data.summary.total_requests_last_minute}</div>
                        <div class="stat-label">Requests (Last Minute)</div>
                    </div>
                    <div class="usage-stat">
                        <div class="stat-number">${data.summary.total_requests_today}</div>
                        <div class="stat-label">Requests (Today)</div>
                    </div>
                    <div class="usage-stat">
                        <div class="stat-number">${data.summary.total_tokens_last_minute.toLocaleString()}</div>
                        <div class="stat-label">Tokens (Last Minute)</div>
                    </div>
                </div>
            </div>
        `;

        if (Object.keys(data.by_model).length > 0) {
            html += `
                <div class="model-usage">
                    <h3>🤖 Usage by Model</h3>
                    <div class="model-details">
            `;

            for (const [model, stats] of Object.entries(data.by_model)) {
                const limits = stats.limits || {};
                html += `
                    <div class="model-card">
                        <div class="model-header">
                            <h4>${model}</h4>
                            <span class="model-type">${model.includes('flash') ? '⚡ Flash' : '🧠 Pro'}</span>
                        </div>
                        <div class="model-stats">
                            <div class="stat-row">
                                <span>Requests/Minute:</span>
                                <span>${stats.requests_last_minute}/${limits.requests_per_minute || 'N/A'} (${stats.rpm_usage_percent?.toFixed(1) || 0}%)</span>
                            </div>
                            <div class="stat-row">
                                <span>Requests/Day:</span>
                                <span>${stats.requests_today}/${limits.requests_per_day || 'N/A'} (${stats.rpd_usage_percent?.toFixed(1) || 0}%)</span>
                            </div>
                            <div class="stat-row">
                                <span>Tokens/Minute:</span>
                                <span>${stats.tokens_last_minute.toLocaleString()}/${limits.tokens_per_minute?.toLocaleString() || 'N/A'} (${stats.tpm_usage_percent?.toFixed(1) || 0}%)</span>
                            </div>
                        </div>
                        <div class="usage-bars">
                            <div class="usage-bar">
                                <div class="usage-bar-fill" style="width: ${Math.min(stats.rpm_usage_percent || 0, 100)}%"></div>
                                <span class="usage-bar-label">RPM</span>
                            </div>
                            <div class="usage-bar">
                                <div class="usage-bar-fill" style="width: ${Math.min(stats.rpd_usage_percent || 0, 100)}%"></div>
                                <span class="usage-bar-label">RPD</span>
                            </div>
                            <div class="usage-bar">
                                <div class="usage-bar-fill" style="width: ${Math.min(stats.tpm_usage_percent || 0, 100)}%"></div>
                                <span class="usage-bar-label">TPM</span>
                            </div>
                        </div>
                    </div>
                `;
            }

            html += `
                    </div>
                </div>
            `;
        } else {
            html += `
                <div class="no-usage">
                    <p>🔍 No Gemini API usage detected yet. Usage will appear after making API calls.</p>
                </div>
            `;
        }

        html += `
            <div class="rate-limits-info">
                <h3>⚠️ Free Tier Limits</h3>
                <div class="limits-grid">
        `;

        for (const [model, limits] of Object.entries(data.rate_limits || {})) {
            html += `
                <div class="limit-card">
                    <h4>${model}</h4>
                    <ul>
                        <li>📝 ${limits.requests_per_minute}/min requests</li>
                        <li>📅 ${limits.requests_per_day}/day requests</li>
                        <li>🪙 ${limits.tokens_per_minute?.toLocaleString()}/min tokens</li>
                    </ul>
                </div>
            `;
        }

        html += `
                </div>
                <p class="note">💡 This system uses <strong>gemini-2.5-flash</strong> for booking extraction and <strong>gemini-2.5-pro</strong> for trip detection to optimize costs while maintaining quality.</p>
            </div>
        `;

        usageContent.innerHTML = html;
    }

    // Booking Extraction methods
    async extractBookings() {
        if (this.isExtractingBookings) {
            console.log('Booking extraction already in progress, ignoring click');
            return;
        }

        this.isExtractingBookings = true;
        this.updateUIForBookingExtraction(true);

        try {
            const response = await fetch('/api/trips/extract-bookings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({})
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to start booking extraction');
            }

            if (!data.started) {
                if (data.message && data.message.includes('already')) {
                    this.displayStatus('⚠️ ' + data.message, 'loading');
                    this.startBookingExtractionMonitoring();
                    return;
                } else {
                    throw new Error(data.message || 'Booking extraction failed to start');
                }
            }

            this.displayStatus('🔍 Starting booking information extraction...', 'loading');
            this.startBookingExtractionMonitoring();

        } catch (error) {
            this.displayError(`Booking extraction failed: ${error.message}`);
            this.isExtractingBookings = false;
            this.updateUIForBookingExtraction(false);
        }
    }

    async stopBookingExtraction() {
        if (!this.isExtractingBookings) return;

        try {
            const response = await fetch('/api/trips/extract-bookings/stop', {
                method: 'POST'
            });

            if (response.ok) {
                this.displayStatus('⏹️ Booking extraction stopped by user', 'status');
                this.isExtractingBookings = false;
                this.stopBookingExtractionMonitoring();
                this.updateUIForBookingExtraction(false);
            }
        } catch (error) {
            console.error('Error stopping booking extraction:', error);
        }
    }

    startBookingExtractionMonitoring() {
        if (window.globalBookingExtractionInterval) {
            clearInterval(window.globalBookingExtractionInterval);
        }
        
        window.globalBookingExtractionInterval = setInterval(async () => {
            await this.updateBookingExtractionProgress();
        }, 2000);
        this.bookingExtractionInterval = window.globalBookingExtractionInterval;
    }

    stopBookingExtractionMonitoring() {
        if (window.globalBookingExtractionInterval) {
            clearInterval(window.globalBookingExtractionInterval);
            window.globalBookingExtractionInterval = null;
            this.bookingExtractionInterval = null;
        }
    }

    async updateBookingExtractionProgress() {
        if (!this.isExtractingBookings) {
            return;
        }

        try {
            const response = await fetch('/api/trips/extract-bookings/progress');
            const data = await response.json();

            if (response.ok) {
                this.displayBookingExtractionProgress(data);
                
                if (data.finished) {
                    this.isExtractingBookings = false;
                    this.stopBookingExtractionMonitoring();
                    
                    this.displayStatus(
                        `✅ ${data.message || 'Booking extraction completed!'}`,
                        'success'
                    );
                    
                    this.updateUIForBookingExtraction(false);
                }
            }
        } catch (error) {
            console.error('Booking extraction progress update error:', error);
        }
    }

    updateUIForBookingExtraction(extracting) {
        const extractBtn = document.getElementById('extractBookingsBtn');
        const stopBtn = document.getElementById('stopBookingExtractionBtn');
        const progressSection = document.getElementById('progress-section');

        if (extracting) {
            extractBtn.disabled = true;
            extractBtn.textContent = 'Extracting...';
            stopBtn.style.display = 'inline-block';
            
            // Hide other sections and show progress
            this.hideAllSections();
            progressSection.style.display = 'block';
        } else {
            extractBtn.disabled = false;
            extractBtn.textContent = 'Extract Bookings';
            stopBtn.style.display = 'none';
            
            setTimeout(() => {
                if (this.currentSection === 'booking-extraction') {
                    progressSection.style.display = 'none';
                    this.showBookingExtractionSection();
                }
                document.getElementById('progressBar').style.width = '0%';
                document.getElementById('progressCount').textContent = '0/0';
            }, 2000);
        }
    }

    displayBookingExtractionProgress(data) {
        const progressBar = document.getElementById('progressBar');
        const progressCount = document.getElementById('progressCount');

        if (data.progress !== undefined) {
            progressBar.style.width = data.progress + '%';
            progressCount.textContent = `${data.processed_emails || 0}/${data.total_emails || 0} emails`;
            
            let statusText = `🔍 Extracting booking information...`;
            
            if (data.current_batch && data.total_batches) {
                statusText += ` Batch ${data.current_batch}/${data.total_batches}`;
            }
            
            if (data.extracted_count !== undefined) {
                statusText += ` (${data.extracted_count} extracted, ${data.failed_count || 0} failed)`;
            }
            
            // Add cost information if available  
            if (data.cost_estimate) {
                statusText += ` | Est. cost: $${data.cost_estimate.estimated_cost_usd.toFixed(4)} (${data.cost_estimate.model})`;
            }
            
            this.displayStatus(statusText, 'loading');
        }
    }

    // Trip Detection methods
    showTripDetectionSection() {
        document.getElementById('trip-detection-section').style.display = 'block';
    }

    showMyTripsSection() {
        document.getElementById('my-trips-section').style.display = 'block';
        this.loadTrips();
    }

    async detectTrips() {
        if (this.isDetectingTrips) {
            console.log('Trip detection already in progress');
            return;
        }

        // Check if booking extraction is required first
        try {
            const statsResponse = await fetch('/api/emails/stats/detailed');
            const stats = await statsResponse.json();
            
            if (statsResponse.ok && stats.booking_extraction) {
                const bookingsPending = stats.booking_extraction.pending || 0;
                const bookingsCompleted = stats.booking_extraction.completed || 0;
                
                // If there are pending bookings and no completed ones, suggest running booking extraction first
                if (bookingsPending > 0 && bookingsCompleted === 0) {
                    const proceed = confirm(
                        `You have ${bookingsPending} emails that need booking information extraction first.\n\n` +
                        `For best results, it's recommended to run "Extract Bookings" before trip detection.\n\n` +
                        `Do you want to proceed with trip detection anyway?`
                    );
                    
                    if (!proceed) {
                        return;
                    }
                }
            }
        } catch (error) {
            console.warn('Could not check booking extraction status:', error);
        }

        this.isDetectingTrips = true;
        this.updateUIForTripDetection(true);

        try {
            const response = await fetch('/api/trips/detect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({})
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to start trip detection');
            }

            if (!data.started) {
                if (data.message && data.message.includes('already')) {
                    this.displayStatus('⚠️ ' + data.message, 'loading');
                    this.startDetectionMonitoring();
                    return;
                } else {
                    throw new Error(data.message || 'Trip detection failed to start');
                }
            }

            this.displayStatus('🗺️ Starting trip detection...', 'loading');
            this.startDetectionMonitoring();

        } catch (error) {
            this.displayError(`Trip detection failed: ${error.message}`);
            this.isDetectingTrips = false;
            this.updateUIForTripDetection(false);
        }
    }

    async stopTripDetection() {
        if (!this.isDetectingTrips) return;

        try {
            const response = await fetch('/api/trips/detection/stop', {
                method: 'POST'
            });

            if (response.ok) {
                this.displayStatus('⏹️ Trip detection stopped by user', 'status');
                this.isDetectingTrips = false;
                this.stopDetectionMonitoring();
                this.updateUIForTripDetection(false);
            }
        } catch (error) {
            console.error('Error stopping trip detection:', error);
        }
    }

    startDetectionMonitoring() {
        if (window.globalDetectionInterval) {
            clearInterval(window.globalDetectionInterval);
        }
        
        window.globalDetectionInterval = setInterval(async () => {
            await this.updateDetectionProgress();
        }, 2000);
        this.detectionInterval = window.globalDetectionInterval;
    }

    stopDetectionMonitoring() {
        if (window.globalDetectionInterval) {
            clearInterval(window.globalDetectionInterval);
            window.globalDetectionInterval = null;
            this.detectionInterval = null;
        }
    }

    async updateDetectionProgress() {
        if (!this.isDetectingTrips) {
            return;
        }

        try {
            const response = await fetch('/api/trips/detection/progress');
            const data = await response.json();

            if (response.ok) {
                this.displayDetectionProgress(data);
                
                if (data.finished) {
                    this.isDetectingTrips = false;
                    this.stopDetectionMonitoring();
                    
                    this.displayStatus(
                        `✅ ${data.message || 'Trip detection completed!'}`,
                        'success'
                    );
                    
                    this.updateUIForTripDetection(false);
                    
                    // Automatically switch to My Trips view
                    setTimeout(() => {
                        this.switchFunction('my-trips');
                    }, 2000);
                }
            }
        } catch (error) {
            console.error('Detection progress update error:', error);
        }
    }

    updateUIForTripDetection(detecting) {
        const detectBtn = document.getElementById('detectTripsBtn');
        const stopBtn = document.getElementById('stopDetectionBtn');
        const progressSection = document.getElementById('progress-section');

        if (detecting) {
            detectBtn.disabled = true;
            detectBtn.textContent = 'Detecting...';
            stopBtn.style.display = 'inline-block';
            
            // Hide other sections and show progress
            this.hideAllSections();
            progressSection.style.display = 'block';
        } else {
            detectBtn.disabled = false;
            detectBtn.textContent = 'Detect Trips';
            stopBtn.style.display = 'none';
            
            setTimeout(() => {
                if (this.currentSection === 'trip-detection') {
                    progressSection.style.display = 'none';
                    this.showTripDetectionSection();
                }
                document.getElementById('progressBar').style.width = '0%';
                document.getElementById('progressCount').textContent = '0/0';
            }, 2000);
        }
    }

    displayDetectionProgress(data) {
        const progressBar = document.getElementById('progressBar');
        const progressCount = document.getElementById('progressCount');

        if (data.progress !== undefined) {
            progressBar.style.width = data.progress + '%';
            progressCount.textContent = `${data.processed_emails || 0}/${data.total_emails || 0} emails`;
            
            let statusText = `🗺️ Analyzing travel emails...`;
            
            if (data.current_batch && data.total_batches) {
                statusText += ` Batch ${data.current_batch}/${data.total_batches}`;
            }
            
            if (data.trips_found !== undefined) {
                statusText += ` (${data.trips_found} trips found)`;
            }
            
            // Add cost information if available
            if (data.cost_estimate) {
                statusText += ` | Est. cost: $${data.cost_estimate.estimated_cost_usd.toFixed(4)} (${data.cost_estimate.model})`;
            }
            
            this.displayStatus(statusText, 'loading');
        }
    }

    // My Trips methods
    async loadTrips() {
        try {
            const response = await fetch('/api/trips/');
            const trips = await response.json();

            if (response.ok) {
                this.displayTrips(trips);
            } else {
                throw new Error('Failed to load trips');
            }
        } catch (error) {
            console.error('Error loading trips:', error);
            this.displayNoTrips();
        }
    }

    displayTrips(trips) {
        const tripsList = document.getElementById('trips-list');
        
        if (!trips || trips.length === 0) {
            this.displayNoTrips();
            return;
        }

        tripsList.innerHTML = trips.map(trip => this.createTripItem(trip)).join('');
    }

    displayNoTrips() {
        const tripsList = document.getElementById('trips-list');
        tripsList.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #666;">
                <h3>No Trips Found</h3>
                <p>Run trip detection to analyze your travel emails and organize them into trips.</p>
            </div>
        `;
    }

    createTripItem(trip) {
        const startDate = new Date(trip.start_date).toLocaleDateString();
        const endDate = new Date(trip.end_date).toLocaleDateString();
        const citiesText = trip.cities_visited.join(' → ');
        
        const statusIcon = trip.has_cancellations ? '⚠️' : '✅';
        const statusText = trip.has_cancellations ? 'Has cancellations' : 'All confirmed';
        
        return `
            <div class="trip-item" onclick="viewTripDetails(${trip.id})">
                <div class="trip-header">
                    <h3>${trip.name}</h3>
                    <span class="trip-status">${statusIcon} ${statusText}</span>
                </div>
                <div class="trip-details">
                    <div class="trip-dates">
                        <span>📅 ${startDate} - ${endDate}</span>
                    </div>
                    <div class="trip-cities">
                        <span>🌍 ${citiesText}</span>
                    </div>
                    <div class="trip-stats">
                        <span>💰 $${trip.total_cost.toFixed(2)}</span>
                        <span>📧 ${trip.booking_counts.total} bookings</span>
                    </div>
                </div>
            </div>
        `;
    }

    async viewTripDetails(tripId) {
        this.currentTripId = tripId;
        
        try {
            const response = await fetch(`/api/trips/${tripId}`);
            const trip = await response.json();

            if (response.ok) {
                this.displayTripDetails(trip);
            } else {
                throw new Error('Failed to load trip details');
            }
        } catch (error) {
            console.error('Error loading trip details:', error);
            this.displayError('Failed to load trip details');
        }
    }

    displayTripDetails(trip) {
        // Hide trips list and show detail view
        this.hideAllSections();
        document.getElementById('trip-detail-section').style.display = 'block';
        
        // Update title
        document.getElementById('trip-detail-title').textContent = trip.name;
        
        // Build detail content
        const content = document.getElementById('trip-detail-content');
        
        content.innerHTML = `
            <div class="trip-overview">
                <div class="trip-info-grid">
                    <div class="trip-info-item">
                        <strong>Dates:</strong> ${new Date(trip.start_date).toLocaleDateString()} - ${new Date(trip.end_date).toLocaleDateString()}
                    </div>
                    <div class="trip-info-item">
                        <strong>Total Cost:</strong> $${trip.total_cost.toFixed(2)}
                    </div>
                    <div class="trip-info-item">
                        <strong>Status:</strong> ${trip.trip_status}
                    </div>
                    <div class="trip-info-item">
                        <strong>Cities:</strong> ${trip.cities_visited.join(' → ')}
                    </div>
                </div>
                
                ${trip.description ? `<div class="trip-description"><p>${trip.description}</p></div>` : ''}
                ${trip.notes ? `<div class="trip-notes"><strong>Notes:</strong> <p>${trip.notes}</p></div>` : ''}
            </div>
            
            ${this.createBookingSection('✈️ Transportation', trip.transport_segments, 'transport')}
            ${this.createBookingSection('🏨 Accommodations', trip.accommodations, 'accommodation')}
            ${this.createBookingSection('🎫 Tours & Activities', trip.tour_activities, 'tour')}
            ${this.createBookingSection('🚢 Cruises', trip.cruises, 'cruise')}
        `;
    }

    createBookingSection(title, bookings, type) {
        if (!bookings || bookings.length === 0) {
            return '';
        }
        
        const bookingItems = bookings.map(booking => {
            switch(type) {
                case 'transport':
                    return this.createTransportItem(booking);
                case 'accommodation':
                    return this.createAccommodationItem(booking);
                case 'tour':
                    return this.createTourItem(booking);
                case 'cruise':
                    return this.createCruiseItem(booking);
                default:
                    return '';
            }
        }).join('');
        
        return `
            <div class="booking-section">
                <h3>${title}</h3>
                <div class="booking-list">
                    ${bookingItems}
                </div>
            </div>
        `;
    }

    createTransportItem(segment) {
        const statusClass = segment.status === 'cancelled' ? 'cancelled' : '';
        const statusIcon = segment.status === 'cancelled' ? '❌' : segment.is_latest_version ? '✅' : '⚠️';
        
        // Format distance information
        let distanceInfo = '';
        if (segment.distance_km) {
            const distanceType = segment.distance_type === 'actual' ? '实际行驶距离' : '直线距离';
            const distanceIcon = segment.distance_type === 'actual' ? '📏' : '📐';
            distanceInfo = `<p>${distanceIcon} ${segment.distance_km.toFixed(0)} km (${distanceType})</p>`;
        }
        
        return `
            <div class="booking-item ${statusClass}">
                <div class="booking-header">
                    <span>${statusIcon} ${segment.segment_type.toUpperCase()}: ${segment.carrier_name} ${segment.segment_number}</span>
                    <span class="booking-cost">$${segment.cost.toFixed(2)}</span>
                </div>
                <div class="booking-details">
                    <p>📍 ${segment.departure_location} → ${segment.arrival_location}</p>
                    <p>🕐 ${new Date(segment.departure_datetime).toLocaleString()} - ${new Date(segment.arrival_datetime).toLocaleString()}</p>
                    ${distanceInfo}
                    <p>📱 ${segment.booking_platform || 'Unknown'} | Confirmation: ${segment.confirmation_number || 'N/A'}</p>
                </div>
            </div>
        `;
    }

    createAccommodationItem(accommodation) {
        const statusClass = accommodation.status === 'cancelled' ? 'cancelled' : '';
        const statusIcon = accommodation.status === 'cancelled' ? '❌' : accommodation.is_latest_version ? '✅' : '⚠️';
        
        return `
            <div class="booking-item ${statusClass}">
                <div class="booking-header">
                    <span>${statusIcon} ${accommodation.property_name}</span>
                    <span class="booking-cost">$${accommodation.cost.toFixed(2)}</span>
                </div>
                <div class="booking-details">
                    <p>📍 ${accommodation.city}, ${accommodation.country}</p>
                    <p>📅 Check-in: ${new Date(accommodation.check_in_date).toLocaleDateString()} | Check-out: ${new Date(accommodation.check_out_date).toLocaleDateString()}</p>
                    <p>📱 ${accommodation.booking_platform || 'Unknown'} | Confirmation: ${accommodation.confirmation_number || 'N/A'}</p>
                </div>
            </div>
        `;
    }

    createTourItem(tour) {
        const statusClass = tour.status === 'cancelled' ? 'cancelled' : '';
        const statusIcon = tour.status === 'cancelled' ? '❌' : tour.is_latest_version ? '✅' : '⚠️';
        
        return `
            <div class="booking-item ${statusClass}">
                <div class="booking-header">
                    <span>${statusIcon} ${tour.activity_name}</span>
                    <span class="booking-cost">$${tour.cost.toFixed(2)}</span>
                </div>
                <div class="booking-details">
                    <p>📍 ${tour.city}</p>
                    <p>🕐 ${new Date(tour.start_datetime).toLocaleString()}</p>
                    <p>📱 ${tour.booking_platform || 'Unknown'} | Confirmation: ${tour.confirmation_number || 'N/A'}</p>
                </div>
            </div>
        `;
    }

    createCruiseItem(cruise) {
        const statusClass = cruise.status === 'cancelled' ? 'cancelled' : '';
        const statusIcon = cruise.status === 'cancelled' ? '❌' : cruise.is_latest_version ? '✅' : '⚠️';
        
        return `
            <div class="booking-item ${statusClass}">
                <div class="booking-header">
                    <span>${statusIcon} ${cruise.cruise_line} - ${cruise.ship_name}</span>
                    <span class="booking-cost">$${cruise.cost.toFixed(2)}</span>
                </div>
                <div class="booking-details">
                    <p>🛳️ Itinerary: ${cruise.itinerary.join(' → ')}</p>
                    <p>🕐 ${new Date(cruise.departure_datetime).toLocaleDateString()} - ${new Date(cruise.arrival_datetime).toLocaleDateString()}</p>
                    <p>📱 ${cruise.booking_platform || 'Unknown'} | Confirmation: ${cruise.confirmation_number || 'N/A'}</p>
                </div>
            </div>
        `;
    }

    backToTripList() {
        this.currentTripId = null;
        this.switchFunction('my-trips');
    }

    async refreshTrips() {
        this.loadTrips();
    }

    async viewBookingInfo(emailId) {
        try {
            const response = await fetch(`/api/emails/${emailId}/booking-info`);
            const data = await response.json();

            if (response.ok) {
                this.showBookingInfoModal(data);
            } else {
                throw new Error(data.detail || 'Failed to load booking information');
            }
        } catch (error) {
            console.error('Error loading booking info:', error);
            alert('Failed to load booking information: ' + error.message);
        }
    }

    showBookingInfoModal(data) {
        // Create modal content
        let bookingInfoHtml = '';
        
        if (data.booking_info) {
            bookingInfoHtml = `
                <div class="booking-info-display">
                    <h3>📋 Booking Summary</h3>
                    ${data.booking_summary ? this.createBookingSummaryHtml(data.booking_summary) : ''}
                    
                    <h3>🔍 Raw Gemini Response</h3>
                    <div class="raw-booking-info">
                        <pre>${JSON.stringify(data.booking_info, null, 2)}</pre>
                    </div>
                </div>
            `;
        } else {
            const statusMessages = {
                'pending': '⏳ Booking extraction is pending',
                'extracting': '🔄 Currently extracting booking information...',
                'failed': `❌ Booking extraction failed: ${data.booking_extraction_error || 'Unknown error'}`,
                'completed': '⚠️ Booking extraction completed but no information was found'
            };
            
            bookingInfoHtml = `
                <div class="booking-status-message">
                    <p>${statusMessages[data.booking_extraction_status] || 'Unknown status'}</p>
                </div>
            `;
        }

        // Create modal
        const modal = document.createElement('div');
        modal.className = 'booking-modal';
        modal.innerHTML = `
            <div class="booking-modal-content">
                <div class="booking-modal-header">
                    <h2>📧 Email Booking Information</h2>
                    <button class="booking-modal-close" onclick="this.closest('.booking-modal').remove()">&times;</button>
                </div>
                <div class="booking-modal-body">
                    <div class="email-info">
                        <h3>Email Details</h3>
                        <p><strong>Subject:</strong> ${data.subject}</p>
                        <p><strong>From:</strong> ${data.sender}</p>
                        <p><strong>Date:</strong> ${data.date}</p>
                        <p><strong>Classification:</strong> ${data.classification}</p>
                        <p><strong>Extraction Status:</strong> ${data.booking_extraction_status}</p>
                    </div>
                    ${bookingInfoHtml}
                </div>
            </div>
        `;

        // Add modal to page
        document.body.appendChild(modal);
        
        // Close modal when clicking outside
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }

    createBookingSummaryHtml(summary) {
        let html = `
            <div class="booking-summary-display">
                <div class="summary-header">
                    <span class="booking-type-badge">${summary.booking_type.replace('_', ' ').toUpperCase()}</span>
                    <span class="booking-status-badge status-${summary.status}">${summary.status}</span>
                </div>
        `;

        if (summary.confirmation_numbers && summary.confirmation_numbers.length > 0) {
            html += `
                <div class="confirmations">
                    <strong>Confirmation Numbers:</strong> ${summary.confirmation_numbers.join(', ')}
                </div>
            `;
        }

        if (summary.key_details && summary.key_details.length > 0) {
            html += `
                <div class="key-details">
                    <strong>Details:</strong>
                    <ul>
                        ${summary.key_details.map(detail => `<li>${detail}</li>`).join('')}
                    </ul>
                </div>
            `;
        }

        if (summary.total_cost) {
            html += `
                <div class="total-cost">
                    <strong>Total Cost:</strong> ${summary.total_cost}
                </div>
            `;
        }

        html += '</div>';
        return html;
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

function refreshGeminiUsage() {
    app.refreshGeminiUsage();
}

function extractBookings() {
    app.extractBookings();
}

function stopBookingExtraction() {
    app.stopBookingExtraction();
}

function detectTrips() {
    app.detectTrips();
}

function stopTripDetection() {
    app.stopTripDetection();
}

function viewTripDetails(tripId) {
    app.viewTripDetails(tripId);
}

function backToTripList() {
    app.backToTripList();
}

function refreshTrips() {
    app.refreshTrips();
}

function viewBookingInfo(emailId) {
    app.viewBookingInfo(emailId);
}

function filterTravelEmails() {
    app.applyTravelEmailFilter();
}

// Helper function to update date range when quick select changes
function updateDateRangeFromQuickSelect() {
    const timeRange = document.getElementById('timeRange').value;
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    
    if (!timeRange) {
        // Custom date range selected, clear dates
        startDateInput.value = '';
        endDateInput.value = '';
        return;
    }
    
    const days = parseInt(timeRange);
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(endDate.getDate() - days);
    
    // Format dates as YYYY-MM-DD
    startDateInput.value = startDate.toISOString().split('T')[0];
    endDateInput.value = endDate.toISOString().split('T')[0];
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    app = new EmailImportApp();
    
    // Add event listeners for date inputs
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    const timeRangeSelect = document.getElementById('timeRange');
    
    if (startDateInput && endDateInput) {
        // When user manually selects dates, clear the quick select
        startDateInput.addEventListener('change', () => {
            if (startDateInput.value && endDateInput.value) {
                timeRangeSelect.value = '';
            }
        });
        
        endDateInput.addEventListener('change', () => {
            if (startDateInput.value && endDateInput.value) {
                timeRangeSelect.value = '';
            }
        });
    }
    
    // Initialize date range based on default selection
    if (timeRangeSelect && timeRangeSelect.value) {
        updateDateRangeFromQuickSelect();
    }
});