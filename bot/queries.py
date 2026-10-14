"""All database work of the bot, as plain functions.

Handlers call them through `db()` (see db.py), so the handlers stay short and
this file is easy to read and test.
"""

from datetime import date, timedelta

from django.utils import timezone

from catalog.models import Category, Color, Location
from matching import services as matching
from matching.models import MatchSuggestion
from reports.models import FoundReport, LostReport, TelegramUser
from storage.models import StoredItem

from .strings import t

RECENT_DAYS = 30
MY_REPORTS_LIMIT = 10


# --- users ---


def get_or_create_user(tg_user):
    username = tg_user.username or ""
    name = tg_user.full_name[:128]
    user, created = TelegramUser.objects.get_or_create(
        telegram_id=tg_user.id, defaults={"username": username, "display_name": name}
    )
    if not created and (user.username, user.display_name) != (username, name):
        user.username, user.display_name = username, name
        user.save(update_fields=["username", "display_name"])
    return user


def set_language(user, lang):
    user.language = lang
    user.save(update_fields=["language"])


# --- choices for the wizard keyboards: lists of (id, label) ---


def categories(lang):
    return [(c.id, f"{c.emoji} {c.label(lang)}") for c in Category.objects.all()]


def colors(lang):
    return [(c.id, c.label(lang)) for c in Color.objects.all()]


def buildings():
    return [(b.id, b.name) for b in Location.objects.filter(parent=None)]


def areas(building_id):
    return [(a.id, a.name) for a in Location.objects.filter(parent_id=building_id)]


# --- reports ---


def summary_fields(data, lang):
    """Readable labels for the wizard summary."""
    category = Category.objects.get(pk=data["category_id"])
    color = Color.objects.get(pk=data["color_id"])
    location = Location.objects.filter(pk=data.get("location_id")).first()
    return {
        "category": f"{category.emoji} {category.label(lang)}",
        "color": color.label(lang),
        "location": str(location) if location else "—",
    }


def save_report(user, data):
    """Create a LostReport or FoundReport from the finished wizard data."""
    common = {
        "reporter": user,
        "category_id": data["category_id"],
        "title": data["title"],
        "description": data["description"],
        "color_id": data["color_id"],
        "photo_file_id": data.get("photo_file_id", ""),
    }
    when = date.fromisoformat(data["date"])
    if data["kind"] == "lost":
        return LostReport.objects.create(
            **common, location_id=data.get("location_id"), date_lost=when
        )
    return FoundReport.objects.create(
        **common,
        location_id=data["location_id"],
        date_found=when,
        kept_by_finder=data.get("kept", False),
        share_contact=data.get("share_contact", False),
    )


def my_reports(user, lang):
    """The user's newest reports as dicts: text plus the action button they can use."""
    rows = []
    for report in LostReport.objects.filter(reporter=user)[:MY_REPORTS_LIMIT]:
        action = {"open": "cancel", "expired": "reopen"}.get(report.status)
        rows.append(("lost", report, action))
    for report in FoundReport.objects.filter(reporter=user)[:MY_REPORTS_LIMIT]:
        rows.append(("found", report, "cancel" if report.status == "open" else None))
    rows.sort(key=lambda row: row[1].created_at, reverse=True)
    return [
        {
            "kind": kind,
            "id": report.id,
            "title": report.title,
            "action": action,
            "line": t(
                lang,
                "mine_line",
                kind=t(lang, f"kind_{kind}"),
                title=report.title,
                status=t(lang, f"status_{report.status}"),
            ),
        }
        for kind, report, action in rows[:MY_REPORTS_LIMIT]
    ]


def cancel_report(user, kind, pk):
    model = LostReport if kind == "lost" else FoundReport
    report = model.objects.filter(pk=pk, reporter=user, status="open").first()
    if report is None:
        return False
    report.status = "cancelled"
    report.save(update_fields=["status"])
    return True


def reopen_report(user, pk):
    report = LostReport.objects.filter(pk=pk, reporter=user, status="expired").first()
    if report is None:
        return False
    report.status = LostReport.Status.OPEN
    report.reopened_at = timezone.now()
    report.save(update_fields=["status", "reopened_at"])
    return True


# --- recent found items ---


def recent_cards(lang, category_id=0):
    """Found items from the last 30 days: items on the shelf and items the finder kept."""
    since = timezone.now() - timedelta(days=RECENT_DAYS)
    items = StoredItem.objects.filter(
        status=StoredItem.Status.IN_STORAGE, received_at__gte=since
    ).select_related("category", "found_report__location__parent")
    kept = FoundReport.objects.filter(
        status=FoundReport.Status.OPEN, kept_by_finder=True, created_at__gte=since
    ).select_related("category", "location__parent", "reporter")
    if category_id:
        items = items.filter(category_id=category_id)
        kept = kept.filter(category_id=category_id)

    cards = []
    for item in items:
        found = item.found_report
        cards.append(
            _card(
                lang,
                "item",
                item,
                item.found_date,
                item.found_location,
                photo_id=found.photo_file_id if found else "",
                photo_path=item.photo.path if item.photo else "",
            )
        )
    for report in kept:
        # The finder's Telegram is shown only if they agreed in the found wizard.
        contact = ""
        if report.share_contact and report.reporter.username:
            contact = f"@{report.reporter.username}"
        cards.append(
            _card(
                lang,
                "found",
                report,
                report.date_found,
                report.location,
                photo_id=report.photo_file_id,
                contact=contact,
            )
        )
    cards.sort(key=lambda card: card["date"], reverse=True)
    return cards


def _card(lang, kind, obj, when, location, photo_id="", photo_path="", contact=""):
    text = t(
        lang,
        "card",
        emoji=obj.category.emoji,
        category=obj.category.label(lang),
        title=obj.title,
        location=str(location) if location else "—",
        date=when.strftime("%d.%m.%Y"),
    )
    if contact:
        text += t(lang, "card_contact", contact=contact)
    return {
        "kind": kind,
        "id": obj.id,
        "date": when,
        "text": text,
        "photo_id": photo_id,
        "photo_path": photo_path,
    }


def claim(user, kind, pk):
    """'This is mine' on a card. Returns "ok", "need_lost" (no lost report) or "missing"."""
    if kind == "item":
        item = StoredItem.objects.filter(pk=pk, status=StoredItem.Status.IN_STORAGE).first()
    else:
        item = FoundReport.objects.filter(pk=pk, status=FoundReport.Status.OPEN).first()
    if item is None:
        return "missing"
    return "ok" if matching.claim_item(user, item) else "need_lost"


# --- match answers ---


def answer_match(user, suggestion_id, yes):
    """The owner answered Yes / No to a match message. Only the owner of the lost report may."""
    suggestion = MatchSuggestion.objects.filter(
        pk=suggestion_id,
        lost_report__reporter=user,
        status=MatchSuggestion.Status.SUGGESTED,
    ).first()
    if suggestion is None:
        return False
    matching.answer_by_reporter(suggestion, yes)
    return True
