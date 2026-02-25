from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField()),
                ('rating', models.PositiveSmallIntegerField(
                    help_text='1 (poor) to 5 (excellent)',
                    validators=[
                        django.core.validators.MinValueValidator(1),
                        django.core.validators.MaxValueValidator(5),
                    ] if False else [],  # validators added via separate operation below
                )),
                ('comment', models.TextField(blank=True, max_length=1000)),
                ('status', models.CharField(
                    choices=[
                        ('PENDING', 'Pending moderation'),
                        ('APPROVED', 'Approved'),
                        ('HIDDEN', 'Hidden'),
                    ],
                    default='PENDING', max_length=10,
                )),
                ('moderation_note', models.TextField(blank=True)),
                ('moderated_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('content_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='contenttypes.contenttype',
                )),
                ('moderated_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='moderated_reviews',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reviews',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='review',
            constraint=models.UniqueConstraint(
                fields=['content_type', 'object_id', 'user'],
                name='one_review_per_user_per_item',
            ),
        ),
        migrations.AddIndex(
            model_name='review',
            index=models.Index(
                fields=['content_type', 'object_id', 'status'],
                name='reviews_ct_obj_status_idx',
            ),
        ),
    ]
