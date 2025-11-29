"""
Email Pipeline API Router
Endpoints for running the full email processing pipeline
"""
from fastapi import APIRouter, HTTPException
from typing import Dict
from backend.services.email_pipeline_service_v2 import EmailPipelineServiceV2

router = APIRouter()

# Global service instance
pipeline_service = EmailPipelineServiceV2()

@router.post("/start")
async def start_pipeline(request: dict) -> Dict:
    """
    Start the email processing pipeline
    
    Request body:
    {
        "date_range": {
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        }
    }
    """
    try:
        date_range = request.get('date_range')
        if not date_range:
            raise HTTPException(status_code=400, detail="date_range is required")
        
        result = pipeline_service.start_pipeline(date_range)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/progress")
async def get_pipeline_progress() -> Dict:
    """Get current pipeline progress"""
    try:
        return pipeline_service.get_pipeline_progress()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop")
async def stop_pipeline() -> Dict:
    """Stop the running pipeline"""
    print("[DEBUG] /api/pipeline/stop endpoint called")
    try:
        print("[DEBUG] Calling pipeline_service.stop_pipeline()")
        result = pipeline_service.stop_pipeline()
        print(f"[DEBUG] stop_pipeline result: {result}")
        return result
    except Exception as e:
        print(f"[DEBUG] Error in stop_pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_pipeline_status() -> Dict:
    """Get detailed pipeline status including all stages"""
    try:
        progress = pipeline_service.get_pipeline_progress()
        
        # Add summary information
        stages = progress.get('stages', {})
        
        # Count completed stages
        completed_stages = sum(1 for stage in stages.values() if stage.get('status') == 'completed')
        total_stages = len(stages)
        
        # Calculate total processed emails
        total_imported = stages.get('import', {}).get('processed', 0)
        total_classified = stages.get('classification', {}).get('processed', 0)
        total_travel = stages.get('classification', {}).get('travel_count', 0)
        total_content_extracted = stages.get('content', {}).get('processed', 0)
        total_bookings_extracted = stages.get('booking', {}).get('processed', 0)
        total_bookings_found = stages.get('booking', {}).get('bookings_found', 0)
        
        # Add summary to response
        progress['summary'] = {
            'stages_completed': f"{completed_stages}/{total_stages}",
            'emails_imported': total_imported,
            'emails_classified': total_classified,
            'travel_emails_found': total_travel,
            'content_extracted': total_content_extracted,
            'bookings_extracted': total_bookings_extracted,
            'bookings_found': total_bookings_found,
            'trips_found': stages.get('trip_detection', {}).get('trips_found', 0),
            'has_errors': len(progress.get('errors', [])) > 0
        }
        
        return progress
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))