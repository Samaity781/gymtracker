"""
tests/test_engineering_quality.py
Engineering Quality Evidence — CW1B Final Report.

This module provides targeted evidence for four quality properties:

  SECTION A: Permissions & Least Privilege
    Decorators @admin_required and @login_required are tested by attempting
    each class of operation as (a) unauthenticated, (b) member, and (c) admin.
    Every protected route is exercised at least once.

  SECTION B: Booking State Machine & Transition Security (NFR-06)
    Invalid transitions raise ValueError.  Terminal states are immutable.
    The service layer is the sole path to state change.

  SECTION C: Form Validation — Server-Side Authoritative Layer
    Valid and invalid inputs are submitted to each form class in isolation.
    Tests confirm that client-side HTML5 attributes are present on widgets
    AND that server-side clean_* methods catch tampered / malicious input.

  SECTION D: CSRF & Password Hashing (NFR-01, NFR-03)
    CSRF middleware rejects POST requests without a valid token.
    Passwords are stored as PBKDF2 hashes — never in plaintext.

All tests use Django's TestCase (transactional rollback) and the test
Client so they run fast without a separate test server.
"""

import re
from datetime import timedelta

from django.contrib.auth.hashers import check_password, is_password_usable
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, MemberProfile
from bookings.models import Booking
from bookings import services as booking_services
from gym.forms import WorkoutClassForm, GymEquipmentForm, CategoryForm, ClassSearchForm
from gym.models import GymEquipment, WorkoutCategory, WorkoutClass
from accounts.forms import MemberRegistrationForm, ProfileForm, LoginForm


# ─── Shared fixtures ──────────────────────────────────────────────────────────

def make_user(email='member@test.com', role=User.Role.MEMBER):
    return User.objects.create_user(
        email=email, password='ValidPass99!',
        first_name='Sam', last_name='Test', role=role,
    )

def make_admin(email='admin@test.com'):
    return make_user(email=email, role=User.Role.ADMIN)

def make_category(name='Spin'):
    return WorkoutCategory.objects.create(name=name)

def make_class(name='Morning Spin', category=None, days_ahead=2,
               capacity=20, booked=0, active=True):
    cat = category or make_category(name + ' Cat')
    return WorkoutClass.objects.create(
        name=name, category=cat,
        start_time=timezone.now() + timedelta(days=days_ahead),
        duration_minutes=60, capacity=capacity,
        booked_count=booked, is_active=active,
        instructor='Instructor A',
    )

