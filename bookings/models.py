"""
bookings/models.py
Epic 6: Booking state machine.

Valid transitions (NFR-06 — invalid transitions are rejected):
  (new)  → BOOKED
  BOOKED → CANCELLED  (member-initiated or admin)
  BOOKED → ATTENDED   (admin only, after class)
  BOOKED → MISSED     (admin only, after class)
  CANCELLED → (terminal — no further transitions)
  ATTENDED  → (terminal)
  MISSED    → (terminal)

Capacity on WorkoutClass.booked_count is updated atomically via
the booking service layer, not directly from model.save(), to avoid
race conditions in the SQLite single-writer model.
"""

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class Booking(models.Model):

    class Status(models.TextChoices):
        BOOKED = 'BOOKED', 'Booked'
        CANCELLED = 'CANCELLED', 'Cancelled'
        ATTENDED = 'ATTENDED', 'Attended'
        MISSED = 'MISSED', 'Missed'

    # ─── Valid transition map ────────────────────────────────────────────────
    # Maps current status → set of statuses that are legally reachable.
    VALID_TRANSITIONS: dict[str, set[str]] = {
        Status.BOOKED:     {Status.CANCELLED, Status.ATTENDED, Status.MISSED},
        Status.CANCELLED:  set(),   # terminal
        Status.ATTENDED:   set(),   # terminal
        Status.MISSED:     set(),   # terminal
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings',
    )
    # A booking is for either a class or equipment — exactly one must be set.
    workout_class = models.ForeignKey(
        'gym.WorkoutClass',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='bookings',
    )
    equipment = models.ForeignKey(
        'gym.GymEquipment',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='bookings',
    )

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.BOOKED)
    booked_at = models.DateTimeField(default=timezone.now)
    # Equipment bookings need a slot
    slot_start = models.DateTimeField(null=True, blank=True)
    slot_end = models.DateTimeField(null=True, blank=True)

    # Audit: who last changed the status and when
    status_changed_at = models.DateTimeField(auto_now=True)
    status_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='booking_changes',
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-booked_at']
        # Prevent a member booking the same class twice while active
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'workout_class'],
                condition=models.Q(status='BOOKED'),
                name='unique_active_class_booking',
            ),
            models.UniqueConstraint(
                fields=['user', 'equipment', 'slot_start'],
                condition=models.Q(status='BOOKED'),
                name='unique_active_equipment_booking',
            ),
        ]

    def __str__(self):
        target = self.workout_class or self.equipment
        return f"{self.user.email} – {target} – {self.status}"

    def clean(self):
        # Enforce XOR: must have exactly one booking target
        if self.workout_class and self.equipment:
            raise ValidationError("A booking may be for a class or equipment, not both.")
        if not self.workout_class and not self.equipment:
            raise ValidationError("A booking must target a class or a piece of equipment.")

    @property
    def booking_target(self):
        return self.workout_class or self.equipment

    @property
    def target_type(self):
        return 'class' if self.workout_class else 'equipment'

    def can_transition_to(self, new_status: str) -> bool:
        """Return True if the requested transition is legal from current status."""
        return new_status in self.VALID_TRANSITIONS.get(self.status, set())

    def assert_transition(self, new_status: str):
        """Raise ValueError with a descriptive message if the transition is illegal."""
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Cannot transition from '{self.get_status_display()}' "
                f"to '{dict(self.Status.choices).get(new_status, new_status)}'."
            )
