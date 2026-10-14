"""The lost and the found wizard. They ask the same questions, so they share this code.

The chosen kind ("lost" or "found") is kept in the FSM data. Only the found wizard
asks the two extra questions: where the item is now, and whether the finder's
Telegram may be shown to the owner.
"""

from datetime import date, datetime, timedelta

from aiogram import F, Router
from django.utils import timezone

from .. import queries
from ..db import db
from ..keyboards import cancel_row, grid, inline, send_menu
from ..states import Wizard
from ..strings import t

router = Router()


# --- start, cancel, edit ---


@router.callback_query(F.data.in_({"menu:lost", "menu:found"}))
async def start_wizard(call, state, user):
    await state.clear()
    await state.update_data(kind=call.data.split(":")[1])
    await call.answer()
    await ask_category(call.message, state, user)


@router.callback_query(F.data == "wiz:cancel")
async def cancel(call, state, user):
    await state.clear()
    await call.answer()
    await call.message.answer(t(user.language, "cancelled"))
    await send_menu(call.message, user.language)


@router.callback_query(Wizard.summary, F.data == "wiz:edit")
async def edit(call, state, user):
    """Edit starts the questions again (the kind stays the same)."""
    kind = (await state.get_data())["kind"]
    await state.clear()
    await state.update_data(kind=kind)
    await call.answer()
    await call.message.answer(t(user.language, "restart"))
    await ask_category(call.message, state, user)


@router.callback_query(Wizard.summary, F.data == "wiz:submit")
async def submit(call, state, user):
    data = await state.get_data()
    await db(queries.save_report, user, data)
    await state.clear()
    await call.answer()
    await call.message.answer(t(user.language, f"saved_{data['kind']}"))
    await send_menu(call.message, user.language)


# --- 1. category ---


async def ask_category(message, state, user):
    lang = user.language
    await state.set_state(Wizard.category)
    pairs = await db(queries.categories, lang)
    buttons = [(label, f"cat:{pk}") for pk, label in pairs]
    await message.answer(
        t(lang, "ask_category"), reply_markup=inline(grid(buttons) + [cancel_row(lang)])
    )


@router.callback_query(Wizard.category, F.data.startswith("cat:"))
async def got_category(call, state, user):
    await state.update_data(category_id=int(call.data.split(":")[1]))
    await state.set_state(Wizard.title)
    await call.answer()
    await call.message.answer(
        t(user.language, "ask_title"), reply_markup=inline([cancel_row(user.language)])
    )


# --- 2. title and 3. description ---


@router.message(Wizard.title, F.text)
async def got_title(message, state, user):
    lang = user.language
    title = message.text.strip()
    if not 3 <= len(title) <= 100:
        await message.answer(t(lang, "err_title"))
        return
    await state.update_data(title=title)
    await state.set_state(Wizard.description)
    await message.answer(t(lang, "ask_description"), reply_markup=inline([cancel_row(lang)]))


@router.message(Wizard.description, F.text)
async def got_description(message, state, user):
    lang = user.language
    description = message.text.strip()
    if not 3 <= len(description) <= 500:
        await message.answer(t(lang, "err_description"))
        return
    await state.update_data(description=description)
    await ask_color(message, state, user)


# --- 4. color ---


async def ask_color(message, state, user):
    lang = user.language
    await state.set_state(Wizard.color)
    pairs = await db(queries.colors, lang)
    buttons = [(label, f"col:{pk}") for pk, label in pairs]
    await message.answer(
        t(lang, "ask_color"), reply_markup=inline(grid(buttons, 3) + [cancel_row(lang)])
    )


@router.callback_query(Wizard.color, F.data.startswith("col:"))
async def got_color(call, state, user):
    await state.update_data(color_id=int(call.data.split(":")[1]))
    await call.answer()
    await ask_building(call.message, state, user)


# --- 5. location: building, then area ---


async def ask_building(message, state, user):
    lang = user.language
    kind = (await state.get_data())["kind"]
    await state.set_state(Wizard.building)
    pairs = await db(queries.buildings)
    rows = grid([(name, f"bld:{pk}") for pk, name in pairs], 1)
    if kind == "lost":  # a lost report may leave the place unknown; a found report may not
        rows.append([(t(lang, "btn_unknown_loc"), "loc:none")])
    await message.answer(t(lang, "ask_building"), reply_markup=inline(rows + [cancel_row(lang)]))


@router.callback_query(Wizard.building, F.data == "loc:none")
async def got_unknown_location(call, state, user):
    await state.update_data(location_id=None)
    await call.answer()
    await ask_date(call.message, state, user)


@router.callback_query(Wizard.building, F.data.startswith("bld:"))
async def got_building(call, state, user):
    lang = user.language
    building_id = int(call.data.split(":")[1])
    await call.answer()
    pairs = await db(queries.areas, building_id)
    if not pairs:  # a building without areas is the location itself
        await state.update_data(location_id=building_id)
        await ask_date(call.message, state, user)
        return
    await state.set_state(Wizard.area)
    rows = grid([(name, f"area:{pk}") for pk, name in pairs], 1)
    await call.message.answer(t(lang, "ask_area"), reply_markup=inline(rows + [cancel_row(lang)]))


