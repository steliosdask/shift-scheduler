"""Monthly on-call schedule generation and validation.

Rules:
  - An open day needs 2 doctors, a closed day needs 1.
  - A doctor needs at least 3 free days between two shifts.
  - Negative days and leaves are respected.
  - Weekends/holidays should be spread evenly.

Generation runs a quick feasibility check, then a time-limited backtracking
search (most-constrained slot first, with forward checking). If no complete
solution is found in time, a greedy partial schedule is returned instead.
"""
import random
import time
from datetime import date
from typing import Optional

MIN_GAP_DAYS = 4  # 3 free days between shifts


def required_doctors(day_type: str) -> int:
    return 2 if day_type == "open" else 1


def doctor_unavailable(doctor: dict, d: date) -> bool:
    """True if the doctor marked the day as negative or is on leave."""
    if d.isoformat() in doctor.get("negative_days", []):
        return True
    for lv in doctor.get("leaves", []):
        if date.fromisoformat(lv["start_date"]) <= d <= date.fromisoformat(lv["end_date"]):
            return True
    return False


# ---------- Validation ----------

def validate_assignment(
    schedule_dates: list[dict],
    doctors: list[dict],
    target_per_doctor: int = 6,
    negative_day_limit: int = 5,
) -> dict:
    hard = []
    soft = []
    per_day: dict = {}
    per_doctor_stats = {
        d["id"]: {"shifts": 0, "weekends": 0, "holidays": 0, "name": d["full_name"]}
        for d in doctors
    }
    doc_map = {d["id"]: d for d in doctors}
    doc_dates: dict[str, list[date]] = {d["id"]: [] for d in doctors}

    def add_hard(d_iso: str, issue: dict):
        per_day[d_iso]["hard"].append(issue)
        hard.append({"date": d_iso, **issue})

    for entry in schedule_dates:
        d_iso = entry["date"]
        d = date.fromisoformat(d_iso)
        is_we = entry.get("is_weekend", d.weekday() >= 5)
        is_hol = entry.get("is_holiday", False)
        per_day[d_iso] = {"hard": [], "soft": []}
        required = required_doctors(entry["type"])
        assigned = entry.get("doctors", [])

        if len(assigned) != required:
            add_hard(d_iso, {
                "code": "HC1",
                "msg": f"Λάθος αριθμός γιατρών: απαιτούνται {required}, βρέθηκαν {len(assigned)}",
            })

        for did in assigned:
            if did not in doc_map:
                continue
            doc = doc_map[did]
            doc_dates[did].append(d)
            per_doctor_stats[did]["shifts"] += 1
            if is_we or is_hol:
                per_doctor_stats[did]["weekends"] += 1
            if is_hol:
                per_doctor_stats[did]["holidays"] += 1
            if doctor_unavailable(doc, d):
                add_hard(d_iso, {
                    "code": "HC34",
                    "msg": f"Ο/Η {doc['full_name']} δεν είναι διαθέσιμος/η ({d_iso})",
                    "doctor_id": did,
                })

        if len(set(assigned)) != len(assigned):
            add_hard(d_iso, {"code": "DUP", "msg": "Ο ίδιος γιατρός εμφανίζεται δύο φορές την ίδια ημέρα"})

    for did, dates in doc_dates.items():
        dates = sorted(dates)
        for prev, cur in zip(dates, dates[1:]):
            gap = (cur - prev).days
            if gap < MIN_GAP_DAYS:
                add_hard(cur.isoformat(), {
                    "code": "HC2",
                    "msg": f"Ο/Η {doc_map[did]['full_name']}: παρήμερα ({prev} και {cur}, διαφορά {gap} ημέρες)",
                    "doctor_id": did,
                })

    weekend_counts = [s["weekends"] for s in per_doctor_stats.values()]
    if weekend_counts and max(weekend_counts) - min(weekend_counts) > 1:
        soft.append({"code": "HC5", "msg": "Άνιση κατανομή Σ/Κ μεταξύ γιατρών (διαφορά > 1)"})

    for did, stats in per_doctor_stats.items():
        if stats["holidays"] > 2:
            msg = f"Ο/Η {stats['name']} έχει {stats['holidays']} αργίες (>2). Η 3η+ αργία δεν πληρώνεται διπλά."
            soft.append({"code": "SC1", "msg": msg, "doctor_id": did})
        if abs(stats["shifts"] - target_per_doctor) > 1:
            msg = f"Ο/Η {stats['name']} έχει {stats['shifts']} εφημερίες (στόχος {target_per_doctor})"
            soft.append({"code": "SC2", "msg": msg, "doctor_id": did})
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


# ---------- Generation ----------

