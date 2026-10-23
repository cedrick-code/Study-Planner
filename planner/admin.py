from django.contrib import admin

from .models import LocalHoliday, Profile, Task


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "due_date", "is_complete", "created_at")
    list_filter = ("is_complete", "due_date")
    search_fields = ("title", "user__username")


@admin.register(LocalHoliday)
class LocalHolidayAdmin(admin.ModelAdmin):
    list_display = ("name", "date", "note")
    list_filter = ("date",)
    search_fields = ("name",)