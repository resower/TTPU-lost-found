"""The bot, end to end: real dispatcher and handlers, pretend Telegram."""

from datetime import timedelta

from asgiref.sync import sync_to_async
from django.utils import timezone

from bot.strings import t
from bot.tests.fake_telegram import FakeTelegram
from catalog.testing import (
    AppTestCase,
    make_area,
    make_category,
    make_color,
    make_found,
    make_item,
    make_lost,
)
from matching.models import MatchSuggestion
from reports.models import FoundReport, LostReport, TelegramUser


class BotFlowTest(AppTestCase):
    def setUp(self):
        self.category = make_category("Bags")
        self.color = make_color("Blue")
        self.area = make_area()
        self.tg = FakeTelegram()

    async def sign_in(self, lang="en"):
        await self.tg.say("/start")
        await self.tg.press(f"lang:{lang}")

    async def answer_questions(self, kind, title="Blue backpack", description="Has a keychain"):
        """Walk the wizard up to the date question."""
        tg = self.tg
        await tg.press(f"menu:{kind}")
        await tg.press(f"cat:{self.category.pk}")
        await tg.say(title)
        await tg.say(description)
        await tg.press(f"col:{self.color.pk}")
        await tg.press(f"bld:{self.area.parent_id}")
        await tg.press(f"area:{self.area.pk}")

    # --- start and language ---

    async def test_start_asks_for_the_language_then_shows_the_menu(self):
        await self.tg.say("/start")
        self.assertEqual(self.tg.buttons(), ["lang:uz", "lang:ru", "lang:en"])
        await self.tg.press("lang:ru")
        user = await TelegramUser.objects.aget(telegram_id=111)
        self.assertEqual(user.language, "ru")
        self.assertEqual(self.tg.texts()[-1], t("ru", "menu_title"))
        self.assertEqual(self.tg.buttons(), ["menu:lost", "menu:found", "menu:recent", "menu:mine"])

    async def test_text_outside_a_wizard_is_not_understood(self):
        await self.sign_in()
        await self.tg.say("hello?")
        self.assertEqual(self.tg.texts()[-1], t("en", "not_understood"))

    async def test_a_blocked_user_gets_one_message_and_nothing_else(self):
        await TelegramUser.objects.acreate(telegram_id=111, display_name="Aziz", is_blocked=True)
        await self.tg.say("/start")
        self.assertEqual(self.tg.texts(), [t("uz", "blocked")])

    # --- lost wizard ---

    async def test_lost_wizard_saves_a_report(self):
        await self.sign_in()
        await self.answer_questions("lost")
        await self.tg.press("date:yesterday")
        await self.tg.press("photo:skip")
        self.assertIn("Blue backpack", self.tg.texts()[-1])  # the summary
        await self.tg.press("wiz:submit")

        report = await LostReport.objects.select_related("reporter").aget()
        self.assertEqual((report.title, report.description), ("Blue backpack", "Has a keychain"))
        self.assertEqual(
            (report.category_id, report.color_id, report.location_id),
            (self.category.pk, self.color.pk, self.area.pk),
        )
        self.assertEqual(report.date_lost, timezone.localdate() - timedelta(days=1))
        self.assertEqual(report.reporter.telegram_id, 111)
        self.assertIn(t("en", "saved_lost"), self.tg.texts())

    async def test_a_lost_report_may_have_an_unknown_place_and_a_typed_date(self):
        await self.sign_in()
        tg = self.tg
        await tg.press("menu:lost")
        await tg.press(f"cat:{self.category.pk}")
        await tg.say("Black umbrella")
        await tg.say("Large, wooden handle")
        await tg.press(f"col:{self.color.pk}")
        await tg.press("loc:none")
        await tg.press("date:pick")
        await tg.say("05.10.2026")
        await tg.send_photo("AgACumbrella")
        await tg.press("wiz:submit")
        report = await LostReport.objects.aget()
        self.assertIsNone(report.location_id)
        self.assertEqual(report.date_lost.isoformat(), "2026-10-05")
        self.assertEqual(report.photo_file_id, "AgACumbrella")

    async def test_bad_answers_are_asked_again(self):
        await self.sign_in()
        tg = self.tg
        await tg.press("menu:lost")
        await tg.press(f"cat:{self.category.pk}")
        await tg.say("ab")  # too short
        self.assertEqual(tg.texts()[-1], t("en", "err_title"))
        await tg.say("Blue bag")
        await tg.say("A bag")
        await tg.press(f"col:{self.color.pk}")
        await tg.press("loc:none")
        await tg.press("date:pick")
        await tg.say("31.02.2026")  # not a date
        await tg.say("01.01.2999")  # in the future
        self.assertEqual(tg.texts().count(t("en", "err_date")), 2)
        await tg.say("01.10.2026")
        await tg.say("not a photo")
        self.assertEqual(tg.texts()[-1], t("en", "err_photo"))

    async def test_cancel_saves_nothing(self):
        await self.sign_in()
        await self.tg.press("menu:lost")
        await self.tg.press("wiz:cancel")
        self.assertEqual(self.tg.texts()[-1], t("en", "menu_title"))
        self.assertEqual(await LostReport.objects.acount(), 0)

    async def test_start_in_the_middle_of_a_wizard_begins_again(self):
        await self.sign_in()
        await self.tg.press("menu:lost")
        await self.tg.say("/start")
        self.assertEqual(self.tg.texts()[-1], t("en", "lang_prompt"))
        await self.tg.say("some text")  # no wizard is running any more
        self.assertEqual(self.tg.texts()[-1], t("en", "not_understood"))

    async def test_edit_restarts_the_questions(self):
        await self.sign_in()
        await self.answer_questions("lost")
        await self.tg.press("date:today")
        await self.tg.press("photo:skip")
        await self.tg.press("wiz:edit")
        self.assertEqual(self.tg.texts()[-1], t("en", "ask_category"))
        self.assertEqual(await LostReport.objects.acount(), 0)

    # --- found wizard ---

    async def test_found_wizard_with_the_item_handed_to_the_office(self):
        await self.sign_in()
        await self.answer_questions("found", "Green scarf", "Wool scarf")
        await self.tg.press("date:today")
        await self.tg.press("photo:skip")
        await self.tg.press("where:office")
        await self.tg.press("wiz:submit")
        report = await FoundReport.objects.aget()
        self.assertEqual(
            (report.kept_by_finder, report.share_contact, report.location_id),
            (False, False, self.area.pk),
        )

    async def test_found_wizard_asks_for_consent_when_the_finder_keeps_the_item(self):
        await self.sign_in()
        await self.answer_questions("found", "Green scarf", "Wool scarf")
        await self.tg.press("date:today")
        await self.tg.press("photo:skip")
        await self.tg.press("where:kept")
        self.assertEqual(self.tg.buttons(), ["consent:yes", "consent:no", "wiz:cancel"])
        await self.tg.press("consent:yes")
        await self.tg.press("wiz:submit")
        report = await FoundReport.objects.aget()
        self.assertEqual((report.kept_by_finder, report.share_contact), (True, True))

    async def test_a_found_report_needs_a_place(self):
        await self.sign_in()
        await self.tg.press("menu:found")
        await self.tg.press(f"cat:{self.category.pk}")
        await self.tg.say("Green scarf")
        await self.tg.say("Wool scarf")
        await self.tg.press(f"col:{self.color.pk}")
        self.assertNotIn("loc:none", self.tg.buttons())

    # --- recent found items and "this is mine" ---

    async def test_recent_items_and_this_is_mine(self):
        await self.sign_in()
        item = await make_item_async(title="Blue backpack")
        await self.tg.press("menu:recent")
        await self.tg.press("recent:0:0")
        self.assertIn(f"mine:item:{item.pk}", self.tg.buttons())

        await self.tg.press(f"mine:item:{item.pk}")  # no lost report yet
        self.assertEqual(self.tg.alerts(), [t("en", "need_lost_report")])

        await make_lost_for(111)
        await self.tg.press(f"mine:item:{item.pk}")
        self.assertEqual(self.tg.alerts()[-1], t("en", "claim_sent"))
        suggestion = await MatchSuggestion.objects.aget()
        self.assertEqual((suggestion.stored_item_id, suggestion.created_by), (item.pk, "user"))

    async def test_recent_items_come_in_pages_of_three(self):
        await self.sign_in()
        for n in range(4):
            await make_item_async(title=f"Bag {n}")
        await self.tg.press("recent:0:0")
        self.assertEqual(self.tg.buttons(), ["recent:0:1"])  # the "more" button
        await self.tg.press("recent:0:1")
        self.assertEqual(sum(1 for text in self.tg.texts() if text.startswith("🎒")), 4)

    async def test_a_card_with_a_photo_is_sent_as_a_photo(self):
        await self.sign_in()
        report = await sync_to_async(make_found)(photo_file_id="AgACcard")
        await sync_to_async(make_item)(found_report=report)
        await self.tg.press("recent:0:0")
        photos = [c for c in self.tg.session.calls if type(c).__name__ == "SendPhoto"]
        self.assertEqual([c.photo for c in photos], ["AgACcard"])

    async def test_no_recent_items(self):
        await self.sign_in()
        await self.tg.press("recent:0:0")
        self.assertEqual(self.tg.texts()[-1], t("en", "recent_empty"))

    # --- my reports ---

    async def test_my_reports_can_cancel_and_reopen(self):
        await self.sign_in()
        open_report = await make_lost_for(111)
        expired = await make_lost_for(111, status=LostReport.Status.EXPIRED)
        await self.tg.press("menu:mine")
        self.assertEqual(
            set(self.tg.buttons()), {f"cancel:lost:{open_report.pk}", f"reopen:{expired.pk}"}
        )

        await self.tg.press(f"cancel:lost:{open_report.pk}")
        await self.tg.press(f"reopen:{expired.pk}")
        await open_report.arefresh_from_db()
        await expired.arefresh_from_db()
        self.assertEqual((open_report.status, expired.status), ("cancelled", "open"))

    async def test_nobody_can_cancel_someone_elses_report(self):
        await self.sign_in()
        other = await sync_make_lost()
        await self.tg.press(f"cancel:lost:{other.pk}")
        await other.arefresh_from_db()
        self.assertEqual(other.status, "open")

    async def test_my_reports_when_there_are_none(self):
        await self.sign_in()
        await self.tg.press("menu:mine")
        self.assertEqual(self.tg.texts()[-1], t("en", "mine_empty"))

    # --- answering a match message ---

    async def test_the_owner_answers_yes_or_no(self):
        await self.sign_in()
        lost = await make_lost_for(111)
        item = await make_item_async()
        yes = await MatchSuggestion.objects.acreate(
            lost_report=lost, stored_item=item, score=8, created_by="system"
        )
        await self.tg.press(f"match:yes:{yes.pk}")
        await yes.arefresh_from_db()
        self.assertEqual((yes.reporter_answer, yes.status), ("yes", "suggested"))
        self.assertEqual(self.tg.texts()[-1], t("en", "match_yes_ack"))

        other_item = await make_item_async(title="Another bag")
        no = await MatchSuggestion.objects.acreate(
            lost_report=lost, stored_item=other_item, score=6, created_by="system"
        )
        await self.tg.press(f"match:no:{no.pk}")
        await no.arefresh_from_db()
        self.assertEqual(no.status, "rejected")


# The helpers in catalog.testing are synchronous; these wrappers run them from async tests.


async def make_item_async(**fields):
    return await sync_to_async(make_item)(**fields)


async def sync_make_lost(**fields):
    return await sync_to_async(make_lost)(**fields)


async def make_lost_for(telegram_id, **fields):
    def create():
        user, _ = TelegramUser.objects.get_or_create(
            telegram_id=telegram_id, defaults={"display_name": "Aziz"}
        )
        return make_lost(reporter=user, **fields)

    return await sync_to_async(create)()
