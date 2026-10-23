from django.contrib import admin

from .models import StudyTask


@admin.register(StudyTask)
class StudyTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'due_date', 'completed', 'created_at')
    list_filter = ('completed', 'due_date')
    search_fields = ('title', 'user__username')
