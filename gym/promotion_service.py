"""
gym/promotion_service.py
CR3: Promotional Placement Service.

Handles recording of impressions and clicks for featured items, and provides
analytics aggregation for the admin dashboard.

Design decisions:
  - Raw events are stored in PromotionEvent for audit purposes.
  - Denormalised counters (impression_count, click_count) on each model are
    updated atomically to keep list-page queries fast.
  - Impressions are recorded per page load (not de-duplicated per session) —
    appropriate for a simple coursework implementation.
  - Clicks are recorded when a user follows a "featured" link, via a thin
    redirect view that records the event before passing to the detail page.
"""

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from .models import GymEquipment, PromotionEvent, WorkoutClass


# ── Impression recording ──────────────────────────────────────────────────────

@transaction.atomic
def record_impressions(items, user, source_page: str = 'dashboard'):
    """
    Record an IMPRESSION event for each item in the supplied iterable.
    Called from the dashboard/list views whenever featured items are rendered.

    Using a bulk_create here avoids N database round-trips for a page with
    multiple featured items.
    """
    if not items:
        return

    events = []
    ct_class     = ContentType.objects.get_for_model(WorkoutClass)
    ct_equipment = ContentType.objects.get_for_model(GymEquipment)

    for item in items:
        ct = ct_class if isinstance(item, WorkoutClass) else ct_equipment
        events.append(PromotionEvent(
            content_type=ct,
            object_id=item.pk,
            event_type=PromotionEvent.EventType.IMPRESSION,
            user=user if user.is_authenticated else None,
            source_page=source_page,
        ))

    PromotionEvent.objects.bulk_create(events)

    # Update denormalised counters atomically so we can query them cheaply
    class_ids = [item.pk for item in items if isinstance(item, WorkoutClass)]
    equip_ids = [item.pk for item in items if isinstance(item, GymEquipment)]

    if class_ids:
        WorkoutClass.objects.filter(pk__in=class_ids).update(
            impression_count=_f_increment('impression_count', 1)
        )
    if equip_ids:
        GymEquipment.objects.filter(pk__in=equip_ids).update(
            impression_count=_f_increment('impression_count', 1)
        )


@transaction.atomic
def record_click(item, user, source_page: str = 'dashboard'):
    """Record a single CLICK event for a featured item."""
    ct = ContentType.objects.get_for_model(item.__class__)
    PromotionEvent.objects.create(
        content_type=ct,
        object_id=item.pk,
        event_type=PromotionEvent.EventType.CLICK,
        user=user if user.is_authenticated else None,
        source_page=source_page,
    )
    item.__class__.objects.filter(pk=item.pk).update(
        click_count=_f_increment('click_count', 1)
    )


def _f_increment(field_name: str, amount: int):
    """Return an F() expression for incrementing a counter field safely."""
    from django.db.models import F
    return F(field_name) + amount


# ── Analytics aggregation ─────────────────────────────────────────────────────

def get_promotion_analytics():
    """
    Return a list of dicts summarising promotion performance for all
    currently-featured items.  Used by the admin analytics view.
    """
    results = []

    for cls in WorkoutClass.objects.filter(is_featured=True):
        results.append({
            'item': cls,
            'item_type': 'Class',
            'impressions': cls.impression_count,
            'clicks': cls.click_count,
            'ctr': cls.ctr,
        })

    for eq in GymEquipment.objects.filter(is_featured=True):
        results.append({
            'item': eq,
            'item_type': 'Equipment',
            'impressions': eq.impression_count,
            'clicks': eq.click_count,
            'ctr': eq.ctr,
        })

    # Sort by impressions descending
    return sorted(results, key=lambda r: r['impressions'], reverse=True)


# ── PromotionSlot scheduling ──────────────────────────────────────────────────

def get_active_slots(slot_context: str):
    """
    CR3: Return all live PromotionSlots for a given context, ordered by position.

    "Live" means: is_active=True AND today falls within [start_date, end_date].
    Called from the dashboard/list views to populate scheduled promotions.

    Returns a queryset of PromotionSlot objects with prefetched content_type,
    ready for template iteration.
    """
    from .models import PromotionSlot
    from django.utils import timezone as tz
    today = tz.now().date()
    return (
        PromotionSlot.objects
        .filter(
            slot_context=slot_context,
            is_active=True,
            start_date__lte=today,
            end_date__gte=today,
        )
        .select_related('content_type', 'created_by')
        .order_by('position')
    )


def get_slot_summary():
    """Return all slots grouped by context for the admin overview page."""
    from .models import PromotionSlot
    from django.utils import timezone
    today = timezone.now().date()
    slots = PromotionSlot.objects.select_related('content_type', 'created_by').order_by(
        'slot_context', 'position'
    )
    result = []
    for slot in slots:
        result.append({
            'slot': slot,
            'is_live': slot.is_currently_live,
            'context_label': slot.get_slot_context_display(),
        })
    return result
