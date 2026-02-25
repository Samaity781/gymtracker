"""gym/admin.py — Django admin registrations for gym models."""
from django.contrib import admin
from .models import GymEquipment, PromotionEvent, PromotionSlot, WorkoutCategory, WorkoutClass


@admin.register(WorkoutCategory)
class WorkoutCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter  = ('is_active',)
    search_fields = ('name',)


@admin.register(WorkoutClass)
class WorkoutClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'instructor', 'start_time', 'capacity',
                    'booked_count', 'is_featured', 'is_active')
    list_filter  = ('is_active', 'is_featured', 'category')
    search_fields = ('name', 'instructor')


@admin.register(GymEquipment)
class GymEquipmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'capacity', 'is_featured', 'is_active')
    list_filter  = ('is_active', 'is_featured', 'category')
    search_fields = ('name',)


@admin.register(PromotionEvent)
class PromotionEventAdmin(admin.ModelAdmin):
    list_display  = ('event_type', 'item', 'user', 'occurred_at', 'source_page')
    list_filter   = ('event_type', 'source_page')
    readonly_fields = ('content_type', 'object_id', 'occurred_at')


@admin.register(PromotionSlot)
class PromotionSlotAdmin(admin.ModelAdmin):
    """
    CR3: Admin interface for managing scheduled promotional placement slots.
    The `is_currently_live` column gives admins an at-a-glance status without
    needing to compare today's date manually.
    """
    list_display  = ('__str__', 'slot_context', 'position', 'start_date',
                     'end_date', 'is_active', 'is_currently_live')
    list_filter   = ('slot_context', 'is_active')
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    ordering = ('slot_context', 'position')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
