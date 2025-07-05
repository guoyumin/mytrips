#!/usr/bin/env python3
"""
Simple test server to verify progress and stop functionality
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
import threading

class TestProgressHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Progress Test</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    button { padding: 10px 20px; margin: 5px; }
                    .stop { background-color: #f44336; color: white; }
                    .progress { width: 100%; height: 20px; background: #f0f0f0; margin: 10px 0; }
                    .progress-bar { height: 100%; background: #4CAF50; width: 0%; transition: width 0.3s; }
                </style>
            </head>
            <body>
                <h1>Progress Test</h1>
                <button onclick="startTest()">Start Test</button>
                <button class="stop" onclick="stopTest()">Stop Test</button>
                
                <div class="progress">
                    <div id="progressBar" class="progress-bar"></div>
                </div>
                
                <div id="progress">0/0</div>
                <div id="status">Ready</div>
                
                <script>
                    let isRunning = false;
                    
                    async function startTest() {
                        if (isRunning) return;
                        isRunning = true;
                        
                        document.getElementById('status').textContent = 'Starting...';
                        
                        try {
                            const response = await fetch('/api/start');
                            const data = await response.json();
                            
                            if (data.success) {
                                updateProgress();
                            }
                        } catch (error) {
                            console.error('Start error:', error);
                        }
                    }
                    
                    async function stopTest() {
                        try {
                            const response = await fetch('/api/stop');
                            const data = await response.json();
                            document.getElementById('status').textContent = 'Stopped by user';
                        } catch (error) {
                            console.error('Stop error:', error);
                        }
                    }
                    
                    async function updateProgress() {
                        if (!isRunning) return;
                        
                        try {
                            const response = await fetch('/api/progress');
                            const data = await response.json();
                            
                            document.getElementById('progress').textContent = `${data.current}/${data.total}`;
                            document.getElementById('progressBar').style.width = data.percent + '%';
                            document.getElementById('status').textContent = data.status;
                            
                            if (data.finished) {
                                isRunning = false;
                                document.getElementById('status').textContent = 'Finished!';
                                return;
                            }
                        } catch (error) {
                            console.error('Progress error:', error);
                        }
                        
                        if (isRunning) {
                            setTimeout(updateProgress, 500);
                        }
                    }
                </script>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
            
        elif self.path == '/api/start':
            self.handle_start()
        elif self.path == '/api/stop':
            self.handle_stop()
        elif self.path == '/api/progress':
            self.handle_progress()
        else:
            self.send_response(404)
            self.end_headers()
    
    def handle_start(self):
        # Start background task
        self.server.task_data = {
            'total': 100,
            'current': 0,
            'should_stop': False,
            'finished': False
        }
        
        threading.Thread(target=self.background_task, daemon=True).start()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'success': True}).encode())
    
    def handle_stop(self):
        if hasattr(self.server, 'task_data'):
            self.server.task_data['should_stop'] = True
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'stopped': True}).encode())
    
    def handle_progress(self):
        data = getattr(self.server, 'task_data', {
            'total': 0,
            'current': 0,
            'should_stop': False,
            'finished': True
        })
        
        percent = (data['current'] / data['total'] * 100) if data['total'] > 0 else 0
        
        response = {
            'total': data['total'],
            'current': data['current'],
            'percent': round(percent, 1),
            'status': f"Processing {data['current']}/{data['total']}",
            'finished': data['finished']
        }
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def background_task(self):
        """Simulate a long-running task"""
        for i in range(1, 101):
            if self.server.task_data['should_stop']:
                break
                
            self.server.task_data['current'] = i
            time.sleep(0.1)  # Simulate work
        
        self.server.task_data['finished'] = True
        print("Background task completed")

def run_test_server(port=8001):
    server_address = ('', port)
    httpd = HTTPServer(server_address, TestProgressHandler)
    
    print(f"🧪 Test server running at http://localhost:{port}")
    print("Press Ctrl+C to stop")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n✋ Test server stopped")

if __name__ == '__main__':
    run_test_server()