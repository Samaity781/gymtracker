from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('user', 'booking_target', 'status', 'booked_at', 'status_changed_by')
    list_filter = ('status',)
    search_fields = ('user__email',)
    readonly_fields = ('booked_at', 'status_changed_at')
