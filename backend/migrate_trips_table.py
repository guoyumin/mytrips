#!/usr/bin/env python3
"""
迁移trips表，添加缺失的字段
"""

import sqlite3
import os
from datetime import datetime

def get_database_path():
    """获取数据库路径"""
    # 尝试不同的可能路径
    possible_paths = [
        '/Users/guoyumin/Workspace/Mytrips/data/mytrips.db',
        '/Users/guoyumin/Workspace/Mytrips/backend/data/mytrips.db',
        'data/mytrips.db',
        '../data/mytrips.db'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    raise FileNotFoundError("Could not find mytrips.db database file")

def migrate_trips_table():
    """迁移trips表，添加缺失的字段"""
    
    db_path = get_database_path()
    print(f"Using database: {db_path}")
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查当前表结构
        cursor.execute("PRAGMA table_info(trips)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        print(f"Existing columns: {existing_columns}")
        
        # 需要添加的字段列表
        new_columns = [
            ('total_cost', 'REAL DEFAULT 0.0'),
            ('origin_city', 'VARCHAR(100) DEFAULT "Zurich"'),
            ('cities_visited', 'TEXT'),
            ('gemini_analysis', 'TEXT')
        ]
        
        # 添加缺失的字段
        for column_name, column_def in new_columns:
            if column_name not in existing_columns:
                sql = f"ALTER TABLE trips ADD COLUMN {column_name} {column_def}"
                print(f"Adding column: {sql}")
                cursor.execute(sql)
                print(f"✅ Added column: {column_name}")
            else:
                print(f"⏭️ Column {column_name} already exists")
        
        # 删除旧的status字段（如果存在且不在新模型中）
        if 'status' in existing_columns:
            print("Note: 'status' field exists but is not in the new model")
        
        # 提交更改
        conn.commit()
        print("✅ Migration completed successfully!")
        
        # 验证结果
        cursor.execute("PRAGMA table_info(trips)")
        updated_columns = [column[1] for column in cursor.fetchall()]
        print(f"Updated columns: {updated_columns}")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_trips_table()