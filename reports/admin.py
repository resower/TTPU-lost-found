from django.contrib import admin

from .models import FoundReport, LostReport, TelegramUser


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ("display_name", "username", "telegram_id", "language", "is_blocked")
    list_filter = ("language", "is_blocked")
    search_fields = ("display_name", "username")


@admin.register(LostReport)
class LostReportAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "reporter", "date_lost", "status")
    list_filter = ("status", "category")
    search_fields = ("title", "description")


@admin.register(FoundReport)
class FoundReportAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "reporter", "date_found", "kept_by_finder", "status")
    list_filter = ("status", "category", "kept_by_finder")
    search_fields = ("title", "description")
