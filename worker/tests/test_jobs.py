from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from catalog.testing import AppTestCase, make_category, make_item, make_lost
from matching.models import MatchSuggestion
from reports.models import LostReport
from storage.models import StoredItem
from worker import jobs


def age(report, days):
    """Make a report `days` old (created_at is set automatically, so update it)."""
    LostReport.objects.filter(pk=report.pk).update(created_at=timezone.now() - timedelta(days=days))
    report.refresh_from_db()


class ExpireLostReportsTest(AppTestCase):
    def test_reports_older_than_90_days_expire_and_the_owner_is_told(self):
        old, fresh = make_lost(), make_lost()
        age(old, 91)
        age(fresh, 89)
        with mock.patch("bot.notify.send_message") as send:
            jobs.expire_lost_reports()
        old.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual((old.status, fresh.status), ("expired", "open"))
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.args[2][0][1], f"reopen:{old.pk}")  # the "reopen" button

    def test_only_open_reports_expire(self):
        report = make_lost(status=LostReport.Status.MATCHED)
        age(report, 200)
        jobs.expire_lost_reports()
        report.refresh_from_db()
        self.assertEqual(report.status, "matched")

    def test_a_reopened_report_is_not_expired_again_at_once(self):
        report = make_lost()
        age(report, 200)
        report.reopened_at = timezone.now() - timedelta(days=1)
        report.save()
        jobs.expire_lost_reports()
        report.refresh_from_db()
        self.assertEqual(report.status, "open")

    def test_a_report_reopened_long_ago_expires_again(self):
        report = make_lost()
        age(report, 300)
        report.reopened_at = timezone.now() - timedelta(days=91)
        report.save()
        jobs.expire_lost_reports()
        report.refresh_from_db()
        self.assertEqual(report.status, "expired")


class DigestTest(AppTestCase):
    def setUp(self):
        today = timezone.localdate()
        self.soon = make_item(title="Soon item", retention_until=today + timedelta(days=3))
        self.overdue = make_item(title="Overdue item", retention_until=today - timedelta(days=5))
        self.later = make_item(title="Later item", retention_until=today + timedelta(days=40))

    def test_digest_lists_expiring_and_overdue_items(self):
        text = jobs.build_digest()
        self.assertIn("Soon item", text)
        self.assertIn("Overdue item", text)
        self.assertNotIn("Later item", text)

    def test_the_digest_never_changes_an_item(self):
        jobs.build_digest()
        self.overdue.refresh_from_db()
        self.assertEqual(self.overdue.status, StoredItem.Status.IN_STORAGE)

    def test_digest_counts(self):
        make_lost()
        text = jobs.build_digest()
        self.assertIn("1", text)

    @override_settings(OFFICE_GROUP_ID="")
    def test_no_group_no_message(self):
        with mock.patch("bot.notify.send_message") as send:
            jobs.daily_digest()
        send.assert_not_called()

    @override_settings(OFFICE_GROUP_ID="-100123")
    def test_the_digest_goes_to_the_office_group(self):
        with mock.patch("bot.notify.send_message") as send:
            jobs.daily_digest()
        self.assertEqual(send.call_args.args[0], "-100123")


class MatchRunTest(AppTestCase):
    def test_the_match_job_creates_suggestions(self):
        lost = make_lost()
        make_item(found_report=None, category=lost.category, color=lost.color)
        jobs.match_run(None)
        self.assertEqual(MatchSuggestion.objects.count(), 1)

    def test_other_categories_are_ignored(self):
        make_lost()
        make_item(category=make_category("Keys"))
        jobs.match_run(None)
        self.assertEqual(MatchSuggestion.objects.count(), 0)
