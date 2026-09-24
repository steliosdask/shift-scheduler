"""End-to-end backend tests for the Greek Shift Scheduler API."""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://doctor-duty-planner.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

CHIEF_USERNAME = os.environ.get("ADMIN_USERNAME", "chief").strip().lower()
CHIEF_PASSWORD = os.environ.get("ADMIN_PASSWORD", "chief2026")


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json={"username": CHIEF_USERNAME, "password": CHIEF_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data and "user" in data
    return data["access_token"]


@pytest.fixture(scope="session")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---- Auth ----
class TestAuth:
    def test_login_success(self):
        r = requests.post(f"{API}/auth/login", json={"username": CHIEF_USERNAME, "password": CHIEF_PASSWORD})
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["username"] == CHIEF_USERNAME
        assert body["user"]["role"] == "chief"

    def test_login_wrong_password_greek(self):
        r = requests.post(f"{API}/auth/login", json={"username": CHIEF_USERNAME, "password": "wrong"})
        assert r.status_code == 401
        detail = r.json().get("detail", "")
        assert "Λάθος" in detail or "κωδικός" in detail

    def test_me_requires_auth(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_returns_user(self, headers):
        r = requests.get(f"{API}/auth/me", headers=headers)
        assert r.status_code == 200
        assert r.json()["username"] == CHIEF_USERNAME


# ---- Doctors ----
class TestDoctors:
    def test_list_doctors_seeded(self, headers):
        r = requests.get(f"{API}/doctors", headers=headers)
        assert r.status_code == 200
        docs = r.json()
        assert isinstance(docs, list)
        assert len(docs) >= 7, f"Expected >=7 seeded doctors, got {len(docs)}"
        # Ensure Greek names
        assert any("Παπαδόπουλος" in d["full_name"] for d in docs)

    def test_doctor_crud(self, headers):
        # Create
        r = requests.post(f"{API}/doctors", json={"full_name": "TEST_Δοκιμαστικός", "notes": "t", "is_active": True}, headers=headers)
        assert r.status_code == 200
        d = r.json()
        assert d["full_name"] == "TEST_Δοκιμαστικός"
        doc_id = d["id"]
        # Verify via GET
        rl = requests.get(f"{API}/doctors", headers=headers)
        assert any(x["id"] == doc_id for x in rl.json())
        # Update
        ru = requests.put(f"{API}/doctors/{doc_id}", json={"full_name": "TEST_Ενημερωμένος", "notes": "", "is_active": False}, headers=headers)
        assert ru.status_code == 200
        assert ru.json()["full_name"] == "TEST_Ενημερωμένος"
        assert ru.json()["is_active"] is False
        # Delete
        rd = requests.delete(f"{API}/doctors/{doc_id}", headers=headers)
        assert rd.status_code == 200
        # Verify gone
        rl2 = requests.get(f"{API}/doctors", headers=headers)
        assert not any(x["id"] == doc_id for x in rl2.json())


# ---- Holidays ----
class TestHolidays:
    def test_2026_holidays(self, headers):
        r = requests.get(f"{API}/holidays/2026", headers=headers)
        assert r.status_code == 200
        items = r.json()["holidays"]
        names = [h["name"] for h in items]
        dates = {h["date"]: h["name"] for h in items}
        assert "Καθαρά Δευτέρα" in names
        assert "Αγίου Πνεύματος" in names
        # Easter 2026 = 2026-04-12
        assert dates.get("2026-04-12") == "Κυριακή του Πάσχα"
        # 25 March
        assert dates.get("2026-03-25") == "Εικοστή Πέμπτη Μαρτίου"


# ---- Schedules ----
class TestSchedules:
    @pytest.fixture(scope="class")
    def schedule(self, headers):
        # Use a far-off month to avoid trampling an existing finalized one; and clean existing if any
        year, month = 2026, 9
        # Clean existing
        r_list = requests.get(f"{API}/schedules", headers=headers)
        for s in r_list.json():
            if s["year"] == year and s["month"] == month and s.get("status") != "finalized":
                requests.delete(f"{API}/schedules/{s['id']}", headers=headers)
        r = requests.post(f"{API}/schedules", json={"year": year, "month": month, "notes": "TEST"}, headers=headers)
        assert r.status_code == 200, r.text
        s = r.json()
        yield s
        requests.delete(f"{API}/schedules/{s['id']}", headers=headers)

    def test_create_has_defaults(self, schedule):
        assert schedule["status"] == "draft"
        assert len(schedule["day_definitions"]) == 30  # September has 30
        assert schedule["day_definitions"][0]["type"] == "open"
        assert schedule["day_definitions"][1]["type"] == "closed"
        assert len(schedule["doctor_constraints"]) >= 7

    def test_update_day_definitions(self, headers, schedule):
        sid = schedule["id"]
        new_defs = [{"date": d["date"], "type": d["type"]} for d in schedule["day_definitions"]]
        # flip first day
        new_defs[0]["type"] = "closed"
        r = requests.put(f"{API}/schedules/{sid}", json={"day_definitions": new_defs}, headers=headers)
        assert r.status_code == 200
        assert r.json()["day_definitions"][0]["type"] == "closed"

    def test_generate_produces_valid(self, headers, schedule):
        sid = schedule["id"]
        r = requests.post(f"{API}/schedules/{sid}/generate", headers=headers)
        assert r.status_code == 200, r.text
        s = r.json()
        assert len(s["shifts"]) == 30
        # Each open day -> 2 doctors, closed -> 1
        type_map = {d["date"]: d["type"] for d in s["day_definitions"]}
        for sh in s["shifts"]:
            need = 2 if type_map[sh["date"]] == "open" else 1
            assert len(sh["doctors"]) == need, f"date {sh['date']} type {type_map[sh['date']]} got {len(sh['doctors'])}"

    def test_validate_clean_after_generate(self, headers, schedule):
        sid = schedule["id"]
        r = requests.post(f"{API}/schedules/{sid}/validate", headers=headers, json={})
        assert r.status_code == 200
        data = r.json()
        assert data["is_valid_hard"] is True, f"hard violations after auto-gen: {data['hard']}"
        assert "per_doctor" in data

    def test_export_pdf_with_bearer(self, headers, schedule):
        sid = schedule["id"]
        r = requests.get(f"{API}/schedules/{sid}/export-pdf", headers=headers)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert len(r.content) > 5000
        assert r.content[:4] == b"%PDF"

    def test_export_pdf_with_query_token(self, token, schedule):
        sid = schedule["id"]
        r = requests.get(f"{API}/schedules/{sid}/export-pdf", params={"token": token})
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert len(r.content) > 5000

    def test_export_pdf_no_token_401(self, schedule):
        sid = schedule["id"]
        r = requests.get(f"{API}/schedules/{sid}/export-pdf")
        assert r.status_code == 401
