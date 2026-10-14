from aiogram.fsm.state import State, StatesGroup


class Wizard(StatesGroup):
    """Steps of the lost and found wizards (they share the same flow)."""

    category = State()
    title = State()
    description = State()
    color = State()
    building = State()
    area = State()
    date = State()
    date_text = State()
    photo = State()
    where = State()  # found wizard only: handed to the office or still with the finder
    consent = State()  # found wizard only: may the owner see the finder's Telegram?
    summary = State()
