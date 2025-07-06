// MyTrips Email Import Application

class EmailImportApp {
    constructor() {
        this.isImporting = false;
        this.isClassifying = false;
        this.progressInterval = null;
        this.classificationInterval = null;
        this.init();
    }

    init() {
        console.log('MyTrips Email Import App initialized');
        // Check initial cache stats
        this.loadCacheStats();
    }

    async importEmails() {
        if (this.isImporting) return;

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
                throw new Error('Import failed to start');
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
        const progress = document.getElementById('progress');
        const progressText = document.getElementById('progressText');

        if (importing) {
            importBtn.disabled = true;
            importBtn.textContent = 'Importing...';
            stopBtn.style.display = 'inline-block';
            progress.style.display = 'block';
            progressText.style.display = 'block';
            document.getElementById('stats').style.display = 'none';
        } else {
            importBtn.disabled = false;
            importBtn.textContent = 'Import Emails (Last Year)';
            stopBtn.style.display = 'none';
            
            setTimeout(() => {
                progress.style.display = 'none';
                progressText.style.display = 'none';
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
        if (this.isClassifying) return;

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
        this.classificationInterval = setInterval(async () => {
            await this.updateClassificationProgress();
        }, 2000);
    }

    stopClassificationMonitoring() {
        if (this.classificationInterval) {
            clearInterval(this.classificationInterval);
            this.classificationInterval = null;
        }
    }

    async updateClassificationProgress() {
        if (!this.isClassifying) return;

        try {
            const response = await fetch('/api/emails/classify/progress');
            const data = await response.json();

            if (response.ok) {
                this.displayClassificationProgress(data);
                
                if (data.finished) {
                    this.isClassifying = false;
                    this.stopClassificationMonitoring();
                    
                    if (data.final_results) {
                        this.displayClassificationResults(data.final_results);
                    }
                    
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

        if (classifying) {
            classifyBtn.disabled = true;
            classifyBtn.textContent = 'Classifying...';
            stopClassifyBtn.style.display = 'inline-block';
        } else {
            classifyBtn.disabled = false;
            classifyBtn.textContent = 'Classify Emails (Test 1000)';
            stopClassifyBtn.style.display = 'none';
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
                statusText += ` • Est. cost: $${data.estimated_cost.estimated_cost_usd.toFixed(6)}`;
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
}

// Global functions for button clicks
let app;

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

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    app = new EmailImportApp();
});