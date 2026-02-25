"""
bookings/services.py
Booking service layer — isolates all booking business logic from views.

This is the "Service" tier in the three-layer Template → View/Service → Model
architecture. Keeping it here means:
  1. Views stay thin and testable without HTTP overhead.
  2. Capacity updates and state transitions are always co-located and atomic.
  3. Future automation (e.g. a management command to mark Missed bookings) can
     import this module directly without duplicating logic.

All public functions return a Booking instance on success and raise
ValueError with a human-readable message on failure.
"""

from django.db import transaction
from django.utils import timezone

from .models import Booking
from gym.models import WorkoutClass, GymEquipment


# ─── Class booking ─────────────────────────────────────────────────────────────

@transaction.atomic
def book_class(user, workout_class: WorkoutClass) -> Booking:
    """
    Create a BOOKED booking for a member on a workout class.
    Guards: class must be active, upcoming, and have available capacity.
    """
    if not workout_class.is_active:
        raise ValueError("This class is no longer available.")
    if not workout_class.is_upcoming:
        raise ValueError("You cannot book a class that has already started or passed.")

    # Re-check capacity inside the transaction to minimise race conditions
    current = WorkoutClass.objects.select_for_update().get(pk=workout_class.pk)
    if current.booked_count >= current.capacity:
        raise ValueError("This class is fully booked.")

    existing = Booking.objects.filter(
        user=user,
        workout_class=workout_class,
        status=Booking.Status.BOOKED,
    ).first()
    if existing:
        raise ValueError("You already have an active booking for this class.")

    booking = Booking.objects.create(
        user=user,
        workout_class=workout_class,
        status=Booking.Status.BOOKED,
    )
    WorkoutClass.objects.filter(pk=workout_class.pk).update(booked_count=current.booked_count + 1)
    return booking


@transaction.atomic
def cancel_booking(booking: Booking, cancelled_by) -> Booking:
    """
    Cancel a BOOKED booking.  Returns the updated Booking.
    Only the booking owner or an admin may cancel.
    """
    booking.assert_transition(Booking.Status.CANCELLED)

    booking.status = Booking.Status.CANCELLED
    booking.status_changed_at = timezone.now()
    booking.status_changed_by = cancelled_by
    booking.save(update_fields=['status', 'status_changed_at', 'status_changed_by'])

    # Restore capacity if the booking was for a class
    if booking.workout_class:
        WorkoutClass.objects.filter(pk=booking.workout_class_id).update(
            booked_count=max(0, booking.workout_class.booked_count - 1)
        )
    return booking


@transaction.atomic
def mark_booking(booking: Booking, new_status: str, admin_user) -> Booking:
    """
    Admin-only: advance a BOOKED booking to ATTENDED or MISSED.
    """
    if new_status not in (Booking.Status.ATTENDED, Booking.Status.MISSED):
        raise ValueError("Admins may only mark bookings as Attended or Missed via this method.")
    booking.assert_transition(new_status)

    booking.status = new_status
    booking.status_changed_at = timezone.now()
    booking.status_changed_by = admin_user
    booking.save(update_fields=['status', 'status_changed_at', 'status_changed_by'])
    return booking


# ─── Equipment booking ─────────────────────────────────────────────────────────

@transaction.atomic
def book_equipment(user, equipment: GymEquipment, slot_start, slot_end) -> Booking:
    """
    Book a piece of equipment for a time slot.
    Guards: no overlapping BOOKED slot for the same equipment and user.
    """
    if not equipment.is_active:
        raise ValueError("This equipment is currently unavailable.")
    if slot_start >= slot_end:
        raise ValueError("Slot end time must be after start time.")
    if slot_start < timezone.now():
        raise ValueError("You cannot book an equipment slot in the past.")

    # Check for overlapping bookings by ANY user on the same equipment
    overlapping = Booking.objects.filter(
        equipment=equipment,
        status=Booking.Status.BOOKED,
        slot_start__lt=slot_end,
        slot_end__gt=slot_start,
    )
    if overlapping.count() >= equipment.capacity:
        raise ValueError("No available slots for this equipment during the selected time.")

    booking = Booking.objects.create(
        user=user,
        equipment=equipment,
        status=Booking.Status.BOOKED,
        slot_start=slot_start,
        slot_end=slot_end,
    )
    GymEquipment.objects.filter(pk=equipment.pk).update(booking_count=equipment.booking_count + 1)
    return booking
