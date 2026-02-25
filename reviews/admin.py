from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display  = ('user', 'item', 'rating', 'status', 'created_at', 'moderated_by')
    list_filter   = ('status', 'rating', 'content_type')
    search_fields = ('user__email', 'comment')
    readonly_fields = ('created_at', 'updated_at', 'moderated_at', 'moderated_by')
    ordering = ('-created_at',)