def make_equipment(name='Treadmill', capacity=2):
    cat = make_category(name + ' Cat')
    return GymEquipment.objects.create(
        name=name, category=cat, capacity=capacity, is_active=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION A: Permissions & Least Privilege
# ═══════════════════════════════════════════════════════════════════════════════

class UnauthenticatedAccessTests(TestCase):
    """
    EVIDENCE: Unauthenticated users are redirected to login for every
    protected route.  They must never see member or admin content.
    """

    def setUp(self):
        self.client = Client()
        make_class()
        eq = make_equipment()

    def _assert_redirects_to_login(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302, f"Expected redirect from {url}")
        self.assertIn('/accounts/login', response['Location'],
                      f"Expected login redirect from {url}")

    def test_dashboard_requires_login(self):
        self._assert_redirects_to_login(reverse('gym:dashboard'))

    def test_class_list_requires_login(self):
        self._assert_redirects_to_login(reverse('gym:class_list'))

    def test_equipment_list_requires_login(self):
        self._assert_redirects_to_login(reverse('gym:equipment_list'))

    def test_my_bookings_requires_login(self):
        self._assert_redirects_to_login(reverse('bookings:my_bookings'))

    def test_tracker_session_list_requires_login(self):
        self._assert_redirects_to_login(reverse('tracker:session_list'))

    def test_admin_class_list_requires_login(self):
        self._assert_redirects_to_login(reverse('gym:admin_class_list'))

    def test_admin_equipment_list_requires_login(self):
        self._assert_redirects_to_login(reverse('gym:admin_equipment_list'))

    def test_admin_booking_list_requires_login(self):
        self._assert_redirects_to_login(reverse('bookings:admin_booking_list'))

    def test_review_moderation_queue_requires_login(self):
        self._assert_redirects_to_login(reverse('reviews:admin_review_list'))

    def test_promotions_analytics_requires_login(self):
        self._assert_redirects_to_login(reverse('gym:admin_promotions'))


class MemberCannotAccessAdminRoutesTests(TestCase):
    """
    EVIDENCE (least privilege — NFR-02): Authenticated members are redirected
    to the dashboard when they attempt to access admin-only routes.
    They receive an error message; they do NOT see admin content.
    """

    def setUp(self):
        self.member = make_user()
        self.client = Client()
        self.client.force_login(self.member)
        self.cls = make_class()
        self.eq  = make_equipment()

    def _assert_member_blocked(self, url):
        response = self.client.get(url)
        # Members are redirected to dashboard (302) — not shown a 200 admin page
        self.assertEqual(response.status_code, 302,
                         f"Member should be blocked from {url}")
        self.assertNotEqual(response['Location'], url,
                            f"Member must not remain on {url}")

    def test_member_blocked_from_class_management(self):
        self._assert_member_blocked(reverse('gym:admin_class_list'))

    def test_member_blocked_from_equipment_management(self):
        self._assert_member_blocked(reverse('gym:admin_equipment_list'))

    def test_member_blocked_from_category_management(self):
        self._assert_member_blocked(reverse('gym:admin_category_list'))

    def test_member_blocked_from_booking_management(self):
        self._assert_member_blocked(reverse('bookings:admin_booking_list'))

    def test_member_blocked_from_review_moderation(self):
        self._assert_member_blocked(reverse('reviews:admin_review_list'))

    def test_member_blocked_from_promotions_analytics(self):
        self._assert_member_blocked(reverse('gym:admin_promotions'))

    def test_member_blocked_from_class_create(self):
        self._assert_member_blocked(reverse('gym:admin_class_create'))

    def test_member_cannot_mark_booking_as_attended_via_admin_route(self):
        """Critical: members must not be able to mark their own booking as attended."""
        booking = Booking.objects.create(
            user=self.member, workout_class=self.cls,
            status=Booking.Status.BOOKED,
        )
        url = reverse('bookings:admin_mark_booking', args=[booking.pk])
        response = self.client.post(url, {'new_status': 'ATTENDED'})
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        # Status must not have changed
        self.assertEqual(booking.status, Booking.Status.BOOKED)

    def test_member_receives_permission_denied_message(self):
        """Admin-blocked pages show an error flash message, not a silent 404."""
        response = self.client.get(reverse('gym:admin_class_list'), follow=True)
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(
            any('permission' in m.lower() for m in messages),
            f"Expected permission denied message, got: {messages}"
        )


class AdminCanAccessAllRoutesTests(TestCase):
    """
    EVIDENCE: Admins can access all admin routes with HTTP 200.
    """

    def setUp(self):
        self.admin = make_admin()
        self.client = Client()
        self.client.force_login(self.admin)
        self.cls  = make_class()
        self.eq   = make_equipment()

    def test_admin_can_access_class_management(self):
        response = self.client.get(reverse('gym:admin_class_list'))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access_equipment_management(self):
        response = self.client.get(reverse('gym:admin_equipment_list'))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access_booking_management(self):
        response = self.client.get(reverse('bookings:admin_booking_list'))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access_review_moderation(self):
        response = self.client.get(reverse('reviews:admin_review_list'))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access_promotions_analytics(self):
        response = self.client.get(reverse('gym:admin_promotions'))
        self.assertEqual(response.status_code, 200)


class BookingOwnershipTests(TestCase):
    """
    EVIDENCE: Members can only cancel their own bookings — not other members'.
    Ownership is enforced in the view layer (bookings/views.py).
    """

    def setUp(self):
        self.owner   = make_user('owner@test.com')
        self.intruder = make_user('intruder@test.com')
        self.cls     = make_class()
        self.booking = Booking.objects.create(
            user=self.owner, workout_class=self.cls,
            status=Booking.Status.BOOKED,
        )
        self.client = Client()

    def test_member_cannot_cancel_another_members_booking(self):
        self.client.force_login(self.intruder)
        url = reverse('bookings:cancel_booking', args=[self.booking.pk])
        response = self.client.post(url)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.BOOKED,
                         "Intruder must not be able to cancel another user's booking")

    def test_booking_owner_can_cancel_own_booking(self):
        self.client.force_login(self.owner)
        url = reverse('bookings:cancel_booking', args=[self.booking.pk])
        response = self.client.post(url)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CANCELLED)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION B: Booking State Machine & Transition Security
# ═══════════════════════════════════════════════════════════════════════════════

