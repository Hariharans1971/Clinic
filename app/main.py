from __future__ import annotations

import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("CLINIC_DB_PATH", str(BASE_DIR / "clinic.db")))


def connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT NOT NULL,
                doctor_name TEXT NOT NULL,
                appointment_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Scheduled',
                created_at TEXT NOT NULL
            )
            """
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ClinicDesk API",
    description="Educational appointment-management API. Use fictional demo data only.",
    version="1.0.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


class AppointmentCreate(BaseModel):
    patient_name: str = Field(min_length=2, max_length=100)
    doctor_name: str = Field(min_length=2, max_length=100)
    appointment_at: str = Field(min_length=10, max_length=30)
    reason: str = Field(min_length=2, max_length=300)


class AppointmentUpdate(BaseModel):
    patient_name: str | None = Field(default=None, min_length=2, max_length=100)
    doctor_name: str | None = Field(default=None, min_length=2, max_length=100)
    appointment_at: str | None = Field(default=None, min_length=10, max_length=30)
    reason: str | None = Field(default=None, min_length=2, max_length=300)


class AppointmentOut(BaseModel):
    id: int
    patient_name: str
    doctor_name: str
    appointment_at: str
    reason: str
    status: Literal["Scheduled", "Completed", "Cancelled"]
    created_at: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home():
    index = BASE_DIR / "static" / "index.html"
    return index.read_text(encoding="utf-8")


@app.get("/api/appointments", response_model=list[AppointmentOut])
def list_appointments(status: str | None = Query(default=None)):
    allowed = {"Scheduled", "Completed", "Cancelled"}
    if status is not None and status not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported status filter.")
    with connect_db() as connection:
        if status:
            rows = connection.execute(
                "SELECT * FROM appointments WHERE status = ? ORDER BY appointment_at",
                (status,),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM appointments ORDER BY appointment_at"
            ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/appointments", response_model=AppointmentOut, status_code=201)
def create_appointment(payload: AppointmentCreate):
    try:
        parsed = datetime.fromisoformat(payload.appointment_at)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="appointment_at must be an ISO date/time, e.g. 2026-11-01T10:30",
        ) from exc

    values = (
        payload.patient_name.strip(),
        payload.doctor_name.strip(),
        parsed.isoformat(timespec="minutes"),
        payload.reason.strip(),
        "Scheduled",
        datetime.now().astimezone().isoformat(timespec="seconds"),
    )
    if not all(values[index] for index in (0, 1, 3)):
        raise HTTPException(status_code=422, detail="Fields cannot be blank.")

    with connect_db() as connection:
        cursor = connection.execute(
            """
            INSERT INTO appointments
                (patient_name, doctor_name, appointment_at, reason, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        row = connection.execute(
            "SELECT * FROM appointments WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return dict(row)



@app.patch("/api/appointments/{appointment_id}", response_model=AppointmentOut)
def update_appointment(appointment_id: int, payload: AppointmentUpdate):
    changes = payload.dict(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="At least one field must be provided.")

    for field_name, value in changes.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            raise HTTPException(status_code=422, detail=f"{field_name} cannot be blank.")

    if "appointment_at" in changes:
        try:
            parsed = datetime.fromisoformat(changes["appointment_at"])
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="appointment_at must be an ISO date/time, e.g. 2026-11-01T10:30",
            ) from exc
        changes["appointment_at"] = parsed.isoformat(timespec="minutes")

    for field_name in ("patient_name", "doctor_name", "reason"):
        if field_name in changes:
            changes[field_name] = changes[field_name].strip()

    # Column names come only from the validated model's fixed field set.
    assignments = ", ".join(f"{column} = ?" for column in changes)
    values = [*changes.values(), appointment_id]
    with connect_db() as connection:
        cursor = connection.execute(
            f"UPDATE appointments SET {assignments} WHERE id = ?",
            values,
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Appointment not found.")
        row = connection.execute(
            "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
        ).fetchone()
    return dict(row)


@app.post("/api/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(appointment_id: int):
    with connect_db() as connection:
        row = connection.execute(
            "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Appointment not found.")
        if row["status"] == "Completed":
            raise HTTPException(
                status_code=409,
                detail="A completed appointment cannot be cancelled.",
            )
        if row["status"] == "Cancelled":
            return dict(row)

        connection.execute(
            "UPDATE appointments SET status = ? WHERE id = ?",
            ("Cancelled", appointment_id),
        )
        updated = connection.execute(
            "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
        ).fetchone()
    return dict(updated)
