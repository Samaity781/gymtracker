"""
gym/forms.py
Admin-facing forms for managing categories, equipment, and classes,
plus the member-facing search forms.

Validation strategy — two complementary layers
──────────────────────────────────────────────
1. CLIENT-SIDE (HTML5 attributes injected via widget attrs):
   `required`, `minlength`, `maxlength`, `min`, `max`, `type`, `pattern`.
   These give instant feedback without a round-trip, improving UX.
   Browser validation can be bypassed by disabling JavaScript or crafting
   a raw HTTP request, so it is NOT trusted for security.

2. SERVER-SIDE (Django form `clean_*` methods and `clean()`):
   All field-level and cross-field constraints are enforced in Python.
   This is the authoritative validation layer.  A form that passes
   client-side checks may still fail here if data has been tampered with.

Both layers exist for every user-facing constraint — never one alone.
"""

from django import forms
from django.utils import timezone
from .models import WorkoutCategory, GymEquipment, WorkoutClass


# ─── Shared widget helpers ────────────────────────────────────────────────────

def _text(placeholder='', maxlength=None, minlength=None):
    attrs = {'placeholder': placeholder, 'class': 'form-control'}
    if maxlength:
        attrs['maxlength'] = str(maxlength)
    if minlength:
        attrs['minlength'] = str(minlength)
    return forms.TextInput(attrs=attrs)

def _textarea(rows=3, maxlength=None):
    attrs = {'rows': str(rows), 'class': 'form-control'}
    if maxlength:
        attrs['maxlength'] = str(maxlength)
    return forms.Textarea(attrs=attrs)

def _number(min_val=None, max_val=None):
    attrs = {'class': 'form-control'}
    if min_val is not None:
        attrs['min'] = str(min_val)
    if max_val is not None:
        attrs['max'] = str(max_val)
    return forms.NumberInput(attrs=attrs)


# ─── Category form ────────────────────────────────────────────────────────────

class CategoryForm(forms.ModelForm):
    """
    Admin form for creating and editing workout categories.

    Client-side:  name is required + minlength=2; icon has maxlength=50.
    Server-side:  name uniqueness enforced by model UniqueConstraint.
    """

    class Meta:
        model = WorkoutCategory
        fields = ('name', 'description', 'icon', 'is_active')
        widgets = {
            'name':        _text('e.g. Spin, Yoga, HIIT', maxlength=100, minlength=2),
            'description': _textarea(rows=3, maxlength=500),
            'icon':        _text('Bootstrap icon class, e.g. bi-bicycle', maxlength=50),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if len(name) < 2:
            raise forms.ValidationError("Category name must be at least 2 characters.")
        return name


# ─── Equipment form ───────────────────────────────────────────────────────────

class GymEquipmentForm(forms.ModelForm):
    """
    Admin form for gym equipment.

    Client-side:  name required, capacity min=1; location maxlength=200.
    Server-side:  capacity ≥ 1 enforced in clean_capacity().
    """

    # Explicit IntegerField overrides PositiveIntegerField's default min_value=0
    # so the rendered widget carries min="1" for client-side validation.
    capacity = forms.IntegerField(
        min_value=1, max_value=100,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '100'}),
    )

    class Meta:
        model = GymEquipment
        fields = ('name', 'description', 'category', 'location',
                  'capacity', 'is_active', 'image', 'is_featured')
        widgets = {
            'name':        _text('Equipment name', maxlength=200, minlength=2),
            'description': _textarea(rows=3, maxlength=1000),
            'location':    _text("e.g. Ground floor, Zone A", maxlength=200),
        }

    # ── Server-side validation ──────────────────────────────────────────────
    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if len(name) < 2:
            raise forms.ValidationError("Equipment name must be at least 2 characters.")
        return name

    def clean_capacity(self):
        value = self.cleaned_data.get('capacity')
        if value is None or value < 1:
            raise forms.ValidationError("Capacity must be at least 1.")
        if value > 100:
            raise forms.ValidationError("Capacity cannot exceed 100.")
        return value


# ─── Workout class form ───────────────────────────────────────────────────────

