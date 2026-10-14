import csv
import io
import tempfile
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.http import Http404
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.testing import (
    AppTestCase,
    make_category,
    make_color,
    make_found,
    make_item,
    make_lost,
    make_staff,
)
from matching.models import MatchSuggestion
from reports.models import FoundReport
from storage.models import Handover, StoredItem
from storage.views import media_file


class StaffTestCase(AppTestCase):
    """Starts every test logged in as office staff."""

    def setUp(self):
        self.staff = make_staff()
        self.client.force_login(self.staff)

    def messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]


class AccessTest(AppTestCase):
    def test_every_page_asks_anonymous_visitors_to_log_in(self):
        item = make_item()
        urls = [
            reverse("dashboard"),
            reverse("storage_list"),
            reverse("receive_item"),
            reverse("export_csv"),
            reverse("storage_detail", args=[item.pk]),
            reverse("return_item", args=[item.pk]),
            reverse("lost_list"),
            reverse("reference"),
            reverse("media_file", args=["items/x.jpg"]),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertTrue(response["Location"].startswith("/login/"), url)

    def test_posts_are_protected_too(self):
        item = make_item()
        response = self.client.post(reverse("change_status", args=[item.pk]), {"action": "dispose"})
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.status, StoredItem.Status.IN_STORAGE)

    def test_a_logged_in_user_who_is_not_staff_is_sent_away(self):
        student = get_user_model().objects.create_user("student", password="pass12345")
        self.client.force_login(student)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_staff_can_log_in_and_a_non_staff_account_cannot(self):
        make_staff()
        get_user_model().objects.create_user("student", password="pass12345")
        ok = self.client.post("/login/", {"username": "staff", "password": "pass12345"})
        self.assertRedirects(ok, "/", fetch_redirect_response=False)
        self.client.logout()
        refused = self.client.post("/login/", {"username": "student", "password": "pass12345"})
        self.assertEqual(refused.status_code, 200)
        self.assertContains(refused, "errorlist")

    def test_the_login_page_is_open(self):
        self.assertEqual(self.client.get("/login/").status_code, 200)


class DashboardTest(StaffTestCase):
    def test_numbers_and_chart_data(self):
        today = timezone.localdate()
        make_item(category=make_category("Bags"))
        make_item(category=make_category("Bags"), retention_until=today + timedelta(days=2))
        make_item(category=make_category("Keys"), retention_until=today - timedelta(days=2))
        make_lost()
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        stats = response.context["stats"]
        self.assertEqual(
            (
                stats["in_storage"],
                stats["expiring"],
                stats["ready_for_disposal"],
                stats["open_lost"],
            ),
            (3, 1, 1, 1),
        )
        self.assertEqual(
            response.context["by_category"], {"labels": ["Bags", "Keys"], "values": [2, 1]}
        )

    def test_the_empty_dashboard_renders(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)


class StorageListTest(StaffTestCase):
    def setUp(self):
        super().setUp()
        self.bag = make_item(title="Blue backpack", shelf_code="A1-01")
        self.key = make_item(title="House key", category=make_category("Keys"), shelf_code="B1-02")
        self.old = make_item(
            title="Old coat", shelf_code="C1-03", status=StoredItem.Status.RETURNED
        )

    def titles(self, **params):
        response = self.client.get(reverse("storage_list"), params)
        return sorted(item.title for item in response.context["items"])

    def test_shows_items_in_storage_by_default(self):
        self.assertEqual(self.titles(), ["Blue backpack", "House key"])

    def test_filters(self):
        self.assertEqual(self.titles(status=""), ["Blue backpack", "House key", "Old coat"])
        self.assertEqual(self.titles(status="returned"), ["Old coat"])
        self.assertEqual(self.titles(q="key", status=""), ["House key"])
        self.assertEqual(self.titles(shelf="b1", status=""), ["House key"])
        self.assertEqual(self.titles(category=self.key.category_id, status=""), ["House key"])

    def test_expiring_filter(self):
        self.key.retention_until = timezone.localdate() + timedelta(days=2)
        self.key.save()
        self.assertEqual(self.titles(expiring="on", status=""), ["House key"])

    def test_csv_export_has_only_items_in_storage(self):
        response = self.client.get(reverse("export_csv"))
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[0], ["shelf", "category", "title", "color", "received", "keep until"])
        self.assertEqual([row[0] for row in rows[1:]], ["A1-01", "B1-02"])
        self.assertIn("attachment", response["Content-Disposition"])


