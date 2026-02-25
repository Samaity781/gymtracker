"""
gym/migrations/0002_cr2_cr3_promotion_ranking_fields.py

Adds:
  - GymEquipment.view_count, impression_count, click_count
  - WorkoutClass.booking_count, impression_count, click_count
  - PromotionEvent model (CR3)
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('gym', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # GymEquipment — add view_count, impression_count, click_count
        migrations.AddField(
            model_name='gymequipment',
            name='view_count',
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name='gymequipment',
            name='impression_count',
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name='gymequipment',
            name='click_count',
            field=models.PositiveIntegerField(default=0, editable=False),
        ),

        # WorkoutClass — add booking_count, impression_count, click_count
        migrations.AddField(
            model_name='workoutclass',
            name='booking_count',
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name='workoutclass',
            name='impression_count',
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.AddField(
            model_name='workoutclass',
            name='click_count',
            field=models.PositiveIntegerField(default=0, editable=False),
        ),

        # PromotionEvent model
        migrations.CreateModel(
            name='PromotionEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField()),
                ('event_type', models.CharField(
                    choices=[('IMPRESSION', 'Impression'), ('CLICK', 'Click')],
                    max_length=12,
                )),
                ('occurred_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('source_page', models.CharField(blank=True, max_length=100)),
                ('content_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='contenttypes.contenttype',
                )),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='promotion_events',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-occurred_at'],
            },
        ),
        migrations.AddIndex(
            model_name='promotionevent',
            index=models.Index(
                fields=['content_type', 'object_id', 'event_type'],
                name='gym_promo_ct_obj_type_idx',
            ),
        ),
    ]