class WorkoutClassForm(forms.ModelForm):
    """
    Admin form for scheduled workout classes.

    Client-side:  name required; capacity min=1; duration min=15;
                  start_time uses datetime-local browser widget.
    Server-side:  capacity ≥ 1, duration ≥ 15, start_time must be in
                  the future (for new classes only — allow editing past ones).
    """

    # Explicit IntegerFields override PositiveIntegerField's default min_value=0,
    # ensuring the rendered widget carries the correct min attribute for
    # client-side (HTML5) validation evidence.
    capacity = forms.IntegerField(
        min_value=1, max_value=200,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '200'}),
    )
    duration_minutes = forms.IntegerField(
        min_value=15, max_value=480,
        initial=60,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '15', 'max': '480'}),
    )

    class Meta:
        model = WorkoutClass
        fields = (
            'name', 'description', 'category', 'instructor', 'location',
            'start_time', 'duration_minutes', 'capacity',
            'is_active', 'image', 'is_featured',
        )
        widgets = {
            'name':             _text('Class name', maxlength=200, minlength=2),
            'description':      _textarea(rows=3, maxlength=2000),
            'instructor':       _text('Instructor name', maxlength=200),
            'location':         _text('e.g. Studio 1', maxlength=200),
            'duration_minutes': _number(min_val=15, max_val=480),
            'capacity':         _number(min_val=1, max_val=200),
            'start_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'}
            ),
        }

    # ── Server-side validation ──────────────────────────────────────────────
    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if len(name) < 2:
            raise forms.ValidationError("Class name must be at least 2 characters.")
        return name

    def clean_capacity(self):
        value = self.cleaned_data.get('capacity')
        if value is None or value < 1:
            raise forms.ValidationError("Capacity must be at least 1.")
        if value > 200:
            raise forms.ValidationError("Capacity cannot exceed 200.")
        return value

    def clean_duration_minutes(self):
        value = self.cleaned_data.get('duration_minutes')
        if value is None or value < 15:
            raise forms.ValidationError("Duration must be at least 15 minutes.")
        if value > 480:
            raise forms.ValidationError("Duration cannot exceed 480 minutes (8 hours).")
        return value

    def clean_start_time(self):
        """
        Server-side: start_time must be in the future for newly-created classes.
        Existing classes can be edited freely (changing instructor, description, etc.)
        without this guard firing.
        """
        dt = self.cleaned_data.get('start_time')
        if dt and not self.instance.pk and dt <= timezone.now():
            raise forms.ValidationError(
                "New classes must be scheduled in the future."
            )
        return dt


# ─── Class search form ────────────────────────────────────────────────────────

class ClassSearchForm(forms.Form):
    """
    FR-09 text search + FR-08 category filter + CR1 advanced filters.

    All fields are optional — an empty submission returns all active classes.
    Cross-field validation enforces date_from ≤ date_to.
    Filter state is preserved in the query string (FR-20) automatically
    because the form uses GET.

    Client-side:  q has maxlength=200; date inputs use type=date.
    Server-side:  date range cross-check in clean().
    """

    q = forms.CharField(
        required=False,
        label='Search',
        widget=forms.TextInput(attrs={
            'placeholder': 'Search classes…',
            'maxlength': '200',
            'class': 'form-control',
        }),
    )
    category = forms.ModelChoiceField(
        queryset=WorkoutCategory.objects.filter(is_active=True),
        required=False,
        empty_label='All categories',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    date_from = forms.DateField(
        required=False,
        label='From date',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    date_to = forms.DateField(
        required=False,
        label='To date',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    available_only = forms.BooleanField(
        required=False,
        label='Available spaces only',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    upcoming_only = forms.BooleanField(
        required=False,
        label='Upcoming classes only',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    # ── Cross-field server-side validation ─────────────────────────────────
    def clean(self):
        cleaned = super().clean()
        date_from = cleaned.get('date_from')
        date_to   = cleaned.get('date_to')
        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError(
                "'From date' must be on or before 'To date'."
            )
        q = cleaned.get('q', '')
        if len(q) > 200:
            raise forms.ValidationError("Search query is too long (max 200 characters).")
        return cleaned


# ─── Equipment search form ────────────────────────────────────────────────────

class EquipmentSearchForm(forms.Form):
    """
    CR1: Equipment text + category filter.
    No date range — equipment has no schedule.

    Client-side: q maxlength=200.
    Server-side: q length check.
    """

    q = forms.CharField(
        required=False,
        label='Search',
        widget=forms.TextInput(attrs={
            'placeholder': 'Search equipment…',
            'maxlength': '200',
            'class': 'form-control',
        }),
    )
    category = forms.ModelChoiceField(
        queryset=WorkoutCategory.objects.filter(is_active=True),
        required=False,
        empty_label='All categories',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def clean_q(self):
        q = self.cleaned_data.get('q', '').strip()
        if len(q) > 200:
            raise forms.ValidationError("Search query is too long (max 200 characters).")
        return q
