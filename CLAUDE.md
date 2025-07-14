# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Starting the Application
```bash
# Start the server (recommended) - handles PYTHONPATH and logging
./start_server.sh

# Or start manually
cd backend && python main.py

# Stop the server
pkill -f 'uvicorn main:app'
```

### Testing
```bash
# Run all tests from project root
pytest tests/

# Run specific test categories
pytest tests/email_classification/
pytest tests/trip_detection/
pytest tests/ai_connection/
pytest tests/booking_extraction/
pytest tests/content_extraction/
pytest tests/email_import/
pytest tests/unit/

# Run with verbose output
pytest tests/ -v

# Run a specific test file
pytest tests/email_classification/test_classification_workflow.py

# Quick test utility
python tests/utils/quick_test.py
```

### Development Tools
```bash
# Install dependencies
pip install -r requirements.txt

# Code formatting
black backend/

# Code linting
flake8 backend/
```

## Architecture Overview

### Core Components
- **FastAPI Backend** (`backend/main.py`): Main application server serving both API and frontend at port 8000
- **Database Layer** (`backend/database/`): SQLAlchemy models for emails, trips, and content
- **AI Services** (`backend/lib/ai/`): Multi-provider AI system supporting Gemini, OpenAI, Claude, and local models
- **Email Processing** (`backend/services/`): Gmail integration, classification, and trip detection
- **Frontend** (`frontend/`): Static HTML/CSS/JS interface served by FastAPI

### Key Services
1. **Email Classification Service**: Categorizes emails as travel-related using AI
2. **Trip Detection Service**: Extracts trip information from classified emails
3. **Content Extraction Service**: Processes email content for structured data
4. **Email Booking Extraction Service**: Parses booking details from emails
5. **Rate Limiter**: Manages API rate limits across different AI providers
6. **Gmail Service**: Handles OAuth2 authentication and email fetching

### AI Provider System
The application uses a factory pattern for AI providers with automatic fallback:
- **GeminiProvider**: Google Gemini models (default)
- **OpenAIProvider**: GPT models
- **ClaudeProvider**: Anthropic Claude models
- **DeepSeekProvider**: DeepSeek models
- **LocalProviders**: Gemma3 and other local models

Models are organized by tiers (fast, standard, advanced) with automatic fallback.

### Database Schema
- **emails**: Gmail message storage with classification status (indexes on date/classification)
- **trips**: Extracted trip information with cost tracking
- **email_content**: Structured email content storage
- **booking_extractions**: Parsed booking details
- **transport_segments**: Flight/train/bus segments
- **accommodations**: Hotel bookings
- **tour_activities**: Tourism activities
- **cruises**: Cruise bookings

### Configuration
- AI provider configs in `config/` directory
- Model pricing in `config/gemini_pricing.json`
- Rate limits in `config/gemini_rate_limits.json`
- OAuth credentials: `credentials.json` (not in repo)
- Application logs: `logs/server.log`

## Key File Locations

### Core Application Files
- `backend/main.py`: FastAPI application entry point
- `backend/database/models.py`: Database model definitions
- `backend/database/config.py`: Database configuration
- `backend/lib/ai/ai_provider_factory.py`: AI provider management
- `backend/services/gmail_service.py`: Gmail API integration
- `backend/services/email_classification_service.py`: Email categorization
- `backend/services/trip_detection_service.py`: Trip extraction logic

### API Routes
- `backend/api/auth_router.py`: OAuth authentication endpoints
- `backend/api/email_router.py`: Email management endpoints
- `backend/api/trips_router.py`: Trip data endpoints
- `backend/api/content_router.py`: Email content endpoints

### Configuration Files
- `config/gemini_config.json`: Gemini API configuration
- `config/openai_config.json`: OpenAI API configuration
- `config/claude_config.json`: Claude API configuration
- `config/deepseek_config.json`: DeepSeek API configuration
- `config/app_config.json`: Application settings

### Testing Structure
- `tests/ai_connection/`: AI provider connectivity tests
- `tests/email_classification/`: Email classification workflow tests
- `tests/trip_detection/`: Trip detection logic tests with test data levels 1-5
- `tests/booking_extraction/`: Booking detail extraction tests
- `tests/content_extraction/`: Email content processing tests
- `tests/email_import/`: Gmail integration tests
- `tests/unit/`: Unit tests for models
- `tests/fixtures/`: Test data and configuration
- `tests/utils/`: Test utilities including quick_test.py

## Development Notes

### Email Processing Flow
1. Gmail API fetches emails via OAuth2
2. Email classification service categorizes messages
3. Trip detection service extracts travel information
4. Content extraction service parses booking details
5. Results stored in database for frontend display

### AI Integration
- Use the AI provider factory for consistent AI interactions
- Implement proper error handling and rate limiting
- Consider model tiers when selecting providers for different tasks
- Provider fallback chain: Gemini → OpenAI → Claude → DeepSeek

### Database Operations
- Use SQLAlchemy ORM for all database interactions
- Database includes proper indexing for performance
- Handle concurrent access with appropriate locking
- Chinese comments in models.py indicate internationalization support

### Frontend Integration
- FastAPI serves static files from `frontend/static/`
- API endpoints are prefixed with `/api/`
- OAuth redirect URI: `http://localhost:8000/api/auth/callback`
- Interactive API docs available at `/docs`

### Gmail OAuth Setup
1. Create project in Google Cloud Console
2. Enable Gmail API
3. Create OAuth 2.0 credentials
4. Download as `credentials.json` to project root
5. Add redirect URI: `http://localhost:8000/api/auth/callback`

### Trip Detection Levels
The test suite includes 5 levels of complexity:
- Level 1: Single booking scenarios
- Level 2: Multi-booking trips
- Level 3: Existing trip modifications
- Level 4: Complex relationships (cancellations, modifications)
- Level 5: Edge cases (cross-year trips, same-day trips)