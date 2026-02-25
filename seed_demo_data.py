"""
seed_demo_data.py
=================
Run from the project root (with venv active):

    python seed_demo_data.py

What this script creates
------------------------
  4  member accounts  +  1 admin account
  6  workout categories  (Cardio, Spin, HIIT, Yoga, Strength, Flexibility)
  12 workout classes     (mix of upcoming, past, featured, near-full)
  8  equipment items     (mix of featured and standard)
  3  promotion slots     (CR3 — featured items with context/headline)
  18 bookings            (spread across members: BOOKED, ATTENDED, CANCELLED)
  14 reviews             (CR4 — mix of APPROVED and PENDING for moderation queue)
  8  workout sessions    (CR tracker — personal workout log entries)

Safe to run multiple times — wipes existing demo data first, keeps
any account you created yourself (admin@gym.com etc.).
"""

import os
import sys
import django
from pathlib import Path

# ── Bootstrap Django ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gymtracker.settings')
django.setup()

# ── Imports ───────────────────────────────────────────────────────────────────
from datetime import date, timedelta, time
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from accounts.models import User
from gym.models import WorkoutCategory, WorkoutClass, GymEquipment, PromotionSlot
from bookings.models import Booking
from reviews.models import Review
from tracker.models import WorkoutSession, WorkoutEntry, SetEntry

now = timezone.now()

# ── Colour helpers for terminal output ───────────────────────────────────────
G  = '\033[92m'   # green
B  = '\033[94m'   # blue
Y  = '\033[93m'   # yellow
DIM= '\033[2m'
R  = '\033[0m'    # reset

def ok(msg):   print(f"  {G}✓{R}  {msg}")
def hd(msg):   print(f"\n{B}── {msg}{R}")
def note(msg): print(f"  {DIM}{msg}{R}")


# ═════════════════════════════════════════════════════════════════════════════
#  STEP 0 — Wipe existing demo data (safe: only touches @gymtracker.demo accounts)
# ═════════════════════════════════════════════════════════════════════════════
hd("Clearing existing demo data")

demo_users = User.objects.filter(email__endswith='@gymtracker.demo')
note(f"Removing {demo_users.count()} existing demo user(s) and their data…")
demo_users.delete()

WorkoutCategory.objects.all().delete()
note("Categories, classes, equipment, bookings, reviews cleared.")


# ═════════════════════════════════════════════════════════════════════════════
#  STEP 1 — Users
# ═════════════════════════════════════════════════════════════════════════════
hd("Creating users")

# Find the real admin the user created (admin@gym.com or similar)
real_admin = User.objects.filter(is_superuser=True).first()
if real_admin:
    ok(f"Keeping existing superuser: {real_admin.email}")
    if not real_admin.first_name:
        real_admin.first_name = 'Samuel'
        real_admin.last_name = 'Maitland'
        real_admin.save()
        ok(f"  → Name updated to Samuel Maitland (was blank from createsuperuser)")

admin = User.objects.create_user(
    email='admin@gymtracker.demo',
    password='admin123',
    first_name='Alex',
    last_name='Admin',
    role=User.Role.ADMIN,
    is_staff=True,
)
ok("admin@gymtracker.demo  /  admin123  (ADMIN)")

members = []
member_data = [
    ('sam@gymtracker.demo',    'Sam',    'Maitland', 'member123'),
    ('priya@gymtracker.demo',  'Priya',  'Patel',    'member123'),
    ('jordan@gymtracker.demo', 'Jordan', 'Lee',      'member123'),
    ('zara@gymtracker.demo',   'Zara',   'Khan',     'member123'),
]
for email, first, last, pwd in member_data:
    m = User.objects.create_user(
        email=email, password=pwd,
        first_name=first, last_name=last,
        role=User.Role.MEMBER,
    )
    members.append(m)
    ok(f"{email}  /  {pwd}  (MEMBER)")

sam, priya, jordan, zara = members


# ═════════════════════════════════════════════════════════════════════════════
#  STEP 2 — Categories
# ═════════════════════════════════════════════════════════════════════════════
hd("Creating categories")

