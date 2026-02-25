"""
reviews/forms.py
CR4: Forms for review submission and admin moderation.
"""

from django import forms
from .models import Review


class ReviewForm(forms.ModelForm):
    """
    Member-facing form for submitting or editing a review.
    status and moderation fields are excluded — those are admin-only.
    """
    rating = forms.ChoiceField(
        choices=[(i, f'{i} star{"s" if i > 1 else ""}') for i in range(1, 6)],
        widget=forms.RadioSelect(attrs={'class': 'star-radio'}),
        label='Your rating',
    )

    class Meta:
        model  = Review
        fields = ('rating', 'comment')
        widgets = {
            'comment': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Share your experience (optional)…',
                'maxlength': 1000,
            }),
        }

    def clean_rating(self):
        value = int(self.cleaned_data['rating'])
        if value < 1 or value > 5:
            raise forms.ValidationError("Rating must be between 1 and 5.")
        return value


class ModerationForm(forms.Form):
    """
    Admin form for approving or hiding a review.
    The action (approve/hide) is driven by which button was pressed in the
    template, so the form only holds the optional note.
    """
    moderation_note = forms.CharField(
        required=False,
        label='Moderation note (admin-only)',
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Optional — explain your decision for audit purposes.',
        }),
    )
