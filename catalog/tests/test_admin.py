from io import StringIO

from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse

from catalog.testing import AppTestCase

OUR_APPS = {"catalog", "reports", "storage", "matching", "worker"}


class AdminTest(AppTestCase):
    """Every model of ours is in the admin, and its pages open (with real rows in them)."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=StringIO())

    def setUp(self):
        self.client.force_login(get_user_model().objects.get(username="office"))

    def test_every_model_is_registered(self):
        for model in apps.get_models():
            if model._meta.app_label in OUR_APPS:
                self.assertIn(model, admin.site._registry, model.__name__)

    def test_list_add_and_change_pages_open(self):
        for model in admin.site._registry:
            if model._meta.app_label not in OUR_APPS:
                continue
            page = f"admin:{model._meta.app_label}_{model._meta.model_name}"
            with self.subTest(model=model.__name__):
                self.assertEqual(self.client.get(reverse(f"{page}_changelist")).status_code, 200)
                self.assertEqual(self.client.get(reverse(f"{page}_add")).status_code, 200)
                first = model.objects.first()
                if first:  # some tables (the worker's job state) start empty
                    change = reverse(f"{page}_change", args=[first.pk])
                    self.assertEqual(self.client.get(change).status_code, 200)