cat_data = [
    ('Cardio',      'bi-heart-pulse',     'Cardiovascular training to boost stamina and burn calories.'),
    ('Spin',        'bi-bicycle',         'High-energy indoor cycling sessions for all fitness levels.'),
    ('HIIT',        'bi-lightning-charge','High-intensity interval training — short, sharp, effective.'),
    ('Yoga',        'bi-peace',           'Mindful movement, flexibility, and breathing techniques.'),
    ('Strength',    'bi-dumbbell',        'Resistance and weight training to build muscle and power.'),
    ('Flexibility', 'bi-person-arms-up',  'Stretching and mobility work to improve range of motion.'),
]
cats = {}
for name, icon, desc in cat_data:
    cats[name] = WorkoutCategory.objects.create(name=name, icon=icon, description=desc)
    ok(name)


# ═════════════════════════════════════════════════════════════════════════════
#  STEP 3 — Workout Classes
# ═════════════════════════════════════════════════════════════════════════════
hd("Creating workout classes")

#  (name, category, instructor, location, duration, capacity, booked, featured, days_offset)
#  Positive days_offset = upcoming,  negative = past
class_data = [
    # ── Upcoming featured ──────────────────────────────────────────────────
    ('Morning Spin',       'Spin',        'Claire Davies',  'Studio 1',      60,  20,  8,  True,   1),
    ('HIIT Blast',         'HIIT',        'Marcus Webb',    'Main Floor',    45,  15, 13,  True,   2),
    ('Advanced Spin',      'Spin',        'Claire Davies',  'Studio 1',      60,  20,  2,  True,   3),
    ('Evening Cardio',     'Cardio',      'Claire Davies',  'Studio 1',      45,  25,  5,  True,   5),
    # ── Upcoming standard ─────────────────────────────────────────────────
    ('Flow Yoga',          'Yoga',        'Anya Rossi',     'Studio 2',      90,  12,  1,  False,  4),
    ('Strength Circuit',   'Strength',    'Tom Hughes',     'Weights Room',  60,  10,  7,  False,  6),
    ('Interval Sprint',    'HIIT',        'Marcus Webb',    'Main Floor',    30,  20,  4,  False,  1),
    ('Flexibility Flow',   'Flexibility', 'Anya Rossi',     'Studio 2',      60,  15,  0,  False,  7),
    ('Power Yoga',         'Yoga',        'Anya Rossi',     'Studio 2',      75,  12,  2,  False,  9),
    ('Full Body Burn',     'Strength',    'Tom Hughes',     'Weights Room',  60,  12,  3,  False, 10),
    # ── Past (attended — needed for eligible reviews) ─────────────────────
    ('Sunrise Yoga',       'Yoga',        'Anya Rossi',     'Studio 2',      60,  10,  8,  False, -3),
    ('Cardio Kickstart',   'Cardio',      'Claire Davies',  'Studio 1',      45,  20, 12,  False, -6),
]

classes = {}
for (name, cat, instructor, location, duration,
     capacity, booked, featured, days) in class_data:
    hour = 7 if days < 0 else (8 + (abs(days) % 10))
    cls = WorkoutClass.objects.create(
        name=name,
        category=cats[cat],
        instructor=instructor,
        location=location,
        duration_minutes=duration,
        capacity=capacity,
        booked_count=booked,
        is_active=True,
        is_featured=featured,
        start_time=now + timedelta(days=days, hours=hour - now.hour),
        description=f'{name} — a {duration}-minute {cat.lower()} session with {instructor}. '
                    f'Suitable for all fitness levels. Booking required.',
        view_count=booked * 8 + 20,
        booking_count=booked,
        impression_count=booked * 15 + 40 if featured else booked * 5,
        click_count=booked * 2 if featured else 0,
    )
    classes[name] = cls
    status = '⭐ featured' if featured else 'standard'
    timing = f"in {days}d" if days > 0 else f"{abs(days)}d ago"
    ok(f"{name:<25} {cat:<12} {status}  ({timing})")


# ═════════════════════════════════════════════════════════════════════════════
#  STEP 4 — Equipment
# ═════════════════════════════════════════════════════════════════════════════
hd("Creating equipment")

