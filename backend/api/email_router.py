from fastapi import APIRouter, HTTPException
from typing import Dict
from services.email_cache_service import EmailCacheService
from services.email_classification_service import EmailClassificationService

router = APIRouter()

# Global service instances
email_cache_service = EmailCacheService()
classification_service = EmailClassificationService()

@router.post("/import") 
async def start_email_import(request: dict) -> Dict:
    """Start email import process"""
    try:
        days = request.get('days', 365)  # Default to 1 year
        message = email_cache_service.start_import(days)
        return {"started": True, "message": message, "days": days}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/import/progress")
async def get_import_progress() -> Dict:
    """Get current import progress"""
    try:
        return email_cache_service.get_import_progress()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import/stop")
async def stop_import() -> Dict:
    """Stop ongoing import process"""
    try:
        message = email_cache_service.stop_import()
        return {"stopped": True, "message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cache/stats")
async def get_cache_stats() -> Dict:
    """Get email cache statistics"""
    try:
        return email_cache_service.get_cache_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Classification endpoints
@router.post("/classify/test")
async def start_test_classification(request: dict) -> Dict:
    """Start test classification of emails"""
    try:
        limit = request.get('limit')  # None means classify all
        result = classification_service.start_test_classification(limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/classify/progress")
async def get_classification_progress() -> Dict:
    """Get current classification progress"""
    try:
        return classification_service.get_classification_progress()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/classify/stop")
async def stop_classification() -> Dict:
    """Stop ongoing classification process"""
    try:
        message = classification_service.stop_classification()
        return {"stopped": True, "message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/classify/stats")
async def get_classification_stats() -> Dict:
    """Get classification test statistics"""
    try:
        return classification_service.get_classification_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))