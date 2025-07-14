# TODO: Parallel Email Processing Refactoring

## Core Objective
Improve email processing performance by converting the current serial processing to parallel processing.

## Specific Requirements

### 1. Parallel Import and Classification
- When importing emails, after each batch of email headers is imported, immediately send them to AI for classification
- Don't wait for all emails to be imported before starting classification

### 2. Two-Stage Classification Mechanism
- **Stage 1**: Use local AI (currently: deepseek/gemma3) for initial classification (lower accuracy)
- **Stage 2**: After initial classification, send emails marked as "travel" to public AI (gemini/openai) for verification
- **Purpose**: Remove false positives (non-travel emails incorrectly marked as travel)

### 3. Parallel Content Extraction
- After the first batch of secondary classification is complete, immediately start extracting content for verified travel emails
- Don't wait for all emails to be classified

### 4. Real-time Booking Extraction
- After each email content is extracted, immediately send it to AI for booking extraction
- Don't wait for all email content to be extracted

## Refactoring Requirements

### Implementation Approach
- Implement in steps
- Preserve existing services while adding new parallel processing service
- Each subsequent step should also be implemented incrementally

### Step 1: Extract Logic from Service to Lib Layer
- Review service layer to identify logic that should be moved to lib layer
- Purpose: Enable reuse of logic in both existing services and new parallel service
- Reference patterns:
  - **Bad pattern**: `email_booking_extraction_service` - all logic in service layer
  - **Good pattern**: `trip_detection_service` - most logic in lib layer

### Refactoring Principles
- Avoid over-engineering (no need for complex common pipeline architecture)
- Focus on practical extraction of reusable logic
- Service layer: orchestration, progress tracking, threading, database operations
- Lib layer: pure business logic without database dependencies

## Current Architecture Notes

### Service Layer (handles orchestration)
- Progress tracking
- Thread management
- Database operations
- Batch processing coordination

### Lib Layer (pure business logic)
- `email_classifier.py` - AI classification logic
- `trip_detector.py` - Trip detection logic
- `email_content_extractor.py` - Email content extraction logic
- **Missing**: Booking extraction logic (currently all in service layer)

## Next Steps
1. Extract booking extraction logic to lib layer
2. Design two-stage classification system
3. Implement parallel processing coordination
4. Update API endpoints for parallel pipeline
5. Add configuration for parallel processing parameters