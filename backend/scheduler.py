"""Schedule auto-generation με backtracking + heuristics.

Βελτιωμένη έκδοση:
  - Pre-search feasibility check (γρήγορη απόρριψη ανέφικτων σεναρίων)
  - Time-budgeted backtracking με wall-clock deadline
  - True MRV variable ordering (re-evaluated σε κάθε βήμα)
  - Forward checking (constraint propagation στις γειτονικές μέρες)
  - Greedy partial fallback όταν δεν βρεθεί πλήρης λύση

Hard constraints:
  HC-1: Open shift = 2 γιατροί, Closed shift = 1 γιατρός
  HC-2: Ελάχιστο κενό 3 ημερών μεταξύ εφημεριών ίδιου γιατρού (gap >= 4)
  HC-3: Σεβασμός αρνητικών ημερών
  HC-4: Σεβασμός αδειών
  HC-5: Δίκαιη κατανομή Σ/Κ + αργιών
"""
from datetime import date, timedelta
from typing import Optional
import random
import time


# ---------- Helpers ----------

def _doctor_unavailable(doctor: dict, d: date) -> bool:
    """True αν ο γιατρός έχει αρνητική μέρα ή είναι σε άδεια εκείνη την ημερομηνία."""
    if d.isoformat() in doctor.get("negative_days", []):
        return True
    for lv in doctor.get("leaves", []):
        s = date.fromisoformat(lv["start_date"])
        e = date.fromisoformat(lv["end_date"])
        if s <= d <= e:
            return True
    return False


# ---------- Validation (η public API παραμένει η ίδια) ----------

def validate_assignment(
    schedule_dates: list[dict],
    doctors: list[dict],
    target_per_doctor: int = 6,
    negative_day_limit: int = 5,
) -> dict:
    """Run all constraint checks. (Αμετάβλητο από την προηγούμενη έκδοση.)"""
    hard = []
    soft = []
    per_day: dict = {}
    per_doctor_stats = {
        d["id"]: {"shifts": 0, "weekends": 0, "holidays": 0, "name": d["full_name"]}
        for d in doctors
    }
    doc_map = {d["id"]: d for d in doctors}
    doc_dates: dict[str, list[date]] = {d["id"]: [] for d in doctors}

    for entry in schedule_dates:
        d_iso = entry["date"]
        d = date.fromisoformat(d_iso)
        is_we = entry.get("is_weekend", d.weekday() >= 5)
        is_hol = entry.get("is_holiday", False)
        per_day[d_iso] = {"hard": [], "soft": []}
        required = 2 if entry["type"] == "open" else 1
        actual_doctors = entry.get("doctors", [])

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

            if _doctor_unavailable(doc, d):
                msg = f"Ο/Η {doc['full_name']} δεν είναι διαθέσιμος/η ({d_iso})"
                per_day[d_iso]["hard"].append({"code": "HC34", "msg": msg, "doctor_id": did})
                hard.append({"date": d_iso, "code": "HC34", "msg": msg, "doctor_id": did})

        if len(set(actual_doctors)) != len(actual_doctors):
            msg = "Ο ίδιος γιατρός εμφανίζεται δύο φορές την ίδια ημέρα"
            per_day[d_iso]["hard"].append({"code": "DUP", "msg": msg})
            hard.append({"date": d_iso, "code": "DUP", "msg": msg})

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


# ---------- Feasibility check (γρήγορος έλεγχος πριν την αναζήτηση) ----------

def _feasibility_check(
    days_sorted: list[dict],
    doctors: list[dict],
) -> tuple[bool, list[str]]:
    """Quick checks πριν το backtracking. Επιστρέφει (ok, list_of_issues)."""
    issues: list[str] = []

    # Έλεγχος 1: κάθε μέρα έχει αρκετούς διαθέσιμους γιατρούς
    for dd in days_sorted:
        d = date.fromisoformat(dd["date"])
        required = 2 if dd["type"] == "open" else 1
        available = [doc for doc in doctors if not _doctor_unavailable(doc, d)]
        if len(available) < required:
            issues.append(
                f"Η ημερομηνία {dd['date']} χρειάζεται {required} γιατρ"
                f"{'ούς' if required == 2 else 'ό'} αλλά μόνο {len(available)} "
                f"είναι διαθέσιμοι (μη αρνητικοί/μη σε άδεια)."
            )

    # Έλεγχος 2: συνολικό capacity vs total demand
    total_demand = sum(2 if d["type"] == "open" else 1 for d in days_sorted)
    n_days = len(days_sorted)
    # Max shifts ανά γιατρό λόγω 3-day gap: ceil(n_days / 4)
    max_per_doctor = (n_days + 3) // 4
    # Adjust για αρνητικές: αν ο γιατρός έχει πολλές αρνητικές, λιγότερες διαθέσιμες
    total_capacity = 0
    for doc in doctors:
        available_days = sum(
            1 for dd in days_sorted
            if not _doctor_unavailable(doc, date.fromisoformat(dd["date"]))
        )
        total_capacity += min(max_per_doctor, available_days)

    if total_capacity < total_demand:
        issues.append(
            f"Συνολικά απαιτούνται {total_demand} εφημερίες αλλά το θεωρητικό "
            f"capacity των γιατρών είναι {total_capacity} (λόγω 3ήμερου κενού + "
            f"αρνητικών δηλώσεων). Διαφορά: {total_demand - total_capacity}."
        )

    return (len(issues) == 0, issues)


