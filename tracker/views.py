"""
tracker/views.py
Epic 7: Personal Fitness Tracker views.
All views are member-only; there is no admin CRUD here (members own their own data).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    RoutineForm, RoutineItemFormSet, WorkoutEntryFormSet,
    WorkoutSessionForm, SetEntryForm,
)
from .models import Routine, WorkoutEntry, WorkoutSession
from . import services


# ─── Workout History ──────────────────────────────────────────────────────────

@login_required
def session_list(request):
    """FR-16: Chronological workout history."""
    sessions = (
        WorkoutSession.objects
        .filter(user=request.user)
        .prefetch_related('entries__sets')
        .order_by('-date')
    )
    summary = services.get_workout_summary(request.user)
    return render(request, 'tracker/session_list.html', {
        'sessions': sessions,
        'summary': summary,
    })


@login_required
def session_detail(request, pk):
    session = get_object_or_404(WorkoutSession, pk=pk, user=request.user)
    return render(request, 'tracker/session_detail.html', {'session': session})


@login_required
def session_create(request):
    """FR-15: Log a workout session with exercises."""
    if request.method == 'POST':
        form = WorkoutSessionForm(request.POST, user=request.user)
        formset = WorkoutEntryFormSet(request.POST, prefix='entries')
        if form.is_valid() and formset.is_valid():
            session = form.save(commit=False)
            session.user = request.user
            session.save()
            formset.instance = session
            formset.save()
            messages.success(request, "Workout session logged.")
            return redirect('tracker:session_detail', pk=session.pk)
    else:
        form = WorkoutSessionForm(user=request.user)
        formset = WorkoutEntryFormSet(prefix='entries')
    return render(request, 'tracker/session_form.html', {
        'form': form, 'formset': formset, 'action': 'Log',
    })


@login_required
def session_edit(request, pk):
    session = get_object_or_404(WorkoutSession, pk=pk, user=request.user)
    if request.method == 'POST':
        form = WorkoutSessionForm(request.POST, instance=session, user=request.user)
        formset = WorkoutEntryFormSet(request.POST, instance=session, prefix='entries')
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Session updated.")
            return redirect('tracker:session_detail', pk=session.pk)
    else:
        form = WorkoutSessionForm(instance=session, user=request.user)
        formset = WorkoutEntryFormSet(instance=session, prefix='entries')
    return render(request, 'tracker/session_form.html', {
        'form': form, 'formset': formset, 'action': 'Edit', 'session': session,
    })


@login_required
def session_delete(request, pk):
    session = get_object_or_404(WorkoutSession, pk=pk, user=request.user)
    if request.method == 'POST':
        session.delete()
        messages.success(request, "Session deleted.")
        return redirect('tracker:session_list')
    return render(request, 'tracker/session_confirm_delete.html', {'session': session})


# ─── Sets within a session entry ──────────────────────────────────────────────

@login_required
def entry_sets(request, entry_pk):
    """Manage sets for a single workout entry (inline add/edit)."""
    entry = get_object_or_404(WorkoutEntry, pk=entry_pk, session__user=request.user)
    SetFormSet = inlineformset_factory(
        WorkoutEntry, entry.sets.model,
        form=SetEntryForm,
        extra=1, can_delete=True,
    )
    if request.method == 'POST':
        formset = SetFormSet(request.POST, instance=entry)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Sets saved.")
            return redirect('tracker:session_detail', pk=entry.session.pk)
    else:
        formset = SetFormSet(instance=entry)
    return render(request, 'tracker/entry_sets.html', {'entry': entry, 'formset': formset})


# ─── Progress ─────────────────────────────────────────────────────────────────

@login_required
def progress_view(request):
    """FR-17: Progress metrics — personal records and volume chart data."""
    exercise_filter = request.GET.get('exercise', '').strip()
    records = services.get_personal_records(request.user)
    volume_data = services.get_volume_over_time(request.user, exercise_name=exercise_filter or None)
    return render(request, 'tracker/progress.html', {
        'records': records,
        'volume_data': volume_data,
        'exercise_filter': exercise_filter,
        'exercise_names': list(records.keys()),
    })


# ─── Routines ─────────────────────────────────────────────────────────────────

@login_required
def routine_list(request):
    routines = Routine.objects.filter(user=request.user).prefetch_related('items')
    return render(request, 'tracker/routine_list.html', {'routines': routines})


@login_required
def routine_create(request):
    """FR-18: Create a reusable workout routine."""
    if request.method == 'POST':
        form = RoutineForm(request.POST)
        formset = RoutineItemFormSet(request.POST, prefix='items')
        if form.is_valid() and formset.is_valid():
            routine = form.save(commit=False)
            routine.user = request.user
            routine.save()
            formset.instance = routine
            formset.save()
            messages.success(request, f'Routine "{routine.name}" created.')
            return redirect('tracker:routine_list')
    else:
        form = RoutineForm()
        formset = RoutineItemFormSet(prefix='items')
    return render(request, 'tracker/routine_form.html', {
        'form': form, 'formset': formset, 'action': 'Create',
    })


@login_required
def routine_edit(request, pk):
    routine = get_object_or_404(Routine, pk=pk, user=request.user)
    if request.method == 'POST':
        form = RoutineForm(request.POST, instance=routine)
        formset = RoutineItemFormSet(request.POST, instance=routine, prefix='items')
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Routine updated.")
            return redirect('tracker:routine_list')
    else:
        form = RoutineForm(instance=routine)
        formset = RoutineItemFormSet(instance=routine, prefix='items')
    return render(request, 'tracker/routine_form.html', {
        'form': form, 'formset': formset, 'action': 'Edit', 'routine': routine,
    })


@login_required
def routine_delete(request, pk):
    routine = get_object_or_404(Routine, pk=pk, user=request.user)
    if request.method == 'POST':
        routine.delete()
        messages.success(request, "Routine deleted.")
        return redirect('tracker:routine_list')
    return render(request, 'tracker/routine_confirm_delete.html', {'routine': routine})
