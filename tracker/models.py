"""
tracker/models.py
Epic 7: Personal Fitness Tracker.

FR-15: log workout sessions with exercises and sets (reps >= 1, weight >= 0)
FR-16: chronological workout history
FR-17: basic progress metrics (total volume, personal records)
FR-18: reusable routines

Model hierarchy:
  Routine
    └── RoutineItem (exercise name + default sets/reps/weight)

  WorkoutSession  (a single gym visit)
    └── WorkoutEntry  (one exercise in the session)
          └── SetEntry  (one set: reps, weight, optional RPE)
"""

from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator


class Routine(models.Model):
    """A reusable workout template that a member can start from."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='routines')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.user.email})"


class RoutineItem(models.Model):
    """One exercise within a routine template."""

    routine = models.ForeignKey(Routine, on_delete=models.CASCADE, related_name='items')
    exercise_name = models.CharField(max_length=200)
    default_sets = models.PositiveIntegerField(default=3)
    default_reps = models.PositiveIntegerField(default=10)
    default_weight_kg = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )
    order = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.exercise_name} (Routine: {self.routine.name})"


class WorkoutSession(models.Model):
    """A logged gym session — the top-level container for a workout."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='workout_sessions')
    name = models.CharField(max_length=200, blank=True, help_text="Optional label, e.g. 'Leg Day'")
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    routine = models.ForeignKey(
        Routine, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sessions',
        help_text="Optional: link to a routine this session was based on.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-start_time']

    def __str__(self):
        return f"{self.user.email} – {self.date} – {self.name or 'Session'}"

    @property
    def total_volume_kg(self):
        """FR-17: sum of (reps × weight) across all sets in this session."""
        total = 0
        for entry in self.entries.prefetch_related('sets'):
            for s in entry.sets.all():
                total += s.reps * float(s.weight_kg)
        return round(total, 2)

    @property
    def duration_minutes(self):
        if self.start_time and self.end_time:
            from datetime import datetime, date
            start = datetime.combine(date.today(), self.start_time)
            end = datetime.combine(date.today(), self.end_time)
            delta = end - start
            return max(0, int(delta.total_seconds() / 60))
        return None


class WorkoutEntry(models.Model):
    """One exercise within a workout session (e.g. Bench Press)."""

    session = models.ForeignKey(WorkoutSession, on_delete=models.CASCADE, related_name='entries')
    exercise_name = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.exercise_name} in {self.session}"

    @property
    def best_set(self):
        """The set with the highest single-rep equivalent weight (weight × reps proxy)."""
        return self.sets.order_by('-weight_kg', '-reps').first()


class SetEntry(models.Model):
    """
    One set within a workout entry.
    FR-15: reps >= 1, weight >= 0.
    RPE (Rate of Perceived Exertion) is optional but useful for progress tracking.
    """

    entry = models.ForeignKey(WorkoutEntry, on_delete=models.CASCADE, related_name='sets')
    set_number = models.PositiveIntegerField(default=1)
    reps = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    weight_kg = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )
    rpe = models.DecimalField(
        max_digits=3, decimal_places=1,
        null=True, blank=True,
        validators=[MinValueValidator(1)],
        help_text="Rate of Perceived Exertion (1–10, optional)",
    )
    is_warmup = models.BooleanField(default=False)

    class Meta:
        ordering = ['set_number']

    def __str__(self):
        return f"Set {self.set_number}: {self.reps}×{self.weight_kg}kg"

    @property
    def volume(self):
        return self.reps * float(self.weight_kg)
