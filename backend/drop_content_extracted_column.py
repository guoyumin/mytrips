#!/usr/bin/env python3
"""
删除Email表中的content_extracted列
因为我们现在使用EmailContent表来跟踪提取状态
"""

import os
import sys
from sqlalchemy import text

# 添加后端目录到Python路径
sys.path.append(os.path.dirname(__file__))

from database.config import SessionLocal, engine
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def drop_content_extracted_column():
    """删除content_extracted列"""
    try:
        logger.info("开始删除content_extracted列...")
        
        with engine.connect() as connection:
            # 首先检查列是否存在
            result = connection.execute(text("""
                PRAGMA table_info(emails);
            """))
            
            columns = [row[1] for row in result]
            
            if 'content_extracted' not in columns:
                logger.info("content_extracted列不存在，无需删除")
                return True
            
            logger.info("发现content_extracted列，开始删除...")
            
            # SQLite不支持直接DROP COLUMN，需要重建表
            # 1. 创建临时表
            connection.execute(text("""
                CREATE TABLE emails_new (
                    id INTEGER PRIMARY KEY,
                    email_id VARCHAR(255) NOT NULL UNIQUE,
                    subject TEXT,
                    sender VARCHAR(500),
                    date VARCHAR(100),
                    timestamp DATETIME,
                    is_classified BOOLEAN DEFAULT 0,
                    classification VARCHAR(50),
                    content TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # 2. 复制数据（排除content_extracted列）
            connection.execute(text("""
                INSERT INTO emails_new (
                    id, email_id, subject, sender, date, timestamp,
                    is_classified, classification, content, created_at, updated_at
                )
                SELECT 
                    id, email_id, subject, sender, date, timestamp,
                    is_classified, classification, content, created_at, updated_at
                FROM emails;
            """))
            
            # 3. 删除旧表
            connection.execute(text("DROP TABLE emails;"))
            
            # 4. 重命名新表
            connection.execute(text("ALTER TABLE emails_new RENAME TO emails;"))
            
            # 5. 重建索引
            connection.execute(text("""
                CREATE INDEX idx_emails_email_id ON emails(email_id);
            """))
            connection.execute(text("""
                CREATE INDEX idx_emails_is_classified ON emails(is_classified);
            """))
            connection.execute(text("""
                CREATE INDEX idx_emails_classification ON emails(classification);
            """))
            connection.execute(text("""
                CREATE INDEX idx_emails_date_classified ON emails(timestamp, is_classified);
            """))
            
            connection.commit()
            
        logger.info("✅ 成功删除content_extracted列")
        return True
        
    except Exception as e:
        logger.error(f"❌ 删除content_extracted列失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("删除Email表中的content_extracted列")
    print("=" * 60)
    
    try:
        success = drop_content_extracted_column()
        
        if success:
            print("\n🎉 数据库迁移成功完成！")
            print("现在只使用EmailContent表来跟踪内容提取状态")
            return True
        else:
            print("\n❌ 数据库迁移失败")
            return False
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)