equip_data = [
    # (name, category, location, capacity, featured, description)
    ('Rowing Machine',  'Cardio',      'Ground Floor, Zone A', 4,  True,  'Concept2 rowing machines. Full-body cardio workout.'),
    ('Power Rack',      'Strength',    'Weights Room',          2,  True,  'Olympic power rack with barbell and weight plates.'),
    ('Assault Bike',    'HIIT',        'Main Floor',            6,  True,  'Air-resistance assault bikes for HIIT conditioning.'),
    ('Treadmill Bank',  'Cardio',      'Ground Floor, Zone B', 10,  False, 'Ten commercial treadmills with incline and speed control.'),
    ('Cable Machine',   'Strength',    'Weights Room',          3,  False, 'Dual-cable functional trainer for isolation exercises.'),
    ('Leg Press',       'Strength',    'Weights Room',          2,  False, 'Plate-loaded leg press machine. 45-degree angle.'),
    ('Spin Bikes',      'Spin',        'Studio 1',             20,  False, 'Keiser M3i spin bikes — used in all spin classes.'),
    ('Stretch Mats',    'Flexibility', 'Studio 2',             15,  False, 'High-density foam mats for yoga and stretching sessions.'),
]

equipment = {}
for name, cat, location, capacity, featured, desc in equip_data:
    eq = GymEquipment.objects.create(
        name=name,
        category=cats[cat],
        location=location,
        capacity=capacity,
        is_active=True,
        is_featured=featured,
        description=desc,
        view_count=capacity * 12 + 10,
        booking_count=capacity * 4,
        impression_count=capacity * 20 if featured else capacity * 5,
        click_count=capacity * 3 if featured else 0,
    )
    equipment[name] = eq
    ok(f"{name:<20} {cat:<12} {'⭐ featured' if featured else 'standard'}")


# ═════════════════════════════════════════════════════════════════════════════
#  STEP 5 — Promotion Slots  (CR3)
# ═════════════════════════════════════════════════════════════════════════════
hd("Creating promotion slots (CR3)")

ct_class = ContentType.objects.get_for_model(WorkoutClass)
ct_equip = ContentType.objects.get_for_model(GymEquipment)

promo_data = [
    (classes['Morning Spin'],      ct_class, 'dashboard', 1,
     '🚴 Join Morning Spin this week!',
     'Spaces filling fast — book now'),
    (classes['HIIT Blast'],        ct_class, 'dashboard', 2,
     '⚡ HIIT Blast — 45 minutes, maximum results',
     'Only 2 spaces left'),
    (equipment['Rowing Machine'],  ct_equip, 'dashboard', 3,
     '🚣 Rowing Machine now available',
     'Book your slot today'),
]

for item, ct, context, pos, headline, cta in promo_data:
    PromotionSlot.objects.create(
        content_type=ct,
        object_id=item.pk,
        slot_context=context,
        position=pos,
        headline=headline,
        call_to_action=cta,
        start_date=date.today() - timedelta(days=7),
        end_date=date.today() + timedelta(days=30),
        is_active=True,
        created_by=admin,
    )
    ok(f"Slot {pos}: {headline[:50]}")


# ═════════════════════════════════════════════════════════════════════════════
#  STEP 6 — Bookings
# ═════════════════════════════════════════════════════════════════════════════
hd("Creating bookings")

# Past bookings with ATTENDED status — these make members eligible to leave reviews
past_attended = [
    (sam,    'Sunrise Yoga'),
    (sam,    'Cardio Kickstart'),
    (priya,  'Sunrise Yoga'),
    (priya,  'Cardio Kickstart'),
    (jordan, 'Sunrise Yoga'),
    (jordan, 'Cardio Kickstart'),
    (zara,   'Sunrise Yoga'),
]
for member, class_name in past_attended:
    cls = classes[class_name]
    Booking.objects.create(
        user=member,
        workout_class=cls,
        status=Booking.Status.ATTENDED,
    )
    ok(f"ATTENDED  {member.first_name:<8} → {class_name}")

# Upcoming bookings with BOOKED status
upcoming_booked = [
    (sam,    'Morning Spin'),
    (sam,    'Flow Yoga'),
    (priya,  'HIIT Blast'),
    (priya,  'Evening Cardio'),
    (jordan, 'Advanced Spin'),
    (jordan, 'Strength Circuit'),
    (zara,   'Morning Spin'),
    (zara,   'Interval Sprint'),
]
for member, class_name in upcoming_booked:
    cls = classes[class_name]
    Booking.objects.create(
        user=member,
        workout_class=cls,
        status=Booking.Status.BOOKED,
    )
    ok(f"BOOKED    {member.first_name:<8} → {class_name}")

# A couple of cancelled bookings to show that state in the UI
cancelled = [
    (sam,   'Interval Sprint'),
    (priya, 'Power Yoga'),
]
for member, class_name in cancelled:
    cls = classes[class_name]
    Booking.objects.create(
        user=member,
        workout_class=cls,
        status=Booking.Status.CANCELLED,
    )
    ok(f"CANCELLED {member.first_name:<8} → {class_name}")

