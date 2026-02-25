"""
accounts/models.py
Epic 1-2: Custom User model with MEMBER / ADMIN roles.

Design rationale: AbstractBaseUser + PermissionsMixin gives us full
control over authentication fields while still participating in Django's
permission system. Email is the login identifier rather than username,
which matches the gym-member use-case where staff remember members by
email rather than an invented handle.
"""

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom manager to support email-as-login and role helpers."""

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('role', User.Role.MEMBER)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.ADMIN)
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Central user model.  Role is stored alongside Django's permission flags so
    that views can do a single .role check rather than relying solely on groups.
    """

    class Role(models.TextChoices):
        MEMBER = 'MEMBER', 'Member'
        ADMIN = 'ADMIN', 'Admin'

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def is_admin_role(self):
        """Convenience check — use in templates/views instead of repeated is_staff checks."""
        return self.role == self.Role.ADMIN or self.is_staff or self.is_superuser


class MemberProfile(models.Model):
    """
    One-to-one extension of User for member-specific data.
    Kept separate so admin users don't need irrelevant fitness fields.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, max_length=500)
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    emergency_contact = models.CharField(max_length=200, blank=True)
    membership_start = models.DateField(null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile – {self.user.email}"
