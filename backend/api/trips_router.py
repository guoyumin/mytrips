from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime
from ..models.trip import Trip, TripSegment
from ..services.trip_service import TripService

router = APIRouter()

@router.get("/", response_model=List[Trip])
async def get_trips(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    destination: Optional[str] = None
):
    try:
        trip_service = TripService()
        trips = trip_service.get_trips(start_date, end_date, destination)
        return trips
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{trip_id}", response_model=Trip)
async def get_trip(trip_id: str):
    try:
        trip_service = TripService()
        trip = trip_service.get_trip_by_id(trip_id)
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        return trip
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/export/{format}")
async def export_trips(
    format: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    try:
        if format not in ["excel", "csv", "pdf"]:
            raise HTTPException(status_code=400, detail="Invalid export format")
            
        trip_service = TripService()
        file_path = trip_service.export_trips(format, start_date, end_date)
        
        return {
            "status": "success",
            "file_path": file_path,
            "format": format
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/summary")
async def get_trip_stats():
    try:
        trip_service = TripService()
        stats = trip_service.get_trip_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))