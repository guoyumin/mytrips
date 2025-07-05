#!/usr/bin/env python3
"""
Simple web server to test Gmail integration without complex dependencies
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import webbrowser
from urllib.parse import parse_qs, urlparse

# Import our Gmail service
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.services.gmail_service import GmailService

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
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
                <title>MyTrips - Simple Test</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    button { padding: 10px 20px; font-size: 16px; cursor: pointer; }
                    .email-list { margin-top: 20px; }
                    .email-item { padding: 10px; border-bottom: 1px solid #eee; }
                </style>
            </head>
            <body>
                <h1>MyTrips - Gmail Integration Test</h1>
                <button onclick="fetchEmails()">Fetch Recent Emails</button>
                <div id="status"></div>
                <div id="emails" class="email-list"></div>
                
                <script>
                    async function fetchEmails() {
                        document.getElementById('status').innerHTML = 'Loading...';
                        try {
                            const response = await fetch('/api/emails');
                            const data = await response.json();
                            
                            if (data.error) {
                                document.getElementById('status').innerHTML = 'Error: ' + data.error;
                                return;
                            }
                            
                            document.getElementById('status').innerHTML = `Found ${data.count} emails`;
                            
                            let html = '';
                            data.emails.forEach((email, index) => {
                                html += `<div class="email-item">
                                    <strong>${index + 1}. ${email.subject}</strong><br>
                                    From: ${email.from}<br>
                                    Date: ${email.date}
                                </div>`;
                            });
                            document.getElementById('emails').innerHTML = html;
                        } catch (error) {
                            document.getElementById('status').innerHTML = 'Error: ' + error.message;
                        }
                    }
                </script>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
            
        elif parsed_path.path == '/api/emails':
            try:
                gmail_service = GmailService()
                emails = gmail_service.search_emails('newer_than:10d', max_results=10)
                
                email_list = []
                for email in emails:
                    email_data = gmail_service.get_email(email['id'])
                    email_list.append({
                        'subject': email_data.get('subject', 'No Subject'),
                        'from': email_data.get('from', 'Unknown'),
                        'date': email_data.get('date', 'Unknown Date')
                    })
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                response = {
                    'count': len(email_list),
                    'emails': email_list
                }
                self.wfile.write(json.dumps(response).encode())
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                error_response = {'error': str(e)}
                self.wfile.write(json.dumps(error_response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress log messages for cleaner output
        pass

def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    
    print(f"🚀 Server running at http://localhost:{port}")
    print("Press Ctrl+C to stop")
    
    # Open browser
    webbrowser.open(f'http://localhost:{port}')
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n✋ Server stopped")

if __name__ == '__main__':
    run_server()