# ---------- Κύρια συνάρτηση παραγωγής ----------

def generate_schedule(
    year: int,
    month: int,
    day_definitions: list[dict],
    doctors: list[dict],
    target_per_doctor: Optional[int] = None,
    time_budget_seconds: float = 15.0,
) -> dict:
    """
    Παράγει πρόγραμμα εντός χρονικού ορίου.

    Επιστρέφει dict:
      {
        "schedule": list[dict] | None,
        "infeasible": bool,
        "partial": bool,
        "reason": str | None,
        "suggestions": list[str],
      }
    """
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

    def _attach_flags(result):
        for entry in result:
            iw, ih = flag_map.get(entry["date"], (False, False))
            entry["is_weekend"] = iw
            entry["is_holiday"] = ih
        return result

    # Στάδιο 1: feasibility check
    feasible, issues = _feasibility_check(days_sorted, doctors)
    if not feasible:
        partial = _greedy_partial(days_sorted, doctors)
        return {
            "schedule": _attach_flags(partial),
            "infeasible": True,
            "partial": True,
            "reason": "Το σενάριο δεν είναι μαθηματικά εφικτό με τους τρέχοντες περιορισμούς.",
            "suggestions": issues + [
                "Μειώστε αρνητικές δηλώσεις σε προβληματικές ημερομηνίες, ή προσθέστε γιατρούς."
            ],
        }

    # Στάδιο 2: backtracking με time budget
    total_slots = sum(2 if d["type"] == "open" else 1 for d in days_sorted)
    if target_per_doctor is None:
        target_per_doctor = max(1, round(total_slots / len(doctors)))

    deadline = time.monotonic() + time_budget_seconds
    best_solution = None
    best_score = float("inf")
    attempt = 0

    # Πολλαπλά γρήγορα tries, όλα μέσα στο time budget
    while time.monotonic() < deadline:
        random.seed(attempt)
        attempt += 1
        result = _attempt_one_smart(days_sorted, doctors, deadline)
        if result is None:
            continue
        _attach_flags(result)
        score = _score_solution(result, target_per_doctor, doctors)
        if score < best_score:
            best_score = score
            best_solution = result
            if score < 1.0:
                break  # near-optimal, σταματάμε νωρίς

    if best_solution is not None:
        return {
            "schedule": best_solution,
            "infeasible": False,
            "partial": False,
            "reason": None,
            "suggestions": [],
        }

    # Στάδιο 3: fallback — greedy partial
    partial = _attach_flags(_greedy_partial(days_sorted, doctors))
    unfilled = [e["date"] for e in partial if len(e["doctors"]) < (2 if e["type"] == "open" else 1)]
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


# ---------- Scoring (για διαλογή μεταξύ feasible λύσεων) ----------

def _score_solution(result: list[dict], target: int, doctors: list[dict]) -> float:
    """Χαμηλότερο = καλύτερο. Συνδυάζει deviation από target και weekend imbalance."""
    stats = {d["id"]: {"shifts": 0, "weekends": 0} for d in doctors}
    for entry in result:
        is_we = entry.get("is_weekend", False)
        is_hol = entry.get("is_holiday", False)
        for did in entry["doctors"]:
            if did not in stats:
                continue
            stats[did]["shifts"] += 1
            if is_we or is_hol:
                stats[did]["weekends"] += 1

    score = 0.0
    for s in stats.values():
        score += (s["shifts"] - target) ** 2
    weekends = [s["weekends"] for s in stats.values()]
    if weekends:
        score += (max(weekends) - min(weekends)) * 10
    return score


# ---------- Smart backtracking με MRV + forward checking ----------

