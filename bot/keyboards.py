from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .strings import t


def inline(rows):
    """Build a keyboard from rows of (text, callback_data) pairs."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
            for row in rows
        ]
    )


def grid(buttons, per_row=2):
    """Split a flat list of buttons into rows."""
    return [buttons[i : i + per_row] for i in range(0, len(buttons), per_row)]


def cancel_row(lang):
    return [(t(lang, "btn_cancel"), "wiz:cancel")]


def language_keyboard():
    return inline([[("O'zbekcha", "lang:uz"), ("Русский", "lang:ru"), ("English", "lang:en")]])


def main_menu(lang):
    return inline(
        [
            [(t(lang, "btn_lost"), "menu:lost")],
            [(t(lang, "btn_found"), "menu:found")],
            [(t(lang, "btn_recent"), "menu:recent")],
            [(t(lang, "btn_mine"), "menu:mine")],
        ]
    )


async def send_menu(message, lang):
    await message.answer(t(lang, "menu_title"), reply_markup=main_menu(lang))
