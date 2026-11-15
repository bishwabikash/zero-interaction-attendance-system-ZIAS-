"""SQLAlchemy models for ZIAS."""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class DeviceTypeEnum(str, enum.Enum):
    RFID = "rfid"
    PIR = "pir"
    BLE_BEACON = "ble_beacon"
    UNIVERSAL = "universal"


class DeviceStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class DirectionEnum(str, enum.Enum):
    ENTRY = "entry"
    EXIT = "exit"
    BOTH = "both"


class UserRoleEnum(str, enum.Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    VIEWER = "viewer"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRoleEnum), default=UserRoleEnum.VIEWER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Student(Base):
    __tablename__ = "student"

    student_id = Column(String(20), primary_key=True)
    stud_name = Column(String(100), nullable=False)
    RFID = Column(String(50), unique=True, nullable=True, index=True)
    email = Column(String(100))
    phone = Column(String(15))
    class_section = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    attendance_logs = relationship("EntryLog", back_populates="student")


class UserDevice(Base):
    __tablename__ = "user_devices"

    device_id = Column(String(50), primary_key=True)
    cluster_ID = Column(Integer, nullable=False, index=True)
    device_type = Column(Enum(DeviceTypeEnum), nullable=False, default=DeviceTypeEnum.UNIVERSAL)
    direction = Column(Enum(DirectionEnum), nullable=False, default=DirectionEnum.ENTRY)
    room_value = Column(String(50), nullable=False, index=True)
    location_description = Column(String(200))
    has_rfid = Column(Boolean, default=False)
    has_pir = Column(Boolean, default=False)
    has_ble = Column(Boolean, default=False)
    has_camera = Column(Boolean, default=False)
    firmware_version = Column(String(20))
    ip_address = Column(String(45))
    last_seen = Column(DateTime)
    status = Column(Enum(DeviceStatusEnum), default=DeviceStatusEnum.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sensor_data = relationship("SensorData", back_populates="device")


class SensorData(Base):
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_ID = Column(String(50), ForeignKey("user_devices.device_id", ondelete="CASCADE"), nullable=False, index=True)
    cluster_ID = Column(Integer, nullable=False, index=True)
    RFID = Column(String(50), index=True)
    time_stamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    sensor_active = Column(Boolean, default=True)
    processed = Column(Boolean, default=False, index=True)

    device = relationship("UserDevice", back_populates="sensor_data")


class EntryLog(Base):
    __tablename__ = "entry_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), ForeignKey("student.student_id", ondelete="SET NULL"), nullable=True, index=True)
    student_name = Column(String(100))
    RFID = Column(String(50), nullable=True, index=True)
    room_value = Column(String(50), index=True)
    status = Column(Integer, nullable=False)  # 1 = entry, -1 = exit
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    confidence = Column(Float, default=1.0)
    source = Column(String(20), default="rfid")  # rfid | ble | face | manual

    student = relationship("Student", back_populates="attendance_logs")


class AttendanceSummary(Base):
    __tablename__ = "attendance_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    total_hours = Column(Float, default=0.0)
    first_entry = Column(DateTime)
    last_exit = Column(DateTime)
    entry_count = Column(Integer, default=0)

    __table_args__ = (UniqueConstraint("student_id", "date", name="uq_student_date"),)


class BLEEvent(Base):
    __tablename__ = "ble_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(20), ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False)
    beacon_uuid = Column(String(100), nullable=False, index=True)
    rssi = Column(Integer)
    latitude = Column(Float)
    longitude = Column(Float)
    event_type = Column(String(20))
    app_version = Column(String(20))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    processed = Column(Boolean, default=False, index=True)
