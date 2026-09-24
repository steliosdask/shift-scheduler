"""Monthly on-call schedule generation and validation.

Hard rules (never broken by the generator):
  - An open day needs 2 doctors, a closed day needs 1.
  - A doctor needs at least 3 free days between two shifts.
  - Nobody works on a day of leave.
  - Nobody works twice on the same day.

Preferences (reported as warnings when not met):
  - Negative days are avoided, unless there is no other way to fill the month.
  - Weekends/holidays and shift counts are spread evenly.

Generation first searches for a schedule that respects every negative day.
If none exists, it searches again allowing negative days, keeping the solution
with the fewest of them. Each search is a time-limited backtracking search
(most-constrained slot first, with forward checking). If nothing complete is
found in time, a greedy partial schedule is returned instead.
"""
import random
import time
from datetime import date
from typing import Optional

MIN_GAP_DAYS = 4  # 3 free days between shifts
MAX_NEGATIVE_DAYS = 5  # more than this per doctor triggers a warning
MAX_PAID_HOLIDAYS = 2  # holidays beyond this are not paid double
NEGATIVE_DAY_PENALTY = 1000  # outweighs any balance difference when scoring
TIME_BUDGET_SECONDS = 15.0


def required_doctors(day_type: str) -> int:
    return 2 if day_type == "open" else 1


def target_shifts(days: list[dict], n_doctors: int) -> int:
    """Average number of shifts per doctor for the month."""
    total_slots = sum(required_doctors(d["type"]) for d in days)
    return max(1, round(total_slots / n_doctors)) if n_doctors else 0


def on_leave(doctor: dict, d: date) -> bool:
    for lv in doctor.get("leaves", []):
        if date.fromisoformat(lv["start_date"]) <= d <= date.fromisoformat(lv["end_date"]):
            return True
    return False


def is_negative_day(doctor: dict, d: date) -> bool:
    return d.isoformat() in doctor.get("negative_days", [])


def can_work(doctor: dict, d: date, allow_negative: bool) -> bool:
    return not on_leave(doctor, d) and (allow_negative or not is_negative_day(doctor, d))


# ---------- Validation ----------

