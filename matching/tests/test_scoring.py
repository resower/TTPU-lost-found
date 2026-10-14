from datetime import date, timedelta

from django.test import SimpleTestCase

from catalog.testing import (
    AppTestCase,
    make_area,
    make_building,
    make_category,
    make_color,
    make_found,
    make_item,
    make_lost,
)
from matching.scoring import DATE_WINDOW_DAYS, WORD_CAP, match_score, words

DAY = date(2026, 9, 10)


class WordsTest(SimpleTestCase):
    def test_ignores_case_and_stop_words(self):
        self.assertEqual(words("The Blue BAG and a pen"), {"blue", "bag", "pen"})

    def test_works_for_cyrillic(self):
        self.assertEqual(words("Синяя сумка и ключи"), {"синяя", "сумка", "ключи"})


class MatchScoreTest(AppTestCase):
    def setUp(self):
        self.area = make_area(name="Library")
        self.lost = make_lost(
            date_lost=DAY, location=self.area, title="Blue backpack", description="notebooks inside"
        )

    def item(self, **fields):
        """A found report on the same day and place, wrapped in a stored item."""
        report = make_found(
            date_found=DAY,
            location=self.area,
            title="Blue backpack",
            description="notebooks inside",
        )
        return make_item(
            found_report=report, title=report.title, description="notebooks inside", **fields
        )

    def test_perfect_match_adds_every_part(self):
        score, breakdown = match_score(self.lost, self.item())
        self.assertEqual(breakdown, {"color": 3, "date": 2, "building": 2, "area": 1, "words": 4})
        self.assertEqual(score, 12)

    def test_different_category_is_never_a_match(self):
        other = make_category("Keys")
        self.assertEqual(match_score(self.lost, self.item(category=other)), (0, {}))

    def test_different_color_loses_the_color_points(self):
        _score, breakdown = match_score(self.lost, self.item(color=make_color("Red")))
        self.assertNotIn("color", breakdown)

    def test_words_are_capped(self):
        text = "one two three four five six seven"
        lost = make_lost(title=text, description="", date_lost=DAY)
        item = make_item(title=text, description="")
        _score, breakdown = match_score(lost, item)
        self.assertEqual(breakdown["words"], WORD_CAP)

    def test_date_window(self):
        def date_points(days_after_loss):
            report = make_found(date_found=DAY + timedelta(days=days_after_loss))
            item = make_item(found_report=report)
            return match_score(self.lost, item)[1].get("date", 0)

        self.assertEqual(date_points(0), 2)
        self.assertEqual(date_points(DATE_WINDOW_DAYS), 2)
        self.assertEqual(date_points(DATE_WINDOW_DAYS + 1), 0)
        self.assertEqual(date_points(-1), 0)  # found before it was lost: not this item

    def test_same_building_other_area_gets_building_points_only(self):
        other_area = make_area(self.area.parent, "Cafeteria")
        report = make_found(date_found=DAY, location=other_area)
        _score, breakdown = match_score(self.lost, make_item(found_report=report))
        self.assertEqual((breakdown["building"], "area" in breakdown), (2, False))

    def test_other_building_gets_no_location_points(self):
        far = make_area(make_building("Engineering block"), "Lab")
        report = make_found(date_found=DAY, location=far)
        _score, breakdown = match_score(self.lost, make_item(found_report=report))
        self.assertNotIn("building", breakdown)

    def test_unknown_lost_location_gets_no_location_points(self):
        lost = make_lost(date_lost=DAY, location=None)
        _score, breakdown = match_score(lost, self.item())
        self.assertNotIn("building", breakdown)

    def test_item_without_report_uses_the_received_date(self):
        # A walk-in item has no found report: it counts as found on the day it was received.
        item = make_item()
        lost = make_lost(date_lost=item.found_date)
        self.assertIn("date", match_score(lost, item)[1])

    def test_works_for_a_found_report_kept_by_the_finder(self):
        report = make_found(date_found=DAY, location=self.area, kept_by_finder=True)
        score, _breakdown = match_score(self.lost, report)
        self.assertGreaterEqual(score, 8)
