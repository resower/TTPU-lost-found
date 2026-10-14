from django.contrib import admin

from .models import MatchSuggestion


@admin.register(MatchSuggestion)
class MatchSuggestionAdmin(admin.ModelAdmin):
    list_display = ("lost_report", "stored_item", "found_report", "score", "created_by", "status")
    list_filter = ("status", "created_by")
