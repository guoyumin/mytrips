# Import Refactoring Documentation

## Overview
We have refactored all Python imports in the backend to use absolute imports starting with `backend.`. This makes the codebase more consistent and allows tests to be run from any directory.

## Changes Made

### 1. Updated Import Statements
All relative imports have been converted to absolute imports:
- `from database import models` → `from backend.database import models`
- `from services.email_service import ...` → `from backend.services.email_service import ...`
- `from lib.ai import ...` → `from backend.lib.ai import ...`

### 2. Updated Startup Script
The `start_server.sh` script now sets the `PYTHONPATH` environment variable to include the project root directory:

```bash
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
```

This ensures that Python can find the `backend` package when running from the backend directory.

### 3. Running Tests
Tests can now be run from the project root directory:

```bash
# From project root (recommended)
python -m pytest tests/

# Or specific test suites
python -m pytest tests/unit/models/
```

### 4. Running the Application
The application can still be started using the startup script:

```bash
./start_server.sh
```

Or manually with PYTHONPATH set:

```bash
cd backend
PYTHONPATH=/path/to/Mytrips python -m uvicorn main:app --reload
```

## Benefits

1. **Consistency**: All imports use the same pattern
2. **Flexibility**: Code can be run from any directory
3. **IDE Support**: Better auto-completion and navigation
4. **Testing**: Easier to run tests from different locations
5. **Maintainability**: Clear module hierarchy

## Technical Details

Python's import system looks for modules in directories listed in `sys.path`. By adding the project root to `PYTHONPATH`, we ensure that Python can always find the `backend` package, regardless of where the script is run from.

This approach is preferred over:
- Relative imports (`.` and `..`): Can be confusing and break when modules are moved
- Conditional imports: Add complexity and make code harder to understand
- Modifying `sys.path` in code: Not recommended as it's hard to maintain