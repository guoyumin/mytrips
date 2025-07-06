"""
邮件缓存库
处理邮件的本地存储和检索
"""
import csv
import os
from typing import List, Dict, Optional, Set
from datetime import datetime
from pathlib import Path

class EmailCache:
    """邮件缓存管理器"""
    
    def __init__(self, cache_file: str):
        """
        初始化缓存管理器
        
        Args:
            cache_file: CSV 缓存文件路径
        """
        self.cache_file = cache_file
        self.headers = ['email_id', 'subject', 'from', 'date', 'timestamp', 
                       'is_classified', 'classification']
        self._ensure_cache_exists()
    
    def _ensure_cache_exists(self):
        """确保缓存文件存在"""
        if not os.path.exists(self.cache_file):
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writeheader()
    
    def get_cached_ids(self) -> Set[str]:
        """
        获取所有已缓存的邮件 ID
        
        Returns:
            邮件 ID 集合
        """
        cached_ids = set()
        
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cached_ids.add(row['email_id'])
        
        return cached_ids
    
    def add_emails(self, emails: List[Dict[str, str]]) -> int:
        """
        添加邮件到缓存
        
        Args:
            emails: 邮件信息列表
            
        Returns:
            新增的邮件数量
        """
        if not emails:
            return 0
        
        # 获取已缓存的 ID
        cached_ids = self.get_cached_ids()
        
        # 过滤出新邮件
        new_emails = []
        for email in emails:
            if email.get('email_id') not in cached_ids:
                # 确保所有必需字段都存在
                email_data = {
                    'email_id': email.get('email_id', ''),
                    'subject': email.get('subject', ''),
                    'from': email.get('from', ''),
                    'date': email.get('date', ''),
                    'timestamp': self._parse_timestamp(email.get('date', '')),
                    'is_classified': email.get('is_classified', 'false'),
                    'classification': email.get('classification', '')
                }
                new_emails.append(email_data)
        
        # 写入新邮件
        if new_emails:
            with open(self.cache_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writerows(new_emails)
        
        return len(new_emails)
    
    def get_emails(self, 
                   limit: Optional[int] = None,
                   offset: int = 0,
                   filter_classified: Optional[bool] = None) -> List[Dict[str, str]]:
        """
        从缓存获取邮件
        
        Args:
            limit: 返回数量限制
            offset: 偏移量
            filter_classified: 是否过滤已分类/未分类邮件
            
        Returns:
            邮件列表
        """
        emails = []
        
        if not os.path.exists(self.cache_file):
            return emails
        
        with open(self.cache_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for i, row in enumerate(reader):
                # 应用偏移
                if i < offset:
                    continue
                
                # 应用分类过滤
                if filter_classified is not None:
                    is_classified = row.get('is_classified', 'false').lower() == 'true'
                    
                    # 如果要获取未分类邮件，也包括分类失败的邮件
                    if filter_classified == False:
                        classification = row.get('classification', '')
                        is_failed = classification == 'classification_failed'
                        # 包括未分类的和分类失败的邮件
                        if is_classified and not is_failed:
                            continue
                    elif filter_classified == True:
                        # 只包括成功分类的邮件（排除失败的）
                        classification = row.get('classification', '')
                        is_failed = classification == 'classification_failed'
                        if not is_classified or is_failed:
                            continue
                
                emails.append(row)
                
                # 应用限制
                if limit and len(emails) >= limit:
                    break
        
        return emails
    
    def update_classifications(self, classifications: Dict[str, str]):
        """
        批量更新邮件分类
        
        Args:
            classifications: {email_id: classification} 字典
        """
        if not classifications:
            return
        
        # 读取所有邮件
        all_emails = []
        with open(self.cache_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            all_emails = list(reader)
        
        # 更新分类
        updated_count = 0
        for email in all_emails:
            if email['email_id'] in classifications:
                email['is_classified'] = 'true'
                email['classification'] = classifications[email['email_id']]
                updated_count += 1
        
        # 写回文件
        with open(self.cache_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writeheader()
            writer.writerows(all_emails)
        
        return updated_count
    
    def reset_failed_classifications(self) -> int:
        """
        重置分类失败的邮件为未分类状态
        
        Returns:
            重置的邮件数量
        """
        # 读取所有邮件
        all_emails = []
        with open(self.cache_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            all_emails = list(reader)
        
        # 重置失败的分类
        reset_count = 0
        for email in all_emails:
            if email.get('classification') == 'classification_failed':
                email['is_classified'] = 'false'
                email['classification'] = ''
                reset_count += 1
        
        # 写回文件
        with open(self.cache_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writeheader()
            writer.writerows(all_emails)
        
        return reset_count
    
    def get_statistics(self) -> Dict[str, any]:
        """
        获取缓存统计信息
        
        Returns:
            包含总数、已分类数、日期范围等的统计信息
        """
        stats = {
            'total_emails': 0,
            'classified_emails': 0,
            'date_range': None,
            'classifications': {}
        }
        
        if not os.path.exists(self.cache_file):
            return stats
        
        dates = []
        with open(self.cache_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                stats['total_emails'] += 1
                
                if row.get('is_classified', 'false').lower() == 'true':
                    stats['classified_emails'] += 1
                    
                    classification = row.get('classification', 'unknown')
                    stats['classifications'][classification] = \
                        stats['classifications'].get(classification, 0) + 1
                
                if row.get('date'):
                    dates.append(row['date'])
        
        # 计算日期范围
        if dates:
            # 解析所有日期
            parsed_dates = []
            for date_str in dates:
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(date_str)
                    parsed_dates.append(dt)
                except:
                    # 如果解析失败，跳过这个日期
                    continue
            
            if parsed_dates:
                # 转换为naive datetime进行比较
                naive_dates = []
                for dt in parsed_dates:
                    if dt.tzinfo is not None:
                        naive_dates.append(dt.replace(tzinfo=None))
                    else:
                        naive_dates.append(dt)
                
                # 取最大和最小值
                oldest_date = min(naive_dates)
                newest_date = max(naive_dates)
                stats['date_range'] = {
                    'oldest': oldest_date.strftime('%Y-%m-%d'),
                    'newest': newest_date.strftime('%Y-%m-%d')
                }
        
        return stats
    
    def _parse_timestamp(self, date_str: str) -> str:
        """解析日期字符串为时间戳"""
        if not date_str:
            return ''
        
        try:
            # 尝试解析 Gmail 日期格式
            # 示例: "Mon, 1 Jan 2024 12:00:00 +0000"
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return date_str