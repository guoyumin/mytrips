"""
Gmail 客户端库
处理 Gmail API 认证和基本操作
"""
import os
import json
import pickle
import base64
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GmailClient:
    """Gmail API 客户端"""
    
    # Gmail API 访问范围
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    def __init__(self, credentials_path: str, token_path: str):
        """
        初始化 Gmail 客户端
        
        Args:
            credentials_path: OAuth2 凭据文件路径
            token_path: 访问令牌存储路径
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """处理 OAuth2 认证流程"""
        creds = None
        
        # 加载已保存的令牌
        if os.path.exists(self.token_path):
            try:
                # 尝试 JSON 格式
                if self.token_path.endswith('.json'):
                    with open(self.token_path, 'r') as token:
                        token_data = json.load(token)
                        creds = Credentials.from_authorized_user_info(token_data, self.SCOPES)
                else:
                    # 尝试 pickle 格式
                    with open(self.token_path, 'rb') as token:
                        creds = pickle.load(token)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # 如果JSON解析失败，尝试pickle格式
                try:
                    with open(self.token_path, 'rb') as token:
                        creds = pickle.load(token)
                except:
                    creds = None
        
        # 如果没有有效凭据，需要用户登录
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # 保存凭据供下次使用 - 保存为JSON格式
            if self.token_path.endswith('.json'):
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
            else:
                with open(self.token_path, 'wb') as token:
                    pickle.dump(creds, token)
        
        self.service = build('gmail', 'v1', credentials=creds)
    
    def list_messages(self, query: str = '', max_results: int = 100) -> List[Dict[str, str]]:
        """
        列出符合查询条件的邮件
        
        Args:
            query: Gmail 搜索查询语句
            max_results: 最大返回结果数
            
        Returns:
            邮件 ID 和线程 ID 列表
        """
        try:
            results = []
            page_token = None
            
            while len(results) < max_results:
                response = self.service.users().messages().list(
                    userId='me',
                    q=query,
                    pageToken=page_token,
                    maxResults=min(100, max_results - len(results))
                ).execute()
                
                messages = response.get('messages', [])
                results.extend(messages)
                
                page_token = response.get('nextPageToken')
                if not page_token or len(results) >= max_results:
                    break
            
            return results[:max_results]
            
        except HttpError as error:
            raise Exception(f"Gmail API 错误: {error}")
    
    def list_messages_all(self, query: str = '') -> List[Dict[str, str]]:
        """
        获取所有符合查询条件的邮件（不设置数量限制）
        
        Args:
            query: Gmail 搜索查询语句
            
        Returns:
            所有匹配的邮件 ID 和线程 ID 列表
        """
        try:
            results = []
            page_token = None
            
            while True:
                response = self.service.users().messages().list(
                    userId='me',
                    q=query,
                    pageToken=page_token,
                    maxResults=500  # Gmail API 单次调用最大值
                ).execute()
                
                messages = response.get('messages', [])
                results.extend(messages)
                
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
            
            return results
            
        except HttpError as error:
            raise Exception(f"Gmail API 错误: {error}")
    
    def get_message(self, message_id: str, format: str = 'full') -> Dict[str, Any]:
        """
        获取邮件详情
        
        Args:
            message_id: 邮件 ID
            format: 返回格式 ('full', 'metadata', 'minimal')
            
        Returns:
            邮件详细信息
        """
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format=format
            ).execute()
            return message
            
        except HttpError as error:
            raise Exception(f"获取邮件失败: {error}")
    
    def get_message_headers(self, message_id: str) -> Dict[str, str]:
        """
        获取邮件头信息
        
        Args:
            message_id: 邮件 ID
            
        Returns:
            包含 Subject, From, Date 等的字典
        """
        message = self.get_message(message_id, format='metadata')
        headers = {}
        
        for header in message.get('payload', {}).get('headers', []):
            name = header['name'].lower()
            if name in ['subject', 'from', 'to', 'date']:
                headers[name] = header['value']
        
        return headers
    
    def get_attachment(self, message_id: str, attachment_id: str) -> Optional[bytes]:
        """
        下载邮件附件
        
        Args:
            message_id: 邮件 ID
            attachment_id: 附件 ID
            
        Returns:
            附件的二进制数据
        """
        try:
            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            # 解码附件数据
            data = attachment['data']
            file_data = base64.urlsafe_b64decode(data)
            
            return file_data
            
        except HttpError as error:
            logger.error(f"Failed to download attachment: {error}")
            return None
    
    def search_emails_by_date_range_paginated(self, start_date: datetime, end_date: datetime, 
                                              page_token: Optional[str] = None, 
                                              max_results: int = 100) -> Dict[str, any]:
        """
        搜索指定日期范围内的邮件（分页版本）
        
        Args:
            start_date: 开始日期 (inclusive)
            end_date: 结束日期 (inclusive)
            page_token: 分页token，用于获取下一页
            max_results: 每页最大结果数
            
        Returns:
            包含邮件列表和下一页token的字典
        """
        after_date = start_date.strftime('%Y/%m/%d')
        before_date = (end_date + timedelta(days=1)).strftime('%Y/%m/%d')
        query = f'after:{after_date} before:{before_date}'
        
        logger.info(f"Searching emails with query: {query}, page_token: {page_token}")
        
        try:
            response = self.service.users().messages().list(
                userId='me',
                q=query,
                pageToken=page_token,
                maxResults=max_results
            ).execute()
            
            return {
                'messages': response.get('messages', []),
                'nextPageToken': response.get('nextPageToken'),
                'resultSizeEstimate': response.get('resultSizeEstimate', 0)
            }
        except Exception as error:
            logger.error(f'An error occurred: {error}')
            return {'messages': [], 'nextPageToken': None, 'resultSizeEstimate': 0}
    
    def search_emails_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, str]]:
        """
        搜索指定日期范围内的邮件
        
        Args:
            start_date: 开始日期 (inclusive)
            end_date: 结束日期 (inclusive)
            
        Returns:
            所有在指定时间范围内的邮件列表
        """
        # Gmail 查询格式: after:2024/1/1 before:2024/1/31
        # Note: Gmail's 'before' is exclusive, so we add one day
        after_date = start_date.strftime('%Y/%m/%d')
        before_date = (end_date + timedelta(days=1)).strftime('%Y/%m/%d')
        query = f'after:{after_date} before:{before_date}'
        
        logger.info(f"Searching emails with query: {query}")
        
        # 获取所有匹配的邮件，不设置人为限制
        return self.list_messages_all(query)
    
    def search_emails_by_date(self, days_back: int = 365) -> List[Dict[str, str]]:
        """
        搜索指定天数内的邮件 (backward compatibility)
        
        Args:
            days_back: 搜索多少天前的邮件
            
        Returns:
            所有在指定时间范围内的邮件列表
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        return self.search_emails_by_date_range(start_date, end_date)
    
    def batch_get_headers(self, message_ids: List[str], batch_size: int = 100) -> List[Dict[str, str]]:
        """
        批量获取邮件头信息
        
        Args:
            message_ids: 邮件 ID 列表
            batch_size: 批处理大小
            
        Returns:
            邮件头信息列表
        """
        headers_list = []
        
        for i in range(0, len(message_ids), batch_size):
            batch = message_ids[i:i + batch_size]
            batch_request = self.service.new_batch_http_request()
            
            for msg_id in batch:
                batch_request.add(
                    self.service.users().messages().get(
                        userId='me',
                        id=msg_id,
                        format='metadata',
                        metadataHeaders=['Subject', 'From', 'Date']
                    )
                )
            
            batch_request.execute()
            
            # 处理批量响应
            for msg_id in batch:
                try:
                    headers = self.get_message_headers(msg_id)
                    headers['email_id'] = msg_id
                    headers_list.append(headers)
                except Exception as e:
                    print(f"获取邮件 {msg_id} 失败: {e}")
        
        return headers_list