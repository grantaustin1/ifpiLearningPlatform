"""Exam routes: CRUD + question management + take + attempt submission."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/exams", tags=["Exams"])

