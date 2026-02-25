# GymTracker – MSc Software Engineering Practice (7WCM2017)
**Product 5: Gym and Workout Tracker Web Application**  
Student: Samuel E. Maitland | Stack: Django 5.x · SQLite · Bootstrap 5 · Django Templates

---

## Quick Setup

```bash
# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run migrations
python manage.py makemigrations accounts gym bookings tracker
python manage.py migrate

# 4. Create a superuser (admin demo account)
python manage.py createsuperuser

# 5. (Optional) Load seed data
python manage.py loaddata seed_data.json

# 6. Run the development server
python manage.py runserver
# → Visit http://127.0.0.1:8000/
```

---

## Running the Test Suite

```bash
python manage.py test tests --verbosity=2
```

Tests are split across three modules:

| Module | Covers |
|--------|--------|
| `tests/test_booking_state_machine.py` | Epic 6 – state transitions, capacity, service layer |
| `tests/test_accounts.py` | Epic 1-2 – user model, registration, role permissions |
| `tests/test_tracker.py` | Epic 7 – set validation, volume calculation, PR service |
| `tests/test_gym_search.py` | Epic 3-5 – text search, category filter, model properties |

---

## Architecture Overview

```
gymtracker/
├── accounts/          # Epic 1-2: Custom User (email login), MemberProfile, auth flows
├── gym/               # Epic 3-5: WorkoutCategory, GymEquipment, WorkoutClass, search/filter
├── bookings/          # Epic 6: Booking state machine (Booked→Cancelled/Attended/Missed)
│   └── services.py    # Service layer — all booking business logic isolated here
├── tracker/           # Epic 7: WorkoutSession, WorkoutEntry, SetEntry, Routine, progress
│   └── services.py    # Progress metrics (volume over time, personal records)
└── templates/         # Base Bootstrap 5 layout + per-app templates
```

### Three-Layer Architecture

```
Template (HTML/Bootstrap 5)
    ↕
View (HTTP request/response, delegates to service)
    ↕
Service (business logic, isolated and testable)
    ↕
Model (Django ORM, SQLite)
```

---

## Seven Core Epics

| Epic | Feature | Key Files |
|------|---------|-----------|
| 1 | Custom User model (email login, role field) | `accounts/models.py` |
| 2 | Auth flows: register, login, password reset, profile, admin CRUD | `accounts/views.py`, `accounts/decorators.py` |
| 3 | Gym Equipment CRUD with category + search | `gym/models.py`, `gym/views.py` |
| 4 | Workout Classes CRUD with category + text search | `gym/views.py`, `gym/forms.py` |
| 5 | Category management | `gym/models.py` (WorkoutCategory) |
| 6 | Booking state machine (Booked, Cancelled, Attended, Missed) | `bookings/models.py`, `bookings/services.py` |
| 7 | Personal Fitness Tracker: sessions, exercises, sets, routines, progress | `tracker/` |

### Change Request (CR) Partial Implementations

| CR | Feature | Status |
|----|---------|--------|
| CR1 | Advanced search filters (date range, availability) | Partial – in `gym/forms.py` (ClassSearchForm) |
| CR2 | Smart ranking (availability ratio, view count, featured flag) | Partial – `_smart_score()` in `gym/views.py` |
| CR3 | Featured/promoted classes on dashboard | Partial – `is_featured` field, dashboard filter |
| CR4 | Ratings/reviews | Deferred (design notes in report) |

---

## Security Controls Demonstrated

- Passwords hashed via Django's built-in PBKDF2 (NFR-01)
- All routes behind `@login_required` or `@admin_required` (NFR-02)
- CSRF tokens on all POST forms (NFR-03)
- Server-side form validation throughout
- `@require_POST` on all state-changing endpoints
- `assert_transition()` rejects illegal state changes (NFR-06)
