from django.urls import reverse

from catalog.testing import AppTestCase, make_category, make_item, make_lost, make_staff
from matching.models import MatchSuggestion
from reports.models import LostReport


class LostReportViewsTest(AppTestCase):
    def setUp(self):
        self.client.force_login(make_staff())
        self.bag = make_lost(title="Blue backpack")
        self.key = make_lost(title="House key", category=make_category("Keys"))
        self.done = make_lost(title="Old coat", status=LostReport.Status.RETURNED)

    def titles(self, **params):
        response = self.client.get(reverse("lost_list"), params)
        return sorted(report.title for report in response.context["reports"])

    def test_list_shows_open_reports_by_default(self):
        self.assertEqual(self.titles(), ["Blue backpack", "House key"])

    def test_list_filters(self):
        self.assertEqual(self.titles(status=""), ["Blue backpack", "House key", "Old coat"])
        self.assertEqual(self.titles(status="returned"), ["Old coat"])
        self.assertEqual(self.titles(q="house", status=""), ["House key"])
        self.assertEqual(self.titles(category=self.key.category_id, status=""), ["House key"])

    def test_detail_lists_suggestions_with_the_reason(self):
        item = make_item()
        MatchSuggestion.objects.create(
            lost_report=self.bag,
            stored_item=item,
            score=8,
            breakdown={"color": 3, "date": 2},
            created_by="system",
        )
        response = self.client.get(
            reverse("lost_detail", args=[self.bag.pk]), headers={"accept-language": "en"}
        )
        self.assertContains(response, "color +3")
        self.assertContains(response, item.shelf_code)

    def test_detail_of_a_report_without_suggestions(self):
        self.assertEqual(
            self.client.get(reverse("lost_detail", args=[self.key.pk])).status_code, 200
        )

    def test_telegram_photo_with_a_strange_id_is_not_found(self):
        response = self.client.get(reverse("tg_photo", args=["..etc"]))
        self.assertEqual(response.status_code, 404)

    def test_telegram_photo_without_a_token_is_not_found(self):
        self.assertEqual(
            self.client.get(reverse("tg_photo", args=["AgACAgIAAxkBAAI"])).status_code, 404
        )

    def test_the_pages_are_in_uzbek_by_default_and_English_on_request(self):
        uzbek = self.client.get(reverse("lost_list"))
        english = self.client.get(reverse("lost_list"), headers={"accept-language": "en"})
        self.assertContains(uzbek, "<h1>Yo'qolgan buyumlar</h1>", html=True)
        self.assertContains(uzbek, '<html lang="uz">')
        self.assertContains(english, "<h1>Lost reports</h1>", html=True)
