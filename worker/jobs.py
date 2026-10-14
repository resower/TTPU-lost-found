"""The background jobs. The scheduler decides when each one runs."""

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from bot import notify
from bot.strings import t
from matching import services as matching
from matching.models import MatchSuggestion
from reports.models import LostReport
from storage.models import EXPIRING_SOON_DAYS, StoredItem

log = logging.getLogger(__name__)

LOST_REPORT_DAYS = 90  # an open lost report expires after this many days
OFFICE_LANGUAGE = "uz"  # the digest is written in this language


def match_run(since):
    """Score open lost reports against items on the shelf; message owners about new matches."""
    created = matching.run_matching(since)
    log.info("match run: %s new suggestions", len(created))


def expire_lost_reports():
    """Open lost reports older than 90 days become 'expired'. The owner can reopen with one tap."""
    cutoff = timezone.now() - timedelta(days=LOST_REPORT_DAYS)
    stale = LostReport.objects.filter(status=LostReport.Status.OPEN).filter(
        Q(reopened_at__isnull=True, created_at__lt=cutoff) | Q(reopened_at__lt=cutoff)
    )
    for report in stale.select_related("reporter"):
        report.status = LostReport.Status.EXPIRED
        report.save(update_fields=["status"])
        notify.notify_user(
            report.reporter,
            "n_expired",
            buttons=[("btn_reopen", f"reopen:{report.id}")],
            title=report.title,
        )
    log.info("expiry: %s reports expired", stale.count())


def build_digest():
    """The text of the daily office digest: retention reminders and open work.

    Items past their retention date are only flagged here. Only staff change their status.
    """
    lang = OFFICE_LANGUAGE
    today = timezone.localdate()
    on_shelf = StoredItem.objects.filter(status=StoredItem.Status.IN_STORAGE)
    soon = on_shelf.filter(
        retention_until__range=(today, today + timedelta(days=EXPIRING_SOON_DAYS))
    ).order_by("retention_until")
    overdue = on_shelf.filter(retention_until__lt=today).order_by("retention_until")

    def lines(items):
        rows = [f"• {i.shelf_code} {i.title} ({i.retention_until:%d.%m})" for i in items]
        return "\n".join(rows) or t(lang, "digest_none")

    counts = t(
        lang,
        "digest_counts",
        lost=LostReport.objects.filter(status=LostReport.Status.OPEN).count(),
        pending=MatchSuggestion.objects.filter(status=MatchSuggestion.Status.SUGGESTED).count(),
    )
    return "\n\n".join(
        [
            t(lang, "digest_title"),
            t(lang, "digest_expiring") + "\n" + lines(soon),
            t(lang, "digest_disposal") + "\n" + lines(overdue),
            counts,
        ]
    )


def daily_digest():
    """Send the digest to the office Telegram group."""
    if not settings.OFFICE_GROUP_ID:
        log.warning("OFFICE_GROUP_ID is not set, the digest was not sent")
        return
    notify.send_message(settings.OFFICE_GROUP_ID, build_digest())
