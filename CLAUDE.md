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
pytest tests/microservices/

# Run with verbose output
pytest tests/ -v

# Run a specific test file
pytest tests/email_classification/test_classification_workflow.py

# Run tests with coverage
pytest tests/ --cov=backend

# Quick test utility
python tests/utils/quick_test.py

# Generate trip detection test summary
python tests/trip_detection/generate_summary.py
```

### Development Tools
```bash
# Install dependencies
pip install -r requirements.txt

# Install minimal dependencies (without optional AI providers)
pip install -r requirements-minimal.txt

# Install web scraping dependencies
pip install -r requirements-web.txt

# Code formatting
black backend/

# Code linting
flake8 backend/
```

### Data Management
```bash
# Reset all email data (clear database)
curl -X POST http://localhost:8000/api/emails/reset-all

# Reset only email classifications
curl -X POST http://localhost:8000/api/emails/reset-classification

# Reset content extraction
curl -X POST http://localhost:8000/api/content/reset

# Reset booking extraction
curl -X POST http://localhost:8000/api/content/reset-booking

# Reset trip detection
curl -X POST http://localhost:8000/api/trips/detection/reset

# Quick reset commands (if .claude/commands.yml is configured)
claude reset_all    # Reset all email and trip data
claude reset_emails # Reset only email data
claude reset_trips  # Reset only trip data
```

## Architecture Overview

### Core Components
- **FastAPI Backend** (`backend/main.py`): Main application server serving both API and frontend at port 8000
- **Database Layer** (`backend/database/`): SQLAlchemy models for emails, trips, and content
- **AI Services** (`backend/lib/ai/`): Multi-provider AI system supporting Gemini, OpenAI, Claude, and local models
- **Email Processing Pipeline** (`backend/services/pipeline/`): Parallel processing pipeline with stages
- **Frontend** (`frontend/`): Static HTML/CSS/JS interface served by FastAPI

### Key Services
1. **Email Pipeline Service V2** (`backend/services/email_pipeline_service_v2.py`): Orchestrates the entire email processing flow
2. **Pipeline Stages** (`backend/services/pipeline/`): 
   - Import Stage: Fetches emails from Gmail
   - Classification Stage: Categorizes travel-related emails
   - Content Extraction Stage: Extracts structured data
   - Booking Extraction Stage: Parses booking details
   - Trip Detection Stage: Groups bookings into trips
3. **Microservices** (`backend/services/micro/`): Base classes for microservice architecture
4. **Gmail Client** (`backend/lib/gmail_client.py`): Handles OAuth2 authentication and email fetching

### AI Provider System
The application uses a factory pattern (`backend/lib/ai/ai_provider_factory.py`) with automatic fallback:
- **GeminiProvider**: Google Gemini models (default)
- **OpenAIProvider**: GPT models  
- **ClaudeProvider**: Anthropic Claude models
- **DeepSeekProvider**: DeepSeek models
- **LocalProviders**: Gemma3 and other local models

Models are organized by tiers (fast, standard, advanced) with automatic fallback and rate limiting.

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

### Email Processing Pipeline
The system uses a parallel processing pipeline with queue-based communication:
1. **Import Stage**: Fetches emails from Gmail API via OAuth2
2. **Classification Stage**: AI categorizes emails as travel-related
3. **Content Extraction Stage**: Extracts structured data from email HTML/text
4. **Booking Extraction Stage**: Parses specific booking details (flights, hotels, etc.)
5. **Trip Detection Stage**: Groups related bookings into coherent trips

Each stage can be stopped/started independently and processes data in parallel batches.

### AI Integration
- Use `AIProviderFactory.get_provider()` for AI interactions
- Providers support different model tiers: fast, standard, advanced
- Automatic fallback chain: Gemini → OpenAI → Claude → DeepSeek → Local
- Rate limiting and error handling built into provider system
- Model pricing tracked in `config/gemini_pricing.json`

### Database Operations
- SQLAlchemy ORM with proper session management
- Tables include indexes for performance (email date, classification status)
- Support for incremental updates and batch operations
- Transaction support for data consistency

### Frontend Integration
- Single-page application served at `/`
- Real-time progress updates via WebSocket/polling
- API endpoints prefixed with `/api/`
- Interactive Swagger docs at `/docs`

### Gmail OAuth Setup
1. Create project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Gmail API
3. Create OAuth 2.0 credentials (Web application type)
4. Download as `credentials.json` to project root
5. Add authorized redirect URI: `http://localhost:8000/api/auth/callback`
6. First run will open browser for authorization

### Testing Strategy
The test suite is organized by functionality and complexity:
- **Unit Tests**: Model and utility function tests
- **Integration Tests**: API endpoint and service tests
- **AI Provider Tests**: Multi-provider compatibility testing
- **Trip Detection Levels** (1-5): Progressive complexity from single bookings to edge cases
- Test data based on real email structures for accuracy