"""My reports: list, cancel an open report, reopen an expired one."""

from aiogram import F, Router

from .. import queries
from ..db import db
from ..keyboards import inline
from ..strings import t

router = Router()


@router.callback_query(F.data == "menu:mine")
async def list_reports(call, user):
    lang = user.language
    reports = await db(queries.my_reports, user, lang)
    await call.answer()
    if not reports:
        await call.message.answer(t(lang, "mine_empty"))
        return
    text = t(lang, "mine_title") + "\n\n" + "\n".join(report["line"] for report in reports)
    rows = []
    for report in reports:
        if report["action"] == "cancel":
            label = t(lang, "btn_cancel_report", title=report["title"])
            rows.append([(label, f"cancel:{report['kind']}:{report['id']}")])
        elif report["action"] == "reopen":
            label = t(lang, "btn_reopen", title=report["title"])
            rows.append([(label, f"reopen:{report['id']}")])
    await call.message.answer(text, reply_markup=inline(rows) if rows else None)


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_report(call, user):
    _, kind, pk = call.data.split(":")
    done = await db(queries.cancel_report, user, kind, int(pk))
    await call.answer(t(user.language, "report_cancelled") if done else None)


@router.callback_query(F.data.startswith("reopen:"))
async def reopen_report(call, user):
    """Also used by the 'your report expired' message sent by the worker."""
    done = await db(queries.reopen_report, user, int(call.data.split(":")[1]))
    await call.answer(t(user.language, "report_reopened") if done else None)
