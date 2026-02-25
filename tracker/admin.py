from django.contrib import admin
from .models import WorkoutSession, WorkoutEntry, SetEntry, Routine, RoutineItem


class WorkoutEntryInline(admin.TabularInline):
    model = WorkoutEntry
    extra = 0


class SetEntryInline(admin.TabularInline):
    model = SetEntry
    extra = 0


@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'date', 'start_time')
    list_filter = ('date',)
    search_fields = ('user__email', 'name')
    inlines = [WorkoutEntryInline]


@admin.register(WorkoutEntry)
class WorkoutEntryAdmin(admin.ModelAdmin):
    list_display = ('exercise_name', 'session')
    inlines = [SetEntryInline]


@admin.register(Routine)
class RoutineAdmin(admin.ModelAdmin):
    list_display = ('name', 'user')
    search_fields = ('name', 'user__email')
