"""Greek Orthodox Easter and holiday calculations for years 2024-2030."""
from datetime import date, timedelta

# Orthodox Easter Sundays (Julian -> Gregorian) for 2024-2030
ORTHODOX_EASTER = {
    2024: date(2024, 5, 5),
    2025: date(2025, 4, 20),
    2026: date(2026, 4, 12),
    2027: date(2027, 5, 2),
    2028: date(2028, 4, 16),
    2029: date(2029, 4, 8),
    2030: date(2030, 4, 28),
}

# Fixed Greek public holidays (paid double for shifts)
FIXED_HOLIDAYS = [
    (1, 1, "Πρωτοχρονιά"),
    (1, 6, "Θεοφάνια"),
    (3, 25, "Εικοστή Πέμπτη Μαρτίου"),
    (5, 1, "Εργατική Πρωτομαγιά"),
    (8, 15, "Κοίμηση Θεοτόκου"),
    (10, 28, "Επέτειος του Όχι"),
    (12, 25, "Χριστούγεννα"),
    (12, 26, "Σύναξη Θεοτόκου"),
]


def get_holidays(year: int) -> dict:
    """Return mapping of date -> holiday name for the given year."""
    holidays: dict[date, str] = {}
    for m, d, name in FIXED_HOLIDAYS:
        holidays[date(year, m, d)] = name

    easter = ORTHODOX_EASTER.get(year)
    if easter:
        # Καθαρά Δευτέρα: 48 days before Easter Sunday
        holidays[easter - timedelta(days=48)] = "Καθαρά Δευτέρα"
        # Μεγάλη Παρασκευή
        holidays[easter - timedelta(days=2)] = "Μεγάλη Παρασκευή"
        # Κυριακή του Πάσχα
        holidays[easter] = "Κυριακή του Πάσχα"
        # Δευτέρα του Πάσχα
        holidays[easter + timedelta(days=1)] = "Δευτέρα του Πάσχα"
        # Αγίου Πνεύματος (50 days after Easter)
        holidays[easter + timedelta(days=50)] = "Αγίου Πνεύματος"
    return holidays


def is_holiday(d: date) -> bool:
    return d in get_holidays(d.year)


def holiday_name(d: date) -> str | None:
    return get_holidays(d.year).get(d)


def is_special_day(d: date) -> bool:
    """Saturday, Sunday, or Greek holiday (Σ/Κ + Αργίες)."""
    return d.weekday() >= 5 or is_holiday(d)
