"""
邮件内容提取服务
管理邮件内容提取的业务逻辑和进度跟踪
"""
import json
import logging
import threading
from typing import Dict, List, Optional
from datetime import datetime

from backend.lib.gmail_client import GmailClient
from backend.lib.email_content_extractor import EmailContentExtractor
from backend.lib.config_manager import config_manager
from backend.database.config import SessionLocal
from backend.database.models import Email, EmailContent
from backend.constants import TRAVEL_CATEGORIES, is_travel_category

logger = logging.getLogger(__name__)

class EmailContentService:
    """邮件内容提取服务 - 管理提取流程和进度"""
    
    def __init__(self, credentials_path: str = None, token_path: str = None):
        """初始化服务"""
        if credentials_path is None:
            credentials_path = config_manager.get_gmail_credentials_path()
        if token_path is None:
            token_path = config_manager.get_gmail_token_path()
            
        # 初始化Gmail客户端
        try:
            self.gmail_client = GmailClient(credentials_path, token_path)
            logger.info("Gmail client initialized for content extraction")
        except Exception as e:
            logger.error(f"Failed to initialize Gmail client: {e}")
            self.gmail_client = None
            
        # 数据存储路径
        self.data_root = config_manager.get_absolute_path('data/email_content')
        
        # 初始化内容提取器
        if self.gmail_client:
            self.extractor = EmailContentExtractor(self.gmail_client, self.data_root)
        else:
            self.extractor = None
            
        # 提取进度跟踪
        self.extraction_progress = {
            'is_running': False,
            'current': 0,
            'total': 0,
            'finished': False,
            'message': '',
            'error': None,
            'extracted_count': 0,
            'failed_count': 0
        }
        self._stop_flag = threading.Event()
        self._extraction_thread = None
        self._lock = threading.Lock()  # Add thread lock for safety
        
    def _get_emails_by_ids(self, email_ids: List[str]) -> List[Dict]:
        """根据邮件ID列表获取邮件信息
        
        Args:
            email_ids: 邮件ID列表
            
        Returns:
            邮件信息列表
        """
        db = SessionLocal()
        try:
            emails = db.query(Email).filter(
                Email.email_id.in_(email_ids)
            ).all()
            
            result = []
            for email in emails:
                if not email:
                    logger.warning("Found None email in query results")
                    continue
                    
                email_dict = {
                    'email_id': email.email_id if hasattr(email, 'email_id') else None,
                    'subject': email.subject if hasattr(email, 'subject') else None,
                    'sender': email.sender if hasattr(email, 'sender') else None,
                    'date': email.date if hasattr(email, 'date') else None,
                    'classification': email.classification if hasattr(email, 'classification') else None
                }
                
                # Only add if we have a valid email_id
                if email_dict['email_id']:
                    result.append(email_dict)
                else:
                    logger.warning(f"Skipping email with no email_id: {email_dict}")
                    
            logger.debug(f"Returning {len(result)} emails for extraction")
            return result
            
        finally:
            db.close()
    
    def get_travel_emails_for_extraction(self) -> List[Dict]:
        """获取需要提取内容的旅行相关邮件"""
        db = SessionLocal()
        try:
            # 查询所有旅行相关邮件，且还未成功提取内容的
            
            # 使用子查询找出已成功提取或不需要提取的邮件ID
            extracted_ids = db.query(EmailContent.email_id).filter(
                EmailContent.extraction_status.in_(['completed', 'not_required'])
            ).subquery()
            
            # 查询旅行邮件且不在已提取列表中
            emails = db.query(Email).filter(
                Email.classification.in_(TRAVEL_CATEGORIES),
                ~Email.email_id.in_(extracted_ids)
            ).all()
            
            result = []
            for email in emails:
                if not email:
                    logger.warning("Found None email in query results")
                    continue
                    
                email_dict = {
                    'email_id': email.email_id if hasattr(email, 'email_id') else None,
                    'subject': email.subject if hasattr(email, 'subject') else None,
                    'sender': email.sender if hasattr(email, 'sender') else None,
                    'date': email.date if hasattr(email, 'date') else None,
                    'classification': email.classification if hasattr(email, 'classification') else None
                }
                
                # Only add if we have a valid email_id
                if email_dict['email_id']:
                    result.append(email_dict)
                else:
                    logger.warning(f"Skipping email with no email_id: {email_dict}")
                    
            logger.debug(f"Returning {len(result)} emails for extraction")
            return result
            
        finally:
            db.close()
            
    def start_extraction(self, limit: Optional[int] = None, email_ids: Optional[List[str]] = None) -> Dict:
        """开始提取邮件内容
        
        Args:
            limit: 限制提取数量（仅在未指定email_ids时生效）
            email_ids: 指定要提取的邮件ID列表，如果为空则从数据库查询
        """
        with self._lock:
            if self.extraction_progress.get('is_running'):
                return {"started": False, "message": "Extraction already in progress"}
                
            # Double-check thread status
            if self._extraction_thread and self._extraction_thread.is_alive():
                return {"started": False, "message": "Extraction thread already running"}
                
            if not self.gmail_client or not self.extractor:
                return {"started": False, "message": "Gmail client not initialized"}
                
            # 重置进度
            self._stop_flag.clear()
            self.extraction_progress = {
                'is_running': True,
                'current': 0,
                'total': 0,
                'finished': False,
                'message': 'Starting extraction...',
                'error': None,
                'extracted_count': 0,
                'failed_count': 0,
                'start_time': datetime.now()
            }
            
            # 启动后台线程
            self._extraction_thread = threading.Thread(
                target=self._background_extraction,
                args=(limit, email_ids),
                daemon=True
            )
            self._extraction_thread.start()
            
            message = f"Started extracting content for {len(email_ids) if email_ids else 'travel'} emails"
            return {"started": True, "message": message}
        
    def stop_extraction(self) -> str:
        """停止提取进程"""
        with self._lock:
            self._stop_flag.set()
            if self.extraction_progress.get('is_running'):
                self.extraction_progress['is_running'] = False
                self.extraction_progress['finished'] = True
                self.extraction_progress['message'] = 'Extraction stopped by user'
        return "Stop signal sent"
        
    def get_extraction_progress(self) -> Dict:
        """获取提取进度"""
        progress = self.extraction_progress.copy()
        
        # 计算百分比
        if progress.get('total', 0) > 0:
            progress['progress'] = round(
                (progress.get('current', 0) / progress['total']) * 100, 1
            )
        else:
            progress['progress'] = 0
            
        return progress
        
    def _mark_non_travel_emails_as_not_required(self):
        """Mark non-travel emails with pending extraction status as not_required"""
        db = SessionLocal()
        try:
            # First get the email IDs of non-travel emails
            non_travel_email_ids = [row[0] for row in db.query(Email.email_id).filter(
                ~Email.classification.in_(TRAVEL_CATEGORIES)
            ).all()]
            
            if non_travel_email_ids:
                # Find non-travel emails with EmailContent records that have pending extraction status
                updated_count = db.query(EmailContent).filter(
                    EmailContent.email_id.in_(non_travel_email_ids),
                    EmailContent.extraction_status.in_(['pending', 'failed'])
                ).update({
                    'extraction_status': 'not_required',
                    'extraction_error': None
                }, synchronize_session=False)
                
                if updated_count > 0:
                    db.commit()
                    logger.info(f"Marked {updated_count} non-travel emails as extraction_status='not_required'")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to mark non-travel emails as not_required: {e}")
        finally:
            db.close()
        
    def _background_extraction(self, limit: Optional[int] = None, email_ids: Optional[List[str]] = None):
        """后台提取线程
        
        Args:
            limit: 限制提取数量（仅在未指定email_ids时生效）
            email_ids: 指定要提取的邮件ID列表，如果为空则从数据库查询
        """
        try:
            logger.info(f"Starting email content extraction (limit: {limit}, email_ids: {len(email_ids) if email_ids else 'None'})")
            
            # First, mark non-travel emails as not_required
            self._mark_non_travel_emails_as_not_required()
            
            # 获取需要提取的邮件
            if email_ids:
                # 使用指定的邮件ID列表
                emails = self._get_emails_by_ids(email_ids)
                logger.info(f"Using specified email IDs: {len(emails)} emails found")
            else:
                # 从数据库查询需要提取的旅行邮件
                emails = self.get_travel_emails_for_extraction()
            
            logger.debug(f"get_travel_emails_for_extraction returned type: {type(emails)}, length: {len(emails) if emails else 0}")
            
            if not emails:
                with self._lock:
                    self.extraction_progress.update({
                        'finished': True,
                        'is_running': False,
                        'message': 'No travel emails found for extraction'
                    })
                return
                
            # 应用限制
            if limit:
                emails = emails[:limit]
                logger.debug(f"Applied limit {limit}, emails length now: {len(emails)}")
                
            self.extraction_progress.update({
                'total': len(emails),
                'message': f'Found {len(emails)} travel emails to extract'
            })
            
            logger.info(f"Processing {len(emails)} travel emails")
            
            # 处理每封邮件
            for i, email_info in enumerate(emails):
                if self._stop_flag.is_set():
                    logger.info("Extraction stopped by user")
                    break
                
                logger.debug(f"Processing email {i+1}/{len(emails)}, email_info type: {type(email_info)}")
                
                # Check if email_info is valid
                if not email_info:
                    logger.error(f"email_info at index {i} is None or empty!")
                    self.extraction_progress['failed_count'] += 1
                    continue
                
                # Safely get subject for progress message
                subject = email_info.get('subject', 'No subject') if isinstance(email_info, dict) else 'Invalid email_info'
                
                # Handle None subject
                if subject is None:
                    subject = 'No subject'
                
                # Safely slice the subject
                display_subject = subject[:50] if subject else ''
                
                self.extraction_progress.update({
                    'current': i + 1,
                    'message': f'Extracting: {display_subject}...'
                })
                
                # 提取邮件内容
                success = self._extract_single_email(email_info)
                
                if success:
                    self.extraction_progress['extracted_count'] += 1
                else:
                    self.extraction_progress['failed_count'] += 1
                    
            # 完成
            with self._lock:
                self.extraction_progress.update({
                    'finished': True,
                    'is_running': False,
                    'message': f'Completed: {self.extraction_progress["extracted_count"]} extracted, {self.extraction_progress["failed_count"]} failed'
                })
            
            logger.info(f"Extraction completed. Extracted: {self.extraction_progress['extracted_count']}, Failed: {self.extraction_progress['failed_count']}")
            
        except Exception as e:
            import traceback
            logger.error(f"Extraction failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            with self._lock:
                self.extraction_progress.update({
                    'finished': True,
                    'is_running': False,
                    'error': str(e),
                    'message': f'Extraction failed: {str(e)}'
                })
            
    def _extract_single_email(self, email_info: Dict) -> bool:
        """提取单个邮件的内容"""
        logger.debug(f"_extract_single_email called with email_info: {email_info}")
        
        if not email_info:
            logger.error("email_info is None!")
            return False
            
        email_id = email_info.get('email_id')
        if not email_id:
            logger.error(f"No email_id in email_info: {email_info}")
            return False
            
        db = SessionLocal()
        email_content = None
        
        try:
            logger.debug(f"Starting extraction for email {email_id}")
            
            # 创建或更新EmailContent记录
            email_content = db.query(EmailContent).filter_by(email_id=email_id).first()
            if not email_content:
                email_content = EmailContent(email_id=email_id)
                db.add(email_content)
                
            email_content.extraction_status = 'extracting'
            db.commit()
            
            # Check if extractor exists
            if not self.extractor:
                logger.error("self.extractor is None!")
                raise Exception("Email content extractor not initialized")
            
            logger.debug(f"Calling extractor.extract_email for {email_id}")
            
            # 使用提取器提取内容
            extracted_data = self.extractor.extract_email(email_id)
            
            logger.debug(f"Extracted data type: {type(extracted_data)}, value: {extracted_data}")
            
            # Check if extraction returned valid data
            if not extracted_data:
                raise Exception(f"Extraction returned None for email {email_id}")
            
            # 保存邮件正文到文件（microservice只读不写，所以这里需要保存）
            content_paths = self.extractor.save_email_content(
                email_id,
                extracted_data.get('text_content', ''),
                extracted_data.get('html_content', '')
            )
            
            # 更新数据库 - use get() to avoid KeyError
            email_content.content_text = extracted_data.get('text_content', '')
            email_content.content_html = extracted_data.get('html_content', '')
            email_content.has_attachments = extracted_data.get('has_attachments', False)
            email_content.attachments_info = json.dumps(extracted_data.get('attachments', []))
            email_content.attachments_count = len(extracted_data.get('attachments', []))
            email_content.extraction_status = 'completed'
            email_content.extracted_at = datetime.now()
            
            db.commit()
            
            logger.info(f"Successfully extracted content for email {email_id}")
            return True
            
        except Exception as e:
            import traceback
            logger.error(f"Failed to extract email {email_id}: {e}")
            logger.error(f"Traceback for email {email_id}: {traceback.format_exc()}")
            
            # 更新失败状态
            if email_content:
                email_content.extraction_status = 'failed'
                email_content.extraction_error = str(e)
                db.commit()
                
            return False
            
        finally:
            db.close()
            
    def get_email_content(self, email_id: str) -> Optional[Dict]:
        """获取邮件内容（用于发送给Gemini分析）"""
        db = SessionLocal()
        try:
            # 查询邮件内容
            content = db.query(EmailContent).filter_by(
                email_id=email_id,
                extraction_status='completed'
            ).first()
            
            if not content:
                return None
                
            # 查询邮件基本信息
            email = db.query(Email).filter_by(email_id=email_id).first()
            
            # 准备返回数据
            result = {
                'email_id': content.email_id,
                'subject': email.subject if email else '',
                'sender': email.sender if email else '',
                'date': email.date if email else '',
                'classification': email.classification if email else '',
                'content_text': content.content_text,
                'content_html': content.content_html,
                'has_attachments': content.has_attachments,
                'attachments': json.loads(content.attachments_info) if content.attachments_info else []
            }
            
            return result
            
        finally:
            db.close()
            
    def get_extraction_stats(self) -> Dict:
        """获取提取统计信息"""
        db = SessionLocal()
        try:
            # 统计旅行邮件
            total_travel_emails = db.query(Email).filter(
                Email.classification.in_(TRAVEL_CATEGORIES)
            ).count()
            
            # 统计已提取的
            extracted_count = db.query(EmailContent).filter(
                EmailContent.extraction_status == 'completed'
            ).count()
            
            # 统计失败的
            failed_count = db.query(EmailContent).filter(
                EmailContent.extraction_status == 'failed'
            ).count()
            
            # 统计待提取的
            pending_count = total_travel_emails - extracted_count - failed_count
            
            return {
                'total_travel_emails': total_travel_emails,
                'extracted': extracted_count,
                'failed': failed_count,
                'pending': pending_count,
                'extraction_rate': round(extracted_count / total_travel_emails * 100, 1) if total_travel_emails > 0 else 0
            }
            
        finally:
            db.close()
    
    def reset_all_content_extraction(self) -> Dict:
        """重置所有内容提取状态"""
        db = SessionLocal()
        try:
            # 确保没有正在运行的提取任务
            if self.extraction_progress.get('is_running'):
                return {
                    'success': False,
                    'message': '内容提取正在进行中，请先停止提取'
                }
            
            # Get travel and non-travel email IDs
            travel_email_ids = [row[0] for row in db.query(Email.email_id).filter(
                Email.classification.in_(TRAVEL_CATEGORIES)
            ).all()]
            
            non_travel_email_ids = [row[0] for row in db.query(Email.email_id).filter(
                ~Email.classification.in_(TRAVEL_CATEGORIES)
            ).all()]
            
            # Reset travel emails to pending
            travel_reset_count = 0
            if travel_email_ids:
                travel_reset_count = db.query(EmailContent).filter(
                    EmailContent.email_id.in_(travel_email_ids)
                ).update({
                    'extraction_status': 'pending',
                    'extraction_error': None,
                    'content_text': None,
                    'content_html': None,
                    'attachments_info': None,
                    'has_attachments': False,
                    'extracted_at': None,
                    'attachments_count': 0
                }, synchronize_session=False)
            
            # Mark non-travel emails as not_required
            non_travel_reset_count = 0
            if non_travel_email_ids:
                non_travel_reset_count = db.query(EmailContent).filter(
                    EmailContent.email_id.in_(non_travel_email_ids)
                ).update({
                    'extraction_status': 'not_required',
                    'extraction_error': None,
                    'content_text': None,
                    'content_html': None,
                    'attachments_info': None,
                    'has_attachments': False,
                    'extracted_at': None,
                    'attachments_count': 0
                }, synchronize_session=False)
            
            reset_count = travel_reset_count + non_travel_reset_count
            db.commit()
            
            # 重置进度状态
            with self._lock:
                self.extraction_progress = {
                    'is_running': False,
                    'total_emails': 0,
                    'processed_emails': 0,
                    'extracted_count': 0,
                    'failed_count': 0,
                    'finished': False,
                    'error': None,
                    'message': ''
                }
            
            logger.info(f"成功重置 {reset_count} 条内容提取记录 (旅行邮件: {travel_reset_count}, 非旅行邮件: {non_travel_reset_count})")
            
            return {
                'success': True,
                'reset_count': reset_count,
                'travel_reset_count': travel_reset_count,
                'non_travel_reset_count': non_travel_reset_count,
                'message': f'成功重置 {reset_count} 条内容提取记录 (旅行邮件: {travel_reset_count}, 非旅行邮件: {non_travel_reset_count})'
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"重置内容提取失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'重置内容提取失败: {str(e)}'
            }
        finally:
            db.close()