"""
tests/test_booking_state_machine.py
Unit tests for the booking state machine (Epic 6, NFR-06).

These tests do not require the Django HTTP stack — they test the model
and service layer in isolation, which aligns with the module's emphasis
on testable, isolated business logic (NFR-09, NFR-12).
"""

from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from bookings.models import Booking
from bookings import services
from gym.models import WorkoutClass, WorkoutCategory


def make_user(email, role=User.Role.MEMBER):
    return User.objects.create_user(email=email, password='TestPass123!', role=role)


def make_upcoming_class(capacity=10, minutes_from_now=60):
    cat = WorkoutCategory.objects.first() or WorkoutCategory.objects.create(name='General')
    return WorkoutClass.objects.create(
        name='Test Spin',
        category=cat,
        start_time=timezone.now() + timedelta(minutes=minutes_from_now),
        capacity=capacity,
    )


class BookingTransitionModelTests(TestCase):
    """Verify the transition table on the Booking model."""

    def test_booked_can_transition_to_cancelled(self):
        booking = Booking(status=Booking.Status.BOOKED)
        self.assertTrue(booking.can_transition_to(Booking.Status.CANCELLED))

    def test_booked_can_transition_to_attended(self):
        booking = Booking(status=Booking.Status.BOOKED)
        self.assertTrue(booking.can_transition_to(Booking.Status.ATTENDED))

    def test_booked_can_transition_to_missed(self):
        booking = Booking(status=Booking.Status.BOOKED)
        self.assertTrue(booking.can_transition_to(Booking.Status.MISSED))

    def test_cancelled_is_terminal(self):
        booking = Booking(status=Booking.Status.CANCELLED)
        self.assertFalse(booking.can_transition_to(Booking.Status.BOOKED))
        self.assertFalse(booking.can_transition_to(Booking.Status.ATTENDED))

    def test_attended_is_terminal(self):
        booking = Booking(status=Booking.Status.ATTENDED)
        self.assertFalse(booking.can_transition_to(Booking.Status.CANCELLED))

    def test_missed_is_terminal(self):
        booking = Booking(status=Booking.Status.MISSED)
        self.assertFalse(booking.can_transition_to(Booking.Status.ATTENDED))

    def test_assert_transition_raises_on_invalid(self):
        booking = Booking(status=Booking.Status.CANCELLED)
        with self.assertRaises(ValueError):
            booking.assert_transition(Booking.Status.ATTENDED)

    def test_assert_transition_does_not_raise_on_valid(self):
        booking = Booking(status=Booking.Status.BOOKED)
        # Should not raise
        booking.assert_transition(Booking.Status.CANCELLED)


class BookingServiceTests(TestCase):
    """Integration tests for the booking service layer."""

    def setUp(self):
        self.member = make_user('member@test.com')
        self.admin = make_user('admin@test.com', role=User.Role.ADMIN)
        self.wc = make_upcoming_class(capacity=2)

    # ── book_class ─────────────────────────────────────────────────────────────

    def test_book_class_creates_booked_booking(self):
        booking = services.book_class(self.member, self.wc)
        self.assertEqual(booking.status, Booking.Status.BOOKED)
        self.assertEqual(booking.user, self.member)

    def test_book_class_decrements_available_spaces(self):
        services.book_class(self.member, self.wc)
        self.wc.refresh_from_db()
        self.assertEqual(self.wc.booked_count, 1)

    def test_book_class_prevents_duplicate_active_booking(self):
        services.book_class(self.member, self.wc)
        with self.assertRaises(ValueError):
            services.book_class(self.member, self.wc)

    def test_book_class_respects_capacity(self):
        user2 = make_user('user2@test.com')
        services.book_class(self.member, self.wc)
        services.book_class(user2, self.wc)
        # Class is now full (capacity = 2)
        user3 = make_user('user3@test.com')
        with self.assertRaises(ValueError):
            services.book_class(user3, self.wc)

    def test_cannot_book_past_class(self):
        past_class = make_upcoming_class(minutes_from_now=-60)
        with self.assertRaises(ValueError):
            services.book_class(self.member, past_class)

    def test_cannot_book_inactive_class(self):
        self.wc.is_active = False
        self.wc.save()
        with self.assertRaises(ValueError):
            services.book_class(self.member, self.wc)

    # ── cancel_booking ─────────────────────────────────────────────────────────

    def test_cancel_booking_changes_status_to_cancelled(self):
        booking = services.book_class(self.member, self.wc)
        updated = services.cancel_booking(booking, cancelled_by=self.member)
        self.assertEqual(updated.status, Booking.Status.CANCELLED)

    def test_cancel_booking_restores_capacity(self):
        booking = services.book_class(self.member, self.wc)
        self.wc.refresh_from_db()
        count_before = self.wc.booked_count
        services.cancel_booking(booking, cancelled_by=self.member)
        self.wc.refresh_from_db()
        self.assertEqual(self.wc.booked_count, count_before - 1)

    def test_cannot_cancel_already_cancelled_booking(self):
        booking = services.book_class(self.member, self.wc)
        services.cancel_booking(booking, cancelled_by=self.member)
        with self.assertRaises(ValueError):
            services.cancel_booking(booking, cancelled_by=self.member)

    # ── mark_booking ───────────────────────────────────────────────────────────

    def test_admin_can_mark_attended(self):
        booking = services.book_class(self.member, self.wc)
        updated = services.mark_booking(booking, Booking.Status.ATTENDED, self.admin)
        self.assertEqual(updated.status, Booking.Status.ATTENDED)
        self.assertEqual(updated.status_changed_by, self.admin)

    def test_admin_can_mark_missed(self):
        booking = services.book_class(self.member, self.wc)
        updated = services.mark_booking(booking, Booking.Status.MISSED, self.admin)
        self.assertEqual(updated.status, Booking.Status.MISSED)

    def test_cannot_mark_attended_twice(self):
        booking = services.book_class(self.member, self.wc)
        services.mark_booking(booking, Booking.Status.ATTENDED, self.admin)
        with self.assertRaises(ValueError):
            services.mark_booking(booking, Booking.Status.ATTENDED, self.admin)

    def test_mark_booking_rejects_invalid_status(self):
        booking = services.book_class(self.member, self.wc)
        with self.assertRaises(ValueError):
            services.mark_booking(booking, 'BOOKED', self.admin)  # Can't mark BOOKED
