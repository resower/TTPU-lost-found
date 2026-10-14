"""Talk to Telegram from the web app and the worker, without running the bot loop.

Messages are sent with plain HTTP calls to the Bot API. If BOT_TOKEN is empty
(development, tests) nothing is sent and the function just returns False.
"""

import logging
import re
from pathlib import Path

import httpx
from django.conf import settings

from .strings import t

log = logging.getLogger(__name__)
API = "https://api.telegram.org"


def send_message(chat_id, text, buttons=None):
    """Send `text`. `buttons` is a list of (label, callback_data), one button per row.

    Returns True if Telegram accepted the message. A failure is logged, never raised,
    so a Telegram outage cannot break a page or a worker job.
    """
    if not settings.BOT_TOKEN:
        log.debug("BOT_TOKEN is not set, skipped a message to chat %s", chat_id)
        return False
    payload = {"chat_id": chat_id, "text": text}
    if buttons:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": label, "callback_data": data}] for label, data in buttons]
        }
    try:
        response = httpx.post(
            f"{API}/bot{settings.BOT_TOKEN}/sendMessage", json=payload, timeout=10
        )
        response.raise_for_status()
    except httpx.HTTPError:
        log.exception("Could not send a Telegram message to chat %s", chat_id)
        return False
    return True


def notify_user(user, key, buttons=None, **fields):
    """Send a text from strings.py to a TelegramUser, in their language.

    `buttons` is a list of (string key, callback_data); the labels are translated too, and
    may use the same {placeholders} as the text.
    """
    text = t(user.language, key, **fields)
    labelled = [(t(user.language, label_key, **fields), data) for label_key, data in buttons or []]
    return send_message(user.telegram_id, text, labelled)


def notify_status(user, title, status):
    """Tell a reporter that their report changed status (matched, returned, expired...)."""
    return notify_user(
        user, "n_report_status", title=title, status=t(user.language, f"status_{status}")
    )


def fetch_photo(file_id):
    """Download a Telegram photo once and keep it in the media folder. Returns its path or None."""
    if not re.fullmatch(r"[\w-]+", file_id):
        return None
    target = Path(settings.MEDIA_ROOT) / "telegram" / f"{file_id}.jpg"
    if target.exists():
        return target
    if not settings.BOT_TOKEN:
        return None
    try:
        info = httpx.get(
            f"{API}/bot{settings.BOT_TOKEN}/getFile", params={"file_id": file_id}, timeout=10
        ).json()
        file_path = info["result"]["file_path"]
        data = httpx.get(f"{API}/file/bot{settings.BOT_TOKEN}/{file_path}", timeout=20).content
    except (httpx.HTTPError, KeyError, ValueError):
        log.exception("Could not download Telegram photo")
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target