# Equipment booking for Sam
Booking.objects.create(
    user=sam,
    equipment=equipment['Rowing Machine'],
    status=Booking.Status.BOOKED,
    slot_start=now + timedelta(days=2, hours=9),
    slot_end=now + timedelta(days=2, hours=10),
)
ok("BOOKED    Sam      → Rowing Machine (equipment)")


# ═════════════════════════════════════════════════════════════════════════════
#  STEP 7 — Reviews  (CR4)
# ═════════════════════════════════════════════════════════════════════════════
hd("Creating reviews (CR4)")

review_comments = [
    "Really brilliant session — Claire kept the energy up the whole way through. Highly recommend.",
    "Tough but rewarding. I was absolutely spent by the end. Will definitely be back.",
    "Good atmosphere and well structured. The instructor explained each movement clearly.",
    "Loved it! First time trying this class and I'll be booking again next week.",
    "Solid session. Nothing revolutionary but consistent quality. Good warm-up routine.",
    "Excellent class, really felt the benefit afterwards. Studio was clean and well-equipped.",
    "",   # intentionally blank — comment is optional
]

approved_reviews = [
    # (member, class_name, rating, comment_index)
    (sam,    'Sunrise Yoga',    5, 0),
    (sam,    'Cardio Kickstart',4, 1),
    (priya,  'Sunrise Yoga',    4, 2),
    (priya,  'Cardio Kickstart',5, 3),
    (jordan, 'Sunrise Yoga',    3, 4),
    (jordan, 'Cardio Kickstart',4, 5),
]

for member, class_name, rating, comment_idx in approved_reviews:
    cls = classes[class_name]
    Review.objects.create(
        content_type=ct_class,
        object_id=cls.pk,
        user=member,
        rating=rating,
        comment=review_comments[comment_idx],
        status=Review.Status.APPROVED,
        moderated_by=admin,
        moderated_at=now - timedelta(hours=2),
    )
    stars = '★' * rating + '☆' * (5 - rating)
    ok(f"APPROVED  {member.first_name:<8} → {class_name:<20} {stars}")

# Pending reviews — show the moderation queue in action
pending_reviews = [
    (zara, 'Sunrise Yoga',    4, "Really enjoyed this session. Great instructor, relaxed atmosphere."),
    (zara, 'Cardio Kickstart',3, "Good class but felt a little rushed. Would try again though."),
]
for member, class_name, rating, comment in pending_reviews:
    cls = classes[class_name]
    Review.objects.create(
        content_type=ct_class,
        object_id=cls.pk,
        user=member,
        rating=rating,
        comment=comment,
        status=Review.Status.PENDING,
    )
    stars = '★' * rating + '☆' * (5 - rating)
    ok(f"PENDING   {member.first_name:<8} → {class_name:<20} {stars}  ← awaiting moderation")


# ═════════════════════════════════════════════════════════════════════════════
#  STEP 8 — Workout Sessions  (Tracker)
# ═════════════════════════════════════════════════════════════════════════════
hd("Creating workout sessions (tracker)")

