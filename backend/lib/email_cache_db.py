"""
基于SQLite数据库的邮件缓存库
替代CSV版本，提供更好的性能和查询能力
"""
import os
import sys
from typing import List, Dict, Optional, Set
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

# 添加数据库模块路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database.config import SessionLocal
from database.models import Email
import logging

logger = logging.getLogger(__name__)

class EmailCacheDB:
    """基于SQLite数据库的邮件缓存管理器"""
    
    def __init__(self):
        """初始化数据库缓存管理器"""
        self.db_session = None
    
    def _get_session(self) -> Session:
        """获取数据库会话"""
        if self.db_session is None:
            self.db_session = SessionLocal()
        return self.db_session
    
    def close(self):
        """关闭数据库连接"""
        if self.db_session:
            self.db_session.close()
            self.db_session = None
    
    def get_cached_ids(self) -> Set[str]:
        """
        获取所有已缓存的邮件 ID
        
        Returns:
            邮件 ID 集合
        """
        db = self._get_session()
        try:
            email_ids = db.query(Email.email_id).all()
            return {email_id[0] for email_id in email_ids}
        except Exception as e:
            logger.error(f"Failed to get cached IDs: {e}")
            return set()
    
    def add_emails(self, emails: List[Dict[str, str]]) -> int:
        """
        添加邮件到数据库
        
        Args:
            emails: 邮件信息列表
            
        Returns:
            新增的邮件数量
        """
        if not emails:
            return 0
        
        db = self._get_session()
        try:
            # 获取已缓存的 ID
            cached_ids = self.get_cached_ids()
            
            # 过滤出新邮件并转换为数据库模型
            new_emails = []
            for email in emails:
                if email.get('email_id') not in cached_ids:
                    # 解析邮件日期
                    timestamp = self._parse_email_date(email.get('date', ''))
                    
                    email_model = Email(
                        email_id=email.get('email_id', ''),
                        subject=email.get('subject', '') or None,
                        sender=email.get('from', '') or None,  # CSV中是'from'，DB中是'sender'
                        date=email.get('date', '') or None,
                        timestamp=timestamp,
                        is_classified=email.get('is_classified', 'false').lower() == 'true',
                        classification=email.get('classification', '') or None
                    )
                    new_emails.append(email_model)
            
            # 批量插入新邮件
            if new_emails:
                db.add_all(new_emails)
                db.commit()
                logger.info(f"Added {len(new_emails)} new emails to database")
            
            return len(new_emails)
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to add emails: {e}")
            raise
    
    def get_emails(self, 
                   limit: Optional[int] = None,
                   offset: int = 0,
                   filter_classified: Optional[bool] = None) -> List[Dict[str, str]]:
        """
        从数据库获取邮件
        
        Args:
            limit: 返回数量限制
            offset: 偏移量
            filter_classified: 是否过滤已分类/未分类邮件
            
        Returns:
            邮件列表，格式与CSV版本兼容
        """
        db = self._get_session()
        try:
            query = db.query(Email)
            
            # 应用分类过滤
            if filter_classified is not None:
                if filter_classified == False:
                    # 获取未分类的邮件，包括分类失败的邮件
                    query = query.filter(
                        or_(
                            Email.is_classified == False,
                            Email.classification == 'classification_failed'
                        )
                    )
                elif filter_classified == True:
                    # 只获取成功分类的邮件（排除失败的）
                    query = query.filter(
                        and_(
                            Email.is_classified == True,
                            Email.classification != 'classification_failed'
                        )
                    )
            
            # 按时间戳排序（最新的在前）
            query = query.order_by(Email.timestamp.desc().nullslast())
            
            # 应用偏移和限制
            if offset > 0:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            # 执行查询并转换为字典格式（与CSV版本兼容）
            emails = []
            for email in query.all():
                email_dict = {
                    'email_id': email.email_id,
                    'subject': email.subject or '',
                    'from': email.sender or '',  # 注意：这里转换回'from'以保持兼容性
                    'date': email.date or '',
                    'timestamp': email.timestamp.isoformat() if email.timestamp else '',
                    'is_classified': 'true' if email.is_classified else 'false',
                    'classification': email.classification or ''
                }
                emails.append(email_dict)
            
            return emails
            
        except Exception as e:
            logger.error(f"Failed to get emails: {e}")
            return []
    
    def update_classifications(self, classifications: Dict[str, str]) -> int:
        """
        批量更新邮件分类
        
        Args:
            classifications: {email_id: classification} 字典
            
        Returns:
            更新的邮件数量
        """
        if not classifications:
            return 0
        
        db = self._get_session()
        try:
            # 分离成功和失败的分类
            successful_classifications = {}
            failed_classifications = {}
            
            for email_id, classification in classifications.items():
                if classification == 'classification_failed':
                    failed_classifications[email_id] = classification
                else:
                    successful_classifications[email_id] = classification
            
            updated_count = 0
            
            # 更新成功的分类
            if successful_classifications:
                for email_id, classification in successful_classifications.items():
                    result = db.query(Email).filter(Email.email_id == email_id).update({
                        'is_classified': True,
                        'classification': classification,
                        'updated_at': func.now()
                    })
                    updated_count += result
            
            # 对于失败的分类，保持为未分类状态
            if failed_classifications:
                for email_id in failed_classifications.keys():
                    db.query(Email).filter(Email.email_id == email_id).update({
                        'is_classified': False,
                        'classification': None,
                        'updated_at': func.now()
                    })
                logger.info(f"Reset {len(failed_classifications)} failed classifications")
            
            db.commit()
            logger.info(f"Updated {updated_count} email classifications")
            return updated_count
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update classifications: {e}")
            raise
    
    def reset_failed_classifications(self) -> int:
        """
        重置分类失败的邮件为未分类状态
        
        Returns:
            重置的邮件数量
        """
        db = self._get_session()
        try:
            result = db.query(Email).filter(
                Email.classification == 'classification_failed'
            ).update({
                'is_classified': False,
                'classification': None,
                'updated_at': func.now()
            })
            
            db.commit()
            logger.info(f"Reset {result} failed classifications")
            return result
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to reset failed classifications: {e}")
            return 0
    
    def get_statistics(self) -> Dict[str, any]:
        """
        获取缓存统计信息
        
        Returns:
            包含总数、已分类数、日期范围等的统计信息
        """
        db = self._get_session()
        try:
            stats = {
                'total_emails': 0,
                'classified_emails': 0,
                'date_range': None,
                'classifications': {}
            }
            
            # 总邮件数
            stats['total_emails'] = db.query(Email).count()
            
            # 已分类邮件数（不包括失败的）
            stats['classified_emails'] = db.query(Email).filter(
                and_(
                    Email.is_classified == True,
                    Email.classification != 'classification_failed'
                )
            ).count()
            
            # 分类分布
            classification_counts = db.query(
                Email.classification, 
                func.count(Email.id)
            ).filter(
                and_(
                    Email.classification.isnot(None),
                    Email.classification != 'classification_failed'
                )
            ).group_by(Email.classification).all()
            
            stats['classifications'] = {cls: count for cls, count in classification_counts}
            
            # 日期范围
            date_range = db.query(
                func.min(Email.timestamp),
                func.max(Email.timestamp)
            ).filter(Email.timestamp.isnot(None)).first()
            
            if date_range and date_range[0] and date_range[1]:
                stats['date_range'] = {
                    'oldest': date_range[0].strftime('%Y-%m-%d'),
                    'newest': date_range[1].strftime('%Y-%m-%d')
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {
                'total_emails': 0,
                'classified_emails': 0,
                'date_range': None,
                'classifications': {}
            }
    
    def _parse_email_date(self, date_str: str) -> Optional[datetime]:
        """解析邮件日期字符串为datetime对象"""
        if not date_str:
            return None
        
        try:
            # 尝试解析 Gmail 日期格式
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            # 移除时区信息以避免SQLite兼容性问题
            return dt.replace(tzinfo=None) if dt else None
        except Exception as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
            return None
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()