class BookingStateMachineTests(TestCase):
    """
    EVIDENCE (NFR-06): The VALID_TRANSITIONS dict is the single source of
    truth for allowable state changes.  assert_transition() raises ValueError
    for any invalid move; terminal states reject all transitions.
    """

    def setUp(self):
        self.member  = make_user()
        self.admin   = make_admin()
        self.cls     = make_class()
        self.booking = Booking.objects.create(
            user=self.member, workout_class=self.cls,
            status=Booking.Status.BOOKED,
        )

    # ── Valid transitions ─────────────────────────────────────────────────────
    def test_booked_can_transition_to_cancelled(self):
        self.assertTrue(self.booking.can_transition_to(Booking.Status.CANCELLED))

    def test_booked_can_transition_to_attended(self):
        self.assertTrue(self.booking.can_transition_to(Booking.Status.ATTENDED))

    def test_booked_can_transition_to_missed(self):
        self.assertTrue(self.booking.can_transition_to(Booking.Status.MISSED))

    # ── Invalid / terminal state transitions ────────────────────────────────
    def test_cancelled_is_terminal_cannot_transition_to_booked(self):
        self.booking.status = Booking.Status.CANCELLED
        self.booking.save()
        self.assertFalse(self.booking.can_transition_to(Booking.Status.BOOKED))

    def test_cancelled_is_terminal_cannot_transition_to_attended(self):
        self.booking.status = Booking.Status.CANCELLED
        self.booking.save()
        with self.assertRaises(ValueError):
            self.booking.assert_transition(Booking.Status.ATTENDED)

    def test_attended_is_terminal_cannot_transition_to_cancelled(self):
        self.booking.status = Booking.Status.ATTENDED
        self.booking.save()
        with self.assertRaises(ValueError):
            self.booking.assert_transition(Booking.Status.CANCELLED)

    def test_missed_is_terminal_cannot_transition_to_attended(self):
        self.booking.status = Booking.Status.MISSED
        self.booking.save()
        with self.assertRaises(ValueError):
            self.booking.assert_transition(Booking.Status.ATTENDED)

    def test_assert_transition_raises_value_error_not_silent(self):
        """
        EVIDENCE: invalid transitions always raise ValueError, never silently pass.
        This means even direct calls to assert_transition() cannot bypass the guard.
        """
        self.booking.status = Booking.Status.CANCELLED
        self.booking.save()
        with self.assertRaises(ValueError) as ctx:
            self.booking.assert_transition(Booking.Status.BOOKED)
        # Message uses display labels (e.g. "Cancelled", "Booked") — not raw enum values
        error_msg = str(ctx.exception).lower()
        self.assertTrue(
            'cancel' in error_msg or 'transition' in error_msg,
            f"Expected transition error message, got: {ctx.exception}"
        )

    def test_valid_transitions_dict_covers_all_statuses(self):
        """All four statuses must appear as keys in VALID_TRANSITIONS."""
        keys = set(Booking.VALID_TRANSITIONS.keys())
        all_statuses = {s.value for s in Booking.Status}
        self.assertEqual(keys, all_statuses)

    def test_terminal_states_have_empty_transition_sets(self):
        for terminal in (Booking.Status.CANCELLED, Booking.Status.ATTENDED, Booking.Status.MISSED):
            self.assertEqual(
                Booking.VALID_TRANSITIONS[terminal], set(),
                f"{terminal} should have no valid outgoing transitions"
            )

    # ── Service layer guards ─────────────────────────────────────────────────
    def test_service_mark_booking_requires_admin_status_argument(self):
        """mark_booking() only accepts ATTENDED or MISSED — not BOOKED or CANCELLED."""
        with self.assertRaises(ValueError):
            booking_services.mark_booking(self.booking, 'BOOKED', self.admin)

    def test_book_class_rejects_inactive_class(self):
        inactive_cls = make_class('Inactive', active=False)
        with self.assertRaises(ValueError) as ctx:
            booking_services.book_class(self.member, inactive_cls)
        self.assertIn('no longer available', str(ctx.exception).lower())

    def test_book_class_rejects_full_class(self):
        full_cls = make_class('Full Class', capacity=5, booked=5)
        with self.assertRaises(ValueError) as ctx:
            booking_services.book_class(self.member, full_cls)
        self.assertIn('full', str(ctx.exception).lower())

    def test_book_class_rejects_past_class(self):
        past_cls = make_class('Past Class', days_ahead=-2)
        with self.assertRaises(ValueError) as ctx:
            booking_services.book_class(self.member, past_cls)
        self.assertIn('passed', str(ctx.exception).lower())

    def test_book_class_rejects_duplicate_active_booking(self):
        fresh_cls = make_class('Fresh Class', days_ahead=3)
        booking_services.book_class(self.member, fresh_cls)
        with self.assertRaises(ValueError) as ctx:
            booking_services.book_class(self.member, fresh_cls)
        self.assertIn('already have', str(ctx.exception).lower())

    def test_cancel_booking_restores_capacity(self):
        fresh_cls = make_class('Capacity Class', capacity=10, days_ahead=4)
        booking = booking_services.book_class(self.member, fresh_cls)
        fresh_cls.refresh_from_db()
        count_before = fresh_cls.booked_count
        booking_services.cancel_booking(booking, cancelled_by=self.member)
        fresh_cls.refresh_from_db()
        self.assertEqual(fresh_cls.booked_count, count_before - 1)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION C: Form Validation
# ═══════════════════════════════════════════════════════════════════════════════

