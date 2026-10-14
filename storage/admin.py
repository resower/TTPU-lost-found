from django.contrib import admin

from .models import Handover, ItemStatusLog, StoredItem


@admin.register(StoredItem)
class StoredItemAdmin(admin.ModelAdmin):
    list_display = ("shelf_code", "title", "category", "received_at", "retention_until", "status")
    list_filter = ("status", "category")
    search_fields = ("title", "description", "shelf_code")


@admin.register(ItemStatusLog)
class ItemStatusLogAdmin(admin.ModelAdmin):
    list_display = ("item", "old_status", "new_status", "staff", "timestamp")
    list_filter = ("new_status",)


@admin.register(Handover)
class HandoverAdmin(admin.ModelAdmin):
    list_display = ("stored_item", "receiver_name", "id_last4", "staff", "handed_at")
