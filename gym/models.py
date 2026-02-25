"""
gym/models.py
Epic 3-5: Gym Equipment, Workout Classes, and Categories.
CR3: PromotionEvent — lightweight impression/click tracking for featured items.

WorkoutCategory is the shared taxonomy used by both equipment and classes.
Active/inactive flags provide soft-delete semantics so admins can hide items
without destroying booking history (important for data integrity).
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class WorkoutCategory(models.Model):
    """Shared taxonomy for both equipment and workout classes."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Bootstrap icon class, e.g. bi-bicycle")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Workout Category'
        verbose_name_plural = 'Workout Categories'

    def __str__(self):
        return self.name


class GymEquipment(models.Model):
    """
    A piece of gym equipment that members can book.
    capacity = how many people can use it simultaneously.
    """

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        WorkoutCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='equipment',
    )
    location = models.CharField(max_length=200, blank=True, help_text="e.g. 'Ground floor, Zone A'")
    capacity = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='equipment/', null=True, blank=True)

    # CR2: popularity counters used by ranking service
    booking_count = models.PositiveIntegerField(default=0, editable=False)
    view_count = models.PositiveIntegerField(default=0, editable=False)
    # CR3: promotional flag and denormalised counters for fast dashboard queries
    is_featured = models.BooleanField(default=False)
    impression_count = models.PositiveIntegerField(default=0, editable=False)
    click_count = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_featured', 'name']
        verbose_name = 'Gym Equipment'
        verbose_name_plural = 'Gym Equipment'

    def __str__(self):
        return self.name

    @property
    def status_label(self):
        return "Active" if self.is_active else "Inactive"

    @property
    def ctr(self):
        """Click-through rate as a percentage — CR3 analytics."""
        if self.impression_count == 0:
            return 0.0
        return round((self.click_count / self.impression_count) * 100, 1)


class WorkoutClass(models.Model):
    """
    A scheduled class (e.g. Spin, Yoga, HIIT) with finite capacity.
    start_time + duration_minutes defines the session window.
    """

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        WorkoutCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='classes',
    )
    instructor = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=200, blank=True)
    start_time = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    capacity = models.PositiveIntegerField(default=20)
    # Derived count maintained by booking service – avoids a COUNT query on every list
    booked_count = models.PositiveIntegerField(default=0, editable=False)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='classes/', null=True, blank=True)

    # CR2: popularity counters used by ranking service
    view_count = models.PositiveIntegerField(default=0, editable=False)
    booking_count = models.PositiveIntegerField(default=0, editable=False)
    # CR3: promotional flag and denormalised impression/click counters
    is_featured = models.BooleanField(default=False)
    impression_count = models.PositiveIntegerField(default=0, editable=False)
    click_count = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_time']
        verbose_name = 'Workout Class'
        verbose_name_plural = 'Workout Classes'

    def __str__(self):
        return f"{self.name} – {self.start_time.strftime('%d %b %Y %H:%M')}"

    @property
    def available_spaces(self):
        return max(0, self.capacity - self.booked_count)

    @property
    def is_full(self):
        return self.available_spaces == 0

    @property
    def is_upcoming(self):
        return self.start_time > timezone.now()

    @property
    def status_label(self):
        if not self.is_active:
            return "Inactive"
        if not self.is_upcoming:
            return "Past"
        if self.is_full:
            return "Full"
        return "Available"

    @property
    def ctr(self):
        """Click-through rate as a percentage — CR3 analytics."""
        if self.impression_count == 0:
            return 0.0
        return round((self.click_count / self.impression_count) * 100, 1)


# ─── CR3: Promotional Placement Tracking ──────────────────────────────────────

class PromotionEvent(models.Model):
    """
    CR3: Records each impression or click on a featured item.

    Uses a GenericForeignKey so it can reference either WorkoutClass or
    GymEquipment without duplicating the tracking table.  The denormalised
    counters on each model are kept in sync by the promotion_service — the
    raw events are preserved here for audit and potential future analytics.
    """

    class EventType(models.TextChoices):
        IMPRESSION = 'IMPRESSION', 'Impression'
        CLICK = 'CLICK', 'Click'

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    item = GenericForeignKey('content_type', 'object_id')

    event_type = models.CharField(max_length=12, choices=EventType.choices)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='promotion_events',
    )
    occurred_at = models.DateTimeField(default=timezone.now)
    # Lightweight extra context — what page triggered the impression/click
    source_page = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id', 'event_type']),
        ]

    def __str__(self):
        return f"{self.event_type} – {self.item} – {self.occurred_at:%d %b %Y %H:%M}"