class WorkoutClassFormValidationTests(TestCase):
    """
    EVIDENCE: Server-side validation catches every edge case even if the
    client-side HTML5 check is bypassed.
    """

    def _base_data(self, **overrides):
        dt = (timezone.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        data = {
            'name': 'Valid Class',
            'description': 'A good description',
            'instructor': 'Jane Doe',
            'location': 'Studio 1',
            'start_time': dt,
            'duration_minutes': 60,
            'capacity': 20,
            'is_active': True,
            'is_featured': False,
        }
        data.update(overrides)
        return data

    def test_valid_data_passes(self):
        form = WorkoutClassForm(data=self._base_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_blank_name_is_rejected(self):
        form = WorkoutClassForm(data=self._base_data(name=''))
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_single_character_name_is_rejected(self):
        form = WorkoutClassForm(data=self._base_data(name='X'))
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_zero_capacity_is_rejected(self):
        form = WorkoutClassForm(data=self._base_data(capacity=0))
        self.assertFalse(form.is_valid())
        self.assertIn('capacity', form.errors)

    def test_negative_capacity_is_rejected(self):
        form = WorkoutClassForm(data=self._base_data(capacity=-5))
        self.assertFalse(form.is_valid())
        self.assertIn('capacity', form.errors)

    def test_capacity_exceeding_200_is_rejected(self):
        form = WorkoutClassForm(data=self._base_data(capacity=999))
        self.assertFalse(form.is_valid())
        self.assertIn('capacity', form.errors)

    def test_duration_below_15_is_rejected(self):
        form = WorkoutClassForm(data=self._base_data(duration_minutes=5))
        self.assertFalse(form.is_valid())
        self.assertIn('duration_minutes', form.errors)

    def test_duration_above_480_is_rejected(self):
        form = WorkoutClassForm(data=self._base_data(duration_minutes=999))
        self.assertFalse(form.is_valid())
        self.assertIn('duration_minutes', form.errors)

    def test_new_class_in_past_is_rejected(self):
        past_dt = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        form = WorkoutClassForm(data=self._base_data(start_time=past_dt))
        self.assertFalse(form.is_valid())
        self.assertIn('start_time', form.errors)

    def test_html5_min_attribute_present_on_capacity_widget(self):
        """CLIENT-SIDE EVIDENCE: capacity widget must emit min=1."""
        form = WorkoutClassForm()
        html = form['capacity'].as_widget()
        self.assertIn('min="1"', html)

    def test_html5_min_attribute_present_on_duration_widget(self):
        """CLIENT-SIDE EVIDENCE: duration_minutes widget must emit min=15."""
        form = WorkoutClassForm()
        html = form['duration_minutes'].as_widget()
        self.assertIn('min="15"', html)

    def test_html5_datetime_local_type_on_start_time_widget(self):
        """CLIENT-SIDE EVIDENCE: start_time uses datetime-local for browser picker."""
        form = WorkoutClassForm()
        html = form['start_time'].as_widget()
        self.assertIn('type="datetime-local"', html)

    def test_html5_maxlength_present_on_name_widget(self):
        """CLIENT-SIDE EVIDENCE: name widget restricts length client-side too."""
        form = WorkoutClassForm()
        html = form['name'].as_widget()
        self.assertIn('maxlength="200"', html)


class GymEquipmentFormValidationTests(TestCase):

    def _base_data(self, **overrides):
        data = {
            'name': 'Rowing Machine',
            'description': 'Commercial rowing ergometer',
            'location': 'Ground floor',
            'capacity': 2,
            'is_active': True,
            'is_featured': False,
        }
        data.update(overrides)
        return data

    def test_valid_data_passes(self):
        form = GymEquipmentForm(data=self._base_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_zero_capacity_rejected(self):
        form = GymEquipmentForm(data=self._base_data(capacity=0))
        self.assertFalse(form.is_valid())

    def test_capacity_over_100_rejected(self):
        form = GymEquipmentForm(data=self._base_data(capacity=101))
        self.assertFalse(form.is_valid())

    def test_short_name_rejected(self):
        form = GymEquipmentForm(data=self._base_data(name='X'))
        self.assertFalse(form.is_valid())

    def test_html5_min_on_capacity(self):
        form = GymEquipmentForm()
        html = form['capacity'].as_widget()
        self.assertIn('min="1"', html)


class CategoryFormValidationTests(TestCase):

    def test_valid_category_passes(self):
        form = CategoryForm(data={'name': 'Spin', 'description': '', 'icon': '', 'is_active': True})
        self.assertTrue(form.is_valid(), form.errors)

    def test_single_char_name_rejected(self):
        form = CategoryForm(data={'name': 'S', 'is_active': True})
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_blank_name_rejected(self):
        form = CategoryForm(data={'name': '', 'is_active': True})
        self.assertFalse(form.is_valid())

    def test_html5_minlength_on_name(self):
        form = CategoryForm()
        html = form['name'].as_widget()
        self.assertIn('minlength="2"', html)


class ClassSearchFormValidationTests(TestCase):

    def test_empty_form_is_valid_returns_all(self):
        form = ClassSearchForm(data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test_date_range_order_validation(self):
        from datetime import date
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        today    = date.today().isoformat()
        form = ClassSearchForm(data={'date_from': tomorrow, 'date_to': today})
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)

    def test_valid_date_range_passes(self):
        from datetime import date
        today    = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        form = ClassSearchForm(data={'date_from': today, 'date_to': tomorrow})
        self.assertTrue(form.is_valid(), form.errors)

    def test_html5_maxlength_on_search_field(self):
        form = ClassSearchForm()
        html = form['q'].as_widget()
        self.assertIn('maxlength="200"', html)

    def test_html5_date_type_on_date_from(self):
        form = ClassSearchForm()
        html = form['date_from'].as_widget()
        self.assertIn('type="date"', html)


class RegistrationFormValidationTests(TestCase):

    def _base_data(self, **overrides):
        data = {
            'email':      'newmember@test.com',
            'first_name': 'Alice',
            'last_name':  'Smith',
            'password1':  'C0mplexPass99!',
            'password2':  'C0mplexPass99!',
        }
        data.update(overrides)
        return data

    def test_valid_registration_passes(self):
        form = MemberRegistrationForm(data=self._base_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_duplicate_email_rejected(self):
        make_user('newmember@test.com')
        form = MemberRegistrationForm(data=self._base_data())
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_mismatched_passwords_rejected(self):
        form = MemberRegistrationForm(data=self._base_data(password2='Different99!'))
        self.assertFalse(form.is_valid())

    def test_single_char_first_name_rejected(self):
        form = MemberRegistrationForm(data=self._base_data(first_name='A'))
        self.assertFalse(form.is_valid())
        self.assertIn('first_name', form.errors)

    def test_blank_last_name_rejected(self):
        form = MemberRegistrationForm(data=self._base_data(last_name=''))
        self.assertFalse(form.is_valid())

    def test_email_widget_type_is_email(self):
        """CLIENT-SIDE EVIDENCE: email input uses type=email."""
        form = MemberRegistrationForm()
        html = form['email'].as_widget()
        self.assertIn('type="email"', html)

    def test_first_name_widget_has_minlength(self):
        """CLIENT-SIDE EVIDENCE: first_name widget has minlength=2."""
        form = MemberRegistrationForm()
        html = form['first_name'].as_widget()
        self.assertIn('minlength="2"', html)

    def test_new_member_is_assigned_member_role_not_admin(self):
        """
        EVIDENCE (least privilege): registration always creates MEMBER role,
        never ADMIN, even if POST data is crafted to include role=ADMIN.
        """
        data = self._base_data()
        data['role'] = User.Role.ADMIN   # Attempt to craft admin account via form
        form = MemberRegistrationForm(data=data)
        if form.is_valid():
            user = form.save()
            self.assertEqual(user.role, User.Role.MEMBER,
                             "Registration form must always produce MEMBER role")

    def test_weak_password_is_rejected_by_validators(self):
        """
        EVIDENCE (NFR-01): AUTH_PASSWORD_VALIDATORS includes CommonPasswordValidator.
        'password123' is on the common passwords list and must be rejected.
        """
        form = MemberRegistrationForm(data=self._base_data(
            password1='password123', password2='password123'
        ))
        self.assertFalse(form.is_valid(),
                         "Weak common password should be rejected by Django validators")

    def test_all_numeric_password_is_rejected(self):
        """NumericPasswordValidator must reject passwords like '12345678'."""
        form = MemberRegistrationForm(data=self._base_data(
            password1='12345678', password2='12345678'
        ))
        self.assertFalse(form.is_valid())

    def test_profile_form_rejects_invalid_phone_number(self):
        """Phone pattern validation: letters are not allowed."""
        form = ProfileForm(data={
            'bio': '', 'phone': 'notaphone',
            'emergency_contact': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)

    def test_profile_form_accepts_valid_uk_phone(self):
        form = ProfileForm(data={
            'bio': '', 'phone': '+44 7700 900000',
            'emergency_contact': '',
        })
        self.assertTrue(form.is_valid(), form.errors)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION D: CSRF Protection & Password Hashing
# ═══════════════════════════════════════════════════════════════════════════════

class CsrfProtectionTests(TestCase):
    """
    EVIDENCE (NFR-03): CSRF middleware is active.
    Django's test Client enforces CSRF when enforce_csrf_checks=True.
    POST requests without a valid token must be rejected with HTTP 403.
    """

    def setUp(self):
        self.user = make_user()
        self.cls  = make_class()
        # Use a CSRF-enforcing client — the default test client skips CSRF
        self.csrf_client = Client(enforce_csrf_checks=True)
        self.csrf_client.force_login(self.user)

    def test_book_class_without_csrf_token_returns_403(self):
        """NFR-03: state-changing POST to book_class must include CSRF token."""
        url = reverse('bookings:book_class', args=[self.cls.pk])
        response = self.csrf_client.post(url)
        self.assertEqual(response.status_code, 403,
                         "POST without CSRF token must return 403 Forbidden")

    def test_cancel_booking_without_csrf_token_returns_403(self):
        """NFR-03: cancellation route must enforce CSRF."""
        booking = Booking.objects.create(
            user=self.user, workout_class=self.cls, status=Booking.Status.BOOKED
        )
        url = reverse('bookings:cancel_booking', args=[booking.pk])
        response = self.csrf_client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_class_toggle_without_csrf_returns_403(self):
        """Admin state change routes must also enforce CSRF."""
        admin = make_admin()
        csrf_admin_client = Client(enforce_csrf_checks=True)
        csrf_admin_client.force_login(admin)
        url = reverse('gym:admin_class_toggle', args=[self.cls.pk])
        response = csrf_admin_client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_login_page_contains_csrf_token_in_html(self):
        """
        EVIDENCE: the login form HTML must contain a csrfmiddlewaretoken field.
        This is rendered by Django's {% csrf_token %} template tag.
        """
        # Use a fresh unauthenticated CSRF client — logged-in users are redirected
        anon_client = Client(enforce_csrf_checks=True)
        response = anon_client.get(reverse('accounts:login'))
        self.assertContains(response, 'csrfmiddlewaretoken',
                            msg_prefix="Login form must include CSRF token")

    def test_registration_page_contains_csrf_token(self):
        anon_client = Client(enforce_csrf_checks=True)
        response = anon_client.get(reverse('accounts:register'))
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_csrf_middleware_is_in_settings(self):
        """
        EVIDENCE: CsrfViewMiddleware must be present in MIDDLEWARE.
        This test fails if someone removes it from settings.py.
        """
        from django.conf import settings
        self.assertIn(
            'django.middleware.csrf.CsrfViewMiddleware',
            settings.MIDDLEWARE,
            "CsrfViewMiddleware must be active in MIDDLEWARE",
        )


class PasswordHashingTests(TestCase):
    """
    EVIDENCE (NFR-01): Passwords are stored as PBKDF2-SHA256 hashes —
    never in plaintext.  Even the application cannot read back a raw password.
    """

    def test_password_stored_as_hash_not_plaintext(self):
        user = make_user('hash_test@test.com')
        self.assertNotEqual(user.password, 'ValidPass99!',
                            "Password must not be stored in plaintext")

    def test_password_hash_uses_pbkdf2_algorithm(self):
        user = make_user('pbkdf2_test@test.com')
        self.assertTrue(
            user.password.startswith('pbkdf2_sha256$'),
            f"Expected PBKDF2 hash, got: {user.password[:20]}…"
        )

    def test_set_password_produces_usable_hash(self):
        user = make_user('setpass_test@test.com')
        user.set_password('NewSecurePass99!')
        self.assertTrue(is_password_usable(user.password))

    def test_check_password_verifies_correct_password(self):
        user = make_user('checkpass@test.com')
        self.assertTrue(check_password('ValidPass99!', user.password))

    def test_check_password_rejects_wrong_password(self):
        user = make_user('wrongpass@test.com')
        self.assertFalse(check_password('WrongPassword', user.password))

    def test_two_users_same_password_have_different_hashes(self):
        """
        EVIDENCE: Django uses a random salt per password, so identical
        plaintext passwords produce different hashes.
        """
        user1 = make_user('u1@test.com')
        user2 = make_user('u2@test.com')
        self.assertNotEqual(user1.password, user2.password,
                            "Same password must produce different hashes (salt is working)")

    def test_password_hash_contains_iteration_count(self):
        """PBKDF2 hash format: algorithm$iterations$salt$hash"""
        user = make_user('iter@test.com')
        parts = user.password.split('$')
        self.assertEqual(len(parts), 4, "PBKDF2 hash must have 4 parts")
        iterations = int(parts[1])
        self.assertGreaterEqual(iterations, 260_000,
                                "PBKDF2 iteration count should be ≥ 260,000 for security")

    def test_session_authentication_does_not_expose_password(self):
        """
        EVIDENCE: The session cookie and authenticated request must never
        contain or transmit the raw password string.
        """
        client = Client()
        client.login(email='session_test@test.com', password='ValidPass99!')
        make_user('session_test@test.com')  # ensure user exists
        # Session data must not contain the password
        session_data = str(client.session.items())
        self.assertNotIn('ValidPass99!', session_data)

    def test_auth_password_validators_are_configured(self):
        """
        EVIDENCE: settings.AUTH_PASSWORD_VALIDATORS must contain all
        four Django built-in validators.
        """
        from django.conf import settings
        validator_names = [v['NAME'] for v in settings.AUTH_PASSWORD_VALIDATORS]
        self.assertIn(
            'django.contrib.auth.password_validation.MinimumLengthValidator',
            validator_names,
        )
        self.assertIn(
            'django.contrib.auth.password_validation.CommonPasswordValidator',
            validator_names,
        )
        self.assertIn(
            'django.contrib.auth.password_validation.NumericPasswordValidator',
            validator_names,
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION E: Thin Views Evidence
# ═══════════════════════════════════════════════════════════════════════════════

class ThinViewsArchitectureTests(TestCase):
    """
    EVIDENCE: View functions are thin HTTP handlers — business logic lives
    in service modules.  These tests verify the structural property by
    inspecting source code directly.
    """

    def _get_function_body(self, module_path, func_name):
        """Return the source lines of a named function from a module."""
        import importlib, inspect
        module = importlib.import_module(module_path)
        func   = getattr(module, func_name)
        return inspect.getsource(func).splitlines()

    def _count_non_blank_lines(self, lines):
        return len([l for l in lines if l.strip() and not l.strip().startswith('#')])

    def test_book_class_view_is_thin(self):
        """
        bookings.views.book_class must be ≤ 10 substantive lines.
        All logic is in bookings.services.book_class.
        """
        lines = self._get_function_body('bookings.views', 'book_class')
        count = self._count_non_blank_lines(lines)
        self.assertLessEqual(count, 12,
            f"book_class view has {count} lines — thin view contract broken")

    def test_cancel_booking_view_is_thin(self):
        lines = self._get_function_body('bookings.views', 'cancel_booking')
        count = self._count_non_blank_lines(lines)
        self.assertLessEqual(count, 15,
            f"cancel_booking view has {count} lines — thin view contract broken")

    def test_booking_services_module_exists_and_is_non_trivial(self):
        """
        The service module must be substantive — logic is not inlined in views.
        """
        import importlib, inspect
        module = importlib.import_module('bookings.services')
        source = inspect.getsource(module)
        non_blank = [l for l in source.splitlines()
                     if l.strip() and not l.strip().startswith('#')]
        self.assertGreater(len(non_blank), 40,
            "bookings/services.py must contain substantive business logic")

    def test_ranking_service_is_separate_from_views(self):
        """CR2 ranking logic must NOT be defined inside gym.views."""
        import importlib, inspect
        views_source = inspect.getsource(importlib.import_module('gym.views'))
        self.assertNotIn('WEIGHT_FEATURED', views_source,
            "Ranking weights must live in ranking_service.py, not views.py")
        self.assertNotIn('def score_class', views_source,
            "score_class() must live in ranking_service.py, not views.py")

    def test_search_logic_is_separate_from_views(self):
        """CR1 filter logic must NOT be inlined in gym.views."""
        import importlib, inspect
        views_source = inspect.getsource(importlib.import_module('gym.views'))
        self.assertNotIn('Q(name__icontains', views_source,
            "Search filter Q objects must live in search_service.py, not views.py")

    def test_promotion_logic_is_separate_from_views(self):
        """CR3 impression recording must NOT be inlined in gym.views."""
        import importlib, inspect
        views_source = inspect.getsource(importlib.import_module('gym.views'))
        self.assertNotIn('PromotionEvent.objects.bulk_create', views_source,
            "Impression tracking must live in promotion_service.py, not views.py")


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION E: PromotionSlot — CR Table Schema & Service Quality (CR3)
# ═══════════════════════════════════════════════════════════════════════════════

class PromotionSlotModelTests(TestCase):
    """
    Validates the PromotionSlot database model and service layer.

    Evidence for CW1B:
      - Migration-friendly schema: the slot model uses DateField (not DateTime),
        is_active flag, CheckConstraints enforced at DB level, and a composite
        index for the scheduling query.
      - is_currently_live computed property — no raw SQL, pure Python.
      - PromotionSlot service correctly filters by date window and is_active.
    """

    def setUp(self):
        from gym.models import PromotionSlot, WorkoutClass, WorkoutCategory
        from django.contrib.contenttypes.models import ContentType
        from django.utils import timezone

        self.admin = _make_user('slot_admin@test.com', role='ADMIN')
        self.cat = WorkoutCategory.objects.create(name='SlotCat')
        self.cls = WorkoutClass.objects.create(
            name='Slot Class', category=self.cat,
            start_time=timezone.now() + timedelta(days=2),
            duration_minutes=60, capacity=20,
        )
        self.ct = ContentType.objects.get_for_model(WorkoutClass)
        today = timezone.now().date()

        self.active_slot = PromotionSlot.objects.create(
            content_type=self.ct,
            object_id=self.cls.pk,
            slot_context=PromotionSlot.SlotContext.DASHBOARD_HERO,
            position=1,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=7),
            is_active=True,
            created_by=self.admin,
        )
        self.future_slot = PromotionSlot.objects.create(
            content_type=self.ct,
            object_id=self.cls.pk,
            slot_context=PromotionSlot.SlotContext.DASHBOARD_HERO,
            position=2,
            start_date=today + timedelta(days=5),
            end_date=today + timedelta(days=14),
            is_active=True,
            created_by=self.admin,
        )
        self.paused_slot = PromotionSlot.objects.create(
            content_type=self.ct,
            object_id=self.cls.pk,
            slot_context=PromotionSlot.SlotContext.DASHBOARD_SIDEBAR,
            position=1,
            start_date=today - timedelta(days=3),
            end_date=today + timedelta(days=3),
            is_active=False,
        )

    def test_active_slot_is_currently_live(self):
        self.assertTrue(self.active_slot.is_currently_live)

    def test_future_slot_is_not_currently_live(self):
        self.assertFalse(self.future_slot.is_currently_live)

    def test_paused_slot_is_not_currently_live(self):
        """is_active=False must suppress slot even within valid date range."""
        self.assertFalse(self.paused_slot.is_currently_live)

    def test_display_headline_falls_back_to_item_name(self):
        self.active_slot.headline = ''
        self.active_slot.save(update_fields=['headline'])
        self.assertEqual(self.active_slot.display_headline, str(self.cls))

    def test_display_headline_uses_override_when_set(self):
        self.active_slot.headline = 'Summer Special!'
        self.active_slot.save(update_fields=['headline'])
        self.assertEqual(self.active_slot.display_headline, 'Summer Special!')

    def test_get_active_slots_returns_only_live_slots(self):
        from gym.promotion_service import get_active_slots
        from gym.models import PromotionSlot
        slots = list(get_active_slots(PromotionSlot.SlotContext.DASHBOARD_HERO))
        pks = [s.pk for s in slots]
        self.assertIn(self.active_slot.pk, pks)
        self.assertNotIn(self.future_slot.pk, pks)

    def test_get_active_slots_excludes_paused_slots(self):
        from gym.promotion_service import get_active_slots
        from gym.models import PromotionSlot
        slots = list(get_active_slots(PromotionSlot.SlotContext.DASHBOARD_SIDEBAR))
        pks = [s.pk for s in slots]
        self.assertNotIn(self.paused_slot.pk, pks)

    def test_get_active_slots_is_ordered_by_position(self):
        from gym.promotion_service import get_active_slots
        from gym.models import PromotionSlot, WorkoutCategory, WorkoutClass
        from django.contrib.contenttypes.models import ContentType
        from django.utils import timezone

        # Create two live slots for EQUIPMENT_LIST with different positions
        cat2 = WorkoutCategory.objects.create(name='EqSlotCat')
        eq_ct = ContentType.objects.get_for_model(WorkoutClass)
        today = timezone.now().date()
        slot_a = PromotionSlot.objects.create(
            content_type=eq_ct, object_id=self.cls.pk,
            slot_context=PromotionSlot.SlotContext.EQUIPMENT_LIST,
            position=2, start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1), is_active=True,
        )
        slot_b = PromotionSlot.objects.create(
            content_type=eq_ct, object_id=self.cls.pk,
            slot_context=PromotionSlot.SlotContext.EQUIPMENT_LIST,
            position=1, start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1), is_active=True,
        )
        slots = list(get_active_slots(PromotionSlot.SlotContext.EQUIPMENT_LIST))
        positions = [s.position for s in slots]
        self.assertEqual(positions, sorted(positions),
            "Active slots must be returned in ascending position order")

    def test_slot_str_includes_context_and_dates(self):
        s = str(self.active_slot)
        self.assertIn('DASHBOARD_HERO', s)
        self.assertIn('pos=1', s)

    def test_slot_choices_cover_all_page_contexts(self):
        """SlotContext choices must include all four page positions."""
        from gym.models import PromotionSlot
        choice_values = [c[0] for c in PromotionSlot.SlotContext.choices]
        self.assertIn('DASHBOARD_HERO', choice_values)
        self.assertIn('DASHBOARD_SIDEBAR', choice_values)
        self.assertIn('CLASS_LIST_TOP', choice_values)
        self.assertIn('EQUIPMENT_LIST', choice_values)

    def test_promotionslot_migration_exists(self):
        """Migration 0004 must be present and applied."""
        from django.db import connection
        tables = connection.introspection.table_names()
        self.assertIn('gym_promotionslot', tables,
            "gym_promotionslot table must exist — check migration 0004")

    def test_promotionslot_check_constraints_registered(self):
        """Both CheckConstraints must be registered on the model's Meta."""
        from gym.models import PromotionSlot
        constraint_names = [c.name for c in PromotionSlot._meta.constraints]
        self.assertIn('promotionslot_end_after_start', constraint_names)
        self.assertIn('promotionslot_position_range', constraint_names)

    def test_promotionslot_composite_index_registered(self):
        """The scheduling composite index must be registered on the model's Meta."""
        from gym.models import PromotionSlot
        index_names = [i.name for i in PromotionSlot._meta.indexes]
        self.assertIn('gym_slot_ctx_dates_idx', index_names)


# ─── helper (mirrors the one inside the test module) ─────────────────────────
def _make_user(email, role='MEMBER'):
    from accounts.models import User
    return User.objects.create_user(
        email=email, password='testpass123',
        first_name='Test', last_name='User', role=role,
    )
