"""
邮件内容提取器
负责从Gmail API提取邮件的完整内容和附件
"""
import base64
import json
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class EmailContentExtractor:
    """邮件内容提取器 - 处理邮件内容解析和附件下载"""
    
    def __init__(self, gmail_client, data_root: str):
        """
        初始化提取器
        
        Args:
            gmail_client: Gmail客户端实例
            data_root: 数据存储根目录
        """
        self.gmail_client = gmail_client
        self.data_root = Path(data_root)
        
    def extract_email(self, email_id: str) -> Dict:
        """
        提取单个邮件的完整内容
        
        Args:
            email_id: Gmail邮件ID
            
        Returns:
            包含内容和附件信息的字典
        """
        try:
            # 获取邮件完整内容
            message = self.gmail_client.get_message(email_id)
            
            if not message:
                logger.error(f"Failed to get message {email_id} from Gmail - message is None")
                # Return empty content instead of raising exception
                return {
                    'text_content': '',
                    'html_content': '',
                    'attachments': [],
                    'has_attachments': False
                }
                
            # 解析邮件内容
            text_content, html_content = self._extract_message_content(message)
            
            # 处理附件
            attachments_info = self._extract_attachments(email_id, message)
            
            return {
                'text_content': text_content,
                'html_content': html_content,
                'attachments': attachments_info,
                'has_attachments': len(attachments_info) > 0
            }
        except Exception as e:
            logger.error(f"Error extracting email {email_id}: {e}")
            # Return empty content on error
            return {
                'text_content': '',
                'html_content': '',
                'attachments': [],
                'has_attachments': False
            }
        
    def _extract_message_content(self, message: Dict) -> Tuple[str, str]:
        """
        从邮件消息中提取文本和HTML内容
        
        Args:
            message: Gmail API返回的消息对象
            
        Returns:
            (纯文本内容, HTML内容)
        """
        text_content = ""
        html_content = ""
        
        def extract_parts(parts):
            nonlocal text_content, html_content
            
            for part in parts:
                mime_type = part.get('mimeType', '')
                
                if mime_type == 'text/plain':
                    data = part.get('body', {}).get('data', '')
                    if data:
                        text_content += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        
                elif mime_type == 'text/html':
                    data = part.get('body', {}).get('data', '')
                    if data:
                        html_content += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        
                elif mime_type.startswith('multipart/'):
                    # 递归处理多部分内容
                    if 'parts' in part:
                        extract_parts(part['parts'])
                        
        # 获取payload
        payload = message.get('payload', {})
        
        # 简单邮件（没有parts）
        if payload.get('body', {}).get('data'):
            mime_type = payload.get('mimeType', '')
            data = payload['body']['data']
            
            if mime_type == 'text/plain':
                text_content = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            elif mime_type == 'text/html':
                html_content = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                
        # 多部分邮件
        elif 'parts' in payload:
            extract_parts(payload['parts'])
            
        return text_content.strip(), html_content.strip()
        
    def _extract_attachments(self, email_id: str, message: Dict) -> List[Dict]:
        """
        提取并保存附件
        
        Args:
            email_id: Gmail邮件ID
            message: Gmail API返回的消息对象
            
        Returns:
            附件信息列表
        """
        attachments = []
        
        def process_parts(parts):
            for part in parts:
                filename = part.get('filename', '')
                
                if filename:
                    # 这是一个附件
                    attachment_info = {
                        'filename': filename,
                        'mime_type': part.get('mimeType', ''),
                        'size': part.get('body', {}).get('size', 0),
                        'attachment_id': part.get('body', {}).get('attachmentId', '')
                    }
                    
                    # 下载并保存附件
                    if attachment_info['attachment_id']:
                        saved_path = self._save_attachment(
                            email_id, 
                            attachment_info['attachment_id'],
                            filename
                        )
                        
                        if saved_path:
                            attachment_info['saved_path'] = saved_path
                            attachment_info['full_path'] = str(self.data_root / saved_path)
                            
                    attachments.append(attachment_info)
                    
                # 递归处理嵌套部分
                if 'parts' in part:
                    process_parts(part['parts'])
                    
        # 处理payload
        payload = message.get('payload', {})
        if 'parts' in payload:
            process_parts(payload['parts'])
            
        return attachments
        
    def _save_attachment(self, email_id: str, attachment_id: str, filename: str) -> Optional[str]:
        """
        下载并保存单个附件
        
        Args:
            email_id: Gmail邮件ID
            attachment_id: 附件ID
            filename: 文件名
            
        Returns:
            相对于data_root的保存路径，失败返回None
        """
        try:
            # 创建邮件专属目录
            email_dir = self.data_root / email_id / 'attachments'
            email_dir.mkdir(parents=True, exist_ok=True)
            
            # 下载附件
            attachment_data = self.gmail_client.get_attachment(email_id, attachment_id)
            
            if attachment_data:
                # 处理文件名冲突
                file_path = email_dir / filename
                
                if file_path.exists():
                    base_name = file_path.stem
                    extension = file_path.suffix
                    counter = 1
                    
                    while file_path.exists():
                        file_path = email_dir / f"{base_name}_{counter}{extension}"
                        counter += 1
                        
                # 保存文件
                with open(file_path, 'wb') as f:
                    f.write(attachment_data)
                    
                logger.info(f"Saved attachment: {file_path}")
                
                # 返回相对路径
                return str(file_path.relative_to(self.data_root))
                
        except Exception as e:
            logger.error(f"Failed to save attachment {filename}: {e}")
            
        return None
        
    def save_email_content(self, email_id: str, text_content: str, html_content: str) -> Dict[str, str]:
        """
        保存邮件正文内容到文件
        
        Args:
            email_id: Gmail邮件ID
            text_content: 纯文本内容
            html_content: HTML内容
            
        Returns:
            保存的文件路径字典
        """
        paths = {}
        
        try:
            # 创建邮件目录
            email_dir = self.data_root / email_id
            email_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存文本内容
            if text_content:
                text_path = email_dir / 'content.txt'
                with open(text_path, 'w', encoding='utf-8') as f:
                    f.write(text_content)
                paths['text'] = str(text_path.relative_to(self.data_root))
                
            # 保存HTML内容
            if html_content:
                html_path = email_dir / 'content.html'
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                paths['html'] = str(html_path.relative_to(self.data_root))
                
            # 保存元数据
            metadata = {
                'email_id': email_id,
                'has_text': bool(text_content),
                'has_html': bool(html_content),
                'extracted_at': datetime.now().isoformat()
            }
            
            metadata_path = email_dir / 'metadata.json'
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
                
            paths['metadata'] = str(metadata_path.relative_to(self.data_root))
            
        except Exception as e:
            logger.error(f"Failed to save email content for {email_id}: {e}")
            
        return paths