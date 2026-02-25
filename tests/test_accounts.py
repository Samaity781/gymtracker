"""
tests/test_accounts.py
Epic 1-2: User model, registration, login, and role-based access control.
"""

from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User, MemberProfile


class UserModelTests(TestCase):

    def test_create_member_user(self):
        user = User.objects.create_user(
            email='member@example.com',
            password='StrongPass1!',
            first_name='Jane',
        )
        self.assertEqual(user.role, User.Role.MEMBER)
        self.assertFalse(user.is_staff)

    def test_create_superuser(self):
        user = User.objects.create_superuser(
            email='super@example.com',
            password='StrongPass1!',
        )
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_admin_role)

    def test_full_name_property(self):
        user = User(first_name='Sam', last_name='Maitland', email='s@m.com')
        self.assertEqual(user.full_name, 'Sam Maitland')

    def test_full_name_falls_back_to_email(self):
        user = User(email='anon@example.com')
        self.assertEqual(user.full_name, 'anon@example.com')

    def test_is_admin_role_true_for_admin(self):
        user = User(role=User.Role.ADMIN)
        self.assertTrue(user.is_admin_role)

    def test_is_admin_role_false_for_member(self):
        user = User(role=User.Role.MEMBER, is_staff=False, is_superuser=False)
        self.assertFalse(user.is_admin_role)

    def test_signal_creates_profile_for_member(self):
        user = User.objects.create_user(email='proftest@ex.com', password='Pass123!')
        self.assertTrue(MemberProfile.objects.filter(user=user).exists())


class RegistrationViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('accounts:register')

    def test_registration_page_loads(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_valid_registration_creates_user(self):
        response = self.client.post(self.url, {
            'email': 'new@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'VeryStrongPass99!',
            'password2': 'VeryStrongPass99!',
        })
        self.assertTrue(User.objects.filter(email='new@example.com').exists())

    def test_valid_registration_redirects_to_dashboard(self):
        response = self.client.post(self.url, {
            'email': 'redir@example.com',
            'first_name': 'Red',
            'last_name': 'Test',
            'password1': 'VeryStrongPass99!',
            'password2': 'VeryStrongPass99!',
        })
        self.assertRedirects(response, reverse('gym:dashboard'))

    def test_mismatched_passwords_rejected(self):
        response = self.client.post(self.url, {
            'email': 'bad@example.com',
            'first_name': 'Bad',
            'last_name': 'User',
            'password1': 'Pass123!',
            'password2': 'Different!',
        })
        self.assertFalse(User.objects.filter(email='bad@example.com').exists())
        self.assertEqual(response.status_code, 200)


class RoleBasedAccessTests(TestCase):

    def setUp(self):
        self.member = User.objects.create_user(
            email='member@ex.com', password='Pass123!', role=User.Role.MEMBER
        )
        self.admin = User.objects.create_user(
            email='admin@ex.com', password='Pass123!', role=User.Role.ADMIN,
            is_staff=True,
        )
        self.client = Client()

    def test_unauthenticated_redirected_from_dashboard(self):
        response = self.client.get(reverse('gym:dashboard'))
        self.assertRedirects(response, '/accounts/login/?next=/dashboard/', fetch_redirect_response=False)

    def test_member_cannot_access_admin_user_list(self):
        self.client.login(email='member@ex.com', password='Pass123!')
        response = self.client.get(reverse('accounts:admin_user_list'))
        # Should redirect to dashboard with an error
        self.assertRedirects(response, reverse('gym:dashboard'))

    def test_admin_can_access_admin_user_list(self):
        self.client.login(email='admin@ex.com', password='Pass123!')
        response = self.client.get(reverse('accounts:admin_user_list'))
        self.assertEqual(response.status_code, 200)

    def test_member_can_access_dashboard(self):
        self.client.login(email='member@ex.com', password='Pass123!')
        response = self.client.get(reverse('gym:dashboard'))
        self.assertEqual(response.status_code, 200)
