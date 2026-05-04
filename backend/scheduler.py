"""Schedule auto-generation algorithm using backtracking with heuristics.

Hard constraints:
  HC-1: Open shift = 2 doctors, Closed shift = 1 doctor
  HC-2: Minimum 4-day separation between any doctor's shifts (3-day gap)
  HC-3: Negative days must be respected
  HC-4: Leaves must be respected
  HC-5: Weekend/holiday distribution should be as fair as possible
"""
from datetime import date, timedelta
from typing import Optional
import random


def _doctor_unavailable(doctor: dict, d: date) -> bool:
    if d.isoformat() in doctor.get("negative_days", []):
        return True
    for lv in doctor.get("leaves", []):
        s = date.fromisoformat(lv["start_date"])
        e = date.fromisoformat(lv["end_date"])
        if s <= d <= e:
            return True
    return False


def validate_assignment(
    schedule_dates: list[dict],  # [{date: ISO, type: 'open'|'closed', doctors: [doc_id,...]}]
    doctors: list[dict],
    target_per_doctor: int = 6,
    negative_day_limit: int = 5,
) -> dict:
    """Run all constraint checks. Returns {hard: [...], soft: [...], per_day: {iso: {hard:[],soft:[]}}, per_doctor: {...}}."""
    hard = []
    soft = []
    per_day: dict = {}
    per_doctor_stats = {
        d["id"]: {"shifts": 0, "weekends": 0, "holidays": 0, "name": d["full_name"]}
        for d in doctors
    }

    doc_map = {d["id"]: d for d in doctors}

    # Build doctor -> dates worked
    doc_dates: dict[str, list[date]] = {d["id"]: [] for d in doctors}

    for entry in schedule_dates:
        d_iso = entry["date"]
        d = date.fromisoformat(d_iso)
        is_we = entry.get("is_weekend", d.weekday() >= 5)
        is_hol = entry.get("is_holiday", False)
        per_day[d_iso] = {"hard": [], "soft": []}
        required = 2 if entry["type"] == "open" else 1
        actual_doctors = entry.get("doctors", [])

        # HC-1: correct count
        if len(actual_doctors) != required:
            msg = f"Λάθος αριθμός γιατρών: απαιτούνται {required}, βρέθηκαν {len(actual_doctors)}"
            per_day[d_iso]["hard"].append({"code": "HC1", "msg": msg})
            hard.append({"date": d_iso, "code": "HC1", "msg": msg})

        for did in actual_doctors:
            if did not in doc_map:
                continue
            doc = doc_map[did]
            doc_dates[did].append(d)
            per_doctor_stats[did]["shifts"] += 1
            if is_we or is_hol:
                per_doctor_stats[did]["weekends"] += 1
            if is_hol:
                per_doctor_stats[did]["holidays"] += 1

            # HC-3, HC-4
            if _doctor_unavailable(doc, d):
                msg = f"Ο/Η {doc['full_name']} δεν είναι διαθέσιμος/η ({d_iso})"
                per_day[d_iso]["hard"].append({"code": "HC34", "msg": msg, "doctor_id": did})
                hard.append({"date": d_iso, "code": "HC34", "msg": msg, "doctor_id": did})

        # No doubling on same day (a doctor twice)
        if len(set(actual_doctors)) != len(actual_doctors):
            msg = "Ο ίδιος γιατρός εμφανίζεται δύο φορές την ίδια ημέρα"
            per_day[d_iso]["hard"].append({"code": "DUP", "msg": msg})
            hard.append({"date": d_iso, "code": "DUP", "msg": msg})

    # HC-2: 3-day gap (min 4 between dates)
    for did, dates_list in doc_dates.items():
        dates_list_sorted = sorted(dates_list)
        for i in range(1, len(dates_list_sorted)):
            gap = (dates_list_sorted[i] - dates_list_sorted[i - 1]).days
            if gap < 4:
                msg = f"Ο/Η {doc_map[did]['full_name']}: παρήμερα ({dates_list_sorted[i-1]} και {dates_list_sorted[i]}, διαφορά {gap} ημέρες)"
                per_day[dates_list_sorted[i].isoformat()]["hard"].append(
                    {"code": "HC2", "msg": msg, "doctor_id": did}
                )
                hard.append(
                    {"date": dates_list_sorted[i].isoformat(), "code": "HC2", "msg": msg, "doctor_id": did}
                )

    # HC-5 / SC: fairness on weekends, equal shifts
    weekend_counts = [s["weekends"] for s in per_doctor_stats.values()]
    if weekend_counts:
        if max(weekend_counts) - min(weekend_counts) > 1:
            soft.append({"code": "HC5", "msg": "Άνιση κατανομή Σ/Κ μεταξύ γιατρών (διαφορά > 1)"})

    for did, stats in per_doctor_stats.items():
        # SC-1: > 2 holidays per doctor (warning)
        if stats["holidays"] > 2:
            msg = f"Ο/Η {stats['name']} έχει {stats['holidays']} αργίες (>2). Η 3η+ αργία δεν πληρώνεται διπλά."
            soft.append({"code": "SC1", "msg": msg, "doctor_id": did})
        # SC-2: shift count deviation
        if abs(stats["shifts"] - target_per_doctor) > 1:
            msg = f"Ο/Η {stats['name']} έχει {stats['shifts']} εφημερίες (στόχος {target_per_doctor})"
            soft.append({"code": "SC2", "msg": msg, "doctor_id": did})
        # SC-3: too many negative days
        nd = len(doc_map[did].get("negative_days", []))
        if nd > negative_day_limit:
            msg = f"Ο/Η {stats['name']} έχει δηλώσει {nd} αρνητικές ημέρες (όριο {negative_day_limit})"
            soft.append({"code": "SC3", "msg": msg, "doctor_id": did})

    return {
        "hard": hard,
        "soft": soft,
        "per_day": per_day,
        "per_doctor": per_doctor_stats,
        "is_valid_hard": len(hard) == 0,
    }