def feasibility_check(days_sorted: list[dict], doctors: list[dict]) -> tuple[bool, list[str]]:
    """Cheap checks that rule out impossible months before searching."""
    issues: list[str] = []

    for dd in days_sorted:
        d = date.fromisoformat(dd["date"])
        required = required_doctors(dd["type"])
        available = [doc for doc in doctors if not doctor_unavailable(doc, d)]
        if len(available) < required:
            issues.append(
                f"Η ημερομηνία {dd['date']} χρειάζεται {required} γιατρ"
                f"{'ούς' if required == 2 else 'ό'} αλλά μόνο {len(available)} "
                f"είναι διαθέσιμοι (μη αρνητικοί/μη σε άδεια)."
            )

    total_demand = sum(required_doctors(d["type"]) for d in days_sorted)
    # Because of the minimum gap, one doctor can cover at most every 4th day.
    max_per_doctor = (len(days_sorted) + MIN_GAP_DAYS - 1) // MIN_GAP_DAYS
    total_capacity = 0
    for doc in doctors:
        available_days = sum(
            1 for dd in days_sorted if not doctor_unavailable(doc, date.fromisoformat(dd["date"]))
        )
        total_capacity += min(max_per_doctor, available_days)

    if total_capacity < total_demand:
        issues.append(
            f"Συνολικά απαιτούνται {total_demand} εφημερίες αλλά το θεωρητικό "
            f"capacity των γιατρών είναι {total_capacity} (λόγω 3ήμερου κενού + "
            f"αρνητικών δηλώσεων). Διαφορά: {total_demand - total_capacity}."
        )

    return len(issues) == 0, issues


def generate_schedule(
    day_definitions: list[dict],
    doctors: list[dict],
    target_per_doctor: Optional[int] = None,
    time_budget_seconds: float = 15.0,
) -> dict:
    """Returns {"schedule", "infeasible", "partial", "reason", "suggestions"}."""
    if not doctors:
        return {
            "schedule": None,
            "infeasible": True,
            "partial": False,
            "reason": "Δεν υπάρχουν ενεργοί γιατροί.",
            "suggestions": ["Προσθέστε γιατρούς ή ενεργοποιήστε υπάρχοντες."],
        }

    days_sorted = sorted(day_definitions, key=lambda x: x["date"])
    flag_map = {
        d["date"]: (d.get("is_weekend", False), d.get("is_holiday", False))
        for d in days_sorted
    }

    def attach_flags(result):
        for entry in result:
            entry["is_weekend"], entry["is_holiday"] = flag_map.get(entry["date"], (False, False))
        return result

    feasible, issues = feasibility_check(days_sorted, doctors)
    if not feasible:
        return {
            "schedule": attach_flags(greedy_partial(days_sorted, doctors)),
            "infeasible": True,
            "partial": True,
            "reason": "Το σενάριο δεν είναι μαθηματικά εφικτό με τους τρέχοντες περιορισμούς.",
            "suggestions": issues + [
                "Μειώστε αρνητικές δηλώσεις σε προβληματικές ημερομηνίες, ή προσθέστε γιατρούς."
            ],
        }

    total_slots = sum(required_doctors(d["type"]) for d in days_sorted)
    if target_per_doctor is None:
        target_per_doctor = max(1, round(total_slots / len(doctors)))

    # Try several randomized searches within the time budget and keep the best one.
    deadline = time.monotonic() + time_budget_seconds
    best_solution = None
    best_score = float("inf")
    attempt = 0
    while time.monotonic() < deadline:
        random.seed(attempt)
        attempt += 1
        result = backtracking_search(days_sorted, doctors, deadline)
        if result is None:
            continue
        attach_flags(result)
        score = score_solution(result, target_per_doctor, doctors)
        if score < best_score:
            best_score = score
            best_solution = result
            if score < 1.0:
                break

    if best_solution is not None:
        return {
            "schedule": best_solution,
            "infeasible": False,
            "partial": False,
            "reason": None,
            "suggestions": [],
        }

    partial = attach_flags(greedy_partial(days_sorted, doctors))
    unfilled = [e["date"] for e in partial if len(e["doctors"]) < required_doctors(e["type"])]
    return {
        "schedule": partial,
        "infeasible": False,
        "partial": True,
        "reason": (
            f"Δεν βρέθηκε πλήρης λύση εντός {int(time_budget_seconds)} δευτερολέπτων. "
            f"Επιστρέφεται μερική λύση που μπορείτε να συμπληρώσετε χειροκίνητα."
        ),
        "suggestions": [
            f"{len(unfilled)} ημερομηνίες δεν γέμισαν: {', '.join(unfilled[:5])}"
            + ("..." if len(unfilled) > 5 else ""),
            "Δοκιμάστε να μειώσετε αρνητικές δηλώσεις, ή συμπληρώστε χειροκίνητα από την οθόνη επεξεργασίας.",
        ],
    }


