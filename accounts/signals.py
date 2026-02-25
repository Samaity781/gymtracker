"""
accounts/signals.py
Ensures a MemberProfile row is created whenever a new User is saved.
Using post_save rather than overriding save() keeps the model lean
and the side-effect visible and removable.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, MemberProfile


@receiver(post_save, sender=User)
def create_member_profile(sender, instance, created, **kwargs):
    if created and instance.role == User.Role.MEMBER:
        MemberProfile.objects.get_or_create(user=instance)