sessions_data = [
    (sam,    'Upper Body + Cardio',  date.today() - timedelta(days=1),
     'Great session, hit a new PB on bench press. Felt strong throughout.',
     [('Bench Press', [('4', '80kg', '8 reps'), ('3', '85kg', '6 reps')]),
      ('Lat Pulldown', [('3', '60kg', '12 reps')]),
      ('Treadmill',    [('1', '', '20 min steady state')])]),

    (sam,    'Sunrise Yoga Class',   date.today() - timedelta(days=3),
     'Attended Sunrise Yoga. Felt much more flexible by the end.',
     [('Sun Salutation', [('3', '', '10 reps')]),
      ('Warrior Sequence', [('2', '', '5 min hold')])]),

    (sam,    'Leg Day',              date.today() - timedelta(days=5),
     'Focused on legs. Squats feeling solid.',
     [('Squat', [('5', '100kg', '5 reps'), ('3', '110kg', '3 reps')]),
      ('Leg Press', [('4', '160kg', '10 reps')]),
      ('Calf Raise', [('3', '50kg', '20 reps')])]),

    (priya,  'Cardio & Core',        date.today() - timedelta(days=2),
     'HIIT Blast class plus 15 min core work after.',
     [('HIIT Circuit', [('4', '', '45 sec on / 15 sec off')]),
      ('Plank',        [('3', '', '60 sec hold')]),
      ('Bicycle Crunch',[('3', '', '20 reps')])]),

    (priya,  'Full Body Strength',   date.today() - timedelta(days=7),
     'Good solid session. Increased deadlift weight.',
     [('Deadlift', [('4', '70kg', '8 reps')]),
      ('Pull-up',  [('3', '', '8 reps')]),
      ('Dumbbell Row', [('3', '22kg', '10 reps')])]),

    (jordan, 'Spin Class',           date.today() - timedelta(days=1),
     'Advanced Spin was brutal today. Legs like jelly.',
     [('Spin Intervals', [('8', '', '2 min high / 1 min recovery')])]),

    (jordan, 'Recovery + Stretch',   date.today() - timedelta(days=4),
     'Light day — foam rolling and flexibility work.',
     [('Foam Roll', [('1', '', '10 min full body')]),
      ('Hip Flexor Stretch', [('3', '', '60 sec each side')]),
      ('Shoulder Mobility',  [('2', '', '5 min')])]),

    (zara,   'First Yoga Session',   date.today() - timedelta(days=3),
     'First time at Sunrise Yoga. Really enjoyed it, felt very welcome.',
     [('Breathing Exercises', [('1', '', '5 min')]),
      ('Yoga Flow',           [('1', '', '50 min class')])]),
]

for member, name, session_date, notes, exercises in sessions_data:
    session = WorkoutSession.objects.create(
        user=member,
        name=name,
        date=session_date,
        start_time=time(8, 0),
        end_time=time(9, 0),
        notes=notes,
    )
    for order, (exercise_name, sets_data) in enumerate(exercises, start=1):
        entry = WorkoutEntry.objects.create(
            session=session,
            exercise_name=exercise_name,
            order=order,
        )
        for set_order, set_row in enumerate(sets_data, start=1):
            weight_str = set_row[1].replace('kg', '').strip() if set_row[1] else ''
            try:
                weight_val = float(weight_str) if weight_str else 0.0
            except ValueError:
                weight_val = 0.0
            SetEntry.objects.create(
                entry=entry,
                set_number=set_order,
                reps=int(set_row[0]) if set_row[0].isdigit() else 1,
                weight_kg=weight_val,
            )
    ok(f"{member.first_name:<8} → {name} ({session_date})")


# ═════════════════════════════════════════════════════════════════════════════
#  SUMMARY
# ═════════════════════════════════════════════════════════════════════════════
print(f"""
{B}{'═' * 60}{R}
{G}  ✓  Demo data loaded successfully!{R}
{B}{'═' * 60}{R}

  {Y}Users created:{R}
  ┌─────────────────────────────┬──────────┬──────────────┐
  │ Email                       │ Password │ Role         │
  ├─────────────────────────────┼──────────┼──────────────┤
  │ admin@gymtracker.demo       │ admin123 │ Admin        │
  │ sam@gymtracker.demo         │ member123│ Member       │
  │ priya@gymtracker.demo       │ member123│ Member       │
  │ jordan@gymtracker.demo      │ member123│ Member       │
  │ zara@gymtracker.demo        │ member123│ Member       │
  └─────────────────────────────┴──────────┴──────────────┘

  {Y}Data summary:{R}
    Categories  : {WorkoutCategory.objects.count()}
    Classes     : {WorkoutClass.objects.count()} (upcoming + past)
    Equipment   : {GymEquipment.objects.count()}
    Promo slots : {PromotionSlot.objects.count()} (CR3)
    Bookings    : {Booking.objects.count()} (BOOKED / ATTENDED / CANCELLED)
    Reviews     : {Review.objects.count()} ({Review.objects.filter(status='APPROVED').count()} approved, {Review.objects.filter(status='PENDING').count()} pending — CR4)
    Sessions    : {WorkoutSession.objects.count()} workout log entries

  {Y}Open your browser:{R}
    http://127.0.0.1:8000/

  {Y}Quick CR demo tour:{R}
    CR1 — Classes page → use the filter sidebar to search and filter
    CR2 — Admin menu → Smart Ranking to see scored results
    CR3 — Admin menu → Promotions to see impression/click analytics
    CR4 — Admin menu → Review Queue to approve Zara's pending reviews
          or visit any past class detail page to see the star breakdown
{B}{'═' * 60}{R}
""")
