from datetime import timedelta
from unittest import mock

from django.db import IntegrityError, transaction
from django.utils import timezone

from catalog.testing import (
    AppTestCase,
    make_category,
    make_color,
    make_found,
    make_item,
    make_lost,
    make_staff,
)
from matching import services
from matching.models import MatchSuggestion
from reports.models import LostReport


def matching_pair():
    """A lost report and a stored item that score well above the threshold."""
    lost = make_lost()
    item = make_item(found_report=make_found(date_found=lost.date_lost))
    return lost, item


class RunMatchingTest(AppTestCase):
    def test_creates_a_suggestion_above_the_threshold(self):
        lost, item = matching_pair()
        created = services.run_matching()
        self.assertEqual(len(created), 1)
        suggestion = created[0]
        self.assertEqual((suggestion.lost_report, suggestion.stored_item), (lost, item))
        self.assertEqual(suggestion.created_by, MatchSuggestion.CreatedBy.SYSTEM)
        self.assertGreaterEqual(suggestion.score, 5)
        self.assertTrue(suggestion.breakdown)

    def test_no_suggestion_below_the_threshold(self):
        make_lost(color=make_color("Red"), title="Red umbrella", description="rain", location=None)
        make_item(color=make_color("Green"), title="Green scarf", description="wool")
        self.assertEqual(services.run_matching(), [])

    def test_running_twice_creates_one_suggestion_and_one_message(self):
        matching_pair()
        with mock.patch("bot.notify.notify_user") as notify_user:
            services.run_matching()
            services.run_matching()
        self.assertEqual(MatchSuggestion.objects.count(), 1)
        self.assertEqual(notify_user.call_count, 1)

    def test_pairs_older_than_the_last_run_are_skipped(self):
        matching_pair()
        later = timezone.now() + timedelta(minutes=1)
        self.assertEqual(services.run_matching(since=later), [])
        self.assertEqual(len(services.run_matching(since=timezone.now() - timedelta(hours=1))), 1)

    def test_only_open_reports_and_items_in_storage_are_scored(self):
        lost, item = matching_pair()
        lost.status = LostReport.Status.CANCELLED
        lost.save()
        self.assertEqual(services.run_matching(), [])
        lost.status = LostReport.Status.OPEN
        lost.save()
        item.status = "returned"
        item.save()
        self.assertEqual(services.run_matching(), [])

    def test_the_owner_is_told_in_their_language(self):
        lost, _item = matching_pair()
        with mock.patch("bot.notify.send_message") as send:
            services.run_matching()
        chat_id, text, buttons = send.call_args.args
        self.assertEqual(chat_id, lost.reporter.telegram_id)
        self.assertIn("Blue backpack", text)
        self.assertEqual(
            [data.split(":")[:2] for _label, data in buttons], [["match", "yes"], ["match", "no"]]
        )


class NoDuplicatesTest(AppTestCase):
    def test_create_suggestion_returns_the_existing_one(self):
        lost, item = matching_pair()
        first, created_first = services.create_suggestion(lost, item, "system")
        second, created_second = services.create_suggestion(lost, item, "staff")
        self.assertEqual((created_first, created_second), (True, False))
        self.assertEqual(first.pk, second.pk)

    def test_database_refuses_a_duplicate_pair(self):
        lost, item = matching_pair()
        MatchSuggestion.objects.create(
            lost_report=lost, stored_item=item, score=7, created_by="system"
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            MatchSuggestion.objects.create(
                lost_report=lost, stored_item=item, score=7, created_by="staff"
            )

    def test_database_refuses_a_suggestion_with_no_item(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            MatchSuggestion.objects.create(lost_report=make_lost(), score=1, created_by="system")

    def test_suggestion_for_an_item_the_finder_kept(self):
        lost = make_lost()
        report = make_found(kept_by_finder=True, date_found=lost.date_lost)
        suggestion, created = services.create_suggestion(lost, report, "staff")
        self.assertTrue(created)
        self.assertEqual(suggestion.item, report)
        self.assertIsNone(suggestion.stored_item)


class ReviewTest(AppTestCase):
    def setUp(self):
        self.staff = make_staff()
        self.lost, self.item = matching_pair()
        self.suggestion, _ = services.create_suggestion(self.lost, self.item, "system")

    def test_confirming_marks_the_lost_report_matched(self):
        services.review_suggestion(self.suggestion, MatchSuggestion.Status.CONFIRMED, self.staff)
        self.lost.refresh_from_db()
        self.suggestion.refresh_from_db()
        self.assertEqual(self.lost.status, LostReport.Status.MATCHED)
        self.assertEqual(self.suggestion.reviewed_by, self.staff)
        self.assertIsNotNone(self.suggestion.reviewed_at)

    def test_rejecting_keeps_the_lost_report_open(self):
        services.review_suggestion(self.suggestion, MatchSuggestion.Status.REJECTED, self.staff)
        self.lost.refresh_from_db()
        self.assertEqual(self.lost.status, LostReport.Status.OPEN)

    def test_owner_says_no_closes_the_suggestion(self):
        services.answer_by_reporter(self.suggestion, yes=False)
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.status, MatchSuggestion.Status.REJECTED)
        self.assertEqual(self.suggestion.reporter_answer, "no")

    def test_owner_says_yes_waits_for_staff(self):
        services.answer_by_reporter(self.suggestion, yes=True)
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.status, MatchSuggestion.Status.SUGGESTED)
        self.assertEqual(self.suggestion.reporter_answer, "yes")


class ClaimTest(AppTestCase):
    def test_claim_attaches_to_the_newest_open_report_of_the_same_category(self):
        user = make_lost().reporter
        older = make_lost(reporter=user)
        newer = make_lost(reporter=user)
        make_lost(reporter=user, category=make_category("Keys"))
        item = make_item()
        suggestion = services.claim_item(user, item)
        self.assertEqual(suggestion.lost_report, newer)
        self.assertNotEqual(suggestion.lost_report, older)
        self.assertEqual(suggestion.created_by, MatchSuggestion.CreatedBy.USER)

    def test_claim_without_a_matching_lost_report(self):
        self.assertIsNone(
            services.claim_item(make_lost().reporter, make_item(category=make_category("Keys")))
        )
