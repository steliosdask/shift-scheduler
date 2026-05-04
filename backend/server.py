from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
import uuid
from calendar import monthrange
from datetime import datetime, timezone, timedelta, date as date_cls
from typing import Optional, List

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field

from holidays_gr import get_holidays, is_holiday, is_special_day
from scheduler import generate_schedule, validate_assignment
from pdf_export import build_schedule_pdf, GREEK_MONTHS

# ----- Setup -----
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_ALGORITHM = "HS256"


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


# ----- Pydantic models -----
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str


class DoctorIn(BaseModel):
    full_name: str
    notes: Optional[str] = ""
    is_active: bool = True


class DoctorOut(DoctorIn):
    id: str
    created_at: datetime


class ScheduleCreate(BaseModel):
    year: int
    month: int
    notes: Optional[str] = ""


class DayDef(BaseModel):
    date: str  # ISO YYYY-MM-DD
    type: str  # 'open' | 'closed' | 'none'
    is_custom_holiday: bool = False


class DoctorConstraint(BaseModel):
    doctor_id: str
    is_participating: bool = True
    negative_days: List[str] = []  # ISO dates
    leaves: List[dict] = []  # [{start_date, end_date, reason}]


class ShiftEntry(BaseModel):
    date: str
    type: str
    doctors: List[str]


class ScheduleUpdate(BaseModel):
    day_definitions: Optional[List[DayDef]] = None
    doctor_constraints: Optional[List[DoctorConstraint]] = None
    shifts: Optional[List[ShiftEntry]] = None
    status: Optional[str] = None  # 'draft' | 'finalized'
    notes: Optional[str] = None


# ----- Auth dependency -----
async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Δεν είστε συνδεδεμένος")
    token = auth[7:]
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(401, "Μη έγκυρο token")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(401, "Ο χρήστης δεν βρέθηκε")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Το token έχει λήξει")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Μη έγκυρο token")


# ----- App & router -----
app = FastAPI()
api = APIRouter(prefix="/api")


# ----- Auth -----
@api.post("/auth/login")
async def login(data: LoginIn):
    user = await db.users.find_one({"email": data.email.lower()})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Λάθος email ή κωδικός")
    token = create_access_token(user["id"], user["email"])
    return {
        "access_token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
        },
    }


@api.get("/auth/me")
async def me(current: dict = Depends(get_current_user)):
    return current


@api.post("/auth/logout")
async def logout(current: dict = Depends(get_current_user)):
    return {"ok": True}


