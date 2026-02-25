"""
accounts/views.py
Epic 1-2: Authentication, registration, profile management, and admin user CRUD.

Three-layer mapping:
  Template  →  templates/accounts/
  View      →  this file
  Model     →  accounts/models.py (User, MemberProfile)
"""

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    AdminUserCreateForm, AdminUserEditForm,
    LoginForm, MemberRegistrationForm, ProfileForm, ProfileNameForm,
)
from .models import MemberProfile, User
from accounts.decorators import admin_required


# ─── Public views ─────────────────────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('gym:dashboard')
    form = MemberRegistrationForm(request.POST or None)
    if form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Welcome, {user.first_name}! Your account has been created.")
        return redirect('gym:dashboard')
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('gym:dashboard')
    form = LoginForm(request, data=request.POST or None)
    if form.is_valid():
        login(request, form.get_user())
        messages.success(request, "You are now logged in.")
        next_url = request.GET.get('next', 'gym:dashboard')
        return redirect(next_url)
    return render(request, 'accounts/login.html', {'form': form})


@require_POST
@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('accounts:login')


# ─── Member profile views ──────────────────────────────────────────────────────

@login_required
def profile_view(request):
    profile, _ = MemberProfile.objects.get_or_create(user=request.user)
    return render(request, 'accounts/profile.html', {'profile': profile})


@login_required
def profile_edit_view(request):
    profile, _ = MemberProfile.objects.get_or_create(user=request.user)
    profile_form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)
    name_form = ProfileNameForm(request.POST or None, instance=request.user)

    if request.method == 'POST':
        if profile_form.is_valid() and name_form.is_valid():
            name_form.save()
            profile_form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('accounts:profile')
    return render(request, 'accounts/profile_edit.html', {
        'profile_form': profile_form,
        'name_form': name_form,
    })


@login_required
def change_password_view(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)  # keeps the user logged in post-change
        messages.success(request, "Password changed successfully.")
        return redirect('accounts:profile')
    return render(request, 'accounts/change_password.html', {'form': form})


# ─── Admin: user management ────────────────────────────────────────────────────

@admin_required
def admin_user_list(request):
    users = User.objects.all().order_by('email')
    return render(request, 'accounts/admin/user_list.html', {'users': users})


@admin_required
def admin_user_create(request):
    form = AdminUserCreateForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "User account created.")
        return redirect('accounts:admin_user_list')
    return render(request, 'accounts/admin/user_form.html', {'form': form, 'action': 'Create'})


@admin_required
def admin_user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = AdminUserEditForm(request.POST or None, instance=user)
    if form.is_valid():
        form.save()
        messages.success(request, f"User {user.email} updated.")
        return redirect('accounts:admin_user_list')
    return render(request, 'accounts/admin/user_form.html', {'form': form, 'action': 'Edit', 'target_user': user})


@admin_required
@require_POST
def admin_user_toggle_active(request, pk):
    """Suspend or reactivate an account without deleting it (preserves audit trail)."""
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "You cannot suspend your own account.")
        return redirect('accounts:admin_user_list')
    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    state = "reactivated" if user.is_active else "suspended"
    messages.success(request, f"{user.email} has been {state}.")
    return redirect('accounts:admin_user_list')


@admin_required
@require_POST
def admin_user_delete(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect('accounts:admin_user_list')
    email = user.email
    user.delete()
    messages.success(request, f"User {email} deleted.")
    return redirect('accounts:admin_user_list')
