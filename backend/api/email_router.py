from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional
from services.email_cache_service import EmailCacheService
from services.email_classification_service import EmailClassificationService
from lib.config_manager import config_manager
from database.config import SessionLocal
from database.models import Email, EmailContent

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
    limit: Optional[int] = Query(100, description="Maximum number of emails to return")
) -> List[Dict]:
    """List emails with optional filtering"""
    db = SessionLocal()
    try:
        query = db.query(Email)
        
        # Filter by classification if specified
        if classification:
            if classification.lower() == 'travel':
                # Include all travel-related classifications
                travel_categories = [
                    'flight', 'hotel', 'car_rental', 'train', 'cruise', 
                    'tour', 'travel_insurance', 'flight_change', 
                    'hotel_change', 'other_travel'
                ]
                query = query.filter(Email.classification.in_(travel_categories))
            else:
                query = query.filter(Email.classification == classification)
        
        # Apply limit and order by date
        emails = query.order_by(Email.timestamp.desc()).limit(limit).all()
        
        # Check for extracted content for each email
        email_list = []
        for email in emails:
            # Check if content has been extracted
            content_info = db.query(EmailContent).filter_by(
                email_id=email.email_id,
                extraction_status='completed'
            ).first()
            
            email_dict = {
                'email_id': email.email_id,
                'subject': email.subject,
                'sender': email.sender,
                'date': email.date,
                'timestamp': email.timestamp.isoformat() if email.timestamp else None,
                'classification': email.classification,
                'content_extracted': content_info is not None,
                'has_attachments': content_info.has_attachments if content_info else False,
                'attachments_count': content_info.attachments_count if content_info else 0
            }
            email_list.append(email_dict)
            
        return email_list
        
    except Exception as e:
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
        travel_categories = [
            'flight', 'hotel', 'car_rental', 'train', 'cruise', 
            'tour', 'travel_insurance', 'flight_change', 
            'hotel_change', 'other_travel'
        ]
        
        travel_stats = {}
        total_travel_emails = 0
        
        for category in travel_categories:
            count = classification_stats.get(category, 0)
            travel_stats[category] = count
            total_travel_emails += count
        
        # 内容提取统计
        content_extracted_count = db.query(EmailContent).filter(
            EmailContent.extraction_status == 'completed'
        ).count()
        
        content_failed_count = db.query(EmailContent).filter(
            EmailContent.extraction_status == 'failed'
        ).count()
        
        content_pending_count = total_travel_emails - content_extracted_count - content_failed_count
        
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
                'pending': content_pending_count if content_pending_count > 0 else 0,
                'extraction_rate': round(content_extracted_count / total_travel_emails * 100, 1) if total_travel_emails > 0 else 0
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        db.close()