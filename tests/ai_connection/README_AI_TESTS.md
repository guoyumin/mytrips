# AI Provider Tests

This directory contains tests for the AI provider system, including connectivity tests, factory tests, and model tier verification.

## Test Files

### 1. `test_ai_connectivity.py`
Quick connectivity test for all AI providers. This is the primary test to run to verify your AI configuration.

**Usage:**
```bash
python test_ai_connectivity.py
```

**What it tests:**
- API key configuration for each provider
- Connectivity to each AI service
- Response time comparison
- Model availability for each tier

**Output:**
- Console output with success/failure for each provider-tier combination
- JSON results file: `ai_connectivity_results.json`

### 2. `test_ai_providers.py`
Comprehensive pytest suite for AI providers.

**Usage:**
```bash
pytest test_ai_providers.py -v -s
```

**Test cases:**
- `test_provider_factory_tier_creation`: Tests creating providers using the tier system
- `test_connectivity_all_providers`: Tests actual API connectivity for all providers
- `test_specific_models_direct`: Tests creating providers with specific model names
- `test_cost_estimation`: Compares cost estimates across providers
- `test_fallback_mechanism`: Tests automatic fallback when primary provider fails

### 3. `test_ai_factory.py`
Unit tests for the AI Provider Factory.

**Usage:**
```bash
pytest test_ai_factory.py -v
```

**Test cases:**
- Provider mapping configuration
- Model tier definitions
- Config file loading and fallback mechanisms
- Provider creation with various parameters
- Error handling and edge cases

### 4. `test_model_tiers.py`
Tests for the model tier abstraction system.

**Usage:**
```bash
python test_model_tiers.py
```

**What it tests:**
- Configuration file validity
- Tier mappings for all providers
- Cost ordering (fast < powerful)
- Service tier usage verification

## Configuration Requirements

Before running tests, ensure you have configured API keys in the following files:

1. `/config/gemini_config.json` - Gemini API key
2. `/config/openai_config.json` - OpenAI API key
3. `/config/claude_config.json` - Claude API key

## Running All Tests

To run all AI tests:

```bash
# Quick connectivity check
python test_ai_connectivity.py

# Full test suite
pytest test_ai_*.py -v

# With coverage
pytest test_ai_*.py --cov=lib.ai --cov-report=html
```

## Interpreting Results

### Connectivity Test Results

**Success indicators:**
- ✅ Provider configured and responding
- Response time under 5000ms
- Valid response received

**Failure indicators:**
- ❌ API key not configured
- ❌ Network/API errors
- ❌ Invalid responses

### Common Issues

1. **"API key not configured"**
   - Check that the config file exists
   - Ensure API key is set and not the default placeholder

2. **"Network error" or timeout**
   - Check internet connectivity
   - Verify API service status
   - Check firewall/proxy settings

3. **"Model not found"**
   - Verify model name in config file
   - Check if model is available in your API plan

## Cost Considerations

Running these tests will make actual API calls and incur costs:

- **Gemini**: Generally free for testing volumes
- **OpenAI**: Charges per token (minimal for test prompts)
- **Claude**: Charges per token (minimal for test prompts)

The test prompts are intentionally short ("Say Hello World", "Respond with OK") to minimize costs.

## Adding New Tests

When adding new AI provider tests:

1. Use minimal prompts to reduce costs
2. Mock expensive operations when possible
3. Add appropriate error handling
4. Document expected outcomes
5. Consider rate limits and quotas

## Continuous Integration

For CI/CD pipelines, consider:

1. Using mock responses for most tests
2. Running real connectivity tests only on schedule (e.g., daily)
3. Setting up test API keys with limited quotas
4. Monitoring test costs