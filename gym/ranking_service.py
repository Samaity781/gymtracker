"""
gym/ranking_service.py
CR2: Intelligent Ranking Service.

Design rationale
────────────────
Ranking is intentionally rule-based rather than ML-based.  This keeps the
logic auditable, testable, and explainable — which matters both for the
coursework demonstration and for a gym operator who might want to understand
why certain classes are surfaced.

Score components (all capped to avoid any single signal dominating):
  ┌──────────────────┬───────────┬──────────────────────────────────────────┐
  │ Component        │ Max pts   │ Rationale                                │
  ├──────────────────┼───────────┼──────────────────────────────────────────┤
  │ Featured flag    │ 60        │ Admin-curated prominence                 │
  │ Availability     │ 30        │ Bookable items rank above full ones       │
  │ Popularity       │ 20        │ view_count + booking_count (capped)      │
  │ Recency          │ 20        │ Upcoming items preferred over far-future  │
  │ Category boost   │ 10        │ Items in high-activity categories        │
  └──────────────────┴───────────┴──────────────────────────────────────────┘
  Maximum possible score: 140 pts (normalised to 0–100 for display)

The admin toggle (request.GET ranking=smart) switches between default
(featured-first, then chronological) and intelligent ordering.
"""

from datetime import timedelta
from django.utils import timezone


# ── Score weights — keep them named so tests and documentation stay in sync ──
WEIGHT_FEATURED     = 60
WEIGHT_AVAILABILITY = 30
WEIGHT_POPULARITY   = 20
WEIGHT_RECENCY      = 20
WEIGHT_CATEGORY     = 10
MAX_RAW_SCORE       = WEIGHT_FEATURED + WEIGHT_AVAILABILITY + WEIGHT_POPULARITY + WEIGHT_RECENCY + WEIGHT_CATEGORY

# Popularity signals are capped to prevent viral items monopolising results
VIEW_COUNT_CAP      = 200
BOOKING_COUNT_CAP   = 100


def score_class(workout_class) -> float:
    """
    Compute a 0–100 relevance score for a WorkoutClass.
    Returns a float — higher is more relevant.
    """
    raw = 0.0

    # 1. Featured flag — admin editorial signal
    if workout_class.is_featured:
        raw += WEIGHT_FEATURED

    # 2. Availability ratio — full classes are less useful to surfacing
    if workout_class.capacity > 0:
        availability_ratio = workout_class.available_spaces / workout_class.capacity
        raw += availability_ratio * WEIGHT_AVAILABILITY

    # 3. Popularity — composite of views and bookings, both capped
    normalised_views    = min(workout_class.view_count, VIEW_COUNT_CAP) / VIEW_COUNT_CAP
    normalised_bookings = min(workout_class.booking_count, BOOKING_COUNT_CAP) / BOOKING_COUNT_CAP
    popularity = (normalised_views * 0.4 + normalised_bookings * 0.6)  # bookings weighted higher
    raw += popularity * WEIGHT_POPULARITY

    # 4. Recency — prefer classes starting within the next 7 days
    if workout_class.is_upcoming:
        days_away = (workout_class.start_time - timezone.now()).days
        if days_away <= 1:
            raw += WEIGHT_RECENCY           # imminent
        elif days_away <= 7:
            raw += WEIGHT_RECENCY * 0.75    # this week
        else:
            raw += WEIGHT_RECENCY * 0.25    # further out

    # 5. Category activity boost — categories with more active classes rank slightly higher
    if workout_class.category_id:
        # Lightweight proxy: number of classes in the same category
        sibling_count = workout_class.category.classes.filter(is_active=True).count()
        if sibling_count >= 3:
            raw += WEIGHT_CATEGORY

    return round((raw / MAX_RAW_SCORE) * 100, 2)


def score_equipment(equipment) -> float:
    """
    Compute a 0–100 relevance score for a GymEquipment item.
    Simplified variant — equipment has no scheduling so recency weight
    is replaced by a utilisation proxy.
    """
    raw = 0.0

    if equipment.is_featured:
        raw += WEIGHT_FEATURED

    # Availability: always assume full capacity is available for equipment
    # (slot availability is dynamic; we use booking_count as utilisation signal)
    utilisation_proxy = min(equipment.booking_count, BOOKING_COUNT_CAP) / max(BOOKING_COUNT_CAP, 1)
    availability_score = 1 - min(utilisation_proxy, 1)  # higher = more available
    raw += availability_score * WEIGHT_AVAILABILITY

    normalised_views    = min(equipment.view_count, VIEW_COUNT_CAP) / VIEW_COUNT_CAP
    normalised_bookings = min(equipment.booking_count, BOOKING_COUNT_CAP) / BOOKING_COUNT_CAP
    popularity = (normalised_views * 0.4 + normalised_bookings * 0.6)
    raw += popularity * WEIGHT_POPULARITY

    # No recency signal for equipment; add category boost instead
    raw += WEIGHT_RECENCY * 0.5  # flat bonus so equipment isn't penalised vs classes

    if equipment.category_id:
        sibling_count = equipment.category.equipment.filter(is_active=True).count()
        if sibling_count >= 2:
            raw += WEIGHT_CATEGORY

    return round((raw / MAX_RAW_SCORE) * 100, 2)


def rank_classes(queryset, descending=True):
    """
    Apply intelligent ranking to a WorkoutClass queryset.
    Returns a sorted list (not a queryset — scores are computed in Python).
    Each item is annotated with a .ranking_score attribute for optional display.
    """
    scored = []
    for cls in queryset:
        cls.ranking_score = score_class(cls)
        scored.append(cls)
    return sorted(scored, key=lambda c: c.ranking_score, reverse=descending)


def rank_equipment(queryset, descending=True):
    """Apply intelligent ranking to a GymEquipment queryset."""
    scored = []
    for eq in queryset:
        eq.ranking_score = score_equipment(eq)
        scored.append(eq)
    return sorted(scored, key=lambda e: e.ranking_score, reverse=descending)


def get_score_breakdown(item) -> dict:
    """
    Return a human-readable breakdown of score components.
    Used by the admin ranking debug view so operators can understand results.
    """
    is_class = hasattr(item, 'start_time')
    total = score_class(item) if is_class else score_equipment(item)

    breakdown = {
        'total_score': total,
        'featured': WEIGHT_FEATURED if item.is_featured else 0,
        'view_count': item.view_count,
        'booking_count': item.booking_count,
    }
    if is_class:
        breakdown['is_upcoming'] = item.is_upcoming
        breakdown['available_spaces'] = item.available_spaces
        breakdown['capacity'] = item.capacity
    return breakdown
