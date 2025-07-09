# AI Provider Configuration

This system supports multiple AI providers with easy switching capability.

## Architecture

The AI provider system follows proper dependency inversion:

```
services/                    # Service layer (orchestration)
├── trip_detection_service.py
├── email_booking_extraction_service.py
└── email_classification_service.py

lib/                        # Business logic layer
├── ai/                     # AI abstraction (moved from services/)
│   ├── ai_provider_interface.py
│   ├── ai_provider_factory.py
│   └── providers/
│       ├── gemini_provider.py
│       └── openai_provider.py
├── trip_detector.py       # Uses injected AIProvider
├── email_classifier.py    # Uses injected AIProvider
└── email_content_extractor.py

```

All business logic components (`TripDetector`, `EmailClassifier`) receive AI providers through dependency injection, maintaining separation of concerns.

## Supported Providers

### Current
- **Gemini** (Google): `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-1.5-flash`, `gemini-1.5-pro`
- **OpenAI**: `gpt-4-turbo-preview`, `gpt-4`, `gpt-3.5-turbo`
- **Claude** (Anthropic): `claude-3-opus-20240229`, `claude-3-sonnet-20240229`, `claude-3-haiku-20240307`

## Configuration

### Model Tier System
Services now use a tier-based system ("fast" or "powerful") instead of specific model names. See [MODEL_TIERS.md](MODEL_TIERS.md) for details.

### Environment Variables
Set the `AI_PROVIDER` environment variable to specify which provider to use:

```bash
# Use Gemini (default)
export AI_PROVIDER=gemini

# Use OpenAI
export AI_PROVIDER=openai

# Use Claude
export AI_PROVIDER=claude
```

### Required Configuration Files
- **Gemini**: `config/gemini_config.json` (already configured)
- **OpenAI**: `config/openai_config.json` (configure with your API key)
- **Claude**: `config/claude_config.json` (configure with your API key)

### Runtime Switching
You can also programmatically create specific providers:

```python
from lib.ai.ai_provider_factory import AIProviderFactory

# Create providers by tier
fast_provider = AIProviderFactory.create_provider(model_tier='fast')
powerful_provider = AIProviderFactory.create_provider(model_tier='powerful')

# Create providers by tier and provider
gemini_fast = AIProviderFactory.create_provider('fast', 'gemini')
openai_powerful = AIProviderFactory.create_provider('powerful', 'openai')
claude_fast = AIProviderFactory.create_provider('fast', 'claude')
```

## Fallback Strategy

The system automatically falls back to available models if the primary choice fails:
1. Try requested model
2. Fall back to `gemini-2.5-flash`
3. Fall back to `gemini-1.5-flash`

## Architecture Benefits

1. **Business Logic Separation**: All prompt building, response parsing, and error handling remains in the business logic layer
2. **Easy Switching**: Change providers with just an environment variable
3. **Fallback Support**: Automatic graceful degradation if primary provider fails
4. **Cost Optimization**: Switch to cheaper models for development/testing
5. **Performance Tuning**: Switch to faster models when needed

## Usage Examples

### Development (Fast & Cheap)
```bash
export AI_PROVIDER=gemini  # Uses gemini-2.5-flash for 'fast' tier
```

### Production (High Quality)
```bash
export AI_PROVIDER=gemini  # Uses gemini-2.5-pro for 'powerful' tier
```

### OpenAI Alternative
```bash
export AI_PROVIDER=openai
# Configure config/openai_config.json with your API key
# Uses gpt-4o-mini for 'fast', gpt-4-turbo-preview for 'powerful'
```

### Claude Alternative (Best for complex reasoning)
```bash
export AI_PROVIDER=claude
# Configure config/claude_config.json with your API key
# Uses claude-3-5-haiku for 'fast', claude-sonnet-4 for 'powerful'
```

## Troubleshooting

If Gemini is experiencing 500 errors:
1. Switch to Claude: `export AI_PROVIDER=claude`
2. Switch to OpenAI: `export AI_PROVIDER=openai`
3. Check logs for specific error messages
4. The system will automatically fall back to alternative providers

The system will automatically log which provider is being used and handle provider-specific errors gracefully.