class ReceiveItemTest(StaffTestCase):
    def form_data(self, **fields):
        data = {
            "category": make_category().pk,
            "title": "Black wallet",
            "description": "Leather",
            "color": make_color("Black").pk,
            "shelf_code": "a1-01",
        }
        return {**data, **fields}

    def test_the_form_suggests_the_next_free_shelf_code(self):
        make_item(shelf_code="A1-01")
        response = self.client.get(reverse("receive_item"))
        self.assertEqual(response.context["form"].initial["shelf_code"], "A1-02")

    def test_a_found_report_prefills_the_form(self):
        report = make_found(title="Green scarf")
        response = self.client.get(reverse("receive_item"), {"found": report.pk})
        self.assertEqual(response.context["form"].initial["title"], "Green scarf")

    def test_saving_creates_the_item(self):
        response = self.client.post(reverse("receive_item"), self.form_data())
        item = StoredItem.objects.get()
        self.assertRedirects(response, reverse("storage_detail", args=[item.pk]))
        self.assertEqual(
            (item.shelf_code, item.received_by), ("A1-01", self.staff)
        )  # code is upper-cased

    def test_linking_a_found_report_marks_it_registered(self):
        report = make_found()
        self.client.post(reverse("receive_item"), self.form_data(found_report=report.pk))
        report.refresh_from_db()
        self.assertEqual(report.status, FoundReport.Status.REGISTERED)
        self.assertEqual(StoredItem.objects.get().found_report, report)

    def test_a_used_shelf_code_is_refused(self):
        make_item(shelf_code="A1-01")
        response = self.client.post(reverse("receive_item"), self.form_data())
        self.assertEqual(response.status_code, 200)
        self.assertIn("shelf_code", response.context["form"].errors)
        self.assertEqual(StoredItem.objects.count(), 1)


class ReturnItemTest(StaffTestCase):
    def setUp(self):
        super().setUp()
        self.item = make_item()
        self.lost = make_lost()
        self.url = reverse("return_item", args=[self.item.pk])

    def test_handing_over(self):
        data = {"lost_report": self.lost.pk, "receiver_name": "Aziz", "id_last4": "4821"}
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse("storage_detail", args=[self.item.pk]))
        handover = Handover.objects.get()
        self.assertEqual((handover.id_last4, handover.lost_report), ("4821", self.lost))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, StoredItem.Status.RETURNED)

    def test_a_long_id_number_is_refused(self):
        for bad in ["AB1234567", "12345", "123", ""]:
            response = self.client.post(self.url, {"receiver_name": "Aziz", "id_last4": bad})
            self.assertIn("id_last4", response.context["form"].errors, bad)
        self.assertFalse(Handover.objects.exists())

    def test_the_confirmed_lost_report_is_preselected(self):
        MatchSuggestion.objects.create(
            lost_report=self.lost,
            stored_item=self.item,
            score=9,
            created_by="staff",
            status=MatchSuggestion.Status.CONFIRMED,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.context["form"].initial["lost_report"], self.lost)

    def test_an_item_that_already_left_cannot_be_returned(self):
        self.item.status = StoredItem.Status.DISPOSED
        self.item.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)


class ChangeStatusViewTest(StaffTestCase):
    def setUp(self):
        super().setUp()
        self.item = make_item()
        self.url = reverse("change_status", args=[self.item.pk])

    def test_dispose_and_transfer(self):
        for action, status in [("dispose", "disposed"), ("transfer", "transferred")]:
            item = make_item()
            self.client.post(
                reverse("change_status", args=[item.pk]), {"action": action, "note": "x"}
            )
            item.refresh_from_db()
            self.assertEqual(item.status, status)

    def test_the_second_change_is_refused_with_a_message(self):
        self.client.post(self.url, {"action": "dispose"})
        response = self.client.post(self.url, {"action": "transfer"}, follow=True)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, StoredItem.Status.DISPOSED)
        self.assertIn("Cannot change", self.messages(response)[-1])

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_an_unknown_action_changes_nothing(self):
        self.client.post(self.url, {"action": "explode"})
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, StoredItem.Status.IN_STORAGE)


class MediaFileTest(StaffTestCase):
    def test_serves_files_inside_the_media_folder_only(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "items").mkdir()
            (Path(folder) / "items" / "a.jpg").write_bytes(b"photo")
            (Path(folder).parent / "secret.txt").write_text("secret")
            with override_settings(MEDIA_ROOT=folder):
                ok = self.client.get(reverse("media_file", args=["items/a.jpg"]))
                self.assertEqual(b"".join(ok.streaming_content), b"photo")
                with self.assertRaises(Http404):  # ../ must not climb out of the media folder
                    media_file(RequestFactory().get("/media/x"), "../secret.txt")
                self.assertEqual(self.client.get("/media/items/missing.jpg").status_code, 404)
