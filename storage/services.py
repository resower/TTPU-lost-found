"""Everything that changes an item lives here, so the rules are written once."""

from itertools import product

from django.db import transaction
from django.utils import timezone

from bot import notify
from reports.models import FoundReport, LostReport

from .models import Handover, ItemStatusLog, StoredItem

# An item may only leave storage, and only once.
ALLOWED_TRANSITIONS = {
    StoredItem.Status.IN_STORAGE: {
        StoredItem.Status.RETURNED,
        StoredItem.Status.DISPOSED,
        StoredItem.Status.TRANSFERRED,
    },
}

SHELF_ROWS = "ABCDEFGH"
SHELF_LEVELS = range(1, 4)
SHELF_SLOTS = range(1, 11)


class InvalidTransition(Exception):
    pass


def next_free_shelf_code():
    """First shelf code (like B2-07) that no item in storage uses. Empty string if all are taken."""
    used = set(
        StoredItem.objects.filter(status=StoredItem.Status.IN_STORAGE).values_list(
            "shelf_code", flat=True
        )
    )
    for row, level, slot in product(SHELF_ROWS, SHELF_LEVELS, SHELF_SLOTS):
        code = f"{row}{level}-{slot:02d}"
        if code not in used:
            return code
    return ""


def register_item(item):
    """Save a newly received item, log it and tell the finder (if the item has a report)."""
    with transaction.atomic():
        item.save()
        ItemStatusLog.objects.create(
            item=item, new_status=item.status, staff=item.received_by, note="Received at the desk"
        )
        report = item.found_report
        if report:
            report.status = FoundReport.Status.REGISTERED
            report.save(update_fields=["status"])
    # Notify only after the transaction is saved, so nobody hears about a rolled-back change.
    if report:
        notify.notify_user(
            report.reporter, "n_item_registered", title=item.title, shelf=item.shelf_code
        )
    return item


def change_status(item, new_status, staff, note=""):
    """The only function that changes an item's status. Checks the rule and writes the log."""
    if new_status not in ALLOWED_TRANSITIONS.get(item.status, set()):
        raise InvalidTransition(f"Cannot change an item from {item.status} to {new_status}.")
    with transaction.atomic():
        ItemStatusLog.objects.create(
            item=item, old_status=item.status, new_status=new_status, staff=staff, note=note
        )
        item.status = new_status
        item.save(update_fields=["status"])
    return item


def return_item(item, staff, receiver_name, id_last4, lost_report=None, note=""):
    """Hand the item back: closes the item and the reports in one transaction, then notifies."""
    with transaction.atomic():
        change_status(item, StoredItem.Status.RETURNED, staff, note=f"Returned to {receiver_name}")
        handover = Handover.objects.create(
            stored_item=item,
            lost_report=lost_report,
            receiver_name=receiver_name,
            id_last4=id_last4,
            staff=staff,
            handed_at=timezone.now(),
            note=note,
        )
        if lost_report:
            lost_report.status = LostReport.Status.RETURNED
            lost_report.save(update_fields=["status"])
        if item.found_report:
            item.found_report.status = FoundReport.Status.RETURNED
            item.found_report.save(update_fields=["status"])
    if lost_report:
        notify.notify_status(lost_report.reporter, lost_report.title, "returned")
    return handover
