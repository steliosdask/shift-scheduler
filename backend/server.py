import logging
import os
import urllib.parse
import uuid
from calendar import monthrange
from datetime import date as date_cls, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).parent / ".env")

from holidays_gr import get_holidays, is_holiday  # noqa: E402
from pdf_export import GREEK_MONTHS, build_schedule_pdf  # noqa: E402
from scheduler import generate_schedule, validate_assignment  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

JWT_ALGORITHM = "HS256"
TOKEN_LIFETIME = timedelta(days=7)


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str, username: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + TOKEN_LIFETIME,
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----- Models -----
class LoginIn(BaseModel):
    username: str
    password: str


class DoctorIn(BaseModel):
    full_name: str
    notes: Optional[str] = ""
    is_active: bool = True


class ScheduleCreate(BaseModel):
    year: int
    month: int
    notes: Optional[str] = ""


class DayDef(BaseModel):
    date: str  # YYYY-MM-DD
    type: str  # "open" | "closed"
    is_custom_holiday: bool = False


class DoctorConstraint(BaseModel):
    doctor_id: str
    is_participating: bool = True
    negative_days: List[str] = []
    leaves: List[dict] = []  # [{start_date, end_date, reason}]


class ShiftEntry(BaseModel):
    date: str
    type: str
    doctors: List[str]


class ScheduleUpdate(BaseModel):
    day_definitions: Optional[List[DayDef]] = None
    doctor_constraints: Optional[List[DoctorConstraint]] = None
    shifts: Optional[List[ShiftEntry]] = None
    status: Optional[str] = None  # "draft" | "finalized"
    notes: Optional[str] = None


