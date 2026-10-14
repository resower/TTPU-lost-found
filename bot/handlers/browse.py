"""Recent found items (last 30 days) and the 'This is mine' button."""

from aiogram import F, Router
from aiogram.types import FSInputFile

from .. import queries
from ..db import db
from ..keyboards import grid, inline
from ..strings import t

router = Router()
PAGE_SIZE = 3  # cards per page


@router.callback_query(F.data == "menu:recent")
async def choose_category(call, user):
    lang = user.language
    pairs = await db(queries.categories, lang)
    buttons = [(t(lang, "all_categories"), "recent:0:0")]
    buttons += [(label, f"recent:{pk}:0") for pk, label in pairs]
    await call.answer()
    await call.message.answer(t(lang, "recent_prompt"), reply_markup=inline(grid(buttons)))


@router.callback_query(F.data.startswith("recent:"))
async def show_page(call, user):
    lang = user.language
    _, category_id, page = call.data.split(":")
    category_id, page = int(category_id), int(page)
    cards = await db(queries.recent_cards, lang, category_id)
    await call.answer()
    if not cards:
        await call.message.answer(t(lang, "recent_empty"))
        return
    first = page * PAGE_SIZE
    for card in cards[first : first + PAGE_SIZE]:
        await send_card(call.message, card, lang)
    if first + PAGE_SIZE < len(cards):
        shown = f"{first + PAGE_SIZE}/{len(cards)}"
        more = [[(t(lang, "btn_more"), f"recent:{category_id}:{page + 1}")]]
        await call.message.answer(shown, reply_markup=inline(more))


async def send_card(message, card, lang):
    markup = inline([[(t(lang, "btn_this_is_mine"), f"mine:{card['kind']}:{card['id']}")]])
    if card["photo_id"]:
        await message.answer_photo(card["photo_id"], caption=card["text"], reply_markup=markup)
    elif card["photo_path"]:
        photo = FSInputFile(card["photo_path"])
        await message.answer_photo(photo, caption=card["text"], reply_markup=markup)
    else:
        await message.answer(card["text"], reply_markup=markup)


@router.callback_query(F.data.startswith("mine:"))
async def this_is_mine(call, user):
    """Creates a suggestion that the office will review."""
    lang = user.language
    _, kind, pk = call.data.split(":")
    result = await db(queries.claim, user, kind, int(pk))
    key = {"ok": "claim_sent", "need_lost": "need_lost_report", "missing": "recent_empty"}[result]
    await call.answer(t(lang, key), show_alert=True)
