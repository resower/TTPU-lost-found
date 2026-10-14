from datetime import timedelta
from unittest import mock

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from catalog.testing import (
    AppTestCase,
    make_category,
    make_found,
    make_item,
    make_lost,
    make_staff,
)
from reports.models import FoundReport, LostReport
from storage import services
from storage.models import Handover, ItemStatusLog, StoredItem


class RetentionTest(AppTestCase):
    def test_keep_until_is_the_received_date_plus_the_category_days(self):
        category = make_category("Clothes", retention_days=30)
        received = timezone.now() - timedelta(days=10)
        item = make_item(category=category, received_at=received)
        self.assertEqual(
            item.retention_until, timezone.localtime(received).date() + timedelta(days=30)
        )

    def test_expiring_soon_and_ready_for_disposal(self):
        today = timezone.localdate()
        soon = make_item(retention_until=today + timedelta(days=3))
        later = make_item(retention_until=today + timedelta(days=30))
        overdue = make_item(retention_until=today - timedelta(days=1))
        self.assertEqual(
            (soon.expiring_soon, later.expiring_soon, overdue.expiring_soon), (True, False, False)
        )
        self.assertEqual((soon.ready_for_disposal, overdue.ready_for_disposal), (False, True))


class ShelfCodeTest(AppTestCase):
    def test_first_free_code(self):
        self.assertEqual(services.next_free_shelf_code(), "A1-01")

    def test_skips_codes_in_use(self):
        make_item(shelf_code="A1-01")
        make_item(shelf_code="A1-02")
        self.assertEqual(services.next_free_shelf_code(), "A1-03")

    def test_a_returned_item_frees_its_code(self):
        item = make_item(shelf_code="A1-01")
        services.return_item(item, make_staff(), "Aziz", "1234")
        self.assertEqual(services.next_free_shelf_code(), "A1-01")

    def test_two_items_in_storage_cannot_share_a_code(self):
        make_item(shelf_code="B2-05")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_item(shelf_code="B2-05")

    def test_a_code_can_be_reused_after_the_first_item_left(self):
        first = make_item(shelf_code="B2-05")
        services.change_status(first, StoredItem.Status.DISPOSED, make_staff())
        make_item(shelf_code="B2-05")  # no error


class RegisterItemTest(AppTestCase):
    def test_registering_logs_it_and_marks_the_found_report(self):
        report = make_found()
        item = StoredItem(
            found_report=report,
            category=report.category,
            title="Bag",
            shelf_code="A1-01",
            received_by=make_staff(),
        )
        services.register_item(item)
        report.refresh_from_db()
        self.assertEqual(report.status, FoundReport.Status.REGISTERED)
        self.assertEqual(item.log.count(), 1)
        self.assertEqual(item.log.get().new_status, StoredItem.Status.IN_STORAGE)


class ChangeStatusTest(AppTestCase):
    def setUp(self):
        self.staff = make_staff()
        self.item = make_item()

    def test_valid_change_is_saved_and_logged(self):
        services.change_status(self.item, StoredItem.Status.DISPOSED, self.staff, "expired")
        self.item.refresh_from_db()
        entry = ItemStatusLog.objects.get(item=self.item)
        self.assertEqual(self.item.status, StoredItem.Status.DISPOSED)
        self.assertEqual(
            (entry.old_status, entry.new_status, entry.staff, entry.note),
            ("in_storage", "disposed", self.staff, "expired"),
        )

    def test_an_item_can_only_leave_storage_once(self):
        services.change_status(self.item, StoredItem.Status.TRANSFERRED, self.staff)
        for new_status in StoredItem.Status.values:
            with self.assertRaises(services.InvalidTransition):
                services.change_status(self.item, new_status, self.staff)
        self.assertEqual(ItemStatusLog.objects.filter(item=self.item).count(), 1)


class ReturnItemTest(AppTestCase):
    def setUp(self):
        self.staff = make_staff()
        self.lost = make_lost()
        self.report = make_found()
        self.item = make_item(found_report=self.report)

    def test_returning_closes_the_item_and_both_reports(self):
        handover = services.return_item(self.item, self.staff, "Aziz Karimov", "4821", self.lost)
        self.item.refresh_from_db()
        self.lost.refresh_from_db()
        self.report.refresh_from_db()
        self.assertEqual(self.item.status, StoredItem.Status.RETURNED)
        self.assertEqual(self.lost.status, LostReport.Status.RETURNED)
        self.assertEqual(self.report.status, FoundReport.Status.RETURNED)
        self.assertEqual(
            (handover.receiver_name, handover.id_last4, handover.staff),
            ("Aziz Karimov", "4821", self.staff),
        )

    def test_the_owner_is_told(self):
        with mock.patch("bot.notify.send_message") as send:
            services.return_item(self.item, self.staff, "Aziz", "4821", self.lost)
        self.assertEqual(send.call_args.args[0], self.lost.reporter.telegram_id)

    def test_an_item_can_be_returned_only_once(self):
        services.return_item(self.item, self.staff, "Aziz", "4821", self.lost)
        with self.assertRaises(services.InvalidTransition):
            services.return_item(self.item, self.staff, "Someone else", "9999")
        self.assertEqual(Handover.objects.count(), 1)

    def test_a_failure_leaves_nothing_half_done(self):
        # The lost report is saved last; if that fails, the item must still be in storage.
        with mock.patch.object(LostReport, "save", side_effect=RuntimeError("disk full")):
            with self.assertRaises(RuntimeError):
                services.return_item(self.item, self.staff, "Aziz", "4821", self.lost)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, StoredItem.Status.IN_STORAGE)
        self.assertEqual(Handover.objects.count(), 0)
        self.assertEqual(ItemStatusLog.objects.filter(item=self.item).count(), 0)

    def test_only_the_last_four_digits_can_be_stored(self):
        for bad in ["12345", "123", "12a4", ""]:
            handover = Handover(
                stored_item=self.item, receiver_name="A", id_last4=bad, staff=self.staff
            )
            with self.assertRaises(ValidationError, msg=bad):
                handover.full_clean(exclude=["lost_report"])
