"""Attendance API routes."""

from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.db_models import EntryLog, Student, User, UserDevice, DeviceStatusEnum
from api.models import (
    AttendanceEvent,
    AttendanceRecord,
    AttendanceRecordList,
    DashboardStats,
    OccupancyResponse,
    OccupancyStudent,
)

router = APIRouter()


def _status_label(value: int) -> str:
    return "entry" if value == 1 else "exit"


@router.post("/event", status_code=201)
async def log_attendance_event(
    event: AttendanceEvent,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.student_id == event.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    status_int = 1 if event.event_type.value == "entry" else -1
    log = EntryLog(
        student_id=student.student_id,
        student_name=student.stud_name,
        RFID=student.RFID,
        room_value=event.location,
        status=status_int,
        timestamp=event.timestamp,
        confidence=event.confidence,
        source=event.source.value,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {"status": "recorded", "event_id": log.id, "timestamp": log.timestamp}


@router.get("/records", response_model=AttendanceRecordList)
async def get_attendance_records(
    student_id: Optional[str] = None,
    room: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(EntryLog).outerjoin(Student, EntryLog.student_id == Student.student_id)

    if student_id:
        query = query.filter(EntryLog.student_id == student_id)
    if room:
        query = query.filter(EntryLog.room_value == room)
    if date_from:
        query = query.filter(EntryLog.timestamp >= datetime.combine(date_from, time.min))
    if date_to:
        query = query.filter(EntryLog.timestamp < datetime.combine(date_to + timedelta(days=1), time.min))

    total = query.count()
    rows = query.order_by(EntryLog.timestamp.desc()).offset(offset).limit(limit).all()

    return AttendanceRecordList(
        total=total,
        records=[
            AttendanceRecord(
                id=r.id,
                student_id=r.student_id or "",
                student_name=r.student_name or "Unknown",
                room=r.room_value or "",
                status=_status_label(r.status),
                timestamp=r.timestamp,
                confidence=r.confidence or 1.0,
                source=r.source or "rfid",
            )
            for r in rows
        ],
    )


@router.get("/summary/{student_id}")
async def get_student_summary(
    student_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    query = db.query(EntryLog).filter(EntryLog.student_id == student.student_id)
    if month and year:
        start = datetime(year, month, 1)
        end = datetime(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        query = query.filter(EntryLog.timestamp >= start, EntryLog.timestamp < end)

    rows = query.order_by(EntryLog.timestamp.asc()).all()

    days_present = len({r.timestamp.date() for r in rows if r.status == 1})
    total_seconds = 0.0
    entry_stack: dict[date, datetime] = {}
    for row in rows:
        day = row.timestamp.date()
        if row.status == 1:
            entry_stack[day] = row.timestamp
        elif row.status == -1 and day in entry_stack:
            total_seconds += (row.timestamp - entry_stack.pop(day)).total_seconds()

    total_hours = round(total_seconds / 3600.0, 2)
    return {
        "student_id": student_id,
        "student_name": student.stud_name,
        "total_hours": total_hours,
        "days_present": days_present,
        "total_entries": sum(1 for r in rows if r.status == 1),
        "average_hours_per_day": round(total_hours / days_present, 2) if days_present else 0.0,
    }


@router.get("/realtime/{room}", response_model=OccupancyResponse)
async def get_realtime_occupancy(
    room: str,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recent = (
        db.query(EntryLog)
        .filter(
            EntryLog.room_value == room,
            EntryLog.timestamp >= datetime.utcnow() - timedelta(hours=12),
        )
        .order_by(EntryLog.timestamp.desc())
        .all()
    )

    latest_by_student: dict[str, EntryLog] = {}
    for row in recent:
        key = row.student_id or row.RFID or f"anon-{row.id}"
        latest_by_student.setdefault(key, row)

    inside = [r for r in latest_by_student.values() if r.status == 1]
    students = []
    for row in inside:
        if row.student_id:
            students.append(OccupancyStudent(student_id=row.student_id, name=row.student_name or "Unknown"))

    return OccupancyResponse(
        room=room,
        current_occupancy=len(inside),
        students=students,
        timestamp=datetime.utcnow(),
    )


@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today_start = datetime.combine(date.today(), time.min)
    total_students = db.query(func.count(Student.student_id)).scalar() or 0
    present_today = (
        db.query(func.count(func.distinct(EntryLog.student_id)))
        .filter(EntryLog.timestamp >= today_start, EntryLog.status == 1)
        .scalar()
        or 0
    )
    active_devices = (
        db.query(func.count(UserDevice.device_id))
        .filter(UserDevice.status == DeviceStatusEnum.ACTIVE)
        .scalar()
        or 0
    )
    return DashboardStats(
        total_students=total_students,
        present_today=present_today,
        absent_today=max(total_students - present_today, 0),
        active_devices=active_devices,
    )
