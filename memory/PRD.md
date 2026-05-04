# Πρόγραμμα Εφημεριών — Greek Medical On-Call Shift Scheduler

## Overview
Mobile-first Expo (React Native) app + FastAPI/MongoDB backend for managing monthly on-call shift schedules at ΠΑΓΝΗ / ΒΕΝΙΖΕΛΕΙΟ hospitals. Single chief admin manages 6–8 doctors. All UI is in Greek.

## Tech Stack
- **Frontend**: Expo SDK 54, React Native 0.81, Expo Router, AsyncStorage, axios
- **Backend**: FastAPI, Motor (MongoDB), bcrypt, PyJWT, ReportLab (PDF), DejaVu Sans (Greek font)
- **Auth**: JWT Bearer tokens (mobile-friendly), single chief admin seeded on startup

## Features Implemented (Phase 1 MVP)

### Authentication
- Custom JWT-based login with bcrypt-hashed password
- Single chief admin auto-seeded: `chief@hospital.gr / chief2026`
- AsyncStorage token persistence on the device
- All API endpoints (except `/auth/login`) require Bearer token

### Doctor Management (Διαχείριση Γιατρών)
- 7 sample Greek doctors auto-seeded on first run
- Add / edit / delete / toggle active state

### Monthly Schedule Lifecycle
1. **Wizard** (`/wizard`) — 4 steps: μήνας/έτος → ενεργοί γιατροί → ΠΑΓΝΗ/ΒΕΝΙΖΕΛΕΙΟ ανοιχτή/κλειστή τοggle → αρνητικές ημέρες
2. **Auto-Generation** — backtracking algorithm (200 attempts, fairness scoring)
   - HC-1: Open=2 doctors, Closed=1 doctor
   - HC-2: ≥4-day separation between a doctor's shifts (3-day gap)
   - HC-3/4: Negative days & leaves respected
   - HC-5: Fair Σ/Κ distribution
   - SC-1/2/3: Holiday cap, shift balance, negative-day limit warnings
3. **Edit View** (`/schedule/[id]`) — calendar grid (Sun–Sat in Greek), red/yellow/green per-day highlighting
4. **Real-time Validation** — every assignment triggers re-validation; banner shows total hard/soft counts
5. **Save Draft / Οριστικοποίηση** — both states preserved (override possible)
6. **PDF Export** — A4 landscape, DejaVu Sans, Greek month/day names, color legend; downloadable from `/api/schedules/{id}/export-pdf`

### Greek Holidays (2024–2030)
- Fixed: Πρωτοχρονιά, Θεοφάνια, 25 Μαρτίου, Πρωτομαγιά, Δεκαπενταύγουστος, Όχι, Χριστούγεννα, Σύναξη Θεοτόκου
- Movable (Easter-relative): Καθαρά Δευτέρα, Μ. Παρασκευή, Πάσχα, Δευτέρα Πάσχα, Αγίου Πνεύματος

## API Endpoints (all under `/api`)
- `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`
- `GET/POST/PUT/DELETE /doctors[/{id}]`
- `GET /holidays/{year}`
- `GET/POST/PUT/DELETE /schedules[/{id}]`
- `POST /schedules/{id}/generate`, `POST /schedules/{id}/validate`
- `GET /schedules/{id}/export-pdf` (Bearer header OR `?token=`)

## Data Models (MongoDB)
- `users` — chief admin
- `doctors` — `{id, full_name, notes, is_active, created_at}`
- `schedules` — `{id, year, month, status, day_definitions[], doctor_constraints[], shifts[]}`

## Test Credentials
See `/app/memory/test_credentials.md`.

## Future (Phase 2 — out of scope)
- Per-doctor accounts + public form for unavailability declarations
- API/scraping import of ΠΑΓΝΗ/ΒΕΝΙΖΕΛΕΙΟ schedule
- Excel export
- Per-doctor configurable shift targets (part-time)