def score_solution(result: list[dict], target: int, doctors: list[dict]) -> float:
    """Lower is better: distance from the target shift count plus weekend imbalance."""
    stats = {d["id"]: {"shifts": 0, "weekends": 0} for d in doctors}
    for entry in result:
        special = entry.get("is_weekend", False) or entry.get("is_holiday", False)
        for did in entry["doctors"]:
            if did not in stats:
                continue
            stats[did]["shifts"] += 1
            if special:
                stats[did]["weekends"] += 1

    score = sum((s["shifts"] - target) ** 2 for s in stats.values())
    weekends = [s["weekends"] for s in stats.values()]
    if weekends:
        score += (max(weekends) - min(weekends)) * 10
    return score


def backtracking_search(
    days_sorted: list[dict],
    doctors: list[dict],
    deadline: float,
) -> Optional[list[dict]]:
    # One slot per required doctor: (day index, date)
    slots: list[tuple[int, date]] = []
    for i, dd in enumerate(days_sorted):
        d = date.fromisoformat(dd["date"])
        slots.extend((i, d) for _ in range(required_doctors(dd["type"])))

    # Candidate doctors per slot; shrinks as assignments are made.
    domains: list[set[str]] = [
        {doc["id"] for doc in doctors if not doctor_unavailable(doc, d)} for _, d in slots
    ]
    result = [{"date": dd["date"], "type": dd["type"], "doctors": []} for dd in days_sorted]
    shift_count: dict[str, int] = {doc["id"]: 0 for doc in doctors}
    assigned: set[int] = set()

    def pick_next_slot() -> Optional[int]:
        best_idx = None
        best_size = float("inf")
        for idx in range(len(slots)):
            if idx in assigned:
                continue
            size = len(domains[idx])
            if size < best_size:
                best_size = size
                best_idx = idx
                if size <= 1:
                    break
        return best_idx

    def assign(slot_idx: int, did: str) -> list[tuple[int, str]]:
        """Assign and remove the doctor from nearby slots. Returns what was removed."""
        removed: list[tuple[int, str]] = []
        day_idx, d = slots[slot_idx]
        result[day_idx]["doctors"].append(did)
        shift_count[did] += 1
        for other_idx, (other_day_idx, other_d) in enumerate(slots):
            if other_idx == slot_idx or did not in domains[other_idx]:
                continue
            if other_day_idx == day_idx or abs((other_d - d).days) < MIN_GAP_DAYS:
                domains[other_idx].discard(did)
                removed.append((other_idx, did))
        return removed

    def unassign(slot_idx: int, did: str, removed: list[tuple[int, str]]) -> None:
        day_idx, _ = slots[slot_idx]
        result[day_idx]["doctors"].pop()
        shift_count[did] -= 1
        for other_idx, rdid in removed:
            domains[other_idx].add(rdid)

    def backtrack() -> bool:
        if time.monotonic() >= deadline:
            return False
        if len(assigned) == len(slots):
            return True
        slot_idx = pick_next_slot()
        if slot_idx is None:
            return True
        if not domains[slot_idx]:
            return False

        # Doctors with fewer shifts first; random tie-break so attempts differ.
        candidates = sorted(domains[slot_idx], key=lambda did: (shift_count[did], random.random()))
        assigned.add(slot_idx)
        for did in candidates:
            removed = assign(slot_idx, did)
            if backtrack():
                return True
            unassign(slot_idx, did, removed)
        assigned.discard(slot_idx)
        return False

    return result if backtrack() else None


def greedy_partial(days_sorted: list[dict], doctors: list[dict]) -> list[dict]:
    """Fill each day with the least-used available doctors, leaving gaps when stuck."""
    doc_assignments: dict[str, list[date]] = {d["id"]: [] for d in doctors}
    result: list[dict] = []
    random.seed(0)
    for dd in days_sorted:
        d = date.fromisoformat(dd["date"])
        n_required = required_doctors(dd["type"])
        candidates = sorted(doctors, key=lambda x: (len(doc_assignments[x["id"]]), random.random()))
        chosen: list[str] = []
        for doc in candidates:
            if len(chosen) >= n_required:
                break
            if doc["id"] in chosen or doctor_unavailable(doc, d):
                continue
            if any(abs((d - prev).days) < MIN_GAP_DAYS for prev in doc_assignments[doc["id"]]):
                continue
            chosen.append(doc["id"])
            doc_assignments[doc["id"]].append(d)
        result.append({"date": dd["date"], "type": dd["type"], "doctors": chosen})
    return result
