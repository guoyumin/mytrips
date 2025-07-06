"""
邮件内容提取服务
管理邮件内容提取的业务逻辑和进度跟踪
"""
import json
import logging
import threading
from typing import Dict, List, Optional
from datetime import datetime

from lib.gmail_client import GmailClient
from lib.email_content_extractor import EmailContentExtractor
from lib.config_manager import config_manager
from database.config import SessionLocal
from database.models import Email, EmailContent

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
        
    def get_travel_emails_for_extraction(self) -> List[Dict]:
        """获取需要提取内容的旅行相关邮件"""
        db = SessionLocal()
        try:
            # 查询所有旅行相关邮件，且还未成功提取内容的
            travel_categories = [
                'flight', 'hotel', 'car_rental', 'train', 'cruise', 
                'tour', 'travel_insurance', 'flight_change', 
                'hotel_change', 'other_travel'
            ]
            
            # 使用子查询找出已成功提取的邮件ID
            extracted_ids = db.query(EmailContent.email_id).filter(
                EmailContent.extraction_status == 'completed'
            ).subquery()
            
            # 查询旅行邮件且不在已提取列表中
            emails = db.query(Email).filter(
                Email.classification.in_(travel_categories),
                ~Email.email_id.in_(extracted_ids)
            ).all()
            
            return [{
                'email_id': email.email_id,
                'subject': email.subject,
                'sender': email.sender,
                'date': email.date,
                'classification': email.classification
            } for email in emails]
            
        finally:
            db.close()
            
    def start_extraction(self, limit: Optional[int] = None) -> Dict:
        """开始提取邮件内容"""
        if self.extraction_progress.get('is_running'):
            return {"started": False, "message": "Extraction already in progress"}
            
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
            args=(limit,),
            daemon=True
        )
        self._extraction_thread.start()
        
        return {"started": True, "message": f"Started extracting content for travel emails"}
        
    def stop_extraction(self) -> str:
        """停止提取进程"""
        self._stop_flag.set()
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
        
    def _background_extraction(self, limit: Optional[int] = None):
        """后台提取线程"""
        try:
            logger.info(f"Starting email content extraction (limit: {limit})")
            
            # 获取需要提取的邮件
            emails = self.get_travel_emails_for_extraction()
            
            if not emails:
                self.extraction_progress.update({
                    'finished': True,
                    'is_running': False,
                    'message': 'No travel emails found for extraction'
                })
                return
                
            # 应用限制
            if limit:
                emails = emails[:limit]
                
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
                    
                self.extraction_progress.update({
                    'current': i + 1,
                    'message': f'Extracting: {email_info["subject"][:50]}...'
                })
                
                # 提取邮件内容
                success = self._extract_single_email(email_info)
                
                if success:
                    self.extraction_progress['extracted_count'] += 1
                else:
                    self.extraction_progress['failed_count'] += 1
                    
            # 完成
            self.extraction_progress.update({
                'finished': True,
                'is_running': False,
                'message': f'Completed: {self.extraction_progress["extracted_count"]} extracted, {self.extraction_progress["failed_count"]} failed'
            })
            
            logger.info(f"Extraction completed. Extracted: {self.extraction_progress['extracted_count']}, Failed: {self.extraction_progress['failed_count']}")
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            self.extraction_progress.update({
                'finished': True,
                'is_running': False,
                'error': str(e),
                'message': f'Extraction failed: {str(e)}'
            })
            
    def _extract_single_email(self, email_info: Dict) -> bool:
        """提取单个邮件的内容"""
        email_id = email_info['email_id']
        db = SessionLocal()
        email_content = None
        
        try:
            # 创建或更新EmailContent记录
            email_content = db.query(EmailContent).filter_by(email_id=email_id).first()
            if not email_content:
                email_content = EmailContent(email_id=email_id)
                db.add(email_content)
                
            email_content.extraction_status = 'extracting'
            db.commit()
            
            # 使用提取器提取内容
            extracted_data = self.extractor.extract_email(email_id)
            
            # 保存邮件正文到文件（可选）
            content_paths = self.extractor.save_email_content(
                email_id,
                extracted_data['text_content'],
                extracted_data['html_content']
            )
            
            # 更新数据库
            email_content.content_text = extracted_data['text_content']
            email_content.content_html = extracted_data['html_content']
            email_content.has_attachments = extracted_data['has_attachments']
            email_content.attachments_info = json.dumps(extracted_data['attachments'])
            email_content.attachments_count = len(extracted_data['attachments'])
            email_content.extraction_status = 'completed'
            email_content.extracted_at = datetime.now()
            
            db.commit()
            
            logger.info(f"Successfully extracted content for email {email_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to extract email {email_id}: {e}")
            
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
            travel_categories = [
                'flight', 'hotel', 'car_rental', 'train', 'cruise', 
                'tour', 'travel_insurance', 'flight_change', 
                'hotel_change', 'other_travel'
            ]
            
            total_travel_emails = db.query(Email).filter(
                Email.classification.in_(travel_categories)
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