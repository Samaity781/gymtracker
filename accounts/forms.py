"""
accounts/forms.py
Registration, profile editing, and admin user-management forms.

Validation strategy (mirrors gym/forms.py):
  Layer 1 – Client-side: HTML5 widget attrs (required, minlength, maxlength, type).
  Layer 2 – Server-side: Django clean_* methods.  Authoritative; cannot be bypassed.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import password_validation
from .models import User, MemberProfile


# ─── Shared widget helpers ────────────────────────────────────────────────────

def _text(placeholder='', maxlength=None, minlength=None, input_type='text'):
    attrs = {'placeholder': placeholder, 'class': 'form-control', 'type': input_type}
    if maxlength:
        attrs['maxlength'] = str(maxlength)
    if minlength:
        attrs['minlength'] = str(minlength)
    return forms.TextInput(attrs=attrs)


# ─── Registration ─────────────────────────────────────────────────────────────

class MemberRegistrationForm(UserCreationForm):
    """
    Public-facing registration form.

    Client-side:  email type=email; first/last name minlength=2, maxlength=150;
                  passwords use type=password.
    Server-side:  email uniqueness via model; names stripped and length-checked;
                  password strength via Django's AUTH_PASSWORD_VALIDATORS (four
                  validators configured in settings.py — see NFR-01 evidence).
    """

    first_name = forms.CharField(
        max_length=150,
        min_length=2,
        required=True,
        label='First name',
        widget=_text('Your first name', maxlength=150, minlength=2),
    )
    last_name = forms.CharField(
        max_length=150,
        min_length=2,
        required=True,
        label='Last name',
        widget=_text('Your last name', maxlength=150, minlength=2),
    )

    class Meta:
        model  = User
        fields = ('email', 'first_name', 'last_name', 'password1', 'password2')
        widgets = {
            'email': forms.EmailInput(attrs={
                'placeholder': 'your@email.com',
                'class': 'form-control',
                'autocomplete': 'email',
                'maxlength': '254',   # RFC 5321 limit
            }),
        }

    # ── Server-side validation ──────────────────────────────────────────────
    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A member with this email already exists.")
        return email

    def clean_first_name(self):
        value = self.cleaned_data.get('first_name', '').strip()
        if len(value) < 2:
            raise forms.ValidationError("First name must be at least 2 characters.")
        return value

    def clean_last_name(self):
        value = self.cleaned_data.get('last_name', '').strip()
        if len(value) < 2:
            raise forms.ValidationError("Last name must be at least 2 characters.")
        return value

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.MEMBER
        if commit:
            user.save()
            MemberProfile.objects.get_or_create(user=user)
        return user


# ─── Login ────────────────────────────────────────────────────────────────────

class LoginForm(AuthenticationForm):
    """
    Thin wrapper over Django's AuthenticationForm for Bootstrap styling.
    AuthenticationForm already validates credentials server-side.

    Client-side: email type=email (browser-level format check).
    Server-side: Django's auth backend handles password verification.
                 Passwords are never compared in plaintext — see NFR-01.
    """

    username = forms.EmailField(
        label='Email address',
        widget=forms.EmailInput(attrs={
            'placeholder': 'your@email.com',
            'class': 'form-control',
            'autocomplete': 'email',
        }),
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'placeholder': '••••••••',
            'class': 'form-control',
            'autocomplete': 'current-password',
        }),
    )


# ─── Profile ─────────────────────────────────────────────────────────────────

class ProfileForm(forms.ModelForm):
    """
    Member profile update form.

    Client-side:  phone maxlength=20; bio maxlength=500;
                  date_of_birth type=date (prevents non-date input).
    Server-side:  bio length; phone format (digits + spaces/dashes allowed).
    """

    class Meta:
        model  = MemberProfile
        fields = ('bio', 'date_of_birth', 'phone', 'emergency_contact', 'avatar')
        widgets = {
            'bio':               forms.Textarea(attrs={
                'rows': '3', 'class': 'form-control',
                'maxlength': '500', 'placeholder': 'Tell us a bit about yourself…',
            }),
            'date_of_birth':     forms.DateInput(attrs={
                'type': 'date', 'class': 'form-control',
            }),
            'phone':             forms.TextInput(attrs={
                'class': 'form-control', 'maxlength': '20',
                'placeholder': '+44 7700 000000',
                'pattern': r'[\d\s\+\-\(\)]{7,20}',
                'title': 'Digits, spaces, +, - and () only',
            }),
            'emergency_contact': forms.TextInput(attrs={
                'class': 'form-control', 'maxlength': '200',
                'placeholder': 'Name and phone number',
            }),
        }

    # ── Server-side validation ──────────────────────────────────────────────
    def clean_bio(self):
        bio = self.cleaned_data.get('bio', '')
        if len(bio) > 500:
            raise forms.ValidationError("Bio cannot exceed 500 characters.")
        return bio

    def clean_phone(self):
        import re
        phone = self.cleaned_data.get('phone', '').strip()
        if phone and not re.match(r'^[\d\s\+\-\(\)]{7,20}$', phone):
            raise forms.ValidationError(
                "Enter a valid phone number (digits, spaces, +, - and () only)."
            )
        return phone


class ProfileNameForm(forms.ModelForm):
    """Separate small form so users can update their display name."""

    class Meta:
        model  = User
        fields = ('first_name', 'last_name')
        widgets = {
            'first_name': _text('First name', maxlength=150, minlength=2),
            'last_name':  _text('Last name',  maxlength=150, minlength=2),
        }


# ─── Admin user-management forms ─────────────────────────────────────────────

class AdminUserCreateForm(UserCreationForm):
    """
    Admin creates a new user and assigns a role.
    Inherits password strength validators from UserCreationForm.
    """

    class Meta:
        model  = User
        fields = ('email', 'first_name', 'last_name', 'role', 'is_active', 'password1', 'password2')
        widgets = {
            'email':      forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': _text('First name', maxlength=150, minlength=2),
            'last_name':  _text('Last name',  maxlength=150, minlength=2),
        }


class AdminUserEditForm(forms.ModelForm):
    """Admin edits an existing user's role, name, and active status."""

    class Meta:
        model  = User
        fields = ('email', 'first_name', 'last_name', 'role', 'is_active', 'is_staff')
        widgets = {
            'email':      forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': _text('First name', maxlength=150),
            'last_name':  _text('Last name',  maxlength=150),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This email is already in use by another account.")
        return email

