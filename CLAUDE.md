# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Starting the Application
```bash
# Start the server (recommended)
./start_server.sh

# Or start manually
cd backend && python main.py
```

### Testing
```bash
# Run tests from project root
pytest tests/

# Run specific test categories
pytest tests/email_classification/
pytest tests/trip_detection/
pytest tests/ai_connection/
```

### Development Tools
```bash
# Install dependencies
pip install -r requirements.txt

# Code formatting (if needed)
black backend/
flake8 backend/
```

## Architecture Overview

### Core Components
- **FastAPI Backend** (`backend/main.py`): Main application server serving both API and frontend
- **Database Layer** (`backend/database/`): SQLAlchemy models for emails, trips, and content
- **AI Services** (`backend/lib/ai/`): Multi-provider AI system supporting Gemini, OpenAI, and Claude
- **Email Processing** (`backend/services/`): Gmail integration, classification, and trip detection
- **Frontend** (`frontend/`): Static HTML/CSS/JS interface

### Key Services
1. **Email Classification Service**: Categorizes emails as travel-related using AI
2. **Trip Detection Service**: Extracts trip information from classified emails
3. **Content Extraction Service**: Processes email content for structured data
4. **Rate Limiter**: Manages API rate limits across different AI providers

### AI Provider System
The application uses a factory pattern for AI providers:
- **GeminiProvider**: Google Gemini models (default)
- **OpenAIProvider**: GPT models
- **ClaudeProvider**: Anthropic Claude models

Models are organized by tiers (fast, standard, advanced) with automatic fallback.

### Database Schema
- **emails**: Gmail message storage with classification status
- **trips**: Extracted trip information 
- **email_content**: Structured email content storage
- **booking_extractions**: Parsed booking details

### Configuration
- AI provider configs in `config/` directory
- Model pricing and rate limits defined in JSON files
- OAuth credentials for Gmail API access

## Key File Locations

### Core Application Files
- `backend/main.py`: FastAPI application entry point
- `backend/database/models.py`: Database model definitions
- `backend/lib/ai/ai_provider_factory.py`: AI provider management
- `backend/services/`: Business logic services

### Configuration Files
- `config/gemini_config.json`: Gemini API configuration
- `config/openai_config.json`: OpenAI API configuration
- `config/claude_config.json`: Claude API configuration
- `config/app_config.json`: Application settings

### Testing Structure
- `tests/ai_connection/`: AI provider connectivity tests
- `tests/email_classification/`: Email classification workflow tests
- `tests/trip_detection/`: Trip detection logic tests
- `tests/fixtures/`: Test data and configuration

## Development Notes

### Email Processing Flow
1. Gmail API fetches emails
2. Email classification service categorizes messages
3. Trip detection service extracts travel information
4. Content extraction service parses booking details
5. Results stored in database for frontend display

### AI Integration
- Use the AI provider factory for consistent AI interactions
- Implement proper error handling and rate limiting
- Consider model tiers when selecting providers for different tasks

### Database Operations
- Use SQLAlchemy ORM for all database interactions
- Implement proper indexing for performance
- Handle concurrent access with appropriate locking

### Frontend Integration
- FastAPI serves static files from `frontend/static/`
- API endpoints are prefixed with `/api/`
- Use CORS middleware for cross-origin requests