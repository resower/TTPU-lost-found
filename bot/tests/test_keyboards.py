from django.test import SimpleTestCase

from bot import keyboards


class KeyboardsTest(SimpleTestCase):
    def test_inline_builds_rows_of_buttons(self):
        markup = keyboards.inline([[("A", "a"), ("B", "b")], [("C", "c")]])
        rows = [[(b.text, b.callback_data) for b in row] for row in markup.inline_keyboard]
        self.assertEqual(rows, [[("A", "a"), ("B", "b")], [("C", "c")]])

    def test_grid_splits_buttons_into_rows(self):
        self.assertEqual(keyboards.grid([1, 2, 3, 4, 5]), [[1, 2], [3, 4], [5]])

    def test_main_menu_has_four_actions_in_every_language(self):
        for lang in ("uz", "ru", "en"):
            data = [row[0].callback_data for row in keyboards.main_menu(lang).inline_keyboard]
            self.assertEqual(data, ["menu:lost", "menu:found", "menu:recent", "menu:mine"])

    def test_every_callback_fits_in_telegrams_64_bytes(self):
        for button_row in keyboards.language_keyboard().inline_keyboard:
            for button in button_row:
                self.assertLessEqual(len(button.callback_data.encode()), 64)
