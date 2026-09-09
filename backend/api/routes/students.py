"""Students API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from api.auth import get_current_user
from api.database import get_db
from api.db_models import Student, User
from api.models import StudentCreate, StudentOut

router = APIRouter()


@router.get("/", response_model=List[StudentOut])
async def list_students(
    limit: int = 100,
    offset: int = 0,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 1000))
    return db.query(Student).order_by(Student.stud_name).offset(offset).limit(limit).all()


@router.post("/", response_model=StudentOut, status_code=201)
async def create_student(
    payload: StudentCreate,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.query(Student).filter(Student.student_id == payload.student_id).first():
        raise HTTPException(status_code=400, detail="Student ID already exists")

    if payload.RFID and db.query(Student).filter(Student.RFID == payload.RFID).first():
        raise HTTPException(status_code=400, detail="RFID already registered")

    student = Student(**payload.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("/{student_id}", response_model=StudentOut)
async def get_student(
    student_id: str,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.delete("/{student_id}", status_code=204)
async def delete_student(
    student_id: str,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    db.delete(student)
    db.commit()
