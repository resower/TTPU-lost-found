from django.contrib import admin

from .models import Category, Color, Location


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "floor")
    list_filter = ("parent",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("emoji", "name_en", "name_uz", "name_ru", "retention_days")


@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ("name_en", "name_uz", "name_ru")
