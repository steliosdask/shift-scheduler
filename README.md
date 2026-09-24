# Shift Scheduler

[Ελληνικά](#ελληνικά) · [English](#english)

---

## Ελληνικά

Εφαρμογή κινητού για τη δημιουργία του μηνιαίου προγράμματος εφημεριών μιας ομάδας γιατρών.

### Τι κάνει

- Κάθε ημέρα του μήνα ορίζεται ως **ανοιχτή** (Νοσοκομείο 1, 2 γιατροί) ή **κλειστή** (Νοσοκομείο 2, 1 γιατρός).
- Οι επίσημες αργίες σημειώνονται αυτόματα και μπορούν να προστεθούν επιπλέον αργίες.
- Για κάθε γιατρό δηλώνονται αρνητικές ημέρες (προτίμηση) και άδειες (υποχρεωτικές).
- Το πρόγραμμα δημιουργείται αυτόματα, με τουλάχιστον 3 ελεύθερες ημέρες μεταξύ δύο εφημεριών του ίδιου γιατρού και ισόποση κατανομή Σαββατοκύριακων και αργιών.
- Το πρόγραμμα μπορεί να διορθωθεί χειροκίνητα. Η εφαρμογή επισημαίνει όποιον κανόνα παραβιάζεται.
- Εξαγωγή του μήνα σε PDF (A4, οριζόντιο).

### Κανόνες προγράμματος

**Υποχρεωτικοί** (δεν παραβιάζονται ποτέ από την αυτόματη δημιουργία· αν παραβιαστούν χειροκίνητα, η ημέρα γίνεται κόκκινη):

1. Ανοιχτή εφημερία: 2 γιατροί. Κλειστή εφημερία: 1 γιατρός.
2. Τουλάχιστον 3 ελεύθερες ημέρες ανάμεσα σε δύο εφημερίες του ίδιου γιατρού.
3. Κανείς δεν εφημερεύει σε ημέρα άδειας.
4. Ο ίδιος γιατρός δεν μπαίνει δύο φορές την ίδια ημέρα.

**Προτιμήσεις** (όταν δεν τηρούνται, η εφαρμογή εμφανίζει προειδοποίηση):

5. Οι αρνητικές ημέρες αποφεύγονται. Αν δεν γίνεται αλλιώς, ο γιατρός μπαίνει με όσο το δυνατόν λιγότερες τέτοιες ημέρες και η ημέρα σημειώνεται με κίτρινο.
6. Σαββατοκύριακα και αργίες μοιράζονται ισόποσα (διαφορά έως 1 μεταξύ γιατρών).
7. Έως 2 αργίες ανά γιατρό· η 3η και οι επόμενες δεν πληρώνονται διπλά.
8. Κάθε γιατρός έχει περίπου όσες εφημερίες αναλογούν στον μήνα (±1).
9. Έως 5 αρνητικές ημέρες ανά γιατρό.

**Δημιουργία:** ο αλγόριθμος ψάχνει πρώτα πρόγραμμα που τηρεί όλες τις αρνητικές ημέρες και, μόνο αν αυτό δεν υπάρχει, επιτρέπει όσο το δυνατόν λιγότερες. Ψάχνει έως 15 δευτερόλεπτα το πιο ισορροπημένο πρόγραμμα· αν δεν βρει πλήρη λύση, δίνει μερική που συμπληρώνεται χειροκίνητα. Οι κανόνες εμφανίζονται και μέσα στην εφαρμογή, από το κουμπί ⓘ της αρχικής οθόνης.

### Τεχνολογίες

- **Frontend:** Expo / React Native (Expo Router), TypeScript
- **Backend:** FastAPI (Python 3.11), MongoDB (Motor), ReportLab για τα PDF
- **Σύνδεση:** όνομα χρήστη και κωδικός, με JWT

### Δομή

```
backend/    FastAPI server, αλγόριθμος προγράμματος, PDF
frontend/   Εφαρμογή Expo
```

### Τοπική εκτέλεση

Απαιτούνται Python 3.11, Node.js και MongoDB.

**Backend**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Το `backend/.env` χρειάζεται τις παρακάτω μεταβλητές:

| Μεταβλητή | Περιγραφή |
|---|---|
| `MONGO_URL` | Διεύθυνση σύνδεσης στη MongoDB |
| `DB_NAME` | Όνομα της βάσης |
| `JWT_SECRET` | Τυχαίο μυστικό για την υπογραφή των tokens |
| `ADMIN_USERNAME` | Όνομα χρήστη του διαχειριστή (δημιουργείται στην εκκίνηση) |
| `ADMIN_PASSWORD` | Κωδικός του διαχειριστή |
| `CORS_ORIGINS` | Προαιρετικό, λίστα διευθύνσεων χωρισμένων με κόμμα (προεπιλογή: όλες) |

**Frontend**

```bash
cd frontend
npm install
npx expo start
```

Το `frontend/.env` χρειάζεται τη μεταβλητή `EXPO_PUBLIC_BACKEND_URL` με τη διεύθυνση του backend (π.χ. `http://<IP-του-υπολογιστή>:8000` για δοκιμή από κινητό στο ίδιο δίκτυο).

Τα αρχεία `.env` δεν ανεβαίνουν στο αποθετήριο.

---

## English

A mobile app for building the monthly on-call schedule of a team of doctors.

### Features

- Each day of the month is marked **open** (Hospital 1, 2 doctors) or **closed** (Hospital 2, 1 doctor).
- Greek public holidays are marked automatically; extra holidays can be added.
- Negative days (preference) and leaves (mandatory) can be set per doctor.
- Automatic schedule generation, with at least 3 free days between two shifts of the same doctor and an even spread of weekends and holidays.
- Manual editing, with rule violations highlighted.
- PDF export of the month (A4 landscape).

### Scheduling rules

**Hard rules** (never broken by automatic generation; a day that breaks one after manual editing turns red):

1. Open day: 2 doctors. Closed day: 1 doctor.
2. At least 3 free days between two shifts of the same doctor.
3. Nobody works on a day of leave.
4. Nobody works twice on the same day.

**Preferences** (the app shows a warning when one is not met):

5. Negative days are avoided. If there is no other way, the doctor is assigned with as few such days as possible and the day is marked yellow.
6. Weekends and holidays are spread evenly (at most 1 apart between doctors).
7. At most 2 holidays per doctor; the 3rd and later are not paid double.
8. Each doctor gets roughly their share of the month's shifts (±1).
9. At most 5 negative days per doctor.

**Generation:** the algorithm first looks for a schedule that respects every negative day and only if none exists allows as few as possible. It searches for up to 15 seconds for the most balanced schedule; if no complete solution is found, it returns a partial one to be completed by hand. The rules are also shown in the app, from the ⓘ button on the home screen.

### Stack

- **Frontend:** Expo / React Native (Expo Router), TypeScript
- **Backend:** FastAPI (Python 3.11), MongoDB (Motor), ReportLab for PDFs
- **Auth:** username and password, JWT

### Layout

```
backend/    FastAPI server, scheduling algorithm, PDF export
frontend/   Expo app
```

### Running locally

Requires Python 3.11, Node.js and MongoDB.

**Backend**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

`backend/.env` needs the following variables:

| Variable | Description |
|---|---|
| `MONGO_URL` | MongoDB connection string |
| `DB_NAME` | Database name |
| `JWT_SECRET` | Random secret used to sign tokens |
| `ADMIN_USERNAME` | Admin username (created on startup) |
| `ADMIN_PASSWORD` | Admin password |
| `CORS_ORIGINS` | Optional, comma-separated list of allowed origins (default: all) |

**Frontend**

```bash
cd frontend
npm install
npx expo start
```

`frontend/.env` needs `EXPO_PUBLIC_BACKEND_URL`, the address of the backend (e.g. `http://<computer-ip>:8000` when testing from a phone on the same network).

`.env` files are not committed.
