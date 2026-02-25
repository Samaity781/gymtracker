from django import forms
from django.utils import timezone


class EquipmentBookingForm(forms.Form):
    slot_start = forms.DateTimeField(
        label='Start time',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )
    slot_end = forms.DateTimeField(
        label='End time',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('slot_start')
        end = cleaned.get('slot_end')
        if start and end:
            if start >= end:
                raise forms.ValidationError("End time must be after start time.")
            if start < timezone.now():
                raise forms.ValidationError("Start time cannot be in the past.")
        return cleaned
