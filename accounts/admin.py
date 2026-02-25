from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, MemberProfile


class MemberProfileInline(admin.StackedInline):
    model = MemberProfile
    can_delete = False
    verbose_name_plural = 'Member Profile'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    inlines = [MemberProfileInline]

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Role & Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'membership_start')
    search_fields = ('user__email', 'user__first_name')
