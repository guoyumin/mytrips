"""
数据库模型定义
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Index, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
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
    
    # 元数据
    created_at = Column(DateTime, default=func.now())  # 创建时间
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())  # 更新时间
    
    # 索引
    __table_args__ = (
        Index('idx_emails_date_classified', 'timestamp', 'is_classified'),
        Index('idx_emails_classification', 'classification'),
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
    
    # 新增字段
    total_cost = Column(Float, default=0.0)  # 总费用
    origin_city = Column(String(100), default='Zurich')  # 出发城市
    cities_visited = Column(Text, nullable=True)  # JSON格式的访问城市列表
    gemini_analysis = Column(Text, nullable=True)  # JSON格式的Gemini分析结果
    
    # 描述信息
    description = Column(Text, nullable=True)  # 旅行描述
    notes = Column(Text, nullable=True)  # 备注
    
    # 元数据
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_trips_dates', 'start_date', 'end_date'),
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

class EmailContent(Base):
    """邮件内容表 - 存储详细的邮件内容和附件信息"""
    __tablename__ = 'email_content'
    
    id = Column(Integer, primary_key=True)
    email_id = Column(String(255), ForeignKey('emails.email_id'), unique=True, nullable=False)
    
    # 邮件内容
    content_text = Column(Text)  # 纯文本内容
    content_html = Column(Text)  # HTML内容
    
    # 附件信息
    has_attachments = Column(Boolean, default=False)
    attachments_info = Column(Text)  # JSON格式的附件信息
    attachments_count = Column(Integer, default=0)
    
    # 提取状态
    extraction_status = Column(String(50), default='pending')  # pending, extracting, completed, failed
    extraction_error = Column(Text)  # 错误信息（如果有）
    
    # 预订信息提取（第一步）
    booking_extraction_status = Column(String(50), default='pending')  # pending, extracting, completed, failed
    extracted_booking_info = Column(Text)  # JSON格式的提取预订信息
    booking_extraction_error = Column(Text)  # 预订信息提取错误信息
    
    # 行程检测状态（第二步）
    trip_detection_status = Column(String(50), default='pending')  # pending, processing, completed, failed
    trip_detection_error = Column(Text)  # 行程检测错误信息
    trip_detection_processed_at = Column(DateTime)  # 处理时间
    
    # 时间戳
    extracted_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    email = relationship("Email", back_populates="email_content")
    
    # 索引
    __table_args__ = (
        Index('idx_email_content_email_id', 'email_id'),
        Index('idx_email_content_status', 'extraction_status'),
        Index('idx_email_content_booking_status', 'booking_extraction_status'),
        Index('idx_email_content_trip_status', 'trip_detection_status'),
    )
    
    def __repr__(self):
        return f"<EmailContent(email_id='{self.email_id}', status='{self.extraction_status}')>"

# 添加Email表的关系
Email.email_content = relationship("EmailContent", back_populates="email", uselist=False)

class TransportSegment(Base):
    """交通段落表 - 存储航班、火车等交通信息"""
    __tablename__ = 'transport_segments'
    
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey('trips.id'), nullable=False)
    
    # 基本信息
    segment_type = Column(String(50), nullable=False)  # flight, train, bus, ferry
    departure_location = Column(String(200), nullable=False)
    arrival_location = Column(String(200), nullable=False)
    departure_datetime = Column(DateTime, nullable=False)
    arrival_datetime = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer)
    
    # Distance information
    distance_km = Column(Float)  # Distance in kilometers
    distance_type = Column(String(20))  # 'actual' or 'straight'
    
    # Cost and booking information
    cost = Column(Float, default=0.0)
    booking_platform = Column(String(100))  # Booking platform
    carrier_name = Column(String(100))  # Airline/Railway company
    segment_number = Column(String(50))  # Flight/Train number
    confirmation_number = Column(String(100))  # Confirmation number
    
    # Status tracking
    status = Column(String(50), default='confirmed')  # confirmed, cancelled, modified
    is_latest_version = Column(Boolean, default=True)
    original_segment_id = Column(Integer, ForeignKey('transport_segments.id'), nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    trip = relationship("Trip", back_populates="transport_segments")
    emails = relationship("Email", secondary="email_transport_segment", back_populates="transport_segments")
    
    # Indexes
    __table_args__ = (
        Index('idx_transport_trip_id', 'trip_id'),
        Index('idx_transport_status', 'status'),
        Index('idx_transport_dates', 'departure_datetime', 'arrival_datetime'),
        Index('idx_transport_confirmation', 'confirmation_number'),
    )

class Accommodation(Base):
    """住宿表 - 存储酒店预订信息"""
    __tablename__ = 'accommodations'
    
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey('trips.id'), nullable=False)
    
    # 基本信息
    check_in_date = Column(DateTime, nullable=False)
    check_out_date = Column(DateTime, nullable=False)
    property_name = Column(String(200), nullable=False)
    address = Column(String(500))
    city = Column(String(100))
    country = Column(String(100))
    
    # 费用和预订信息
    cost = Column(Float, default=0.0)
    booking_platform = Column(String(100))
    confirmation_number = Column(String(100))
    
    # 状态跟踪
    status = Column(String(50), default='confirmed')  # confirmed, cancelled, modified
    is_latest_version = Column(Boolean, default=True)
    original_accommodation_id = Column(Integer, ForeignKey('accommodations.id'), nullable=True)
    
    # 元数据
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    trip = relationship("Trip", back_populates="accommodations")
    emails = relationship("Email", secondary="email_accommodation", back_populates="accommodations")
    
    # 索引
    __table_args__ = (
        Index('idx_accommodation_trip_id', 'trip_id'),
        Index('idx_accommodation_dates', 'check_in_date', 'check_out_date'),
        Index('idx_accommodation_confirmation', 'confirmation_number'),
    )

class TourActivity(Base):
    """旅游活动表 - 存储旅游和活动预订信息"""
    __tablename__ = 'tour_activities'
    
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey('trips.id'), nullable=False)
    
    # 基本信息
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)
    activity_name = Column(String(200), nullable=False)
    description = Column(Text)
    location = Column(String(200))
    city = Column(String(100))
    
    # 费用和预订信息
    cost = Column(Float, default=0.0)
    booking_platform = Column(String(100))
    confirmation_number = Column(String(100))
    
    # 状态跟踪
    status = Column(String(50), default='confirmed')  # confirmed, cancelled, modified
    is_latest_version = Column(Boolean, default=True)
    original_tour_id = Column(Integer, ForeignKey('tour_activities.id'), nullable=True)
    
    # 元数据
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    trip = relationship("Trip", back_populates="tour_activities")
    emails = relationship("Email", secondary="email_tour_activity", back_populates="tour_activities")
    
    # 索引
    __table_args__ = (
        Index('idx_tour_trip_id', 'trip_id'),
        Index('idx_tour_dates', 'start_datetime', 'end_datetime'),
        Index('idx_tour_confirmation', 'confirmation_number'),
    )

class Cruise(Base):
    """邮轮表 - 存储邮轮预订信息"""
    __tablename__ = 'cruises'
    
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey('trips.id'), nullable=False)
    
    # 基本信息
    departure_datetime = Column(DateTime, nullable=False)
    arrival_datetime = Column(DateTime, nullable=False)
    cruise_line = Column(String(100), nullable=False)
    ship_name = Column(String(100))
    itinerary = Column(Text)  # JSON格式的港口列表
    
    # 费用和预订信息
    cost = Column(Float, default=0.0)
    booking_platform = Column(String(100))
    confirmation_number = Column(String(100))
    
    # 状态跟踪
    status = Column(String(50), default='confirmed')  # confirmed, cancelled, modified
    is_latest_version = Column(Boolean, default=True)
    original_cruise_id = Column(Integer, ForeignKey('cruises.id'), nullable=True)
    
    # 元数据
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    trip = relationship("Trip", back_populates="cruises")
    emails = relationship("Email", secondary="email_cruise", back_populates="cruises")
    
    # 索引
    __table_args__ = (
        Index('idx_cruise_trip_id', 'trip_id'),
        Index('idx_cruise_dates', 'departure_datetime', 'arrival_datetime'),
        Index('idx_cruise_confirmation', 'confirmation_number'),
    )

# 关联表 - 多对多关系
class EmailTransportSegment(Base):
    """邮件与交通段落关联表"""
    __tablename__ = 'email_transport_segment'
    
    email_id = Column(String(255), ForeignKey('emails.email_id'), primary_key=True)
    transport_segment_id = Column(Integer, ForeignKey('transport_segments.id'), primary_key=True)
    created_at = Column(DateTime, default=func.now())

class EmailAccommodation(Base):
    """邮件与住宿关联表"""
    __tablename__ = 'email_accommodation'
    
    email_id = Column(String(255), ForeignKey('emails.email_id'), primary_key=True)
    accommodation_id = Column(Integer, ForeignKey('accommodations.id'), primary_key=True)
    created_at = Column(DateTime, default=func.now())

class EmailTourActivity(Base):
    """邮件与旅游活动关联表"""
    __tablename__ = 'email_tour_activity'
    
    email_id = Column(String(255), ForeignKey('emails.email_id'), primary_key=True)
    tour_activity_id = Column(Integer, ForeignKey('tour_activities.id'), primary_key=True)
    created_at = Column(DateTime, default=func.now())

class EmailCruise(Base):
    """邮件与邮轮关联表"""
    __tablename__ = 'email_cruise'
    
    email_id = Column(String(255), ForeignKey('emails.email_id'), primary_key=True)
    cruise_id = Column(Integer, ForeignKey('cruises.id'), primary_key=True)
    created_at = Column(DateTime, default=func.now())

# 添加Trip表的关系
Trip.transport_segments = relationship("TransportSegment", back_populates="trip")
Trip.accommodations = relationship("Accommodation", back_populates="trip")
Trip.tour_activities = relationship("TourActivity", back_populates="trip")
Trip.cruises = relationship("Cruise", back_populates="trip")

# 添加Email表的关系
Email.transport_segments = relationship("TransportSegment", secondary="email_transport_segment", back_populates="emails")
Email.accommodations = relationship("Accommodation", secondary="email_accommodation", back_populates="emails")
Email.tour_activities = relationship("TourActivity", secondary="email_tour_activity", back_populates="emails")
Email.cruises = relationship("Cruise", secondary="email_cruise", back_populates="emails")