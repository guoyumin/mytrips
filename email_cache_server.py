#!/usr/bin/env python3
"""
Email caching server with import functionality
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import webbrowser
from urllib.parse import parse_qs, urlparse
import csv
import os
from datetime import datetime, timedelta
import hashlib

# Import our Gmail service
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.services.gmail_service import GmailService

# CSV file path
CACHE_FILE = 'email_cache.csv'
CSV_HEADERS = ['email_id', 'subject', 'from', 'date', 'timestamp', 'is_classified', 'classification']

class EmailCacheHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>MyTrips - Email Import</title>
                <style>
                    body { 
                        font-family: Arial, sans-serif; 
                        margin: 40px;
                        background-color: #f5f5f5;
                    }
                    .container {
                        max-width: 800px;
                        margin: 0 auto;
                        background: white;
                        padding: 30px;
                        border-radius: 8px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }
                    h1 { color: #333; }
                    button { 
                        background-color: #4CAF50;
                        color: white;
                        padding: 12px 30px; 
                        font-size: 16px; 
                        cursor: pointer;
                        border: none;
                        border-radius: 4px;
                        margin: 10px 0;
                    }
                    button:hover { background-color: #45a049; }
                    button:disabled { 
                        background-color: #ccc; 
                        cursor: not-allowed; 
                    }
                    .status {
                        margin: 20px 0;
                        padding: 15px;
                        border-radius: 4px;
                        background-color: #f0f0f0;
                    }
                    .status.loading { background-color: #e3f2fd; }
                    .status.success { background-color: #e8f5e9; }
                    .status.error { background-color: #ffebee; }
                    .stats {
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                        gap: 15px;
                        margin: 20px 0;
                    }
                    .stat-box {
                        padding: 15px;
                        background-color: #f5f5f5;
                        border-radius: 4px;
                        text-align: center;
                    }
                    .stat-number {
                        font-size: 24px;
                        font-weight: bold;
                        color: #2196F3;
                    }
                    .stat-label {
                        font-size: 14px;
                        color: #666;
                        margin-top: 5px;
                    }
                    .progress {
                        width: 100%;
                        height: 20px;
                        background-color: #f0f0f0;
                        border-radius: 10px;
                        margin: 10px 0;
                        overflow: hidden;
                        display: none;
                    }
                    .progress-bar {
                        height: 100%;
                        background-color: #4CAF50;
                        width: 0%;
                        transition: width 0.3s ease;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>MyTrips - Email Import</h1>
                    <p>Import emails from the last year to build your travel history database.</p>
                    
                    <button id="importBtn" onclick="importEmails()">Import Emails (Last Year)</button>
                    <button id="stopBtn" onclick="stopImport()" style="background-color: #f44336; display:none;">Stop Import</button>
                    <button onclick="viewCache()">View Cached Emails</button>
                    
                    <div id="progress" class="progress">
                        <div id="progressBar" class="progress-bar"></div>
                    </div>
                    
                    <div id="progressText" style="text-align: center; margin: 10px 0; font-weight: bold; display:none;">
                        <span id="progressCount">0/0</span> emails processed
                    </div>
                    
                    <div id="status" class="status" style="display:none;"></div>
                    
                    <div id="stats" class="stats" style="display:none;">
                        <div class="stat-box">
                            <div class="stat-number" id="newEmails">0</div>
                            <div class="stat-label">New Emails Imported</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-number" id="skippedEmails">0</div>
                            <div class="stat-label">Already Cached (Skipped)</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-number" id="totalCached">0</div>
                            <div class="stat-label">Total Emails in Cache</div>
                        </div>
                    </div>
                    
                    <div id="dateRange" style="margin-top: 20px; display:none;">
                        <strong>Date Range:</strong> <span id="dateRangeText"></span>
                    </div>
                </div>
                
                <script>
                    let isImporting = false;
                    
                    async function importEmails() {
                        if (isImporting) return;
                        
                        isImporting = true;
                        const importBtn = document.getElementById('importBtn');
                        const stopBtn = document.getElementById('stopBtn');
                        
                        importBtn.disabled = true;
                        importBtn.textContent = 'Importing...';
                        stopBtn.style.display = 'inline-block';
                        
                        document.getElementById('status').style.display = 'block';
                        document.getElementById('status').className = 'status loading';
                        document.getElementById('status').innerHTML = 'Starting email import...';
                        document.getElementById('progress').style.display = 'block';
                        document.getElementById('progressText').style.display = 'block';
                        document.getElementById('stats').style.display = 'none';
                        
                        // Start progress updates
                        startProgressUpdates();
                        
                        try {
                            const response = await fetch('/api/import');
                            const data = await response.json();
                            
                            if (data.error) {
                                throw new Error(data.error);
                            }
                            
                            if (!data.started) {
                                throw new Error('Failed to start import');
                            }
                            
                            // Wait for completion and get final results
                            const finalResults = await waitForCompletion();
                            
                            if (finalResults) {
                                // Update stats
                                document.getElementById('stats').style.display = 'grid';
                                document.getElementById('newEmails').textContent = finalResults.new_emails;
                                document.getElementById('skippedEmails').textContent = finalResults.skipped_emails;
                                document.getElementById('totalCached').textContent = finalResults.total_cached;
                                
                                // Update date range
                                if (finalResults.date_range) {
                                    document.getElementById('dateRange').style.display = 'block';
                                    document.getElementById('dateRangeText').textContent = 
                                        `${finalResults.date_range.oldest} to ${finalResults.date_range.newest}`;
                                }
                                
                                // Update status
                                document.getElementById('status').className = 'status success';
                                document.getElementById('status').innerHTML = 
                                    `✅ Import completed! Imported ${finalResults.new_emails} new emails, skipped ${finalResults.skipped_emails} duplicates.`;
                            }
                            
                            // Update progress
                            document.getElementById('progressBar').style.width = '100%';
                            
                        } catch (error) {
                            document.getElementById('status').className = 'status error';
                            document.getElementById('status').innerHTML = '❌ Error: ' + error.message;
                        } finally {
                            isImporting = false;
                            importBtn.disabled = false;
                            importBtn.textContent = 'Import Emails (Last Year)';
                            stopBtn.style.display = 'none';
                            setTimeout(() => {
                                document.getElementById('progress').style.display = 'none';
                                document.getElementById('progressText').style.display = 'none';
                                document.getElementById('progressBar').style.width = '0%';
                                document.getElementById('progressCount').textContent = '0/0';
                            }, 1000);
                        }
                    }
                    
                    async function stopImport() {
                        if (!isImporting) return;
                        
                        try {
                            await fetch('/api/stop');
                            document.getElementById('status').className = 'status';
                            document.getElementById('status').innerHTML = '⏹️ Import stopped by user';
                        } catch (error) {
                            console.error('Error stopping import:', error);
                        }
                    }
                    
                    async function viewCache() {
                        window.location.href = '/cache';
                    }
                    
                    // Update progress periodically
                    async function updateProgress() {
                        if (!isImporting) return;
                        
                        try {
                            const response = await fetch('/api/progress');
                            const data = await response.json();
                            
                            if (data.progress !== undefined) {
                                document.getElementById('progressBar').style.width = data.progress + '%';
                                document.getElementById('progressCount').textContent = `${data.processed || 0}/${data.total || 0}`;
                                document.getElementById('status').innerHTML = 
                                    `Processing emails... (${data.new_count || 0} new, ${data.skip_count || 0} skipped)`;
                            }
                        } catch (error) {
                            console.error('Progress update error:', error);
                        }
                        
                        // Continue updating if still importing
                        if (isImporting) {
                            setTimeout(updateProgress, 1000);
                        }
                    }
                    
                    // Wait for import completion
                    async function waitForCompletion() {
                        return new Promise((resolve) => {
                            const checkCompletion = async () => {
                                try {
                                    const response = await fetch('/api/progress');
                                    const data = await response.json();
                                    
                                    if (data.finished) {
                                        if (data.error) {
                                            throw new Error(data.error);
                                        }
                                        resolve(data.final_results || null);
                                        return;
                                    }
                                    
                                    // Continue checking
                                    setTimeout(checkCompletion, 1000);
                                } catch (error) {
                                    resolve(null);
                                }
                            };
                            
                            checkCompletion();
                        });
                    }
                    
                    // Start progress updates when importing starts
                    function startProgressUpdates() {
                        if (isImporting) {
                            updateProgress();
                        }
                    }
                </script>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
            
        elif parsed_path.path == '/api/import':
            self.handle_import()
            
        elif parsed_path.path == '/api/progress':
            self.handle_progress()
            
        elif parsed_path.path == '/api/stop':
            self.handle_stop()
            
        elif parsed_path.path == '/cache':
            self.show_cache_view()
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def handle_import(self):
        try:
            # Start background import task
            import threading
            
            # Initialize progress tracking
            self.server.import_progress = {
                'total': 0,
                'processed': 0,
                'new_count': 0,
                'skip_count': 0,
                'should_stop': False,
                'finished': False,
                'error': None
            }
            
            # Start import in background thread
            thread = threading.Thread(target=self._background_import, daemon=True)
            thread.start()
            
            # Return immediately
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'started': True}
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_response = {'error': str(e)}
            self.wfile.write(json.dumps(error_response).encode())
    
    def _background_import(self):
        """Background import process"""
        try:
            # Initialize Gmail service
            gmail_service = GmailService()
            
            # Load existing cache
            existing_ids = self.load_cached_ids()
            
            # Search for emails from last year
            query = 'newer_than:365d'
            all_emails = []
            page_token = None
            
            # Fetch all emails with pagination
            while True:
                if page_token:
                    results = gmail_service.service.users().messages().list(
                        userId='me',
                        q=query,
                        pageToken=page_token,
                        maxResults=500
                    ).execute()
                else:
                    results = gmail_service.service.users().messages().list(
                        userId='me',
                        q=query,
                        maxResults=500
                    ).execute()
                
                messages = results.get('messages', [])
                all_emails.extend(messages)
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            self.server.import_progress['total'] = len(all_emails)
            print(f"Found {len(all_emails)} emails to process")  # Debug info
            
            # Process emails
            new_emails = 0
            skipped_emails = 0
            oldest_date = None
            newest_date = None
            
            # Ensure CSV file exists with headers
            if not os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                    writer.writeheader()
            
            # Open CSV for appending
            with open(CACHE_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                
                for i, email in enumerate(all_emails):
                    # Check if stop was requested
                    if getattr(self.server, 'import_progress', {}).get('should_stop', False):
                        break
                        
                    email_id = email['id']
                    
                    # Update progress
                    self.server.import_progress['processed'] = i + 1
                    
                    # Debug print every 50 emails
                    if i % 50 == 0:
                        print(f"Progress: {i+1}/{len(all_emails)}")
                    
                    # Skip if already cached
                    if email_id in existing_ids:
                        skipped_emails += 1
                        self.server.import_progress['skip_count'] = skipped_emails
                        continue
                    
                    # Fetch email details
                    try:
                        email_data = gmail_service.get_email(email_id)
                        
                        # Extract date for range tracking
                        date_str = email_data.get('date', '')
                        try:
                            # Parse date
                            from email.utils import parsedate_to_datetime
                            email_date = parsedate_to_datetime(date_str)
                            
                            if not oldest_date or email_date < oldest_date:
                                oldest_date = email_date
                            if not newest_date or email_date > newest_date:
                                newest_date = email_date
                        except:
                            pass
                        
                        # Write to CSV
                        writer.writerow({
                            'email_id': email_id,
                            'subject': email_data.get('subject', ''),
                            'from': email_data.get('from', ''),
                            'date': date_str,
                            'timestamp': datetime.now().isoformat(),
                            'is_classified': 'false',
                            'classification': ''
                        })
                        
                        new_emails += 1
                        self.server.import_progress['new_count'] = new_emails
                        
                    except Exception as e:
                        print(f"Error processing email {email_id}: {str(e)}")
                        continue
            
            # Count total cached emails
            total_cached = len(existing_ids) + new_emails
            
            # Mark as finished and store final results
            self.server.import_progress['finished'] = True
            self.server.import_progress['final_results'] = {
                'new_emails': new_emails,
                'skipped_emails': skipped_emails,
                'total_cached': total_cached,
                'date_range': {
                    'oldest': oldest_date.strftime('%Y-%m-%d') if oldest_date else 'N/A',
                    'newest': newest_date.strftime('%Y-%m-%d') if newest_date else 'N/A'
                }
            }
            
            print(f"Import completed: {new_emails} new, {skipped_emails} skipped")
            
        except Exception as e:
            print(f"Import error: {str(e)}")
            self.server.import_progress['error'] = str(e)
            self.server.import_progress['finished'] = True
    
    def handle_progress(self):
        progress_data = getattr(self.server, 'import_progress', {})
        
        # Calculate progress percentage
        if progress_data.get('total', 0) > 0:
            progress = (progress_data.get('processed', 0) / progress_data['total']) * 100
            progress_data['progress'] = round(progress, 1)
        else:
            progress_data['progress'] = 0
        
        # Include final results if finished
        if progress_data.get('finished') and 'final_results' in progress_data:
            progress_data['final_results'] = progress_data['final_results']
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(progress_data).encode())
    
    def handle_stop(self):
        # Set stop flag
        if hasattr(self.server, 'import_progress'):
            self.server.import_progress['should_stop'] = True
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = {'status': 'stopped'}
        self.wfile.write(json.dumps(response).encode())
    
    def show_cache_view(self):
        # Simple view of cached emails
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Email Cache</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                .back-btn { margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <div class="back-btn">
                <button onclick="window.location.href='/'">← Back to Import</button>
            </div>
            <h1>Cached Emails</h1>
        """
        
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                emails = list(reader)
                
            html += f"<p>Total emails in cache: {len(emails)}</p>"
            html += "<table><tr><th>Subject</th><th>From</th><th>Date</th><th>Classified</th></tr>"
            
            for email in emails[-100:]:  # Show last 100
                html += f"""
                <tr>
                    <td>{email.get('subject', '')[:80]}...</td>
                    <td>{email.get('from', '')[:50]}...</td>
                    <td>{email.get('date', '')[:30]}</td>
                    <td>{email.get('is_classified', 'false')}</td>
                </tr>
                """
            
            html += "</table>"
            if len(emails) > 100:
                html += f"<p>Showing last 100 of {len(emails)} emails</p>"
        else:
            html += "<p>No cached emails found.</p>"
        
        html += "</body></html>"
        self.wfile.write(html.encode())
    
    def load_cached_ids(self):
        """Load existing email IDs from cache"""
        existing_ids = set()
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing_ids.add(row['email_id'])
        return existing_ids
    
    def log_message(self, format, *args):
        # Suppress log messages for cleaner output
        pass

def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, EmailCacheHandler)
    
    print(f"🚀 Email Cache Server running at http://localhost:{port}")
    print("Press Ctrl+C to stop")
    
    # Open browser
    webbrowser.open(f'http://localhost:{port}')
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n✋ Server stopped")

if __name__ == '__main__':
    run_server()