def generate_schedule(
    year: int,
    month: int,
    day_definitions: list[dict],  # [{date, type}]
    doctors: list[dict],  # [{id, full_name, negative_days, leaves}]
    target_per_doctor: int = 6,
    max_attempts: int = 200,
) -> Optional[list[dict]]:
    """Attempt to generate a valid schedule. Returns list of {date, type, doctors:[ids]} or None."""
    if not doctors:
        return None

    # Build slots: each open day = 2 slots, closed = 1 slot, ordered by date
    days_sorted = sorted(day_definitions, key=lambda x: x["date"])

    best_solution = None
    best_score = float("inf")

    for attempt in range(max_attempts):
        random.seed(attempt)
        result = _attempt_one(days_sorted, doctors, target_per_doctor)
        if result is None:
            continue
        # Carry over is_weekend/is_holiday flags from input day_definitions
        flag_map = {d["date"]: (d.get("is_weekend", False), d.get("is_holiday", False)) for d in days_sorted}
        for entry in result:
            iw, ih = flag_map.get(entry["date"], (False, False))
            entry["is_weekend"] = iw
            entry["is_holiday"] = ih
        # Score it (lower is better): sum of squared deviation from target + weekend imbalance
        stats = {d["id"]: {"shifts": 0, "weekends": 0, "holidays": 0} for d in doctors}
        for entry in result:
            is_we = entry.get("is_weekend", False)
            is_hol = entry.get("is_holiday", False)
            for did in entry["doctors"]:
                stats[did]["shifts"] += 1
                if is_we or is_hol:
                    stats[did]["weekends"] += 1
        score = 0.0
        for did, s in stats.items():
            score += (s["shifts"] - target_per_doctor) ** 2
        weekends = [s["weekends"] for s in stats.values()]
        if weekends:
            score += (max(weekends) - min(weekends)) * 10

        if score < best_score:
            best_score = score
            best_solution = result
            if score < 1.0:  # near optimal
                break
    return best_solution


def _attempt_one(
    days_sorted: list[dict], doctors: list[dict], target: int
) -> Optional[list[dict]]:
    """One backtracking attempt with random doctor ordering."""
    # State: doctor -> sorted list of date objects assigned
    doc_assignments: dict[str, list[date]] = {d["id"]: [] for d in doctors}
    result = [
        {"date": d["date"], "type": d["type"], "doctors": []} for d in days_sorted
    ]

    def can_assign(did: str, d: date, doc: dict) -> bool:
        # HC-3,4
        if _doctor_unavailable(doc, d):
            return False
        # HC-2: 3-day gap
        for prev in doc_assignments[did]:
            if abs((d - prev).days) < 4:
                return False
        return True

    # Build slot list: each entry needs N doctors
    slots: list[tuple[int, int]] = []  # (day_idx, slot_idx_within_day)
    for i, dd in enumerate(days_sorted):
        n = 2 if dd["type"] == "open" else 1
        for j in range(n):
            slots.append((i, j))

    # Order slots by constraint difficulty (descending count of unavailable doctors)
    def slot_difficulty(slot):
        i, _ = slot
        d = date.fromisoformat(days_sorted[i]["date"])
        unavail = sum(1 for doc in doctors if _doctor_unavailable(doc, d))
        # Closed days harder than open (since 1 slot covers it)
        return -unavail

    slots.sort(key=slot_difficulty)

    doc_map = {d["id"]: d for d in doctors}

    def backtrack(slot_idx: int) -> bool:
        if slot_idx == len(slots):
            return True
        i, _ = slots[slot_idx]
        d = date.fromisoformat(days_sorted[i]["date"])

        # Order doctors: those with fewer shifts first (load balancing); randomize ties
        candidates = sorted(
            doctors,
            key=lambda x: (
                len(doc_assignments[x["id"]]),
                random.random(),
            ),
        )
        already_today = set(result[i]["doctors"])
        for doc in candidates:
            did = doc["id"]
            if did in already_today:
                continue
            if not can_assign(did, d, doc):
                continue
            # Assign
            result[i]["doctors"].append(did)
            doc_assignments[did].append(d)
            if backtrack(slot_idx + 1):
                return True
            # Undo
            result[i]["doctors"].pop()
            doc_assignments[did].pop()
        return False

    success = backtrack(0)
    return result if success else None