def _attempt_one_smart(
    days_sorted: list[dict],
    doctors: list[dict],
    deadline: float,
) -> Optional[list[dict]]:
    """
    Backtracking με:
      - True MRV: σε κάθε βήμα διαλέγουμε το slot με τους λιγότερους candidates
      - Forward checking: μετά από ανάθεση, ενημερώνουμε domains των επόμενων slots
      - Wall-clock deadline (κοινό με τις άλλες προσπάθειες)
    """
    # Κατασκευή slots: (day_idx, slot_idx, date_obj)
    slots: list[tuple[int, int, date]] = []
    for i, dd in enumerate(days_sorted):
        n = 2 if dd["type"] == "open" else 1
        d = date.fromisoformat(dd["date"])
        for j in range(n):
            slots.append((i, j, d))

    # Domain ανά slot: σύνολο doctor_ids που είναι candidates
    # Αρχικά: όσοι γιατροί δεν είναι unavailable τη μέρα του slot
    domains: list[set[str]] = []
    for (_, _, d) in slots:
        dom = {doc["id"] for doc in doctors if not _doctor_unavailable(doc, d)}
        domains.append(dom)

    # Result placeholder: για κάθε ημέρα, η λίστα γιατρών
    result = [
        {"date": dd["date"], "type": dd["type"], "doctors": []}
        for dd in days_sorted
    ]

    # Για forward checking: doctor_id → set των slot_indices που έχει assigned
    doc_to_slots: dict[str, set[int]] = {doc["id"]: set() for doc in doctors}

    # Counter για load balancing (κατά voor candidate ordering)
    doc_shift_count: dict[str, int] = {doc["id"]: 0 for doc in doctors}

    def pick_next_slot(assigned: set[int]) -> Optional[int]:
        """Επιστρέφει το index του slot με το μικρότερο domain (MRV)."""
        best_idx = None
        best_size = float("inf")
        for idx in range(len(slots)):
            if idx in assigned:
                continue
            sz = len(domains[idx])
            if sz < best_size:
                best_size = sz
                best_idx = idx
                if sz <= 1:  # δεν θα βρούμε καλύτερο
                    return best_idx
        return best_idx

    def apply_assignment(slot_idx: int, did: str) -> list[tuple[int, str]]:
        """Αναθέτει γιατρό σε slot και κάνει forward checking.
        Επιστρέφει list (other_slot_idx, removed_did) ώστε να γίνει undo."""
        removed: list[tuple[int, str]] = []
        day_idx, _, d = slots[slot_idx]
        result[day_idx]["doctors"].append(did)
        doc_to_slots[did].add(slot_idx)
        doc_shift_count[did] += 1

        # Αφαίρεσε τον γιατρό από όλα τα slots που είναι:
        # (α) ίδια μέρα (no double-booking)
        # (β) εντός 3 ημερών από αυτό (3-day gap)
        for other_idx in range(len(slots)):
            if other_idx == slot_idx:
                continue
            other_day_idx, _, other_d = slots[other_idx]
            close_in_time = abs((other_d - d).days) < 4
            same_day = other_day_idx == day_idx
            if (close_in_time or same_day) and did in domains[other_idx]:
                domains[other_idx].discard(did)
                removed.append((other_idx, did))
        return removed

    def undo_assignment(slot_idx: int, did: str, removed: list[tuple[int, str]]) -> None:
        day_idx, _, _ = slots[slot_idx]
        result[day_idx]["doctors"].pop()
        doc_to_slots[did].discard(slot_idx)
        doc_shift_count[did] -= 1
        for (other_idx, rdid) in removed:
            domains[other_idx].add(rdid)

    assigned: set[int] = set()

    def backtrack() -> bool:
        # Time check ανά step (cheap)
        if time.monotonic() >= deadline:
            return False

        if len(assigned) == len(slots):
            return True

        slot_idx = pick_next_slot(assigned)
        if slot_idx is None:
            return True
        # Αν το domain έχει αδειάσει, dead end
        if not domains[slot_idx]:
            return False

        # Order candidates: γιατροί με λιγότερες εφημερίες πρώτα (load balancing)
        # + tiny random tiebreak για variety μεταξύ attempts
        candidates = sorted(
            domains[slot_idx],
            key=lambda did: (doc_shift_count[did], random.random()),
        )

        assigned.add(slot_idx)
        for did in candidates:
            removed = apply_assignment(slot_idx, did)
            if backtrack():
                return True
            undo_assignment(slot_idx, did, removed)
        assigned.discard(slot_idx)
        return False

    success = backtrack()
    return result if success else None


# ---------- Greedy partial fallback ----------

def _greedy_partial(days_sorted: list[dict], doctors: list[dict]) -> list[dict]:
    """Για κάθε μέρα, διάλεξε γιατρούς με τις λιγότερες εφημερίες μέχρι τώρα.
    Παραλείπει slots που δεν μπορούν να γεμίσουν αντί να αποτυγχάνει."""
    doc_assignments: dict[str, list[date]] = {d["id"]: [] for d in doctors}
    result: list[dict] = []
    random.seed(0)
    for dd in days_sorted:
        d = date.fromisoformat(dd["date"])
        n_required = 2 if dd["type"] == "open" else 1
        candidates = sorted(
            doctors,
            key=lambda x: (len(doc_assignments[x["id"]]), random.random()),
        )
        chosen: list[str] = []
        for doc in candidates:
            if len(chosen) >= n_required:
                break
            if doc["id"] in chosen:
                continue
            if _doctor_unavailable(doc, d):
                continue
            ok = True
            for prev in doc_assignments[doc["id"]]:
                if abs((d - prev).days) < 4:
                    ok = False
                    break
            if not ok:
                continue
            chosen.append(doc["id"])
            doc_assignments[doc["id"]].append(d)
        result.append({"date": dd["date"], "type": dd["type"], "doctors": chosen})
    return result