#!/usr/bin/env python3
"""
数据库初始化脚本
"""

import os
import sys

# 添加后端目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from backend.database.config import engine, create_tables, DATABASE_URL
from backend.database.models import Base

def init_database():
    """初始化数据库"""
    print("🗄️  初始化 MyTrips 数据库...")
    print(f"数据库位置: {DATABASE_URL}")
    
    try:
        # 创建所有表
        create_tables()
        print("✅ 数据库表创建成功！")
        
        # 显示创建的表
        print("\n📋 已创建的表:")
        for table_name in Base.metadata.tables.keys():
            print(f"  • {table_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False

def check_database():
    """检查数据库状态"""
    print("🔍 检查数据库状态...")
    
    try:
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        if existing_tables:
            print(f"✅ 找到 {len(existing_tables)} 个表:")
            for table in existing_tables:
                print(f"  • {table}")
        else:
            print("ℹ️  数据库中没有表")
        
        return existing_tables
        
    except Exception as e:
        print(f"❌ 检查数据库失败: {e}")
        return []

if __name__ == "__main__":
    print("=" * 50)
    print("MyTrips 数据库管理")
    print("=" * 50)
    
    # 检查现有状态
    existing_tables = check_database()
    
    if existing_tables:
        print(f"\n⚠️  数据库已存在，包含 {len(existing_tables)} 个表")
        answer = input("是否要重新初始化数据库？(y/N): ").lower()
        if answer != 'y':
            print("取消操作")
            sys.exit(0)
    
    # 初始化数据库
    print()
    success = init_database()
    
    if success:
        print("\n🎉 数据库初始化完成！")
        print("现在可以开始使用数据库存储邮件数据了。")
    else:
        print("\n💥 数据库初始化失败！")
        sys.exit(1)