# ----- Auth -----
async def user_from_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Το token έχει λήξει")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Μη έγκυρο token")
    if payload.get("type") != "access":
        raise HTTPException(401, "Μη έγκυρο token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "Ο χρήστης δεν βρέθηκε")
    return user


async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Δεν είστε συνδεδεμένος")
    return await user_from_token(auth[7:])


app = FastAPI()
api = APIRouter(prefix="/api")


@api.post("/auth/login")
async def login(data: LoginIn):
    user = await db.users.find_one({"username": data.username.strip().lower()})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Λάθος όνομα χρήστη ή κωδικός")
    return {
        "access_token": create_access_token(user["id"], user["username"]),
        "user": {"id": user["id"], "username": user["username"], "role": user["role"]},
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
    return await db.doctors.find({}, {"_id": 0}).sort("created_at", 1).to_list(1000)


@api.post("/doctors")
async def create_doctor(data: DoctorIn, current: dict = Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "full_name": data.full_name,
        "notes": data.notes or "",
        "is_active": data.is_active,
        "created_at": now_iso(),
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
    return await db.doctors.find_one({"id": doctor_id}, {"_id": 0})


@api.delete("/doctors/{doctor_id}")
async def delete_doctor(doctor_id: str, current: dict = Depends(get_current_user)):
    res = await db.doctors.delete_one({"id": doctor_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Ο γιατρός δεν βρέθηκε")
    return {"ok": True}


@api.get("/holidays/{year}")
async def holidays_year(year: int, current: dict = Depends(get_current_user)):
    h = get_holidays(year)
    return {"holidays": [{"date": d.isoformat(), "name": name} for d, name in sorted(h.items())]}


# ----- Schedules -----
def default_day_definitions(year: int, month: int) -> list[dict]:
    """Alternate open/closed days, starting with an open day on the 1st."""
    out = []
    for day in range(1, monthrange(year, month)[1] + 1):
        d = date_cls(year, month, day)
        out.append(
            {
                "date": d.isoformat(),
                "type": "open" if day % 2 == 1 else "closed",
                "is_weekend": d.weekday() >= 5,
                "is_holiday": is_holiday(d),
            }
        )
    return out


async def get_schedule_or_404(schedule_id: str) -> dict:
    s = await db.schedules.find_one({"id": schedule_id}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Το πρόγραμμα δεν βρέθηκε")
    return s


@api.get("/schedules")
async def list_schedules(current: dict = Depends(get_current_user)):
    return await db.schedules.find({}, {"_id": 0}).sort([("year", -1), ("month", -1)]).to_list(1000)


@api.post("/schedules")
async def create_schedule(data: ScheduleCreate, current: dict = Depends(get_current_user)):
    # A month has at most one schedule; an existing draft is replaced.
    existing = await db.schedules.find_one({"year": data.year, "month": data.month})
    if existing and existing.get("status") == "finalized":
        raise HTTPException(400, "Υπάρχει ήδη οριστικοποιημένο πρόγραμμα γι' αυτόν τον μήνα")
    if existing:
        await db.schedules.delete_one({"id": existing["id"]})

    doctors = await db.doctors.find({"is_active": True}, {"_id": 0}).to_list(100)
    now = now_iso()
    schedule = {
        "id": str(uuid.uuid4()),
        "year": data.year,
        "month": data.month,
        "status": "draft",
        "notes": data.notes or "",
        "created_at": now,
        "updated_at": now,
        "finalized_at": None,
        "day_definitions": default_day_definitions(data.year, data.month),
        "doctor_constraints": [
            {"doctor_id": d["id"], "is_participating": True, "negative_days": [], "leaves": []}
            for d in doctors
        ],
        "shifts": [],
    }
    await db.schedules.insert_one(schedule.copy())
    return schedule


@api.get("/schedules/{schedule_id}")
async def get_schedule(schedule_id: str, current: dict = Depends(get_current_user)):
    return await get_schedule_or_404(schedule_id)


@api.put("/schedules/{schedule_id}")
async def update_schedule(schedule_id: str, data: ScheduleUpdate, current: dict = Depends(get_current_user)):
    await get_schedule_or_404(schedule_id)
    update: dict = {"updated_at": now_iso()}
    if data.day_definitions is not None:
        day_defs = []
        for d in data.day_definitions:
            day = date_cls.fromisoformat(d.date)
            day_defs.append(
                {
                    **d.dict(),
                    "is_weekend": day.weekday() >= 5,
                    "is_holiday": is_holiday(day) or d.is_custom_holiday,
                }
            )
        update["day_definitions"] = day_defs
    if data.doctor_constraints is not None:
        update["doctor_constraints"] = [c.dict() for c in data.doctor_constraints]
    if data.shifts is not None:
        update["shifts"] = [s.dict() for s in data.shifts]
    if data.status is not None:
        update["status"] = data.status
        if data.status == "finalized":
            update["finalized_at"] = now_iso()
    if data.notes is not None:
        update["notes"] = data.notes
    await db.schedules.update_one({"id": schedule_id}, {"$set": update})
    return await get_schedule_or_404(schedule_id)


@api.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str, current: dict = Depends(get_current_user)):
    res = await db.schedules.delete_one({"id": schedule_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Το πρόγραμμα δεν βρέθηκε")
    return {"ok": True}


def participating_doctors(schedule: dict, doctors: list[dict]) -> list[dict]:
    """Doctors taking part in this schedule, merged with their constraints."""
    constraints = {c["doctor_id"]: c for c in schedule.get("doctor_constraints", [])}
    out = []
    for d in doctors:
        c = constraints.get(d["id"])
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
    s = await get_schedule_or_404(schedule_id)
    all_doctors = await db.doctors.find({}, {"_id": 0}).to_list(100)
    doctors = participating_doctors(s, all_doctors)
    if not doctors:
        raise HTTPException(400, "Δεν υπάρχουν ενεργοί γιατροί στο πρόγραμμα")

    day_defs = [d for d in s["day_definitions"] if d["type"] in ("open", "closed")]
    result = generate_schedule(day_definitions=day_defs, doctors=doctors)
    if result["infeasible"]:
        raise HTTPException(422, " ".join([result["reason"], *result["suggestions"]]))

    await db.schedules.update_one(
        {"id": schedule_id},
        {"$set": {"shifts": result["schedule"], "updated_at": now_iso()}},
    )
    return await get_schedule_or_404(schedule_id)


@api.post("/schedules/{schedule_id}/validate")
async def validate(schedule_id: str, payload: Optional[dict] = None, current: dict = Depends(get_current_user)):
    s = await get_schedule_or_404(schedule_id)
    all_doctors = await db.doctors.find({}, {"_id": 0}).to_list(100)
    # The client may send unsaved shifts to validate them before saving.
    shifts = (payload or {}).get("shifts")
    if shifts is None:
        shifts = s.get("shifts", [])
    day_flags = {d["date"]: d for d in s["day_definitions"]}
    return validate_assignment(
        schedule_dates=[
            {
                "date": e["date"],
                "type": e.get("type", "open"),
                "doctors": e.get("doctors", []),
                "is_weekend": day_flags.get(e["date"], {}).get("is_weekend", False),
                "is_holiday": day_flags.get(e["date"], {}).get("is_holiday", False),
            }
            for e in shifts
        ],
        doctors=participating_doctors(s, all_doctors),
    )


@api.get("/schedules/{schedule_id}/export-pdf")
async def export_pdf(schedule_id: str, request: Request, token: Optional[str] = None):
    # The app opens this URL in the browser, so the token may come as a query parameter.
    auth = request.headers.get("Authorization", "")
    raw_token = token or (auth[7:] if auth.startswith("Bearer ") else None)
    if not raw_token:
        raise HTTPException(401, "Δεν είστε συνδεδεμένος")
    await user_from_token(raw_token)

    s = await get_schedule_or_404(schedule_id)
    all_doctors = await db.doctors.find({}, {"_id": 0}).to_list(100)
    pdf_bytes = build_schedule_pdf(
        year=s["year"],
        month=s["month"],
        day_definitions=s["day_definitions"],
        shifts=s.get("shifts", []),
        doctors=all_doctors,
    )
    filename = urllib.parse.quote(f"Εφημερίες_{GREEK_MONTHS[s['month']]}_{s['year']}.pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"schedule.pdf\"; filename*=UTF-8''{filename}"},
    )


@api.get("/")
async def root():
    return {"message": "Shift Scheduler API"}


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("username", unique=True)
    await db.doctors.create_index("id", unique=True)
    await db.schedules.create_index("id", unique=True)
    await db.schedules.create_index([("year", 1), ("month", 1)])

    # Make sure the admin account from the environment exists and has the configured password.
    admin_username = os.environ["ADMIN_USERNAME"].strip().lower()
    admin_password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"username": admin_username})
    if not existing:
        await db.users.insert_one(
            {
                "id": str(uuid.uuid4()),
                "username": admin_username,
                "password_hash": hash_password(admin_password),
                "role": "chief",
                "created_at": now_iso(),
            }
        )
        logger.info(f"Created admin user: {admin_username}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"username": admin_username},
            {"$set": {"password_hash": hash_password(admin_password)}},
        )
        logger.info("Updated admin password")


@app.on_event("shutdown")
async def shutdown():
    client.close()