# ─── CR3: Promotion Slots ──────────────────────────────────────────────────────

class PromotionSlot(models.Model):
    """
    CR3: Admin-managed promotional placement slot.

    Design rationale
    ────────────────
    PromotionEvent (above) is passive — it records what happened.
    PromotionSlot is active — it controls what *should* appear in a named
    position (e.g. "dashboard_hero", "class_list_banner") during a given
    date window.  This allows admins to schedule promotions in advance and
    set end dates so slots expire automatically without manual intervention.

    Schema decisions:
      - GenericForeignKey lets one table serve both WorkoutClass and
        GymEquipment without duplicating the slot logic.
      - position (1–5) determines the order when multiple slots are active
        for the same page context at the same time.
      - start_date / end_date are inclusive date bounds (timezone-aware
        comparisons done in the service layer).
      - is_active provides a manual on/off without deleting the record,
        preserving the scheduling history for reporting.

    Migration notes:
      The GenericForeignKey relies on django.contrib.contenttypes, which is
      already an installed app.  No additional dependency is introduced.
    """

    class SlotContext(models.TextChoices):
        DASHBOARD_HERO    = 'DASHBOARD_HERO',    'Dashboard — hero banner'
        DASHBOARD_SIDEBAR = 'DASHBOARD_SIDEBAR', 'Dashboard — sidebar panel'
        CLASS_LIST_TOP    = 'CLASS_LIST_TOP',    'Class list — top placement'
        EQUIPMENT_LIST    = 'EQUIPMENT_LIST',    'Equipment list — featured strip'

    # ── Which item is being promoted ──────────────────────────────────────────
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text='WorkoutClass or GymEquipment.',
    )
    object_id = models.PositiveIntegerField()
    item       = GenericForeignKey('content_type', 'object_id')

    # ── Slot configuration ────────────────────────────────────────────────────
    slot_context = models.CharField(
        max_length=24,
        choices=SlotContext.choices,
        default=SlotContext.DASHBOARD_HERO,
        help_text='Which page / position this slot occupies.',
    )
    position = models.PositiveSmallIntegerField(
        default=1,
        help_text='Lower numbers appear first when multiple slots are active (1 = top).',
    )
    headline = models.CharField(
        max_length=200,
        blank=True,
        help_text='Optional override headline shown in the slot (falls back to item name).',
    )
    call_to_action = models.CharField(
        max_length=80,
        blank=True,
        default='View Details',
        help_text='Button label shown in the slot.',
    )

    # ── Scheduling ────────────────────────────────────────────────────────────
    start_date = models.DateField(help_text='Slot becomes visible from this date (inclusive).')
    end_date   = models.DateField(help_text='Slot expires after this date (inclusive).')
    is_active  = models.BooleanField(
        default=True,
        help_text='Manual override: uncheck to pause without deleting.',
    )

    # ── Ownership / audit ─────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_promotion_slots',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['slot_context', 'position']
        verbose_name      = 'Promotion Slot'
        verbose_name_plural = 'Promotion Slots'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F('start_date')),
                name='promotionslot_end_after_start',
            ),
            models.CheckConstraint(
                condition=models.Q(position__gte=1) & models.Q(position__lte=5),
                name='promotionslot_position_range',
            ),
        ]
        indexes = [
            models.Index(
                fields=['slot_context', 'is_active', 'start_date', 'end_date'],
                name='gym_slot_ctx_dates_idx',
            ),
        ]

    def __str__(self):
        return f"[{self.slot_context}] pos={self.position} – {self.item} ({self.start_date} → {self.end_date})"

    @property
    def is_currently_live(self) -> bool:
        """
        True if the slot is active and today falls within the date window.
        This is a property for quick template/admin display — the service
        layer uses a queryset-level filter for actual scheduling logic.
        """
        today = timezone.now().date()
        return self.is_active and self.start_date <= today <= self.end_date

    @property
    def display_headline(self) -> str:
        """Return override headline or fall back to item name."""
        return self.headline or str(self.item)
