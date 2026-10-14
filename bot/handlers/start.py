from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.state import default_state

from .. import queries
from ..db import db
from ..keyboards import language_keyboard, send_menu
from ..strings import LANGUAGES, t

router = Router()


@router.message(CommandStart())
@router.message(Command("settings"))
async def choose_language(message, state, user):
    """/start and /settings both begin with the language choice."""
    await state.clear()
    await message.answer(t(user.language, "lang_prompt"), reply_markup=language_keyboard())


@router.callback_query(F.data.startswith("lang:"))
async def language_chosen(call, user):
    lang = call.data.split(":")[1]
    await call.answer()
    if lang in LANGUAGES:
        await db(queries.set_language, user, lang)
        await send_menu(call.message, lang)


@router.message(StateFilter(default_state))
async def not_understood(message, user):
    """Any other message, when no wizard is running."""
    await message.answer(t(user.language, "not_understood"))
