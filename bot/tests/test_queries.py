from datetime import timedelta
from types import SimpleNamespace

from django.utils import timezone

from bot import queries
from catalog.testing import (
    AppTestCase,
    make_area,
    make_category,
    make_color,
    make_found,
    make_item,
    make_lost,
    make_user,
)
from matching.models import MatchSuggestion
from reports.models import FoundReport, LostReport, TelegramUser


def telegram_user(id=555, username="aziz", full_name="Aziz Karimov"):
    return SimpleNamespace(id=id, username=username, full_name=full_name)


class UserTest(AppTestCase):
    def test_a_new_telegram_user_is_created_once(self):
        first = queries.get_or_create_user(telegram_user())
        again = queries.get_or_create_user(telegram_user())
        self.assertEqual(first.pk, again.pk)
        self.assertEqual((first.display_name, first.language), ("Aziz Karimov", "uz"))

    def test_a_changed_username_is_updated(self):
        queries.get_or_create_user(telegram_user())
        user = queries.get_or_create_user(telegram_user(username="aziz2"))
        self.assertEqual(TelegramUser.objects.get().username, "aziz2")
        self.assertEqual(user.username, "aziz2")

    def test_set_language(self):
        user = make_user()
        queries.set_language(user, "ru")
        user.refresh_from_db()
        self.assertEqual(user.language, "ru")


class SaveReportTest(AppTestCase):
    def wizard_data(self, **fields):
        data = {
            "kind": "lost",
            "category_id": make_category().pk,
            "title": "Blue bag",
            "description": "With notebooks",
            "color_id": make_color().pk,
            "date": "2026-10-05",
        }
        return {**data, **fields}

    def test_lost_report_without_a_known_place(self):
        report = queries.save_report(make_user(), self.wizard_data())
        self.assertIsInstance(report, LostReport)
        self.assertEqual((report.location, report.date_lost.isoformat()), (None, "2026-10-05"))

    def test_found_report_keeps_the_finders_choices(self):
        data = self.wizard_data(
            kind="found",
            location_id=make_area().pk,
            kept=True,
            share_contact=True,
            photo_file_id="AgAC",
        )
        report = queries.save_report(make_user(), data)
        self.assertIsInstance(report, FoundReport)
        self.assertEqual(
            (report.kept_by_finder, report.share_contact, report.photo_file_id),
            (True, True, "AgAC"),
        )

    def test_summary_fields_are_in_the_users_language(self):
        data = self.wizard_data(location_id=make_area().pk)
        fields = queries.summary_fields(data, "en")
        self.assertEqual(fields["color"], "Blue")
        self.assertEqual(fields["location"], "Main building / Library")


class MyReportsTest(AppTestCase):
    def setUp(self):
        self.user = make_user()

    def test_cancel_only_own_open_reports(self):
        mine = make_lost(reporter=self.user)
        other = make_lost()
        self.assertFalse(queries.cancel_report(self.user, "lost", other.pk))
        self.assertTrue(queries.cancel_report(self.user, "lost", mine.pk))
        mine.refresh_from_db()
        self.assertEqual(mine.status, LostReport.Status.CANCELLED)
        self.assertFalse(queries.cancel_report(self.user, "lost", mine.pk))  # already cancelled

    def test_reopen_an_expired_report(self):
        report = make_lost(reporter=self.user, status=LostReport.Status.EXPIRED)
        self.assertTrue(queries.reopen_report(self.user, report.pk))
        report.refresh_from_db()
        self.assertEqual(report.status, LostReport.Status.OPEN)
        self.assertIsNotNone(report.reopened_at)

    def test_only_expired_reports_can_be_reopened(self):
        report = make_lost(reporter=self.user)
        self.assertFalse(queries.reopen_report(self.user, report.pk))

    def test_listing_offers_the_right_button(self):
        make_lost(reporter=self.user, title="Open one")
        make_lost(reporter=self.user, title="Expired one", status=LostReport.Status.EXPIRED)
        make_found(reporter=self.user, title="Found one", status=FoundReport.Status.REGISTERED)
        actions = {row["title"]: row["action"] for row in queries.my_reports(self.user, "en")}
        self.assertEqual(
            actions, {"Open one": "cancel", "Expired one": "reopen", "Found one": None}
        )


class RecentCardsTest(AppTestCase):
    def test_shows_shelf_items_and_items_the_finder_kept(self):
        make_item(title="On the shelf")
        make_found(title="Kept by finder", kept_by_finder=True)
        titles = {card["kind"]: card["text"] for card in queries.recent_cards("en")}
        self.assertEqual(set(titles), {"item", "found"})

    def test_the_finders_contact_needs_their_consent(self):
        make_found(kept_by_finder=True, share_contact=False, reporter=make_user())
        shared = make_found(kept_by_finder=True, share_contact=True, reporter=make_user())
        texts = [card["text"] for card in queries.recent_cards("en")]
        self.assertEqual(sum("@user" in text for text in texts), 1)
        self.assertTrue(any(f"@{shared.reporter.username}" in text for text in texts))

    def test_old_items_and_other_categories_are_left_out(self):
        make_item(title="Old", received_at=timezone.now() - timedelta(days=45))
        keys = make_item(title="Keys", category=make_category("Keys"))
        make_item(title="Bag")
        self.assertEqual(len(queries.recent_cards("en")), 2)
        cards = queries.recent_cards("en", category_id=keys.category_id)
        self.assertEqual([card["id"] for card in cards], [keys.pk])

    def test_returned_items_are_not_shown(self):
        make_item(status="returned")
        self.assertEqual(queries.recent_cards("en"), [])


class ClaimAndAnswerTest(AppTestCase):
    def test_claim_results(self):
        item = make_item()
        owner = make_user()
        self.assertEqual(queries.claim(owner, "item", 99999), "missing")
        self.assertEqual(queries.claim(owner, "item", item.pk), "need_lost")
        make_lost(reporter=owner)
        self.assertEqual(queries.claim(owner, "item", item.pk), "ok")
        self.assertEqual(MatchSuggestion.objects.get().created_by, "user")

    def test_claiming_twice_does_not_duplicate(self):
        item = make_item()
        owner = make_lost().reporter
        queries.claim(owner, "item", item.pk)
        queries.claim(owner, "item", item.pk)
        self.assertEqual(MatchSuggestion.objects.count(), 1)

    def test_claim_a_kept_item(self):
        report = make_found(kept_by_finder=True)
        owner = make_lost().reporter
        self.assertEqual(queries.claim(owner, "found", report.pk), "ok")

    def test_only_the_owner_can_answer(self):
        lost = make_lost()
        suggestion = MatchSuggestion.objects.create(
            lost_report=lost, stored_item=make_item(), score=8, created_by="system"
        )
        self.assertFalse(queries.answer_match(make_user(), suggestion.pk, yes=True))
        self.assertTrue(queries.answer_match(lost.reporter, suggestion.pk, yes=False))
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, MatchSuggestion.Status.REJECTED)
        # A closed suggestion cannot be answered again.
        self.assertFalse(queries.answer_match(lost.reporter, suggestion.pk, yes=True))
