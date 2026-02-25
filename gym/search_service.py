"""
gym/search_service.py
CR1: Advanced Search Service.

Isolates all filter and search logic from the view layer so that:
  - The same logic can be applied to both classes and equipment.
  - Query parameters are validated in one place.
  - Tests can exercise search behaviour without a full HTTP cycle.

FR-19: combined text, category, date, and availability filters.
FR-20: filter state preserved in query string (handled by the view's GET form
        — this module operates on already-validated form data).
"""

from django.db.models import Q, QuerySet
from django.utils import timezone


def apply_class_filters(queryset: QuerySet, cleaned_data: dict) -> QuerySet:
    """
    Apply all class search filters from a validated ClassSearchForm.
    Returns a filtered (but not yet ordered/ranked) queryset.
    """
    q            = cleaned_data.get('q', '').strip()
    category     = cleaned_data.get('category')
    date_from    = cleaned_data.get('date_from')
    date_to      = cleaned_data.get('date_to')
    available_only = cleaned_data.get('available_only', False)
    upcoming_only  = cleaned_data.get('upcoming_only', False)

    if q:
        queryset = queryset.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(instructor__icontains=q) |
            Q(location__icontains=q) |
            Q(category__name__icontains=q)  # also search the category name
        )

    if category:
        queryset = queryset.filter(category=category)

    if date_from:
        queryset = queryset.filter(start_time__date__gte=date_from)

    if date_to:
        queryset = queryset.filter(start_time__date__lte=date_to)

    if upcoming_only:
        queryset = queryset.filter(start_time__gte=timezone.now())

    # available_only must be done in Python because available_spaces is a property
    if available_only:
        ids = [c.pk for c in queryset if not c.is_full]
        queryset = queryset.filter(pk__in=ids)

    return queryset


def apply_equipment_filters(queryset: QuerySet, cleaned_data: dict) -> QuerySet:
    """
    Apply all equipment search filters.  Equipment has no schedule so
    date fields are not relevant, but text, category, and availability apply.
    """
    q        = cleaned_data.get('q', '').strip()
    category = cleaned_data.get('category')

    if q:
        queryset = queryset.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(location__icontains=q) |
            Q(category__name__icontains=q)
        )

    if category:
        queryset = queryset.filter(category=category)

    return queryset


def build_filter_querystring(get_params: dict, exclude_keys=('page', 'ranking')) -> str:
    """
    Rebuild a query string from GET params while stripping pagination and
    ranking keys.  Used in templates to preserve filter state across page
    changes and ranking toggles.

    Example:
        ?q=spin&category=3&ranking=default  →  q=spin&category=3
    """
    from urllib.parse import urlencode
    filtered = {k: v for k, v in get_params.items() if k not in exclude_keys}
    return urlencode(filtered)


def get_active_filter_count(cleaned_data: dict) -> int:
    """Return a count of how many non-trivial filters are active — used in UI."""
    active = 0
    if cleaned_data.get('q'):
        active += 1
    if cleaned_data.get('category'):
        active += 1
    if cleaned_data.get('date_from') or cleaned_data.get('date_to'):
        active += 1
    if cleaned_data.get('available_only'):
        active += 1
    if cleaned_data.get('upcoming_only'):
        active += 1
    return active
