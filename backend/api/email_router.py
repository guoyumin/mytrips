from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional
from sqlalchemy import or_
from backend.services.email_cache_service import EmailCacheService
from backend.services.email_classification_service import EmailClassificationService
from backend.lib.config_manager import config_manager
from backend.database.config import SessionLocal
from backend.database.models import Email, EmailContent, Trip
from backend.services.rate_limiter import get_rate_limiter
from backend.constants import TRAVEL_CATEGORIES
import json

router = APIRouter()

# Global service instances
email_cache_service = EmailCacheService()
classification_service = EmailClassificationService()

def get_trip_detection_stats(db, booking_completed_count):
    """Get trip detection statistics"""
    try:
        # Trip detection status counts
        trip_pending_count = db.query(EmailContent).filter_by(trip_detection_status='pending').count()
        trip_processing_count = db.query(EmailContent).filter_by(trip_detection_status='processing').count()
        trip_completed_count = db.query(EmailContent).filter_by(trip_detection_status='completed').count()
        trip_failed_count = db.query(EmailContent).filter_by(trip_detection_status='failed').count()
        
        # Count detected trips
        total_trips = db.query(Trip).count()
        
        # Count emails with actual booking info (non-null booking_type)
        booking_emails_count = 0
        if booking_completed_count > 0:
            # Get count of emails with actual booking information (not just completed extraction)
            booking_emails = db.query(EmailContent).filter(
                EmailContent.booking_extraction_status == 'completed',
                EmailContent.extracted_booking_info.isnot(None)
            ).all()
            
            for email_content in booking_emails:
                try:
                    booking_info = json.loads(email_content.extracted_booking_info)
                    if booking_info.get('booking_type'):  # Has actual booking info
                        booking_emails_count += 1
                except:
                    continue
        
        return {
            'pending': trip_pending_count,
            'processing': trip_processing_count,  
            'completed': trip_completed_count,
            'failed': trip_failed_count,
            'total_trips_detected': total_trips,
            'booking_emails_count': booking_emails_count,
            'completion_rate': round(trip_completed_count / booking_emails_count * 100, 1) if booking_emails_count > 0 else 0,
            'trip_coverage_rate': round(total_trips / booking_emails_count * 100, 1) if booking_emails_count > 0 else 0
        }
        
    except Exception as e:
        print(f"Error getting trip detection stats: {e}")
        return {
            'pending': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0,
            'total_trips_detected': 0,
            'booking_emails_count': 0,
            'completion_rate': 0,
            'trip_coverage_rate': 0
        }

def _create_booking_summary(booking_info: dict) -> dict:
    """Create a summary of booking information for display"""
    if not booking_info:
        return None
    
    # Handle non-booking emails (booking_type is null)
    if booking_info.get('booking_type') is None:
        return {
            'booking_type': None,
            'non_booking_type': booking_info.get('non_booking_type', 'unknown'),
            'reason': booking_info.get('reason', 'Not a booking email'),
            'status': 'non_booking',
            'confirmation_numbers': [],
            'key_details': []
        }
    
    summary = {
        'booking_type': booking_info.get('booking_type', 'unknown'),
        'status': booking_info.get('status', 'unknown'),
        'confirmation_numbers': booking_info.get('confirmation_numbers', []),
        'key_details': []
    }
    
    # Add type-specific details
    if 'transport_segments' in booking_info and booking_info['transport_segments']:
        transport_segments = booking_info['transport_segments']
        
        # Always expect array format
        for i, transport in enumerate(transport_segments):
            segment_label = f"Segment {i+1}" if len(transport_segments) > 1 else ""
            detail = f"{transport.get('segment_type', 'Transport').title()}: {transport.get('carrier_name', '')} {transport.get('segment_number', '')}"
            if transport.get('departure_location') and transport.get('arrival_location'):
                detail += f" from {transport['departure_location']} to {transport['arrival_location']}"
            if transport.get('departure_datetime'):
                detail += f" on {transport['departure_datetime'][:10]}"
            if segment_label:
                detail = f"{segment_label} - {detail}"
            summary['key_details'].append(detail)
    
    if 'accommodations' in booking_info and booking_info['accommodations']:
        # Always expect array format
        for accommodation in booking_info['accommodations']:
            detail = f"Hotel: {accommodation.get('property_name', 'Unknown')}"
            if accommodation.get('city'):
                detail += f" in {accommodation['city']}"
            if accommodation.get('check_in_date') and accommodation.get('check_out_date'):
                detail += f" ({accommodation['check_in_date']} to {accommodation['check_out_date']})"
            summary['key_details'].append(detail)
    
    if 'activities' in booking_info and booking_info['activities']:
        # Always expect array format
        for activity in booking_info['activities']:
            detail = f"Activity: {activity.get('activity_name', 'Unknown')}"
            if activity.get('location'):
                detail += f" at {activity['location']}"
            if activity.get('start_datetime'):
                detail += f" on {activity['start_datetime'][:10]}"
            summary['key_details'].append(detail)
    
    if 'cruises' in booking_info and booking_info['cruises']:
        # Always expect array format
        for cruise in booking_info['cruises']:
            detail = f"Cruise: {cruise.get('cruise_line', '')} - {cruise.get('ship_name', '')}"
            if cruise.get('departure_datetime'):
                detail += f" departing {cruise['departure_datetime'][:10]}"
            summary['key_details'].append(detail)
    
    # Add cost information
    if 'cost_info' in booking_info and booking_info['cost_info']:
        cost = booking_info['cost_info']
        if cost.get('total_cost'):
            summary['total_cost'] = f"{cost.get('currency', '')} {cost['total_cost']}"
    
    return summary

