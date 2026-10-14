from django.contrib import admin

from .models import JobState


@admin.register(JobState)
class JobStateAdmin(admin.ModelAdmin):
    list_display = ("name", "last_run_at")
