"""A pretend Telegram, so the bot can be tested without a token or internet.

FakeTelegram feeds updates (messages, button presses) into the real dispatcher and records
everything the bot sends back.
"""

import itertools
import time
from datetime import datetime

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import SendMessage
from aiogram.types import Chat, Message

from bot.main import build_dispatcher

_ids = itertools.count(1)
_dispatcher = None


def get_dispatcher():
    """The routers can be attached to only one dispatcher, so every test shares this one."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = build_dispatcher()
    _dispatcher.fsm.storage.storage.clear()  # forget the wizard state of earlier tests
    return _dispatcher


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []

    async def close(self):
        pass

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, SendMessage):
            chat = Chat(id=method.chat_id, type="private")
            return Message(
                message_id=next(_ids), date=datetime.now(), chat=chat, text=method.text
            ).as_(bot)
        return True

    async def stream_content(self, *args, **kwargs):
        yield b""


class FakeTelegram:
    def __init__(self, user_id=111, username="aziz", name="Aziz"):
        self.session = FakeSession()
        self.bot = Bot(token="123456:fake-token", session=self.session)
        self.dispatcher = get_dispatcher()
        self.person = {"id": user_id, "is_bot": False, "first_name": name, "username": username}

    def _message(self, **extra):
        return {
            "message_id": next(_ids),
            "date": int(time.time()),
            "chat": {"id": self.person["id"], "type": "private"},
            "from": self.person,
            **extra,
        }

    async def _feed(self, **update):
        await self.dispatcher.feed_raw_update(self.bot, {"update_id": next(_ids), **update})

    async def say(self, text):
        """The user types a message. '/start' is sent as a command."""
        extra = {"text": text}
        if text.startswith("/"):
            extra["entities"] = [
                {"type": "bot_command", "offset": 0, "length": len(text.split()[0])}
            ]
        await self._feed(message=self._message(**extra))

    async def send_photo(self, file_id="AgACphoto"):
        sizes = [
            {"file_id": "small", "file_unique_id": "a", "width": 90, "height": 90},
            {"file_id": file_id, "file_unique_id": "b", "width": 800, "height": 800},
        ]
        await self._feed(message=self._message(photo=sizes))

    async def press(self, data):
        """The user presses an inline button with this callback data."""
        query = {
            "id": str(next(_ids)),
            "from": self.person,
            "chat_instance": "1",
            "data": data,
            "message": self._message(),
        }
        await self._feed(callback_query=query)

    # --- what the bot sent ---

    def texts(self):
        return [call.text for call in self.session.calls if isinstance(call, SendMessage)]

    def buttons(self):
        """Callback data of every button in the last message that had a keyboard."""
        for call in reversed(self.session.calls):
            markup = getattr(call, "reply_markup", None)
            if markup:
                return [b.callback_data for row in markup.inline_keyboard for b in row]
        return []

    def alerts(self):
        """Texts shown in pop-ups after a button press."""
        return [
            c.text
            for c in self.session.calls
            if type(c).__name__ == "AnswerCallbackQuery" and c.text
        ]