# ----- Doctors -----
@api.get("/doctors")
async def list_doctors(current: dict = Depends(get_current_user)):
    docs = await db.doctors.find({}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    return docs


@api.post("/doctors")
async def create_doctor(data: DoctorIn, current: dict = Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "full_name": data.full_name,
        "notes": data.notes or "",
        "is_active": data.is_active,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.doctors.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.put("/doctors/{doctor_id}")
async def update_doctor(doctor_id: str, data: DoctorIn, current: dict = Depends(get_current_user)):
    res = await db.doctors.update_one(
        {"id": doctor_id},
        {"$set": {"full_name": data.full_name, "notes": data.notes or "", "is_active": data.is_active}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Ο γιατρός δεν βρέθηκε")
    doc = await db.doctors.find_one({"id": doctor_id}, {"_id": 0})
    return doc


@api.delete("/doctors/{doctor_id}")
async def delete_doctor(doctor_id: str, current: dict = Depends(get_current_user)):
    res = await db.doctors.delete_one({"id": doctor_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Ο γιατρός δεν βρέθηκε")
    return {"ok": True}


# ----- Holidays -----
@api.get("/holidays/{year}")
async def holidays_year(year: int, current: dict = Depends(get_current_user)):
    h = get_holidays(year)
    return {"holidays": [{"date": d.isoformat(), "name": name} for d, name in sorted(h.items())]}


# ----- Schedules -----
def _default_day_definitions(year: int, month: int) -> list[dict]:
    """Default: alternating open/closed starting with open on day 1."""
    n = monthrange(year, month)[1]
    out = []
    for day in range(1, n + 1):
        d = date_cls(year, month, day)
        out.append(
            {
                "date": d.isoformat(),
                "type": "open" if (day % 2 == 1) else "closed",
                "is_weekend": d.weekday() >= 5,
                "is_holiday": is_holiday(d),
            }
        )
    return out


def _serialize_schedule(s: dict) -> dict:
    s.pop("_id", None)
    return s


@api.get("/schedules")
async def list_schedules(current: dict = Depends(get_current_user)):
    items = await db.schedules.find({}, {"_id": 0}).sort([("year", -1), ("month", -1)]).to_list(1000)
    return items


@api.post("/schedules")
async def create_schedule(data: ScheduleCreate, current: dict = Depends(get_current_user)):
    # Allow multiple per month? for simplicity allow re-create overriding draft
    existing = await db.schedules.find_one({"year": data.year, "month": data.month})
    if existing and existing.get("status") == "finalized":
        raise HTTPException(400, "Υπάρχει ήδη οριστικοποιημένο πρόγραμμα γι' αυτόν τον μήνα")
    if existing:
        await db.schedules.delete_one({"id": existing["id"]})

    doctors = await db.doctors.find({"is_active": True}, {"_id": 0}).to_list(100)
    sched_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    schedule = {
        "id": sched_id,
        "year": data.year,
        "month": data.month,
        "status": "draft",
        "notes": data.notes or "",
        "created_at": now,
        "updated_at": now,
        "finalized_at": None,
        "day_definitions": _default_day_definitions(data.year, data.month),
        "doctor_constraints": [
            {
                "doctor_id": d["id"],
                "is_participating": True,
                "negative_days": [],
                "leaves": [],
            }
            for d in doctors
        ],
        "shifts": [],
    }
    await db.schedules.insert_one(schedule.copy())
    schedule.pop("_id", None)
    return schedule


@api.get("/schedules/{schedule_id}")
async def get_schedule(schedule_id: str, current: dict = Depends(get_current_user)):
    s = await db.schedules.find_one({"id": schedule_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Το πρόγραμμα δεν βρέθηκε")
    return s


@api.put("/schedules/{schedule_id}")
async def update_schedule(schedule_id: str, data: ScheduleUpdate, current: dict = Depends(get_current_user)):
    s = await db.schedules.find_one({"id": schedule_id})
    if not s:
        raise HTTPException(404, "Το πρόγραμμα δεν βρέθηκε")
    update: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if data.day_definitions is not None:
        update["day_definitions"] = [
            {
                **d.dict(),
                "is_weekend": date_cls.fromisoformat(d.date).weekday() >= 5,
                "is_holiday": is_holiday(date_cls.fromisoformat(d.date)) or d.is_custom_holiday,
            }
            for d in data.day_definitions
        ]
    if data.doctor_constraints is not None:
        update["doctor_constraints"] = [c.dict() for c in data.doctor_constraints]
    if data.shifts is not None:
        update["shifts"] = [s.dict() for s in data.shifts]
    if data.status is not None:
        update["status"] = data.status
        if data.status == "finalized":
            update["finalized_at"] = datetime.now(timezone.utc).isoformat()
    if data.notes is not None:
        update["notes"] = data.notes
    await db.schedules.update_one({"id": schedule_id}, {"$set": update})
    s2 = await db.schedules.find_one({"id": schedule_id}, {"_id": 0})
    return s2


@api.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str, current: dict = Depends(get_current_user)):
    res = await db.schedules.delete_one({"id": schedule_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Το πρόγραμμα δεν βρέθηκε")
    return {"ok": True}


def _build_doctor_payload(schedule: dict, doctors: list[dict]) -> list[dict]:
    """Merge doctors with their per-schedule constraints, only those participating."""
    constraints_by_id = {c["doctor_id"]: c for c in schedule.get("doctor_constraints", [])}
    out = []
    for d in doctors:
        c = constraints_by_id.get(d["id"])
        if not c or not c.get("is_participating"):
            continue
        out.append(
            {
                "id": d["id"],
                "full_name": d["full_name"],
                "negative_days": c.get("negative_days", []),
                "leaves": c.get("leaves", []),
            }
        )
    return out


@api.post("/schedules/{schedule_id}/generate")
async def auto_generate(schedule_id: str, current: dict = Depends(get_current_user)):
    s = await db.schedules.find_one({"id": schedule_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Το πρόγραμμα δεν βρέθηκε")
    all_doctors = await db.doctors.find({}, {"_id": 0}).to_list(100)
    doctors_payload = _build_doctor_payload(s, all_doctors)
    if not doctors_payload:
        raise HTTPException(400, "Δεν υπάρχουν ενεργοί γιατροί στο πρόγραμμα")

    day_defs = [d for d in s["day_definitions"] if d["type"] in ("open", "closed")]
    result = generate_schedule(
        year=s["year"],
        month=s["month"],
        day_definitions=day_defs,
        doctors=doctors_payload,
    )
    if result is None:
        raise HTTPException(
            422,
            "Δεν βρέθηκε αποδεκτή λύση. Ελέγξτε αρνητικές ημέρες / άδειες (ίσως πολλές ταυτόχρονα).",
        )
    await db.schedules.update_one(
        {"id": schedule_id},
        {
            "$set": {
                "shifts": result,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    s2 = await db.schedules.find_one({"id": schedule_id}, {"_id": 0})
    return s2


@api.post("/schedules/{schedule_id}/validate")
async def validate(schedule_id: str, payload: dict = None, current: dict = Depends(get_current_user)):
    s = await db.schedules.find_one({"id": schedule_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Το πρόγραμμα δεν βρέθηκε")
    all_doctors = await db.doctors.find({}, {"_id": 0}).to_list(100)
    # Allow validation against unsaved shifts via payload
    shifts = (payload or {}).get("shifts") if payload else None
    if shifts is None:
        shifts = s.get("shifts", [])
    doctors_payload = _build_doctor_payload(s, all_doctors)
    res = validate_assignment(
        schedule_dates=[
            {
                "date": e["date"],
                "type": e.get("type", "open"),
                "doctors": e.get("doctors", []),
                "is_weekend": next((d.get("is_weekend", False) for d in s["day_definitions"] if d["date"] == e["date"]), False),
                "is_holiday": next((d.get("is_holiday", False) for d in s["day_definitions"] if d["date"] == e["date"]), False),
            }
            for e in shifts
        ],
        doctors=doctors_payload,
    )
    return res


@api.get("/schedules/{schedule_id}/export-pdf")
async def export_pdf(schedule_id: str, request: Request, token: Optional[str] = None):
    # Accept either Bearer header OR ?token= query param (mobile Linking.openURL compat)
    auth = request.headers.get("Authorization", "")
    raw_token = token or (auth[7:] if auth.startswith("Bearer ") else None)
    if not raw_token:
        raise HTTPException(401, "Δεν είστε συνδεδεμένος")
    try:
        payload = jwt.decode(raw_token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(401, "Ο χρήστης δεν βρέθηκε")
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Το token έχει λήξει")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Μη έγκυρο token")

    s = await db.schedules.find_one({"id": schedule_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Το πρόγραμμα δεν βρέθηκε")
    all_doctors = await db.doctors.find({}, {"_id": 0}).to_list(100)
    pdf_bytes = build_schedule_pdf(
        year=s["year"],
        month=s["month"],
        day_definitions=s["day_definitions"],
        shifts=s.get("shifts", []),
        doctors=all_doctors,
    )
    filename = f"Εφημερίες_{GREEK_MONTHS[s['month']]}_{s['year']}.pdf"
    # ascii-fallback for Content-Disposition header (RFC 5987 utf-8 filename*)
    import urllib.parse as ulp
    quoted = ulp.quote(filename)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"schedule.pdf\"; filename*=UTF-8''{quoted}",
        },
    )


@api.get("/")
async def root():
    return {"message": "Shift Scheduler API"}


# ----- App wiring -----
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    # Indexes
    await db.users.create_index("email", unique=True)
    await db.doctors.create_index("id", unique=True)
    await db.schedules.create_index("id", unique=True)
    await db.schedules.create_index([("year", 1), ("month", 1)])

    # Seed admin
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one(
            {
                "id": str(uuid.uuid4()),
                "email": admin_email,
                "password_hash": hash_password(admin_password),
                "name": "Διευθυντής",
                "role": "chief",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        logger.info(f"Seeded admin user: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}},
        )
        logger.info("Updated admin password")

    # Seed sample doctors if none exist (for first-run UX)
    doc_count = await db.doctors.count_documents({})
    if doc_count == 0:
        sample = [
            "Παπαδόπουλος Γεώργιος",
            "Γεωργίου Ελένη",
            "Δημητρίου Νικόλαος",
            "Καραγιάννη Μαρία",
            "Σταμάτης Δημήτριος",
            "Κωνσταντίνου Σοφία",
            "Αντωνίου Ιωάννης",
        ]
        for name in sample:
            await db.doctors.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "full_name": name,
                    "notes": "",
                    "is_active": True,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        logger.info(f"Seeded {len(sample)} sample doctors")


@app.on_event("shutdown")
async def shutdown():
    client.close()
