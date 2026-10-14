"""Small helpers that create test data. Every app's tests use them.

`AppTestCase` also switches Telegram off (no token), so no test can send a real message.
"""

import itertools
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from catalog.models import Category, Color, Location
from reports.models import FoundReport, LostReport, TelegramUser
from storage.models import StoredItem

_numbers = itertools.count(1)


@override_settings(
    BOT_TOKEN="",
    OFFICE_GROUP_ID="",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],  # fast, tests only
)
class AppTestCase(TestCase):
    pass


def make_staff(username="staff"):
    user, created = get_user_model().objects.get_or_create(
        username=username, defaults={"is_staff": True}
    )
    if created:
        user.set_password("pass12345")
        user.save()
    return user


def make_category(name="Bags", retention_days=60):
    category, _created = Category.objects.get_or_create(
        name_en=name,
        defaults={
            "name_uz": name,
            "name_ru": name,
            "emoji": "🎒",
            "retention_days": retention_days,
        },
    )
    return category


def make_color(name="Blue"):
    color, _created = Color.objects.get_or_create(
        name_en=name, defaults={"name_uz": name, "name_ru": name}
    )
    return color


def make_building(name="Main building"):
    return Location.objects.get_or_create(name=name, parent=None)[0]


def make_area(building=None, name="Library"):
    building = building or make_building()
    return Location.objects.get_or_create(name=name, parent=building)[0]


def make_user(language="en"):
    n = next(_numbers)
    return TelegramUser.objects.create(
        telegram_id=1000 + n, username=f"user{n}", display_name=f"User {n}", language=language
    )


def make_lost(**fields):
    defaults = {
        "reporter": make_user(),
        "category": make_category(),
        "title": "Blue backpack",
        "description": "Backpack with notebooks",
        "color": make_color(),
        "date_lost": timezone.localdate() - timedelta(days=3),
    }
    return LostReport.objects.create(**{**defaults, **fields})


def make_found(**fields):
    defaults = {
        "reporter": make_user(),
        "category": make_category(),
        "title": "Blue backpack",
        "description": "Backpack with notebooks",
        "color": make_color(),
        "location": make_area(),
        "date_found": timezone.localdate() - timedelta(days=2),
    }
    return FoundReport.objects.create(**{**defaults, **fields})


def make_item(**fields):
    """A StoredItem on the shelf. The shelf code is unique unless you pass one."""
    defaults = {
        "category": make_category(),
        "title": "Blue backpack",
        "description": "Backpack with notebooks",
        "color": make_color(),
        "shelf_code": f"T{next(_numbers)}",
        "received_by": make_staff(),
    }
    return StoredItem.objects.create(**{**defaults, **fields})
