from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Time
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class Business(Base):
    """Kuaför / Berber işletmesi"""
    __tablename__ = "businesses"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String(100), nullable=False)           # İşletme adı
    slug          = Column(String(120), unique=True, index=True)  # URL: randevucum.com/kuafor-ali
    category      = Column(String(50), default="kuafor")          # kuafor | berber
    phone         = Column(String(20), nullable=False)
    email         = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    address       = Column(String(255))
    city          = Column(String(50), default="Uşak")
    district      = Column(String(50))
    description   = Column(Text)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    plan          = Column(String(20), default="temel")        # temel | premium
    plan_expires_at = Column(DateTime, nullable=True)          # None = süresiz

    services      = relationship("Service", back_populates="business", cascade="all, delete")
    staff         = relationship("Staff", back_populates="business", cascade="all, delete")
    appointments  = relationship("Appointment", back_populates="business", cascade="all, delete")
    work_hours    = relationship("WorkHour", back_populates="business", cascade="all, delete")
    photos        = relationship("BusinessPhoto", back_populates="business", cascade="all, delete")


class Service(Base):
    """Hizmet: Saç kesimi, Fön, vb."""
    __tablename__ = "services"

    id          = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    name        = Column(String(100), nullable=False)   # Saç Kesimi
    duration    = Column(Integer, default=30)           # Dakika
    price       = Column(Integer, default=0)            # TL
    is_active   = Column(Boolean, default=True)

    business    = relationship("Business", back_populates="services")


class Staff(Base):
    """Personel"""
    __tablename__ = "staff"

    id          = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    name        = Column(String(100), nullable=False)
    email       = Column(String(120), nullable=True, index=True)
    phone       = Column(String(20), nullable=True)
    pin         = Column(String(10), nullable=True)
    is_active   = Column(Boolean, default=True)

    business    = relationship("Business", back_populates="staff")


class WorkHour(Base):
    """Çalışma saatleri: Pazartesi 09:00-19:00 gibi"""
    __tablename__ = "work_hours"

    id          = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)   # 0=Pazartesi, 6=Pazar
    open_time   = Column(String(5), default="09:00")
    close_time  = Column(String(5), default="19:00")
    is_closed   = Column(Boolean, default=False)

    business    = relationship("Business", back_populates="work_hours")


class Appointment(Base):
    """Randevu"""
    __tablename__ = "appointments"

    id              = Column(Integer, primary_key=True, index=True)
    business_id     = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    service_id      = Column(Integer, ForeignKey("services.id"), nullable=False)
    staff_id        = Column(Integer, ForeignKey("staff.id"), nullable=True)

    customer_name   = Column(String(100), nullable=False)
    customer_phone  = Column(String(20), nullable=False)

    date            = Column(String(10), nullable=False)   # 2025-03-17
    time            = Column(String(5), nullable=False)    # 14:30
    status          = Column(String(20), default="bekliyor")  # bekliyor | onaylandi | iptal

    sms_confirm_sent   = Column(Boolean, default=False)
    sms_day_before_sent = Column(Boolean, default=False)
    sms_2h_before_sent  = Column(Boolean, default=False)

    notes           = Column(Text)
    created_at      = Column(DateTime, default=datetime.utcnow)

    business  = relationship("Business", back_populates="appointments")
    service   = relationship("Service")
    staff     = relationship("Staff")


class BusinessPhoto(Base):
    """İşletme fotoğrafları"""
    __tablename__ = "business_photos"

    id          = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    filename    = Column(String(255), nullable=False)
    s3_url      = Column(String(500), nullable=True)  # S3 URL
    is_cover    = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    business    = relationship("Business", back_populates="photos")


class PasswordResetToken(Base):
    """Şifre sıfırlama tokenleri"""
    __tablename__ = "password_reset_tokens"

    id          = Column(Integer, primary_key=True, index=True)
    email       = Column(String(120), nullable=False, index=True)
    token       = Column(String(255), unique=True, nullable=False, index=True)
    expires_at  = Column(DateTime, nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

