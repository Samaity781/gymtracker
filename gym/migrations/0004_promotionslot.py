"""
gym/migrations/0004_promotionslot.py

CR3: Adds the PromotionSlot model.

Design notes (for CW1B report evidence)
────────────────────────────────────────
- Uses GenericForeignKey (content_type + object_id) so one table serves both
  WorkoutClass and GymEquipment without duplicating the slot schema.
- Two CheckConstraints are enforced at the database level (not just Django):
    1. end_date >= start_date  — prevents logically impossible date windows.
    2. position in 1–5        — keeps the ordering bounded.
- A composite index on (slot_context, is_active, start_date, end_date) makes
  the "which slots are live right now?" query fast without a full table scan.
- The migration is fully reversible (operations list supports backwards migration).
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gym', '0003_rename_gym_promo_ct_obj_type_idx_gym_promoti_content_709427_idx'),
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PromotionSlot',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID',
                )),
                ('object_id', models.PositiveIntegerField()),
                ('slot_context', models.CharField(
                    choices=[
                        ('DASHBOARD_HERO',    'Dashboard — hero banner'),
                        ('DASHBOARD_SIDEBAR', 'Dashboard — sidebar panel'),
                        ('CLASS_LIST_TOP',    'Class list — top placement'),
                        ('EQUIPMENT_LIST',    'Equipment list — featured strip'),
                    ],
                    default='DASHBOARD_HERO',
                    max_length=24,
                )),
                ('position', models.PositiveSmallIntegerField(
                    default=1,
                    help_text='Lower numbers appear first (1 = top).',
                )),
                ('headline', models.CharField(blank=True, max_length=200)),
                ('call_to_action', models.CharField(
                    blank=True, default='View Details', max_length=80,
                )),
                ('start_date', models.DateField()),
                ('end_date',   models.DateField()),
                ('is_active',  models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                # Foreign keys
                ('content_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='contenttypes.contenttype',
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_promotion_slots',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name':       'Promotion Slot',
                'verbose_name_plural': 'Promotion Slots',
                'ordering': ['slot_context', 'position'],
            },
        ),

        # ── Database-level constraints (not just Django) ────────────────────
        migrations.AddConstraint(
            model_name='promotionslot',
            constraint=models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F('start_date')),
                name='promotionslot_end_after_start',
            ),
        ),
        migrations.AddConstraint(
            model_name='promotionslot',
            constraint=models.CheckConstraint(
                condition=models.Q(position__gte=1) & models.Q(position__lte=5),
                name='promotionslot_position_range',
            ),
        ),

        # ── Composite query-optimisation index ─────────────────────────────
        migrations.AddIndex(
            model_name='promotionslot',
            index=models.Index(
                fields=['slot_context', 'is_active', 'start_date', 'end_date'],
                name='gym_slot_ctx_dates_idx',
            ),
        ),
    ]
