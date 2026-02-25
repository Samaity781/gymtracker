"""
reviews/models.py
CR4: Reviews and Ratings.

Design decisions
────────────────
- Generic foreign key (ContentType) lets the same table serve both WorkoutClass
  and GymEquipment reviews without duplication.
- One review per user/item is enforced at the database level via UniqueConstraint.
- The moderation workflow uses a Status enum: PENDING → APPROVED or HIDDEN.
  Admins cannot delete reviews — they can only hide them — to preserve the audit
  trail (analogous to the booking state machine's terminal states).
- Aggregate rating is computed on demand via get_aggregate() rather than
  denormalised, keeping the model simple while still being efficient enough
  for the coursework scale.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count
from django.utils import timezone


class Review(models.Model):
    """A user review with a 1–5 star rating and optional comment."""

    class Status(models.TextChoices):
        PENDING  = 'PENDING',  'Pending moderation'
        APPROVED = 'APPROVED', 'Approved'
        HIDDEN   = 'HIDDEN',   'Hidden'

    # ── Generic target (WorkoutClass or GymEquipment) ─────────────────────────
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id    = models.PositiveIntegerField()
    item         = GenericForeignKey('content_type', 'object_id')

    # ── Review content ────────────────────────────────────────────────────────
    user    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    rating  = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='1 (poor) to 5 (excellent)',
    )
    comment = models.TextField(blank=True, max_length=1000)

    # ── Moderation ────────────────────────────────────────────────────────────
    status           = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    moderation_note  = models.TextField(
        blank=True,
        help_text='Admin-only note explaining moderation action.',
    )
    moderated_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='moderated_reviews',
    )
    moderated_at  = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['content_type', 'object_id', 'user'],
                name='one_review_per_user_per_item',
            )
        ]
        indexes = [
            models.Index(fields=['content_type', 'object_id', 'status']),
        ]

    def __str__(self):
        return f"{self.user.email} – {self.rating}★ – {self.status}"

    @property
    def stars_display(self):
        """Return filled/empty star strings for template rendering."""
        return '★' * self.rating + '☆' * (5 - self.rating)

    @property
    def is_editable(self):
        """A review can still be edited if it is PENDING (not yet moderated)."""
        return self.status == self.Status.PENDING

    def approve(self, admin_user, note: str = ''):
        """Transition to APPROVED — called from the moderation service."""
        self.status          = self.Status.APPROVED
        self.moderation_note = note
        self.moderated_by    = admin_user
        self.moderated_at    = timezone.now()
        self.save(update_fields=['status', 'moderation_note', 'moderated_by', 'moderated_at'])

    def hide(self, admin_user, note: str = ''):
        """Transition to HIDDEN — content is suppressed but not deleted."""
        self.status          = self.Status.HIDDEN
        self.moderation_note = note
        self.moderated_by    = admin_user
        self.moderated_at    = timezone.now()
        self.save(update_fields=['status', 'moderation_note', 'moderated_by', 'moderated_at'])

    # ── Class-level aggregate helper ──────────────────────────────────────────

    @classmethod
    def get_aggregate(cls, content_type, object_id) -> dict:
        """
        Return aggregate stats for all APPROVED reviews on a given item.

        Returns a dict with keys: avg_rating, total_count, star_breakdown.
        star_breakdown maps 1–5 to a count.
        """
        qs = cls.objects.filter(
            content_type=content_type,
            object_id=object_id,
            status=cls.Status.APPROVED,
        )
        agg = qs.aggregate(avg_rating=Avg('rating'), total_count=Count('pk'))

        star_breakdown = {}
        for star in range(1, 6):
            star_breakdown[star] = qs.filter(rating=star).count()

        return {
            'avg_rating':    round(agg['avg_rating'], 1) if agg['avg_rating'] else None,
            'total_count':   agg['total_count'],
            'star_breakdown': star_breakdown,
        }
