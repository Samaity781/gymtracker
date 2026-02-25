"""
tests/test_tracker.py
Epic 7: Personal Fitness Tracker — model constraints and progress service.
"""

from datetime import date, time
from django.test import TestCase

from accounts.models import User
from tracker.models import WorkoutSession, WorkoutEntry, SetEntry, Routine, RoutineItem
from tracker import services


def make_user(email='tracker@test.com'):
    return User.objects.create_user(email=email, password='Pass123!')


def make_session(user, name='Leg Day', d=None):
    return WorkoutSession.objects.create(user=user, name=name, date=d or date.today())


def make_entry(session, exercise='Squat'):
    return WorkoutEntry.objects.create(session=session, exercise_name=exercise)


def make_set(entry, reps=5, weight_kg=100.0, is_warmup=False):
    count = entry.sets.count()
    return SetEntry.objects.create(
        entry=entry,
        set_number=count + 1,
        reps=reps,
        weight_kg=weight_kg,
        is_warmup=is_warmup,
    )


class SetEntryValidationTests(TestCase):
    """FR-15: reps >= 1, weight >= 0."""

    def setUp(self):
        self.user = make_user()
        self.session = make_session(self.user)
        self.entry = make_entry(self.session)

    def test_valid_set_saves(self):
        s = make_set(self.entry, reps=3, weight_kg=60)
        self.assertEqual(s.reps, 3)
        self.assertEqual(float(s.weight_kg), 60.0)

    def test_zero_weight_is_valid(self):
        s = make_set(self.entry, reps=1, weight_kg=0)
        self.assertEqual(float(s.weight_kg), 0.0)

    def test_volume_property(self):
        s = make_set(self.entry, reps=5, weight_kg=100)
        self.assertAlmostEqual(s.volume, 500.0)


class WorkoutSessionTests(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_total_volume_kg_is_zero_for_empty_session(self):
        session = make_session(self.user)
        self.assertEqual(session.total_volume_kg, 0)

    def test_total_volume_kg_sums_across_entries(self):
        session = make_session(self.user)
        e1 = make_entry(session, 'Bench Press')
        e2 = make_entry(session, 'Squat')
        make_set(e1, reps=5, weight_kg=80)   # 400
        make_set(e1, reps=5, weight_kg=80)   # 400
        make_set(e2, reps=3, weight_kg=120)  # 360
        self.assertAlmostEqual(session.total_volume_kg, 1160.0)

    def test_duration_minutes_calculated_correctly(self):
        session = WorkoutSession(
            user=self.user,
            date=date.today(),
            start_time=time(9, 0),
            end_time=time(10, 30),
        )
        self.assertEqual(session.duration_minutes, 90)


class ProgressServiceTests(TestCase):

    def setUp(self):
        self.user = make_user()

    def _build_session(self, exercise, weight, d):
        s = make_session(self.user, d=d)
        e = make_entry(s, exercise)
        make_set(e, reps=5, weight_kg=weight)
        return s

    def test_get_personal_records_returns_max_weight(self):
        self._build_session('Deadlift', 100, date(2025, 1, 1))
        self._build_session('Deadlift', 150, date(2025, 2, 1))
        self._build_session('Deadlift', 130, date(2025, 3, 1))
        records = services.get_personal_records(self.user)
        self.assertIn('Deadlift', records)
        self.assertAlmostEqual(records['Deadlift']['max_weight_kg'], 150.0)

    def test_get_personal_records_ignores_warmup_sets(self):
        s = make_session(self.user, d=date(2025, 1, 1))
        e = make_entry(s, 'Press')
        make_set(e, reps=10, weight_kg=20, is_warmup=True)  # Should be ignored
        make_set(e, reps=5, weight_kg=60, is_warmup=False)
        records = services.get_personal_records(self.user)
        self.assertAlmostEqual(records['Press']['max_weight_kg'], 60.0)

    def test_get_volume_over_time_returns_one_entry_per_session(self):
        self._build_session('Squat', 80, date(2025, 1, 1))
        self._build_session('Squat', 90, date(2025, 2, 1))
        result = services.get_volume_over_time(self.user)
        self.assertEqual(len(result), 2)

    def test_get_workout_summary_counts_sessions(self):
        self._build_session('Row', 50, date(2025, 1, 5))
        self._build_session('Row', 55, date(2025, 1, 10))
        summary = services.get_workout_summary(self.user)
        self.assertEqual(summary['total_sessions'], 2)
