#!/usr/bin/env python3
"""
Script to update relative imports to absolute imports in backend files
"""
import os
import re
from pathlib import Path

# Define the replacements
IMPORT_REPLACEMENTS = [
    # Standard imports
    (r'^from database import', 'from backend.database import'),
    (r'^from models import', 'from backend.models import'),
    (r'^from services import', 'from backend.services import'),
    (r'^from lib import', 'from backend.lib import'),
    (r'^from api import', 'from backend.api import'),
    
    # From module.submodule patterns
    (r'^from database\.', 'from backend.database.'),
    (r'^from models\.', 'from backend.models.'),
    (r'^from services\.', 'from backend.services.'),
    (r'^from lib\.', 'from backend.lib.'),
    (r'^from api\.', 'from backend.api.'),
    
    # Import ... as patterns
    (r'^import database\.', 'import backend.database.'),
    (r'^import models\.', 'import backend.models.'),
    (r'^import services\.', 'import backend.services.'),
    (r'^import lib\.', 'import backend.lib.'),
    (r'^import api\.', 'import backend.api.'),
]

# Files to process
FILES_TO_UPDATE = [
    "backend/analyze_trip_detection_failures.py",
    "backend/api/content_router.py",
    "backend/api/email_router.py",
    "backend/api/trips_router.py",
    "backend/create_missing_tables.py",
    "backend/create_trip_tables.py",
    "backend/database/init_db.py",
    "backend/database/models.py",
    "backend/drop_content_extracted_column.py",
    "backend/lib/ai/ai_provider_factory.py",
    "backend/lib/ai/providers/claude_provider.py",
    "backend/lib/ai/providers/deepseek_provider.py",
    "backend/lib/ai/providers/gemini_provider.py",
    "backend/lib/ai/providers/gemma3_provider.py",
    "backend/lib/ai/providers/openai_provider.py",
    "backend/lib/email_cache_db.py",
    "backend/lib/email_classifier.py",
    "backend/lib/trip_detector.py",
    "backend/main.py",
    "backend/migrate_csv_to_db.py",
    "backend/models/repositories/trip_repository.py",
    "backend/models/trip.py",
    "backend/reset_booking_extraction.py",
    "backend/reset_failed_trip_detection.py",
    "backend/services/email_booking_extraction_service.py",
    "backend/services/email_cache_service.py",
    "backend/services/email_classification_service.py",
    "backend/services/email_content_service.py",
    "backend/services/trip_detection_service.py",
    "backend/test_array_format.py",
    "backend/migrate_booking_extraction_fields.py",
    "backend/migrate_trips_table.py",
    "backend/update_gemini_pricing.py",
]

# Special files with relative imports
RELATIVE_IMPORT_FILES = {
    "backend/lib/ai/__init__.py": [
        (r'^from \.ai_provider_interface import', 'from backend.lib.ai.ai_provider_interface import'),
        (r'^from \.ai_provider_factory import', 'from backend.lib.ai.ai_provider_factory import'),
    ],
    "backend/api/gmail_router.py": [
        (r'^from \.\.services\.gmail_service import', 'from backend.services.gmail_service import'),
        (r'^from \.\.database import', 'from backend.database import'),
        (r'^from \.\.lib import', 'from backend.lib import'),
    ]
}


def update_file(filepath, replacements):
    """Update imports in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Updated: {filepath}")
            return True
        else:
            print(f"⏭️  No changes: {filepath}")
            return False
    except FileNotFoundError:
        print(f"❌ Not found: {filepath}")
        return False
    except Exception as e:
        print(f"❌ Error in {filepath}: {e}")
        return False


def main():
    """Main function"""
    print("Starting import updates...\n")
    
    updated_count = 0
    
    # Update standard imports
    print("Updating standard imports...")
    for filepath in FILES_TO_UPDATE:
        if update_file(filepath, IMPORT_REPLACEMENTS):
            updated_count += 1
    
    # Update relative imports
    print("\nUpdating relative imports...")
    for filepath, replacements in RELATIVE_IMPORT_FILES.items():
        if update_file(filepath, replacements):
            updated_count += 1
    
    print(f"\n✅ Updated {updated_count} files")
    

if __name__ == "__main__":
    main()