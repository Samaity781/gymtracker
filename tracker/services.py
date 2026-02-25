"""
tracker/services.py
Progress metric calculations for FR-17.

Keeping these here rather than as model class methods means:
- They can be tested without creating full model instances.
- They can be swapped out or extended (e.g. Chart.js data formatting) independently.
"""

from collections import defaultdict
from django.db.models import Sum, Max
from .models import WorkoutSession, SetEntry


def get_volume_over_time(user, exercise_name: str = None, limit: int = 12):
    """
    Return a list of (date, total_volume_kg) tuples in chronological order.
    If exercise_name is provided, filter to that exercise only.
    Suitable for passing to Chart.js as labels + data arrays.
    """
    sessions = (
        WorkoutSession.objects
        .filter(user=user)
        .order_by('date')
        .prefetch_related('entries__sets')
    )
    if limit:
        sessions = sessions[:limit]

    result = []
    for session in sessions:
        volume = 0
        for entry in session.entries.all():
            if exercise_name and entry.exercise_name.lower() != exercise_name.lower():
                continue
            for s in entry.sets.all():
                volume += s.reps * float(s.weight_kg)
        result.append({'date': str(session.date), 'volume': round(volume, 2)})
    return result


def get_personal_records(user):
    """
    Return a dict of exercise_name → {max_weight_kg, max_reps_at_max_weight, date}.
    Looks across all sessions for the heaviest single set per exercise.
    """
    records = {}
    sessions = (
        WorkoutSession.objects
        .filter(user=user)
        .prefetch_related('entries__sets')
        .order_by('date')
    )
    for session in sessions:
        for entry in session.entries.all():
            name = entry.exercise_name
            for s in entry.sets.all():
                if s.is_warmup:
                    continue
                if name not in records or float(s.weight_kg) > records[name]['max_weight_kg']:
                    records[name] = {
                        'max_weight_kg': float(s.weight_kg),
                        'reps': s.reps,
                        'date': str(session.date),
                    }
    return records


def get_workout_summary(user):
    """High-level stats for the dashboard/profile overview."""
    total_sessions = WorkoutSession.objects.filter(user=user).count()
    exercise_names = (
        WorkoutSession.objects
        .filter(user=user)
        .values_list('entries__exercise_name', flat=True)
        .distinct()
    )
    unique_exercises = len([e for e in exercise_names if e])
    return {
        'total_sessions': total_sessions,
        'unique_exercises': unique_exercises,
    }
