"""
数据库模型定义
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Index
from sqlalchemy.sql import func
from datetime import datetime
from database.config import Base

class Email(Base):
    """邮件表"""
    __tablename__ = "emails"
    
    # 主键
    id = Column(Integer, primary_key=True, index=True)
    
    # 邮件基本信息
    email_id = Column(String(255), unique=True, index=True, nullable=False)  # Gmail 邮件 ID
    subject = Column(Text, nullable=True)  # 邮件主题
    sender = Column(String(500), nullable=True)  # 发件人
    date = Column(String(100), nullable=True)  # 邮件日期（原始格式）
    timestamp = Column(DateTime, nullable=True)  # 时间戳
    
    # 分类信息
    is_classified = Column(Boolean, default=False, index=True)  # 是否已分类
    classification = Column(String(50), nullable=True, index=True)  # 分类结果
    
    # 邮件内容（为下一步内容提取准备）
    content = Column(Text, nullable=True)  # 邮件正文内容
    content_extracted = Column(Boolean, default=False, index=True)  # 是否已提取内容
    
    # 元数据
    created_at = Column(DateTime, default=func.now())  # 创建时间
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())  # 更新时间
    
    # 索引
    __table_args__ = (
        Index('idx_emails_date_classified', 'timestamp', 'is_classified'),
        Index('idx_emails_classification', 'classification'),
        Index('idx_emails_content_extracted', 'content_extracted'),
    )
    
    def __repr__(self):
        return f"<Email(id={self.id}, email_id='{self.email_id}', subject='{self.subject[:50] if self.subject else 'None'}...')>"
    
    def is_travel_related(self) -> bool:
        """判断是否为旅行相关邮件"""
        travel_categories = {
            'flight', 'hotel', 'car_rental', 'train', 'cruise', 
            'tour', 'travel_insurance', 'flight_change', 
            'hotel_change', 'other_travel'
        }
        return self.classification in travel_categories

class Trip(Base):
    """旅行记录表（未来扩展用）"""
    __tablename__ = "trips"
    
    # 主键
    id = Column(Integer, primary_key=True, index=True)
    
    # 旅行基本信息
    name = Column(String(200), nullable=False)  # 旅行名称
    destination = Column(String(200), nullable=True)  # 目的地
    start_date = Column(DateTime, nullable=True)  # 开始日期
    end_date = Column(DateTime, nullable=True)  # 结束日期
    
    # 旅行状态
    status = Column(String(20), default='planned')  # planned, ongoing, completed, cancelled
    
    # 描述信息
    description = Column(Text, nullable=True)  # 旅行描述
    notes = Column(Text, nullable=True)  # 备注
    
    # 元数据
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_trips_dates', 'start_date', 'end_date'),
        Index('idx_trips_status', 'status'),
    )
    
    def __repr__(self):
        return f"<Trip(id={self.id}, name='{self.name}', destination='{self.destination}')>"

class ClassificationStats(Base):
    """分类统计表"""
    __tablename__ = "classification_stats"
    
    # 主键
    id = Column(Integer, primary_key=True, index=True)
    
    # 统计信息
    date = Column(DateTime, default=func.now(), index=True)  # 统计日期
    total_emails = Column(Integer, default=0)  # 总邮件数
    classified_emails = Column(Integer, default=0)  # 已分类邮件数
    travel_emails = Column(Integer, default=0)  # 旅行相关邮件数
    
    # 分类计数
    flight_count = Column(Integer, default=0)
    hotel_count = Column(Integer, default=0)
    train_count = Column(Integer, default=0)
    car_rental_count = Column(Integer, default=0)
    marketing_count = Column(Integer, default=0)
    not_travel_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    
    # 元数据
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<ClassificationStats(date={self.date}, total={self.total_emails}, travel={self.travel_emails})>"