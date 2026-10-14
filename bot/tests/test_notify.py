from unittest import mock

import httpx
from django.test import override_settings

from bot import notify
from catalog.testing import AppTestCase, make_user


class SendMessageTest(AppTestCase):
    def test_without_a_token_nothing_is_sent(self):
        with mock.patch("bot.notify.httpx.post") as post:
            self.assertFalse(notify.send_message(1, "hello"))
        post.assert_not_called()

    @override_settings(BOT_TOKEN="123:abc")
    def test_sends_text_and_buttons(self):
        with mock.patch("bot.notify.httpx.post") as post:
            self.assertTrue(notify.send_message(42, "hello", [("Yes", "match:yes:1")]))
        url = post.call_args.args[0]
        payload = post.call_args.kwargs["json"]
        self.assertTrue(url.endswith("/bot123:abc/sendMessage"))
        self.assertEqual((payload["chat_id"], payload["text"]), (42, "hello"))
        self.assertEqual(
            payload["reply_markup"]["inline_keyboard"][0][0]["callback_data"], "match:yes:1"
        )

    @override_settings(BOT_TOKEN="123:abc")
    def test_a_telegram_failure_is_logged_but_never_raised(self):
        with mock.patch("bot.notify.httpx.post", side_effect=httpx.ConnectError("down")):
            with self.assertLogs("bot.notify", "ERROR"):
                self.assertFalse(notify.send_message(42, "hello"))

    def test_notify_user_uses_the_users_language(self):
        user = make_user(language="ru")
        with mock.patch("bot.notify.send_message") as send:
            notify.notify_user(user, "n_item_registered", title="Сумка", shelf="A1-01")
        chat_id, text, buttons = send.call_args.args
        self.assertEqual(chat_id, user.telegram_id)
        self.assertIn("Сумка", text)
        self.assertEqual(buttons, [])

    def test_notify_user_translates_the_button_labels(self):
        user = make_user(language="en")
        with mock.patch("bot.notify.send_message") as send:
            notify.notify_user(
                user,
                "n_match_found",
                buttons=[("btn_match_yes", "match:yes:1")],
                title="Bag",
                room="104",
            )
        label, data = send.call_args.args[2][0]
        self.assertEqual(data, "match:yes:1")
        self.assertNotEqual(label, "btn_match_yes")

    def test_button_labels_can_use_the_same_placeholders_as_the_text(self):
        # Regression: the "reopen" button of the expiry message has {title} in its label.
        user = make_user(language="en")
        with mock.patch("bot.notify.send_message") as send:
            notify.notify_user(
                user, "n_expired", buttons=[("btn_reopen", "reopen:7")], title="Blue bag"
            )
        label, data = send.call_args.args[2][0]
        self.assertIn("Blue bag", label)
        self.assertEqual(data, "reopen:7")


class FetchPhotoTest(AppTestCase):
    def test_a_strange_id_is_refused(self):
        self.assertIsNone(notify.fetch_photo("../../etc/passwd"))

    def test_without_a_token_and_a_cached_file_there_is_nothing(self):
        self.assertIsNone(notify.fetch_photo("AgACAgIAAxkBAAI"))


class RunBotCommandTest(AppTestCase):
    def test_runbot_explains_a_missing_token(self):
        from django.core.management import CommandError, call_command

        with self.assertRaisesMessage(CommandError, "BOT_TOKEN"):
            call_command("runbot")
