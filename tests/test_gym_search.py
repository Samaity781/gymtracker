"""
tests/test_gym_search.py
Epic 3-5: Workout class search and category filter (FR-08, FR-09, CR1 partial).
"""

from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from gym.models import WorkoutCategory, WorkoutClass


class ClassSearchTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(email='s@test.com', password='Pass123!')
        self.client = Client()
        self.client.login(email='s@test.com', password='Pass123!')

        self.cat_spin = WorkoutCategory.objects.create(name='Spin', is_active=True)
        self.cat_yoga = WorkoutCategory.objects.create(name='Yoga', is_active=True)

        now = timezone.now()
        self.spin1 = WorkoutClass.objects.create(
            name='Morning Spin', category=self.cat_spin,
            start_time=now + timedelta(hours=1), capacity=10, is_active=True,
        )
        self.yoga1 = WorkoutClass.objects.create(
            name='Evening Yoga', category=self.cat_yoga,
            start_time=now + timedelta(hours=3), capacity=8, is_active=True,
        )
        # Inactive class should not appear
        self.inactive = WorkoutClass.objects.create(
            name='Old Class', category=self.cat_spin,
            start_time=now + timedelta(days=1), capacity=5, is_active=False,
        )

    def test_class_list_returns_active_classes_only(self):
        response = self.client.get(reverse('gym:class_list'))
        classes = list(response.context['classes'])
        self.assertIn(self.spin1, classes)
        self.assertIn(self.yoga1, classes)
        self.assertNotIn(self.inactive, classes)

    def test_text_search_filters_by_name(self):
        response = self.client.get(reverse('gym:class_list'), {'q': 'Spin'})
        classes = list(response.context['classes'])
        self.assertIn(self.spin1, classes)
        self.assertNotIn(self.yoga1, classes)

    def test_category_filter_works(self):
        response = self.client.get(
            reverse('gym:class_list'), {'category': self.cat_yoga.pk}
        )
        classes = list(response.context['classes'])
        self.assertIn(self.yoga1, classes)
        self.assertNotIn(self.spin1, classes)

    def test_combined_text_and_category_filter(self):
        response = self.client.get(
            reverse('gym:class_list'), {'q': 'Morning', 'category': self.cat_spin.pk}
        )
        classes = list(response.context['classes'])
        self.assertIn(self.spin1, classes)
        self.assertNotIn(self.yoga1, classes)

    def test_search_no_results_returns_empty_list(self):
        response = self.client.get(reverse('gym:class_list'), {'q': 'NonexistentXYZ'})
        classes = list(response.context['classes'])
        self.assertEqual(len(classes), 0)


class ClassModelTests(TestCase):

    def test_available_spaces_reduces_with_bookings(self):
        cat = WorkoutCategory.objects.create(name='HIIT')
        wc = WorkoutClass(
            name='HIIT', category=cat,
            start_time=timezone.now() + timedelta(hours=2),
            capacity=20, booked_count=5,
        )
        self.assertEqual(wc.available_spaces, 15)

    def test_is_full_when_at_capacity(self):
        cat = WorkoutCategory.objects.create(name='Pilates')
        wc = WorkoutClass(
            name='Pilates', category=cat,
            start_time=timezone.now() + timedelta(hours=2),
            capacity=10, booked_count=10,
        )
        self.assertTrue(wc.is_full)

    def test_is_not_full_below_capacity(self):
        cat = WorkoutCategory.objects.create(name='Boxing')
        wc = WorkoutClass(
            name='Boxing', category=cat,
            start_time=timezone.now() + timedelta(hours=2),
            capacity=10, booked_count=9,
        )
        self.assertFalse(wc.is_full)
