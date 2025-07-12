from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime, timedelta
from backend.services.gmail_service import GmailService
from ..services.email_analyzer import EmailAnalyzer

router = APIRouter()

@router.get("/sync")
async def sync_emails(days: int = 365):
    try:
        gmail_service = GmailService()
        analyzer = EmailAnalyzer()
        
        # Search for travel-related emails
        travel_keywords = [
            "flight confirmation",
            "booking confirmation", 
            "hotel reservation",
            "itinerary",
            "e-ticket",
            "check-in",
            "boarding pass"
        ]
        
        query = f"({' OR '.join(travel_keywords)}) newer_than:{days}d"
        emails = gmail_service.search_emails(query)
        
        analyzed_count = 0
        for email in emails:
            email_data = gmail_service.get_email(email['id'])
            analyzer.analyze_email(email_data)
            analyzed_count += 1
        
        return {
            "status": "success",
            "emails_found": len(emails),
            "emails_analyzed": analyzed_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/emails")
async def get_emails(limit: int = 50, query: Optional[str] = None):
    try:
        gmail_service = GmailService()
        
        if not query:
            query = "newer_than:365d"
            
        emails = gmail_service.search_emails(query, limit)
        return {"emails": emails}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))