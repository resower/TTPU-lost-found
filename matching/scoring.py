"""How well does a lost report match a found item? A small, explainable score.

All the weights are constants at the top, so you can change them in one place.
"""

import re

from django.utils.translation import gettext_lazy as _

W_COLOR = 3  # same color
W_DATE = 2  # lost on or before the day it was found, within DATE_WINDOW_DAYS
W_BUILDING = 2  # same building
W_AREA = 1  # same area too (added on top of W_BUILDING)
W_WORD = 1  # each shared word in the title/description
WORD_CAP = 4  # the word points never go above this
DATE_WINDOW_DAYS = 14
THRESHOLD = 5  # the worker creates a suggestion from this score up

# How a breakdown key is shown to staff.
LABELS = {
    "color": _("color"),
    "date": _("date"),
    "building": _("building"),
    "area": _("area"),
    "words": _("words"),
}

STOP_WORDS = {
    # English
    "a", "an", "the", "and", "or", "of", "with", "in", "on", "at", "to", "for", "is", "it", "my",
    # Russian
    "и", "в", "на", "с", "у", "по", "для", "это", "мой", "моя",
    # Uzbek
    "va", "bilan", "uchun", "bu", "men", "mening", "bir",
}  # fmt: skip


def words(text):
    """Lower-cased words of a text, without stop words."""
    return {word for word in re.findall(r"\w+", text.lower()) if word not in STOP_WORDS}


def match_score(lost, item):
    """Score a LostReport against a StoredItem or a FoundReport.

    Returns (score, breakdown). The breakdown says where each point came from.
    A different category means no match at all.
    """
    if lost.category_id != item.category_id:
        return 0, {}

    breakdown = {}

    if lost.color_id and lost.color_id == item.color_id:
        breakdown["color"] = W_COLOR

    days = (item.found_date - lost.date_lost).days
    if 0 <= days <= DATE_WINDOW_DAYS:
        breakdown["date"] = W_DATE

    place = item.found_location
    if lost.location and place and lost.location.building.id == place.building.id:
        breakdown["building"] = W_BUILDING
        if lost.location_id == place.id:
            breakdown["area"] = W_AREA

    shared = words(lost.search_text) & words(item.search_text)
    if shared:
        breakdown["words"] = min(len(shared) * W_WORD, WORD_CAP)

    return sum(breakdown.values()), breakdown
