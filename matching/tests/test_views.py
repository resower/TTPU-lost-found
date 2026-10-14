from django.urls import reverse

from catalog.testing import AppTestCase, make_item, make_lost, make_staff
from matching import services
from matching.models import MatchSuggestion
from reports.models import LostReport


class MatchViewsTest(AppTestCase):
    def setUp(self):
        self.staff = make_staff()
        self.client.force_login(self.staff)
        self.lost = make_lost()
        self.item = make_item()
        self.suggestion, _ = services.create_suggestion(self.lost, self.item, "system")

    def test_confirm(self):
        response = self.client.post(reverse("match_confirm", args=[self.suggestion.pk]))
        self.assertRedirects(response, reverse("lost_detail", args=[self.lost.pk]))
        self.suggestion.refresh_from_db()
        self.lost.refresh_from_db()
        self.assertEqual(self.suggestion.status, MatchSuggestion.Status.CONFIRMED)
        self.assertEqual(self.suggestion.reviewed_by, self.staff)
        self.assertEqual(self.lost.status, LostReport.Status.MATCHED)

    def test_reject(self):
        self.client.post(reverse("match_reject", args=[self.suggestion.pk]))
        self.suggestion.refresh_from_db()
        self.assertEqual(self.suggestion.status, MatchSuggestion.Status.REJECTED)

    def test_changes_need_a_post(self):
        for name in ("match_confirm", "match_reject"):
            response = self.client.get(reverse(name, args=[self.suggestion.pk]))
            self.assertEqual(response.status_code, 405)

    def test_picking_an_item_by_hand_adds_a_staff_suggestion(self):
        other = make_item(title="Black wallet")
        self.client.post(reverse("match_pick", args=[self.lost.pk]), {"stored_item": other.pk})
        suggestion = MatchSuggestion.objects.get(stored_item=other)
        self.assertEqual(suggestion.created_by, MatchSuggestion.CreatedBy.STAFF)

    def test_picking_the_same_item_twice_adds_only_one(self):
        url = reverse("match_pick", args=[self.lost.pk])
        self.client.post(url, {"stored_item": self.item.pk})
        self.client.post(url, {"stored_item": self.item.pk})
        self.assertEqual(MatchSuggestion.objects.count(), 1)
