"""The owner's Yes / No answer to 'an item similar to yours was handed to the office'."""

from aiogram import F, Router

from .. import queries
from ..db import db
from ..strings import t

router = Router()


@router.callback_query(F.data.startswith("match:"))
async def answer(call, user):
    _, choice, pk = call.data.split(":")
    yes = choice == "yes"
    done = await db(queries.answer_match, user, int(pk), yes)
    await call.answer()
    if done:
        await call.message.edit_reply_markup(reply_markup=None)  # remove the buttons
        await call.message.answer(t(user.language, "match_yes_ack" if yes else "match_no_ack"))
