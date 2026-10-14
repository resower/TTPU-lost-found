from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command

from catalog.models import Category, Location
from catalog.testing import AppTestCase
from matching.models import MatchSuggestion
from matching.services import run_matching
from reports.models import FoundReport, LostReport
from storage.models import Handover, StoredItem


def seed(*args):
    out = StringIO()
    call_command("seed_demo", *args, stdout=out)
    return out.getvalue()


class SeedDemoTest(AppTestCase):
    def test_creates_the_planned_amount_of_data(self):
        seed()
        self.assertEqual(LostReport.objects.count(), 40)
        self.assertEqual(FoundReport.objects.count(), 30)
        self.assertEqual(StoredItem.objects.count(), 25)
        self.assertEqual(Handover.objects.count(), 4)
        self.assertEqual(Category.objects.count(), 9)
        self.assertEqual(Location.objects.filter(parent=None).count(), 3)
        self.assertEqual(Location.objects.exclude(parent=None).count(), 20)
        self.assertTrue(get_user_model().objects.get(username="office").is_staff)

    def test_has_every_kind_of_state_a_demo_needs(self):
        seed()
        items = StoredItem.objects.all()
        self.assertEqual(sum(item.expiring_soon for item in items), 2)
        self.assertEqual(sum(item.ready_for_disposal for item in items), 2)
        statuses = set(MatchSuggestion.objects.values_list("status", flat=True))
        self.assertEqual(statuses, {"suggested", "confirmed"})
        self.assertTrue(MatchSuggestion.objects.filter(reporter_answer="yes").exists())
        self.assertTrue(MatchSuggestion.objects.filter(found_report__isnull=False).exists())
        self.assertTrue(FoundReport.objects.filter(kept_by_finder=True).exists())

    def test_the_worker_has_something_to_find(self):
        seed()
        self.assertGreaterEqual(len(run_matching()), 2)

    def test_running_it_twice_does_not_duplicate_anything(self):
        seed()
        self.assertIn("already there", seed())
        self.assertEqual(LostReport.objects.count(), 40)
        self.assertEqual(get_user_model().objects.filter(username="office").count(), 1)

    def test_reset_rebuilds_the_data(self):
        seed()
        seed("--reset")
        self.assertEqual(LostReport.objects.count(), 40)
        self.assertEqual(StoredItem.objects.count(), 25)
