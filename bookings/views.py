"""
bookings/views.py
Epic 6: Views delegate to bookings.services — zero business logic here.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required
from gym.models import GymEquipment, WorkoutClass
from .models import Booking
from . import services


# ─── Member booking flow ───────────────────────────────────────────────────────

@login_required
@require_POST
def book_class(request, pk):
    workout_class = get_object_or_404(WorkoutClass, pk=pk, is_active=True)
    try:
        services.book_class(request.user, workout_class)
        messages.success(request, f"You have been booked onto '{workout_class.name}'.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect('gym:class_detail', pk=pk)


@login_required
@require_POST
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    # Ownership check: member can only cancel their own bookings
    if booking.user != request.user and not request.user.is_admin_role:
        messages.error(request, "You do not have permission to cancel this booking.")
        return redirect('bookings:my_bookings')
    try:
        services.cancel_booking(booking, cancelled_by=request.user)
        messages.success(request, "Booking cancelled.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect('bookings:my_bookings')


@login_required
def my_bookings(request):
    bookings = (
        Booking.objects
        .filter(user=request.user)
        .select_related('workout_class__category', 'equipment__category')
        .order_by('-booked_at')
    )
    return render(request, 'bookings/my_bookings.html', {'bookings': bookings})


# ─── Equipment booking ─────────────────────────────────────────────────────────

@login_required
def book_equipment_view(request, pk):
    equipment = get_object_or_404(GymEquipment, pk=pk, is_active=True)
    if request.method == 'POST':
        from bookings.forms import EquipmentBookingForm
        form = EquipmentBookingForm(request.POST)
        if form.is_valid():
            try:
                services.book_equipment(
                    request.user, equipment,
                    form.cleaned_data['slot_start'],
                    form.cleaned_data['slot_end'],
                )
                messages.success(request, f"Equipment '{equipment.name}' booked successfully.")
                return redirect('bookings:my_bookings')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        from bookings.forms import EquipmentBookingForm
        form = EquipmentBookingForm()
    return render(request, 'bookings/book_equipment.html', {'equipment': equipment, 'form': form})


# ─── Admin booking management ──────────────────────────────────────────────────

@admin_required
def admin_booking_list(request):
    status_filter = request.GET.get('status', '')
    bookings = Booking.objects.all().select_related(
        'user', 'workout_class', 'equipment', 'status_changed_by'
    ).order_by('-booked_at')
    if status_filter:
        bookings = bookings.filter(status=status_filter)
    return render(request, 'bookings/admin/booking_list.html', {
        'bookings': bookings,
        'status_choices': Booking.Status.choices,
        'status_filter': status_filter,
    })


@admin_required
@require_POST
def admin_mark_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    new_status = request.POST.get('new_status')
    try:
        services.mark_booking(booking, new_status, admin_user=request.user)
        messages.success(request, f"Booking marked as {new_status.lower()}.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect('bookings:admin_booking_list')
