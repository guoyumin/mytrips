#!/usr/bin/env python3
"""
创建缺失的数据库表
"""

import os
import sys
sys.path.append('.')

from backend.database.config import SessionLocal, engine
from backend.database.models import Base

def create_missing_tables():
    """创建所有缺失的数据库表"""
    try:
        print("Creating missing database tables...")
        
        # 这会创建所有在models.py中定义但数据库中不存在的表
        Base.metadata.create_all(bind=engine)
        
        print("✅ All missing tables created successfully!")
        
        # 验证表创建
        with engine.connect() as conn:
            result = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in result]
            print(f"Current tables: {', '.join(sorted(tables))}")
            
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        raise

if __name__ == "__main__":
    create_missing_tables()