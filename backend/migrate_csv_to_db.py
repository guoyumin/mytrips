#!/usr/bin/env python3
"""
CSV数据迁移到SQLite数据库
"""

import os
import sys
import csv
from datetime import datetime
from typing import Dict, List

# 添加后端目录到Python路径
sys.path.append(os.path.dirname(__file__))

from database.config import SessionLocal, engine
from database.models import Email, Base
from lib.config_manager import config_manager
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_email_date(date_str: str) -> datetime:
    """解析邮件日期字符串为datetime对象"""
    if not date_str:
        return None
    
    try:
        # 尝试解析 Gmail 日期格式
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        # 移除时区信息以避免SQLite兼容性问题
        return dt.replace(tzinfo=None)
    except Exception as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}")
        return None

def load_csv_data(csv_file: str) -> List[Dict]:
    """从CSV文件加载数据"""
    emails = []
    
    if not os.path.exists(csv_file):
        logger.warning(f"CSV file not found: {csv_file}")
        return emails
    
    logger.info(f"Loading data from CSV: {csv_file}")
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row_num, row in enumerate(reader, 1):
            try:
                email_data = {
                    'email_id': row.get('email_id', '').strip(),
                    'subject': row.get('subject', '').strip() or None,
                    'sender': row.get('from', '').strip() or None,  # CSV中是'from'，DB中是'sender'
                    'date': row.get('date', '').strip() or None,
                    'timestamp': parse_email_date(row.get('date', '')),
                    'is_classified': row.get('is_classified', 'false').lower() == 'true',
                    'classification': row.get('classification', '').strip() or None
                }
                
                # 验证必需字段
                if not email_data['email_id']:
                    logger.warning(f"Row {row_num}: Missing email_id, skipping")
                    continue
                
                emails.append(email_data)
                
            except Exception as e:
                logger.error(f"Row {row_num}: Error processing row: {e}")
                continue
    
    logger.info(f"Loaded {len(emails)} emails from CSV")
    return emails

def migrate_to_database(emails: List[Dict]) -> int:
    """将邮件数据迁移到数据库"""
    if not emails:
        logger.info("No emails to migrate")
        return 0
    
    db = SessionLocal()
    try:
        # 获取现有邮件ID以避免重复
        existing_ids = set(
            db.query(Email.email_id).all()
        )
        existing_ids = {email_id[0] for email_id in existing_ids}
        
        logger.info(f"Found {len(existing_ids)} existing emails in database")
        
        # 过滤出新邮件
        new_emails = []
        for email_data in emails:
            if email_data['email_id'] not in existing_ids:
                new_emails.append(Email(**email_data))
        
        logger.info(f"Preparing to insert {len(new_emails)} new emails")
        
        if new_emails:
            # 批量插入
            db.add_all(new_emails)
            db.commit()
            logger.info(f"✅ Successfully migrated {len(new_emails)} emails to database")
        else:
            logger.info("No new emails to migrate (all already exist)")
        
        return len(new_emails)
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()

def get_migration_stats(db_session) -> Dict:
    """获取迁移统计信息"""
    stats = {}
    
    try:
        # 总邮件数
        stats['total_emails'] = db_session.query(Email).count()
        
        # 已分类邮件数
        stats['classified_emails'] = db_session.query(Email).filter(Email.is_classified == True).count()
        
        # 分类分布
        classifications = db_session.query(
            Email.classification, 
            db_session.query(Email).filter(Email.classification == Email.classification).count()
        ).filter(Email.classification.isnot(None)).distinct().all()
        
        stats['classifications'] = {cls: count for cls, count in classifications}
        
        # 日期范围
        date_range = db_session.query(
            db_session.query(Email.timestamp).filter(Email.timestamp.isnot(None)).order_by(Email.timestamp.asc()).first(),
            db_session.query(Email.timestamp).filter(Email.timestamp.isnot(None)).order_by(Email.timestamp.desc()).first()
        ).first()
        
        if date_range and date_range[0] and date_range[1]:
            stats['date_range'] = {
                'oldest': date_range[0][0].strftime('%Y-%m-%d'),
                'newest': date_range[1][0].strftime('%Y-%m-%d')
            }
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
    
    return stats

def main():
    """主函数"""
    print("=" * 60)
    print("MyTrips: CSV数据迁移到SQLite数据库")
    print("=" * 60)
    
    try:
        # 获取CSV文件路径
        csv_file = config_manager.get_cache_file_path()
        logger.info(f"CSV file: {csv_file}")
        
        # 检查CSV文件是否存在
        if not os.path.exists(csv_file):
            logger.error(f"CSV file not found: {csv_file}")
            return False
        
        # 加载CSV数据
        emails = load_csv_data(csv_file)
        
        if not emails:
            logger.warning("No emails found in CSV file")
            return True
        
        # 迁移到数据库
        migrated_count = migrate_to_database(emails)
        
        # 显示统计信息
        db = SessionLocal()
        try:
            stats = get_migration_stats(db)
            
            print(f"\n📊 迁移完成统计:")
            print(f"  • 新增邮件: {migrated_count}")
            print(f"  • 数据库总邮件数: {stats.get('total_emails', 0)}")
            print(f"  • 已分类邮件数: {stats.get('classified_emails', 0)}")
            
            if stats.get('date_range'):
                print(f"  • 日期范围: {stats['date_range']['oldest']} 到 {stats['date_range']['newest']}")
            
            if stats.get('classifications'):
                print(f"  • 分类分布:")
                for classification, count in stats['classifications'].items():
                    print(f"    - {classification}: {count}")
        
        finally:
            db.close()
        
        print(f"\n🎉 数据迁移成功完成！")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)