@router.post("/import") 
async def start_email_import(request: dict) -> Dict:
    """Start email import process (legacy endpoint - supports days only)"""
    try:
        days = request.get('days', 365)  # Default to 1 year
        message = email_cache_service.start_import(days)
        return {"started": True, "message": message, "days": days}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import/date-range")
async def start_email_import_date_range(request: dict) -> Dict:
    """Start email import process with date range support"""
    try:
        from datetime import datetime
        from backend.services.orchestrators.email_processing_orchestrator import EmailProcessingOrchestrator
        
        # Parse dates
        start_date_str = request.get('start_date')
        end_date_str = request.get('end_date')
        
        if not start_date_str or not end_date_str:
            raise HTTPException(status_code=400, detail="start_date and end_date are required")
        
        try:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
        
        # Options
        process_immediately = request.get('process_immediately', True)
        auto_continue = request.get('auto_continue', True)
        
        # Create orchestrator and start import
        orchestrator = EmailProcessingOrchestrator()
        result = orchestrator.import_and_process_date_range(
            start_date, 
            end_date, 
            process_immediately=process_immediately
        )
        
        return {
            "started": True,
            "message": f"Import started for {result['new_count']} new emails",
            "import_result": result,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import/days")
async def start_email_import_days(request: dict) -> Dict:
    """Start email import for last N days (new endpoint)"""
    try:
        from datetime import datetime, timedelta
        from backend.services.orchestrators.email_processing_orchestrator import EmailProcessingOrchestrator
        
        days = request.get('days', 7)  # Default to 1 week
        if not isinstance(days, int) or days < 1:
            raise HTTPException(status_code=400, detail="days must be a positive integer")
        
        # Options
        process_immediately = request.get('process_immediately', True)
        auto_continue = request.get('auto_continue', True)
        
        # Create orchestrator and start import
        orchestrator = EmailProcessingOrchestrator()
        result = orchestrator.import_and_process_days(
            days,
            process_immediately=process_immediately
        )
        
        return {
            "started": True,
            "message": f"Import started for {result['new_count']} new emails",
            "import_result": result,
            "days": days
        }
    except HTTPException:
        raise
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
    """Start test classification of emails (legacy endpoint)"""
    try:
        limit = request.get('limit')  # None means classify all
        result = classification_service.start_test_classification(limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process/classify")
async def process_classification(request: dict) -> Dict:
    """Process email classification using new orchestrator"""
    try:
        from backend.services.orchestrators.email_processing_orchestrator import EmailProcessingOrchestrator
        
        email_ids = request.get('email_ids', None)
        limit = request.get('limit', None)
        auto_continue = request.get('auto_continue', True)
        
        orchestrator = EmailProcessingOrchestrator()
        result = orchestrator.process_classification(
            email_ids=email_ids,
            limit=limit,
            auto_continue=auto_continue
        )
        
        return {
            "success": True,
            "message": f"Classified {len(result.get('classifications', []))} emails",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process/content-extraction")
async def process_content_extraction(request: dict) -> Dict:
    """Process content extraction for travel emails"""
    try:
        from backend.services.orchestrators.email_processing_orchestrator import EmailProcessingOrchestrator
        
        email_ids = request.get('email_ids', None)
        limit = request.get('limit', None)
        auto_continue = request.get('auto_continue', True)
        
        orchestrator = EmailProcessingOrchestrator()
        result = orchestrator.process_content_extraction(
            email_ids=email_ids,
            limit=limit,
            auto_continue=auto_continue
        )
        
        return {
            "success": True,
            "message": f"Extracted content from {result.get('success_count', 0)} emails",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process/booking-extraction")
async def process_booking_extraction(request: dict) -> Dict:
    """Process booking extraction"""
    try:
        from backend.services.orchestrators.email_processing_orchestrator import EmailProcessingOrchestrator
        
        email_ids = request.get('email_ids', None)
        limit = request.get('limit', None)
        
        orchestrator = EmailProcessingOrchestrator()
        result = orchestrator.process_booking_extraction(
            email_ids=email_ids,
            limit=limit
        )
        
        return {
            "success": True,
            "message": f"Extracted bookings from {result.get('success_count', 0)} emails",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process/full-pipeline")
async def process_full_pipeline(request: dict) -> Dict:
    """Run the full processing pipeline"""
    try:
        from datetime import datetime
        from backend.services.orchestrators.email_processing_orchestrator import EmailProcessingOrchestrator
        
        # Parse dates
        start_date_str = request.get('start_date')
        end_date_str = request.get('end_date')
        
        if not start_date_str or not end_date_str:
            raise HTTPException(status_code=400, detail="start_date and end_date are required")
        
        try:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
        
        orchestrator = EmailProcessingOrchestrator()
        result = orchestrator.process_full_pipeline(start_date, end_date)
        
        return {
            "success": True,
            "message": "Full pipeline completed",
            "result": result
        }
    except HTTPException:
        raise
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

# Configuration management endpoints
@router.get("/config")
async def get_config() -> Dict:
    """Get current configuration"""
    try:
        return {
            "database_path": config_manager.get_database_path(),
            "batch_size": config_manager.get_batch_size(),
            "log_level": config_manager.get_log_level(),
            "config": config_manager.get_config()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config/batch_size")
async def set_batch_size(request: dict) -> Dict:
    """Set batch size for processing"""
    try:
        batch_size = request.get('batch_size', 20)
        
        # Validate batch size
        if not isinstance(batch_size, int) or batch_size < 1 or batch_size > 100:
            raise HTTPException(status_code=400, detail="Batch size must be an integer between 1 and 100")
        
        # Update config (this would need to be implemented in config_manager)
        
        return {
            "success": True,
            "batch_size": batch_size,
            "message": "Batch size updated."
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config/log_level")
async def set_log_level(request: dict) -> Dict:
    """Set log level"""
    try:
        log_level = request.get('log_level', 'INFO')
        
        # Validate log level
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if log_level.upper() not in valid_levels:
            raise HTTPException(status_code=400, detail=f"Invalid log level. Must be one of: {valid_levels}")
        
        config_manager.set_log_level(log_level)
        
        return {
            "success": True,
            "log_level": log_level.upper(),
            "message": "Log level updated. Restart services to apply changes."
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def list_emails(
    classification: Optional[str] = Query(None, description="Filter by classification type"),
    limit: Optional[int] = Query(100, description="Maximum number of emails to return"),
    offset: Optional[int] = Query(0, description="Number of emails to skip"),
    booking_status: Optional[str] = Query(None, description="Filter by booking extraction status"),
    trip_detection_status: Optional[str] = Query(None, description="Filter by trip detection status"),
    search: Optional[str] = Query(None, description="Search in subject and email ID")
) -> Dict:
    """List emails with optional filtering"""
    db = SessionLocal()
    try:
        query = db.query(Email)
        
        # Filter by classification if specified
        if classification:
            if classification.lower() == 'travel':
                # Include all travel-related classifications
                query = query.filter(Email.classification.in_(TRAVEL_CATEGORIES))
            else:
                query = query.filter(Email.classification == classification)
        
        # Filter by booking status if specified
        if booking_status:
            if booking_status == 'has_booking':
                # Special filter for emails that have actual booking information
                query = query.join(EmailContent).filter(
                    EmailContent.booking_extraction_status == 'completed',
                    EmailContent.extracted_booking_info.isnot(None),
                    EmailContent.extracted_booking_info != 'null',
                    EmailContent.extracted_booking_info.contains('"booking_type"')
                ).filter(~EmailContent.extracted_booking_info.contains('"booking_type": null'))
            else:
                query = query.join(EmailContent).filter(EmailContent.booking_extraction_status == booking_status)
        
        # Filter by trip detection status if specified
        if trip_detection_status:
            # Join with EmailContent if not already joined
            if not booking_status:
                query = query.join(EmailContent)
            query = query.filter(EmailContent.trip_detection_status == trip_detection_status)
        
        # Search filter
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Email.subject.ilike(search_pattern),
                    Email.email_id.ilike(search_pattern)
                )
            )
        
        # Get total count before applying limit/offset
        total_count = query.count()
        
        # Apply offset, limit and order by date
        emails = query.order_by(Email.timestamp.desc()).offset(offset).limit(limit).all()
        
        # Check for extracted content and booking info for each email
        email_list = []
        for email in emails:
            # Check if content has been extracted (any status, not just 'completed')
            content_info = db.query(EmailContent).filter_by(
                email_id=email.email_id
            ).first()
            
            # Parse extracted booking info if available
            booking_info = None
            booking_summary = None
            if content_info and content_info.extracted_booking_info:
                try:
                    booking_info = json.loads(content_info.extracted_booking_info)
                    booking_summary = _create_booking_summary(booking_info)
                except:
                    booking_info = None
                    booking_summary = None
            
            email_dict = {
                'email_id': email.email_id,
                'subject': email.subject,
                'sender': email.sender,
                'date': email.date,
                'timestamp': email.timestamp.isoformat() if email.timestamp else None,
                'classification': email.classification,
                'content_extracted': content_info is not None and content_info.extraction_status == 'completed',
                'has_attachments': content_info.has_attachments if content_info else False,
                'attachments_count': content_info.attachments_count if content_info else 0,
                'booking_extraction_status': content_info.booking_extraction_status if content_info else 'pending',
                'trip_detection_status': content_info.trip_detection_status if content_info else 'pending',
                'has_booking_info': booking_info is not None and booking_info.get('booking_type') is not None,
                'booking_summary': booking_summary,
                'raw_booking_info': booking_info
            }
            email_list.append(email_dict)
        
        return {
            'emails': email_list,
            'total_count': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': offset + len(email_list) < total_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/{email_id}/booking-info")
async def get_email_booking_info(email_id: str) -> Dict:
    """Get detailed booking information for a specific email"""
    db = SessionLocal()
    try:
        # Get email content (any extraction status)
        content_info = db.query(EmailContent).filter_by(
            email_id=email_id
        ).first()
        
        if not content_info:
            raise HTTPException(status_code=404, detail="Email content not found")
        
        # Get email basic info
        email = db.query(Email).filter_by(email_id=email_id).first()
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Parse booking info - show raw response even if no booking found
        booking_info = None
        raw_booking_response = content_info.extracted_booking_info
        
        if raw_booking_response:
            try:
                booking_info = json.loads(raw_booking_response)
            except json.JSONDecodeError:
                # If it's not valid JSON, treat it as raw text
                booking_info = {"raw_response": raw_booking_response}
        
        return {
            'email_id': email_id,
            'subject': email.subject,
            'sender': email.sender,
            'date': email.date,
            'classification': email.classification,
            'booking_extraction_status': content_info.booking_extraction_status or 'pending',
            'booking_extraction_error': content_info.booking_extraction_error,
            'has_booking_info': booking_info is not None and isinstance(booking_info, dict) and booking_info.get('booking_type') is not None,
            'booking_info': booking_info,
            'raw_booking_response': raw_booking_response,
            'booking_summary': _create_booking_summary(booking_info) if booking_info and isinstance(booking_info, dict) and booking_info.get('booking_type') else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error in get_email_booking_info: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/stats/detailed")
async def get_detailed_email_stats() -> Dict:
    """获取详细的邮件统计信息"""
    try:
        db = SessionLocal()
        
        # 基础统计
        total_emails = db.query(Email).count()
        
        # 日期范围 - 使用timestamp字段而不是date字段
        date_range = None
        if total_emails > 0:
            oldest_email = db.query(Email).filter(Email.timestamp.isnot(None)).order_by(Email.timestamp.asc()).first()
            newest_email = db.query(Email).filter(Email.timestamp.isnot(None)).order_by(Email.timestamp.desc()).first()
            if oldest_email and newest_email:
                date_range = {
                    'oldest': oldest_email.timestamp.strftime('%Y-%m-%d') if oldest_email.timestamp else None,
                    'newest': newest_email.timestamp.strftime('%Y-%m-%d') if newest_email.timestamp else None
                }
        
        # 分类统计 - 处理None和unclassified
        from sqlalchemy import or_
        classified_count = db.query(Email).filter(
            Email.classification.isnot(None),
            Email.classification != 'unclassified'
        ).count()
        unclassified_count = db.query(Email).filter(
            or_(Email.classification.is_(None), Email.classification == 'unclassified')
        ).count()
        
        # 各分类详细统计
        classification_stats = {}
        
        # 查询所有分类及其数量
        from sqlalchemy import func
        classification_counts = db.query(
            Email.classification,
            func.count(Email.email_id).label('count')
        ).group_by(Email.classification).all()
        
        for classification, count in classification_counts:
            # Convert None to 'unclassified' for consistency
            if classification is None:
                classification = 'unclassified'
            classification_stats[classification] = count
        
        # 旅行相关分类统计
        travel_stats = {}
        total_travel_emails = 0
        
        for category in TRAVEL_CATEGORIES:
            count = classification_stats.get(category, 0)
            travel_stats[category] = count
            total_travel_emails += count
        
        # 内容提取统计 - 只统计旅行相关邮件的提取状态
        # 首先获取所有旅行相关邮件的ID列表
        travel_email_ids_list = [
            row[0] for row in db.query(Email.email_id).filter(
                Email.classification.in_(TRAVEL_CATEGORIES)
            ).all()
        ]
        
        # 初始化计数器
        content_extracted_count = 0
        content_failed_count = 0
        content_extracting_count = 0
        content_pending_count = 0
        content_not_required_count = 0
        booking_completed_count = 0
        booking_failed_count = 0
        booking_extracting_count = 0
        booking_pending_count = 0
        booking_not_travel_count = 0
        booking_no_booking_count = 0
        
        try:
            # 检查EmailContent表是否有新字段
            # 先尝试一个简单的查询来测试字段是否存在
            test_query = db.query(EmailContent).filter(
                EmailContent.email_id.in_(travel_email_ids_list)
            ).first()
            
            # 如果到这里没有异常，说明基础字段存在，继续统计
            content_extracted_count = db.query(EmailContent).filter(
                EmailContent.extraction_status == 'completed',
                EmailContent.email_id.in_(travel_email_ids_list)
            ).count()
            
            content_failed_count = db.query(EmailContent).filter(
                EmailContent.extraction_status == 'failed',
                EmailContent.email_id.in_(travel_email_ids_list)
            ).count()
            
            content_extracting_count = db.query(EmailContent).filter(
                EmailContent.extraction_status == 'extracting',
                EmailContent.email_id.in_(travel_email_ids_list)
            ).count()
            
            # Count not_required status for non-travel emails
            non_travel_email_ids_list = [
                row[0] for row in db.query(Email.email_id).filter(
                    ~Email.classification.in_(TRAVEL_CATEGORIES)
                ).all()
            ]
            
            content_not_required_count = db.query(EmailContent).filter(
                EmailContent.extraction_status == 'not_required',
                EmailContent.email_id.in_(non_travel_email_ids_list)
            ).count()
            
            content_pending_count = total_travel_emails - content_extracted_count - content_failed_count - content_extracting_count
            
            # 现在尝试booking extraction相关的查询
            try:
                booking_completed_count = db.query(EmailContent).filter(
                    EmailContent.booking_extraction_status == 'completed',
                    EmailContent.email_id.in_(travel_email_ids_list)
                ).count()
                
                booking_failed_count = db.query(EmailContent).filter(
                    EmailContent.booking_extraction_status == 'failed',
                    EmailContent.email_id.in_(travel_email_ids_list)
                ).count()
                
                booking_extracting_count = db.query(EmailContent).filter(
                    EmailContent.booking_extraction_status == 'extracting',
                    EmailContent.email_id.in_(travel_email_ids_list)
                ).count()
                
                # 查询no_booking状态的数量
                booking_no_booking_count = db.query(EmailContent).filter(
                    EmailContent.booking_extraction_status == 'no_booking',
                    EmailContent.email_id.in_(travel_email_ids_list)
                ).count()
                
                # 查询not_travel状态的数量
                booking_not_travel_count = db.query(EmailContent).filter(
                    EmailContent.booking_extraction_status == 'not_travel',
                    EmailContent.email_id.in_(non_travel_email_ids_list)
                ).count()
                
                # 真正的pending数量应该直接查询
                booking_pending_count = db.query(EmailContent).filter(
                    EmailContent.booking_extraction_status == 'pending',
                    EmailContent.email_id.in_(travel_email_ids_list)
                ).count()
                
            except Exception as e:
                # booking extraction字段不存在，所有已提取内容的邮件都标记为待处理
                booking_pending_count = content_extracted_count
                print(f"Booking extraction columns not found, marking {content_extracted_count} emails as pending booking extraction")
                
        except Exception as e:
            # EmailContent表查询失败，可能表不存在或字段有问题
            print(f"EmailContent table query failed: {e}")
            content_pending_count = total_travel_emails
        
        return {
            'total_emails': total_emails,
            'date_range': date_range,
            'classification_summary': {
                'classified': classified_count,
                'unclassified': unclassified_count,
                'classification_rate': round(classified_count / total_emails * 100, 1) if total_emails > 0 else 0
            },
            'classification_details': classification_stats,
            'travel_summary': {
                'total_travel_emails': total_travel_emails,
                'travel_categories': travel_stats
            },
            'content_extraction': {
                'extracted': content_extracted_count,
                'failed': content_failed_count,
                'extracting': content_extracting_count,
                'pending': content_pending_count if content_pending_count > 0 else 0,
                'not_required': content_not_required_count,
                'extraction_rate': round(content_extracted_count / total_travel_emails * 100, 1) if total_travel_emails > 0 else 0
            },
            'booking_extraction': {
                'completed': booking_completed_count,
                'no_booking': booking_no_booking_count if 'booking_no_booking_count' in locals() else 0,
                'not_travel': booking_not_travel_count if 'booking_not_travel_count' in locals() else 0,
                'failed': booking_failed_count,
                'extracting': booking_extracting_count,
                'pending': booking_pending_count if booking_pending_count > 0 else 0,
                'completion_rate': round((booking_completed_count + booking_no_booking_count if 'booking_no_booking_count' in locals() else 0) / content_extracted_count * 100, 1) if content_extracted_count > 0 else 0
            },
            'trip_detection': get_trip_detection_stats(db, booking_completed_count)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        db.close()

@router.get("/gemini-usage")
async def get_gemini_usage() -> Dict:
    """Get current Gemini API usage statistics"""
    try:
        rate_limiter = get_rate_limiter()
        usage_stats = rate_limiter.get_usage_stats()
        
        # Calculate summary statistics
        total_rpm = sum(stats.get('requests_last_minute', 0) for stats in usage_stats.values())
        total_rpd = sum(stats.get('requests_today', 0) for stats in usage_stats.values())
        total_tokens = sum(stats.get('tokens_last_minute', 0) for stats in usage_stats.values())
        
        return {
            'summary': {
                'total_requests_last_minute': total_rpm,
                'total_requests_today': total_rpd,
                'total_tokens_last_minute': total_tokens
            },
            'by_model': usage_stats,
            'rate_limits': rate_limiter.rate_limits
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset-all")
async def reset_all_emails():
    """完全重置所有邮件数据"""
    try:
        result = email_cache_service.reset_all_emails()
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result['message'])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset-classification")
async def reset_classification():
    """重置邮件分类"""
    try:
        result = classification_service.reset_all_classifications()
        if result['success']:
            return result
        else:
            raise HTTPException(status_code=400, detail=result['message'])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))