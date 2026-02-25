"""
accounts/decorators.py
Reusable access-control decorators so views stay clean.

Using a decorator rather than a mixin keeps function-based views lean
and makes the permission intent immediately visible at the top of each view.
"""

from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def admin_required(view_func):
    """
    Requires the user to be authenticated AND to hold an admin role.
    Unauthenticated users are redirected to login; authenticated non-admins
    receive a 403-style error message and are sent to the dashboard.
    """
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_admin_role:
            messages.error(request, "You do not have permission to access that area.")
            return redirect('gym:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped


def member_required(view_func):
    """
    Requires the user to be authenticated.  Any role is accepted.
    This is effectively an alias for @login_required but makes intent explicit.
    """
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return _wrapped
