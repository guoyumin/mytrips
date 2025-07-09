#!/bin/bash

# MyTrips Server Startup Script
# This script starts the FastAPI server for the MyTrips application

echo "Starting MyTrips server..."

# Change to backend directory
cd backend

# Create logs directory if it doesn't exist
mkdir -p ../logs

# Stop any existing server
echo "Stopping any existing server..."
pkill -f "uvicorn main:app" 2>/dev/null || true
sleep 2

# Start server in background with logging
echo "Starting server on http://0.0.0.0:8000"
nohup python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 > ../logs/server.log 2>&1 &

# Get the process ID
SERVER_PID=$!
echo "Server started with PID: $SERVER_PID"

# Wait a moment and check if server started successfully
sleep 3
if ps -p $SERVER_PID > /dev/null; then
    echo "✅ Server is running successfully!"
    echo "📝 Logs are being written to logs/server.log"
    echo "🌐 Access the application at: http://localhost:8000"
    echo "🛑 To stop the server, run: pkill -f 'uvicorn main:app'"
else
    echo "❌ Server failed to start. Check logs/server.log for details."
    exit 1
fi