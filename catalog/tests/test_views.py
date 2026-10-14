from django.urls import reverse

from catalog.models import Category, Location
from catalog.testing import AppTestCase, make_area, make_building, make_category, make_staff


class ReferenceDataTest(AppTestCase):
    def setUp(self):
        self.client.force_login(make_staff())

    def test_reference_page_lists_buildings_areas_and_categories(self):
        area = make_area(make_building("Engineering block"), "Lab 1")
        make_category("Bags")
        response = self.client.get(reverse("reference"))
        self.assertContains(response, "Engineering block")
        self.assertContains(response, area.name)
        self.assertContains(response, "Bags")

    def test_add_a_building_and_an_area(self):
        self.client.post(reverse("location_new"), {"name": "Dormitory", "floor": ""})
        building = Location.objects.get(name="Dormitory")
        self.assertIsNone(building.parent)
        self.client.post(
            reverse("location_new"), {"name": "Hall", "floor": "1", "parent": building.pk}
        )
        self.assertEqual(Location.objects.get(name="Hall").building, building)

    def test_an_area_cannot_be_the_parent_of_another_area(self):
        area = make_area()
        response = self.client.post(
            reverse("location_new"), {"name": "Shelf", "floor": "", "parent": area.pk}
        )
        self.assertIn("parent", response.context["form"].errors)

    def test_the_same_area_name_twice_in_a_building_is_refused(self):
        area = make_area()
        data = {"name": area.name, "floor": "", "parent": area.parent.pk}
        response = self.client.post(reverse("location_new"), data)
        self.assertEqual(response.status_code, 200)  # form shown again with an error
        self.assertEqual(Location.objects.filter(name=area.name).count(), 1)

    def test_edit_a_category(self):
        category = make_category("Bags", retention_days=60)
        data = {
            "emoji": "🎒",
            "name_uz": "Sumka",
            "name_ru": "Сумка",
            "name_en": "Bags",
            "retention_days": 45,
        }
        self.client.post(reverse("category_edit", args=[category.pk]), data)
        category.refresh_from_db()
        self.assertEqual((category.retention_days, category.name_uz), (45, "Sumka"))

    def test_name_in_the_current_language(self):
        category = Category(name_uz="Sumka", name_ru="Сумка", name_en="Bag")
        self.assertEqual(
            (category.label("uz"), category.label("ru"), category.label("en")),
            ("Sumka", "Сумка", "Bag"),
        )
        self.assertEqual(Category(name_en="Bag").label("uz"), "Bag")  # falls back to English
