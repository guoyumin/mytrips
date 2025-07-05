# MyTrips - Gmail Travel Analyzer

A web application that analyzes your Gmail emails to automatically extract and visualize your travel history.

## Features

- 🔐 Secure Gmail authentication via OAuth2
- ✈️ Automatic detection of flights, hotels, and travel activities
- 📊 Interactive dashboard with travel statistics
- 🗺️ Visual map of all your destinations
- 📁 Export trips to Excel, CSV, or PDF
- 🔄 Real-time email synchronization

## Prerequisites

- Python 3.8+
- Gmail API credentials
- Modern web browser

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/mytrips.git
   cd mytrips
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Gmail API**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable Gmail API
   - Create OAuth 2.0 credentials
   - Download credentials as `credentials.json` and place in project root

4. **Configure OAuth redirect URI**
   - Add `http://localhost:8000/api/auth/callback` to authorized redirect URIs

5. **Run the application**
   ```bash
   cd backend
   python main.py
   ```

6. **Access the application**
   - Open browser to `http://localhost:8000`
   - Click "Connect Gmail Account" to authorize
   - Start analyzing your travel emails!

## Project Structure

```
mytrips/
├── backend/
│   ├── api/            # API endpoints
│   ├── models/         # Data models
│   ├── services/       # Business logic
│   └── main.py         # FastAPI application
├── frontend/
│   ├── static/         # CSS, JS files
│   └── templates/      # HTML templates
├── tests/              # Test files
├── requirements.txt    # Python dependencies
└── README.md
```

## API Documentation

Once running, access the interactive API docs at `http://localhost:8000/docs`

## Security

- OAuth2 authentication for Gmail access
- Read-only Gmail permissions
- Credentials stored locally (not in repo)
- CORS configured for security

## License

MIT License