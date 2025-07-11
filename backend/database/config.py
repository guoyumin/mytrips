"""
数据库配置
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 使用config_manager获取数据库路径
try:
    from lib.config_manager import config_manager
    DATABASE_PATH = config_manager.get_database_path()
except ImportError:
    # 如果config_manager不可用，使用默认路径
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    DATABASE_PATH = os.path.join(PROJECT_ROOT, 'data', 'mytrips.db')

# 确保数据库目录存在
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

# SQLite 数据库路径
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    echo=False,  # 设为 True 可以看到 SQL 查询日志
    connect_args={"check_same_thread": False}  # SQLite 需要这个参数
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明基类
Base = declarative_base()

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """创建所有表"""
    Base.metadata.create_all(bind=engine)

def drop_tables():
    """删除所有表（慎用）"""
    Base.metadata.drop_all(bind=engine)