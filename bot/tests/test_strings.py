import re
from pathlib import Path
from string import Formatter

from django.conf import settings
from django.test import SimpleTestCase

from bot.strings import DEFAULT_LANGUAGE, LANGUAGES, STRINGS, t
from reports.models import FoundReport, LostReport


def placeholders(text):
    return {name for _literal, name, _spec, _conv in Formatter().parse(text) if name}


class StringsTest(SimpleTestCase):
    def test_every_text_exists_in_all_three_languages(self):
        for key, texts in STRINGS.items():
            for lang in LANGUAGES:
                self.assertTrue(texts.get(lang, "").strip(), f"{key} is empty in {lang}")

    def test_every_language_uses_the_same_placeholders(self):
        for key, texts in STRINGS.items():
            found = {lang: placeholders(texts[lang]) for lang in LANGUAGES}
            self.assertEqual(
                len({frozenset(names) for names in found.values()}), 1, f"{key}: {found}"
            )

    def test_every_key_used_in_the_code_exists(self):
        patterns = [
            r'\bt\(\s*[\w.]+,\s*"(\w+)"',  # t(lang, "key")
            r'notify_user\(\s*[\w.]+,\s*"(\w+)"',  # notify_user(user, "key")
            r'\("(btn_\w+)",',  # button lists: ("btn_key", "callback")
            r'"(btn_\w+)"',
        ]
        used = set()
        for folder in ("bot", "matching", "storage", "worker"):
            for path in Path(settings.BASE_DIR, folder).rglob("*.py"):
                if "tests" in path.parts:
                    continue
                for pattern in patterns:
                    used.update(re.findall(pattern, path.read_text()))
        self.assertGreater(len(used), 20)  # the search itself works
        self.assertEqual(sorted(used - set(STRINGS)), [])

    def test_there_is_a_text_for_every_report_status(self):
        for status in set(LostReport.Status.values) | set(FoundReport.Status.values):
            self.assertIn(f"status_{status}", STRINGS)

    def test_t_fills_placeholders_and_falls_back_to_uzbek(self):
        self.assertIn("Blue bag", t("en", "n_item_registered", title="Blue bag", shelf="A1-01"))
        self.assertEqual(t("de", "menu_title"), t(DEFAULT_LANGUAGE, "menu_title"))
