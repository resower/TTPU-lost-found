from django.conf import settings
from django.utils import timezone

from bot import notify
from reports.models import LostReport
from storage.models import StoredItem

from .models import MatchSuggestion
from .scoring import THRESHOLD, match_score


def create_suggestion(lost, item, created_by, score=None, breakdown=None):
    """Create the suggestion unless this pair already has one. Returns (suggestion, created).

    The pair is the lookup key and the database has a unique constraint on it, so the same
    suggestion can never exist twice, however often (or after however many restarts) this runs.
    """
    if score is None:
        score, breakdown = match_score(lost, item)
    pair = {"stored_item": item} if isinstance(item, StoredItem) else {"found_report": item}
    return MatchSuggestion.objects.get_or_create(
        lost_report=lost,
        **pair,
        defaults={"score": score, "breakdown": breakdown or {}, "created_by": created_by},
    )


def notify_match(suggestion):
    """Tell the owner that a similar item is waiting, with Yes / No buttons."""
    lost = suggestion.lost_report
    notify.notify_user(
        lost.reporter,
        "n_match_found",
        buttons=[
            ("btn_match_yes", f"match:yes:{suggestion.id}"),
            ("btn_match_no", f"match:no:{suggestion.id}"),
        ],
        title=lost.title,
        room=settings.OFFICE_ROOM,
    )


def run_matching(since=None):
    """Score open lost reports against items on the shelf and create suggestions.

    `since` is the time of the last successful run. A pair is skipped only when both the
    report and the item are older than that, because that pair was already scored before.
    Returns the suggestions created in this run.
    """
    items = list(
        StoredItem.objects.filter(status=StoredItem.Status.IN_STORAGE).select_related(
            "found_report__location__parent", "category", "color"
        )
    )
    reports = LostReport.objects.filter(status=LostReport.Status.OPEN).select_related(
        "location__parent", "reporter"
    )
    created = []
    for lost in reports:
        for item in items:
            if since and lost.created_at <= since and item.received_at <= since:
                continue
            score, breakdown = match_score(lost, item)
            if score < THRESHOLD:
                continue
            suggestion, is_new = create_suggestion(
                lost, item, MatchSuggestion.CreatedBy.SYSTEM, score, breakdown
            )
            if is_new:  # only a new suggestion sends a message, so nobody is told twice
                notify_match(suggestion)
                created.append(suggestion)
    return created


def review_suggestion(suggestion, status, staff):
    """Staff confirm or reject a suggestion."""
    suggestion.status = status
    suggestion.reviewed_by = staff
    suggestion.reviewed_at = timezone.now()
    suggestion.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    lost = suggestion.lost_report
    if status == MatchSuggestion.Status.CONFIRMED and lost.status == LostReport.Status.OPEN:
        lost.status = LostReport.Status.MATCHED
        lost.save(update_fields=["status"])
        notify.notify_status(lost.reporter, lost.title, "matched")
    return suggestion


def answer_by_reporter(suggestion, yes):
    """The owner pressed Yes or No in the bot. 'No' closes the suggestion; 'Yes' waits for staff."""
    suggestion.reporter_answer = "yes" if yes else "no"
    if not yes:
        suggestion.status = MatchSuggestion.Status.REJECTED
    suggestion.save(update_fields=["reporter_answer", "status"])
    return suggestion


def claim_item(user, item):
    """The owner pressed 'This is mine' on a found item: ask the office to review it.

    The claim is attached to the owner's newest open lost report of the same category.
    Returns the suggestion, or None if the owner has no such report.
    """
    lost = (
        LostReport.objects.filter(
            reporter=user, category=item.category, status=LostReport.Status.OPEN
        )
        .order_by("-created_at")
        .first()
    )
    if lost is None:
        return None
    suggestion, _created = create_suggestion(lost, item, MatchSuggestion.CreatedBy.USER)
    return suggestion