@router.callback_query(Wizard.area, F.data.startswith("area:"))
async def got_area(call, state, user):
    await state.update_data(location_id=int(call.data.split(":")[1]))
    await call.answer()
    await ask_date(call.message, state, user)


# --- 6. date ---


async def ask_date(message, state, user):
    lang = user.language
    await state.set_state(Wizard.date)
    rows = [
        [(t(lang, "btn_today"), "date:today"), (t(lang, "btn_yesterday"), "date:yesterday")],
        [(t(lang, "btn_pick_date"), "date:pick")],
        cancel_row(lang),
    ]
    await message.answer(t(lang, "ask_date"), reply_markup=inline(rows))


@router.callback_query(Wizard.date, F.data.startswith("date:"))
async def got_date_choice(call, state, user):
    choice = call.data.split(":")[1]
    await call.answer()
    if choice == "pick":
        await state.set_state(Wizard.date_text)
        await call.message.answer(
            t(user.language, "ask_date_text"), reply_markup=inline([cancel_row(user.language)])
        )
        return
    day = timezone.localdate() - timedelta(days=1 if choice == "yesterday" else 0)
    await save_date(call.message, state, user, day)


@router.message(Wizard.date_text, F.text)
async def got_date_text(message, state, user):
    try:
        day = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        day = None
    if day is None or day > timezone.localdate():
        await message.answer(t(user.language, "err_date"))
        return
    await save_date(message, state, user, day)


async def save_date(message, state, user, day):
    await state.update_data(date=day.isoformat())
    await ask_photo(message, state, user)


# --- 7. optional photo ---


async def ask_photo(message, state, user):
    lang = user.language
    await state.set_state(Wizard.photo)
    rows = [[(t(lang, "btn_skip"), "photo:skip")], cancel_row(lang)]
    await message.answer(t(lang, "ask_photo"), reply_markup=inline(rows))


@router.message(Wizard.photo, F.photo)
async def got_photo(message, state, user):
    # Telegram sends several sizes; the last one is the biggest. We keep only its file_id.
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await after_photo(message, state, user)


@router.message(Wizard.photo)
async def wrong_photo(message, user):
    await message.answer(t(user.language, "err_photo"))


@router.callback_query(Wizard.photo, F.data == "photo:skip")
async def skip_photo(call, state, user):
    await call.answer()
    await after_photo(call.message, state, user)


async def after_photo(message, state, user):
    if (await state.get_data())["kind"] == "found":
        await ask_where(message, state, user)
    else:
        await show_summary(message, state, user)


# --- 8. found wizard only: where is the item, and may we share the finder's contact ---


async def ask_where(message, state, user):
    lang = user.language
    await state.set_state(Wizard.where)
    rows = [
        [(t(lang, "btn_office"), "where:office")],
        [(t(lang, "btn_kept"), "where:kept")],
        cancel_row(lang),
    ]
    await message.answer(t(lang, "ask_where"), reply_markup=inline(rows))


@router.callback_query(Wizard.where, F.data.startswith("where:"))
async def got_where(call, state, user):
    kept = call.data.endswith("kept")
    await state.update_data(kept=kept)
    await call.answer()
    if not kept:
        await show_summary(call.message, state, user)
        return
    lang = user.language
    await state.set_state(Wizard.consent)
    rows = [
        [(t(lang, "btn_yes"), "consent:yes"), (t(lang, "btn_no"), "consent:no")],
        cancel_row(lang),
    ]
    await call.message.answer(t(lang, "ask_consent"), reply_markup=inline(rows))


@router.callback_query(Wizard.consent, F.data.startswith("consent:"))
async def got_consent(call, state, user):
    await state.update_data(share_contact=call.data.endswith("yes"))
    await call.answer()
    await show_summary(call.message, state, user)


# --- 9. summary ---


async def show_summary(message, state, user):
    lang = user.language
    data = await state.get_data()
    fields = await db(queries.summary_fields, data, lang)
    text = t(
        lang,
        "summary",
        kind=t(lang, f"kind_{data['kind']}"),
        title=data["title"],
        description=data["description"],
        date=date.fromisoformat(data["date"]).strftime("%d.%m.%Y"),
        photo=t(lang, "btn_yes" if data.get("photo_file_id") else "btn_no"),
        **fields,
    )
    if data["kind"] == "found":
        where = t(lang, "btn_kept" if data.get("kept") else "btn_office")
        text += t(lang, "summary_where", where=where)
    await state.set_state(Wizard.summary)
    rows = [
        [(t(lang, "btn_submit"), "wiz:submit"), (t(lang, "btn_edit"), "wiz:edit")],
        cancel_row(lang),
    ]
    await message.answer(text, reply_markup=inline(rows))