def validate_assignment(schedule_dates: list[dict], doctors: list[dict]) -> dict:
    hard = []
    soft = []
    per_day: dict = {}
    per_doctor_stats = {
        d["id"]: {"shifts": 0, "weekends": 0, "holidays": 0, "name": d["full_name"]}
        for d in doctors
    }
    doc_map = {d["id"]: d for d in doctors}
    doc_dates: dict[str, list[date]] = {d["id"]: [] for d in doctors}

    target = target_shifts(schedule_dates, len(doctors))

    def add_hard(d_iso: str, issue: dict):
        per_day[d_iso]["hard"].append(issue)
        hard.append({"date": d_iso, **issue})

    def add_soft(d_iso: str, issue: dict):
        per_day[d_iso]["soft"].append(issue)
        soft.append({"date": d_iso, **issue})

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
            if on_leave(doc, d):
                add_hard(d_iso, {
                    "code": "HC4",
                    "msg": f"Ο/Η {doc['full_name']} είναι σε άδεια ({d_iso})",
                    "doctor_id": did,
                })
            elif is_negative_day(doc, d):
                add_soft(d_iso, {
                    "code": "SC4",
                    "msg": f"Ο/Η {doc['full_name']} εφημερεύει σε αρνητική ημέρα ({d_iso})",
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
        soft.append({"code": "SC5", "msg": "Άνιση κατανομή Σ/Κ μεταξύ γιατρών (διαφορά > 1)"})

    for did, stats in per_doctor_stats.items():
        if stats["holidays"] > MAX_PAID_HOLIDAYS:
            msg = (
                f"Ο/Η {stats['name']} έχει {stats['holidays']} αργίες (>{MAX_PAID_HOLIDAYS}). "
                f"Η {MAX_PAID_HOLIDAYS + 1}η+ αργία δεν πληρώνεται διπλά."
            )
            soft.append({"code": "SC1", "msg": msg, "doctor_id": did})
        if abs(stats["shifts"] - target) > 1:
            msg = f"Ο/Η {stats['name']} έχει {stats['shifts']} εφημερίες (στόχος {target})"
            soft.append({"code": "SC2", "msg": msg, "doctor_id": did})
        nd = len(doc_map[did].get("negative_days", []))
        if nd > MAX_NEGATIVE_DAYS:
            msg = f"Ο/Η {stats['name']} έχει δηλώσει {nd} αρνητικές ημέρες (όριο {MAX_NEGATIVE_DAYS})"
            soft.append({"code": "SC3", "msg": msg, "doctor_id": did})

    return {
        "hard": hard,
        "soft": soft,
        "per_day": per_day,
        "per_doctor": per_doctor_stats,
    }


# ---------- Generation ----------

def feasibility_issues(days_sorted: list[dict], doctors: list[dict], allow_negative: bool) -> list[str]:
    """Cheap checks that rule out impossible months before searching.

    Only the check with allow_negative=True is shown to the user (leaves are the
    only hard limit); the strict one just decides whether to try without negative days.
    """
    issues: list[str] = []

    for dd in days_sorted:
        d = date.fromisoformat(dd["date"])
        required = required_doctors(dd["type"])
        available = sum(1 for doc in doctors if can_work(doc, d, allow_negative))
        if available < required:
            issues.append(
                f"Η ημερομηνία {dd['date']} χρειάζεται {required} γιατρ"
                f"{'ούς' if required == 2 else 'ό'} αλλά μόνο {available} "
                f"είναι διαθέσιμοι (μη σε άδεια)."
            )

    total_demand = sum(required_doctors(d["type"]) for d in days_sorted)
    # Because of the minimum gap, one doctor can cover at most every 4th day.
    max_per_doctor = (len(days_sorted) + MIN_GAP_DAYS - 1) // MIN_GAP_DAYS
    total_capacity = 0
    for doc in doctors:
        available_days = sum(
            1 for dd in days_sorted if can_work(doc, date.fromisoformat(dd["date"]), allow_negative)
        )
        total_capacity += min(max_per_doctor, available_days)

    if total_capacity < total_demand:
        issues.append(
            f"Συνολικά απαιτούνται {total_demand} εφημερίες αλλά το θεωρητικό "
            f"capacity των γιατρών είναι {total_capacity} (λόγω 3ήμερου κενού + αδειών). "
            f"Διαφορά: {total_demand - total_capacity}."
        )

    return issues


def generate_schedule(
    day_definitions: list[dict],
    doctors: list[dict],
    time_budget_seconds: float = TIME_BUDGET_SECONDS,
) -> dict:
    """Returns {"schedule", "infeasible", "reason", "suggestions"}.

    An infeasible month has no schedule, only the reason and suggestions.
    """
    days_sorted = sorted(day_definitions, key=lambda x: x["date"])

    # Negative days are only preferences, so only leaves can make a month impossible.
    issues = feasibility_issues(days_sorted, doctors, allow_negative=True)
    if issues:
        return {
            "schedule": None,
            "infeasible": True,
            "reason": "Το σενάριο δεν είναι μαθηματικά εφικτό με τους τρέχοντες περιορισμούς.",
            "suggestions": issues + ["Μειώστε τις άδειες σε προβληματικές ημερομηνίες, ή προσθέστε γιατρούς."],
        }

    flag_map = {
        d["date"]: (d.get("is_weekend", False), d.get("is_holiday", False))
        for d in days_sorted
    }

    def attach_flags(result):
        for entry in result:
            entry["is_weekend"], entry["is_holiday"] = flag_map.get(entry["date"], (False, False))
        return result

    target = target_shifts(days_sorted, len(doctors))
    start = time.monotonic()

    def search(allow_negative: bool, until: float) -> Optional[list[dict]]:
        """Run randomized searches until `until` and return the best schedule found."""
        best_solution = None
        best_score = float("inf")
        attempt = 0
        while time.monotonic() < until:
            random.seed(attempt)
            attempt += 1
            result = backtracking_search(days_sorted, doctors, until, allow_negative)
            if result is None:
                continue
            attach_flags(result)
            score = score_solution(result, target, doctors)
            if score < best_score:
                best_score = score
                best_solution = result
                if score < 1.0:
                    break
        return best_solution

    best = None
    if not feasibility_issues(days_sorted, doctors, allow_negative=False):
        best = search(allow_negative=False, until=start + time_budget_seconds * 0.6)
    if best is None:
        best = search(allow_negative=True, until=start + time_budget_seconds)

    if best is not None:
        return {"schedule": best, "infeasible": False, "reason": None, "suggestions": []}

    partial = attach_flags(greedy_partial(days_sorted, doctors))
    unfilled = [e["date"] for e in partial if len(e["doctors"]) < required_doctors(e["type"])]
    return {
        "schedule": partial,
        "infeasible": False,
        "reason": (
            f"Δεν βρέθηκε πλήρης λύση εντός {int(time_budget_seconds)} δευτερολέπτων. "
            f"Επιστρέφεται μερική λύση που μπορείτε να συμπληρώσετε χειροκίνητα."
        ),
        "suggestions": [
            f"{len(unfilled)} ημερομηνίες δεν γέμισαν: {', '.join(unfilled[:5])}"
            + ("..." if len(unfilled) > 5 else ""),
            "Δοκιμάστε να μειώσετε τις άδειες, ή συμπληρώστε χειροκίνητα από την οθόνη επεξεργασίας.",
        ],
    }


def score_solution(result: list[dict], target: int, doctors: list[dict]) -> float:
    """Lower is better: negative days used, distance from the target, weekend imbalance."""
    doc_map = {d["id"]: d for d in doctors}
    stats = {d["id"]: {"shifts": 0, "weekends": 0} for d in doctors}
    negatives = 0
    for entry in result:
        special = entry.get("is_weekend", False) or entry.get("is_holiday", False)
        d = date.fromisoformat(entry["date"])
        for did in entry["doctors"]:
            stats[did]["shifts"] += 1
            if special:
                stats[did]["weekends"] += 1
            if is_negative_day(doc_map[did], d):
                negatives += 1

    weekends = [s["weekends"] for s in stats.values()]
    return (
        negatives * NEGATIVE_DAY_PENALTY
        + sum((s["shifts"] - target) ** 2 for s in stats.values())
        + (max(weekends) - min(weekends)) * 10
    )


def backtracking_search(
    days_sorted: list[dict],
    doctors: list[dict],
    deadline: float,
    allow_negative: bool,
) -> Optional[list[dict]]:
    doc_map = {doc["id"]: doc for doc in doctors}

    # One slot per required doctor: (day index, date)
    slots: list[tuple[int, date]] = []
    for i, dd in enumerate(days_sorted):
        d = date.fromisoformat(dd["date"])
        slots.extend((i, d) for _ in range(required_doctors(dd["type"])))

    # Candidate doctors per slot; shrinks as assignments are made.
    domains: list[set[str]] = [
        {doc["id"] for doc in doctors if can_work(doc, d, allow_negative)} for _, d in slots
    ]
    result = [{"date": dd["date"], "type": dd["type"], "doctors": []} for dd in days_sorted]
    shift_count: dict[str, int] = {doc["id"]: 0 for doc in doctors}
    assigned: set[int] = set()

    def pick_next_slot() -> int:
        best_idx = -1
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
        if not domains[slot_idx]:
            return False

        # Doctors without a negative day here first, then fewer shifts; random tie-break.
        d = slots[slot_idx][1]
        candidates = sorted(
            domains[slot_idx],
            key=lambda did: (is_negative_day(doc_map[did], d), shift_count[did], random.random()),
        )
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
    """Fill each day with the least-used available doctors, leaving gaps when stuck.

    Negative days are used only when a day cannot be filled otherwise.
    """
    doc_assignments: dict[str, list[date]] = {d["id"]: [] for d in doctors}
    result: list[dict] = []
    random.seed(0)
    for dd in days_sorted:
        d = date.fromisoformat(dd["date"])
        n_required = required_doctors(dd["type"])
        candidates = sorted(doctors, key=lambda x: (len(doc_assignments[x["id"]]), random.random()))
        chosen: list[str] = []
        for allow_negative in (False, True):
            for doc in candidates:
                if len(chosen) >= n_required:
                    break
                if doc["id"] in chosen or not can_work(doc, d, allow_negative):
                    continue
                if any(abs((d - prev).days) < MIN_GAP_DAYS for prev in doc_assignments[doc["id"]]):
                    continue
                chosen.append(doc["id"])
                doc_assignments[doc["id"]].append(d)
        result.append({"date": dd["date"], "type": dd["type"], "doctors": chosen})
    return result
