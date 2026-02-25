"""
tracker/forms.py
Forms for the personal fitness tracker.
Uses inlineformset_factory to allow adding multiple exercises and sets
within a single page submission — keeps the UX clean without requiring
multi-step navigation.
"""

from django import forms
from django.forms import inlineformset_factory
from .models import WorkoutSession, WorkoutEntry, SetEntry, Routine, RoutineItem


class WorkoutSessionForm(forms.ModelForm):
    class Meta:
        model = WorkoutSession
        fields = ('name', 'date', 'start_time', 'end_time', 'notes', 'routine')
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['routine'].queryset = Routine.objects.filter(user=user)


class WorkoutEntryForm(forms.ModelForm):
    class Meta:
        model = WorkoutEntry
        fields = ('exercise_name', 'order', 'notes')
        widgets = {
            'notes': forms.TextInput(attrs={'placeholder': 'Optional notes…'}),
        }


class SetEntryForm(forms.ModelForm):
    class Meta:
        model = SetEntry
        fields = ('set_number', 'reps', 'weight_kg', 'rpe', 'is_warmup')
        widgets = {
            'weight_kg': forms.NumberInput(attrs={'step': '0.25', 'min': '0'}),
            'rpe': forms.NumberInput(attrs={'step': '0.5', 'min': '1', 'max': '10', 'placeholder': '–'}),
        }


WorkoutEntryFormSet = inlineformset_factory(
    WorkoutSession, WorkoutEntry,
    form=WorkoutEntryForm,
    extra=1,
    can_delete=True,
)

SetEntryFormSet = inlineformset_factory(
    WorkoutEntry, SetEntry,
    form=SetEntryForm,
    extra=1,
    can_delete=True,
)


class RoutineForm(forms.ModelForm):
    class Meta:
        model = Routine
        fields = ('name', 'description')
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}


class RoutineItemForm(forms.ModelForm):
    class Meta:
        model = RoutineItem
        fields = ('exercise_name', 'default_sets', 'default_reps', 'default_weight_kg', 'order', 'notes')


RoutineItemFormSet = inlineformset_factory(
    Routine, RoutineItem,
    form=RoutineItemForm,
    extra=1,
    can_delete=True,
)
