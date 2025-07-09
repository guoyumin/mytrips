# Model Tier System

The AI provider system now supports a tier-based model selection, allowing services to choose between "fast" and "powerful" models without hardcoding specific model names.

## Usage

### Service Layer Usage

Services can now request models by performance tier instead of specific model names:

```python
from lib.ai.ai_provider_factory import AIProviderFactory

# For fast, cost-effective operations (e.g., email classification)
fast_provider = AIProviderFactory.create_provider(model_tier='fast')

# For complex reasoning tasks (e.g., trip detection)
powerful_provider = AIProviderFactory.create_provider(model_tier='powerful')

# Optionally specify provider
openai_fast = AIProviderFactory.create_provider(model_tier='fast', provider_name='openai')
claude_powerful = AIProviderFactory.create_provider(model_tier='powerful', provider_name='claude')
```

### Environment Configuration

Set the default provider via environment variable:

```bash
# Use Gemini as default provider
export AI_PROVIDER=gemini

# Use OpenAI as default provider
export AI_PROVIDER=openai

# Use Claude as default provider
export AI_PROVIDER=claude
```

## Model Tier Mappings

The actual models used for each tier are configured in the respective config files:

### Gemini (`config/gemini_config.json`)
- **fast**: `gemini-2.5-flash`
- **powerful**: `gemini-2.5-pro`

### OpenAI (`config/openai_config.json`)
- **fast**: `gpt-4o-mini`
- **powerful**: `gpt-4-turbo-preview`

### Claude (`config/claude_config.json`)
- **fast**: `claude-3-5-haiku-20241022`
- **powerful**: `claude-sonnet-4-20250514`

## Service Recommendations

### Use "fast" tier for:
- Email classification
- Initial content extraction
- High-volume operations
- Real-time responses
- Cost-sensitive operations

### Use "powerful" tier for:
- Trip detection and analysis
- Complex reasoning tasks
- Data synthesis from multiple sources
- Critical accuracy requirements
- Lower-volume, high-value operations

## Examples in Current Services

1. **EmailClassificationService**: Uses `fast` tier for classifying large volumes of emails
2. **EmailBookingExtractionService**: Uses `fast` tier for extracting booking information
3. **TripDetectionService**: Uses `powerful` tier for complex trip analysis and organization

## Backward Compatibility

For specific model requirements, you can still create providers with exact model names:

```python
# Create provider with specific model
specific_provider = AIProviderFactory.create_provider_direct('gemini-2.5-flash')
```

## Benefits

1. **Abstraction**: Services don't need to know specific model names
2. **Flexibility**: Easy to update models by changing config files
3. **Cost Optimization**: Services automatically use appropriate tier for their use case
4. **Provider Switching**: Easy to switch between providers while maintaining tier semantics
5. **Future-Proof**: New models can be added to configs without changing service code