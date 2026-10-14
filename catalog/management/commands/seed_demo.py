"""Fill the database with believable demo data, so every page has something to show.

    python manage.py seed_demo            # fill an empty database
    python manage.py seed_demo --reset    # delete all reports, items and reference data first

It also creates the office login:  office / office12345
Everything is built with the same service functions the real app uses, then the dates are
moved into the past, so the data tells a story over the last two months.
"""

import random
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.test import override_settings
from django.utils import timezone

from catalog.models import Category, Color, Location
from matching import services as matching
from matching.models import MatchSuggestion
from reports.models import FoundReport, LostReport, TelegramUser
from storage import services as storage
from storage.models import Handover, ItemStatusLog, StoredItem
from worker.models import JobState

# building -> [(area, floor)]
BUILDINGS = {
    "Main building": [
        ("Library", "2"), ("Cafeteria", "1"), ("Lobby", "1"), ("Lecture hall 101", "1"),
        ("Lecture hall 204", "2"), ("Computer lab", "3"), ("Dean's corridor", "2"),
        ("Restrooms", "2"),
    ],
    "Engineering block": [
        ("Lab 1", "1"), ("Lab 2", "1"), ("Workshop", "0"), ("Lecture hall E-12", "2"),
        ("Lobby", "1"), ("Stairwell", ""),
    ],
    "Campus grounds": [
        ("Parking", ""), ("Main entrance", ""), ("Football field", ""), ("Bus stop", ""),
        ("Garden", ""), ("Dormitory yard", ""),
    ],
}  # fmt: skip

# key -> (emoji, uz, ru, en, days the office keeps an unclaimed item)
CATEGORIES = {
    "documents": ("📄", "Hujjatlar", "Документы", "Documents", 180),
    "keys": ("🔑", "Kalitlar", "Ключи", "Keys", 60),
    "electronics": ("📱", "Elektronika", "Электроника", "Electronics", 90),
    "clothing": ("🧥", "Kiyim", "Одежда", "Clothing", 30),
    "bags": ("🎒", "Sumkalar", "Сумки", "Bags", 60),
    "bottles": ("🧴", "Shishalar", "Бутылки", "Bottles", 30),
    "books": ("📚", "Kitoblar", "Книги", "Books", 60),
    "jewellery": ("💍", "Zargarlik buyumlari", "Украшения", "Jewellery", 90),
    "other": ("📦", "Boshqa", "Другое", "Other", 30),
}

# key -> (uz, ru, en)
COLORS = {
    "black": ("Qora", "Чёрный", "Black"),
    "white": ("Oq", "Белый", "White"),
    "grey": ("Kulrang", "Серый", "Grey"),
    "red": ("Qizil", "Красный", "Red"),
    "blue": ("Ko'k", "Синий", "Blue"),
    "green": ("Yashil", "Зелёный", "Green"),
    "yellow": ("Sariq", "Жёлтый", "Yellow"),
    "brown": ("Jigarrang", "Коричневый", "Brown"),
    "pink": ("Pushti", "Розовый", "Pink"),
    "orange": ("To'q sariq", "Оранжевый", "Orange"),
    "purple": ("Binafsha", "Фиолетовый", "Purple"),
    "silver": ("Kumush", "Серебристый", "Silver"),
}

# title -> (category, description, color, brand or marks)
KINDS = {
    "Student ID card": ("documents", "Plastic student card with a photo in a blue holder", "blue", "Turin Polytechnic"),
    "Passport cover": ("documents", "Brown leather passport cover with a few papers inside", "brown", ""),
    "Dormitory keys": ("keys", "Three keys on a metal ring with a small robot keychain", "silver", "robot keychain"),
    "Car key": ("keys", "Black car key with a remote button", "black", "Chevrolet"),
    "iPhone 13": ("electronics", "Phone in a clear case with a crack in the corner of the screen", "black", "Apple"),
    "Wireless earbuds": ("electronics", "White earbuds in a small charging case", "white", "Samsung"),
    "Laptop charger": ("electronics", "Black laptop charger with a long cable", "black", "Lenovo"),
    "Power bank": ("electronics", "Grey power bank 10000 mAh with a sticker on the back", "grey", "Xiaomi"),
    "Black hoodie": ("clothing", "Warm black hoodie with a small logo on the chest", "black", "Nike"),
    "Grey scarf": ("clothing", "Soft grey wool scarf", "grey", ""),
    "Winter gloves": ("clothing", "Dark blue knitted gloves", "blue", ""),
    "Yellow raincoat": ("clothing", "Bright yellow raincoat with a hood", "yellow", ""),
    "Blue backpack": ("bags", "Blue backpack with notebooks and a pencil case inside", "blue", "Adidas"),
    "Laptop bag": ("bags", "Black laptop bag with a broken zipper", "black", "Dell"),
    "Steel water bottle": ("bottles", "Silver steel bottle with a dent near the bottom", "silver", "Thermos"),
    "Pink thermos": ("bottles", "Pink thermos with a cat sticker", "pink", ""),
    "Calculus textbook": ("books", "Thick calculus textbook with notes in the margins", "red", "Stewart"),
    "Notebook": ("books", "Green notebook full of programming lecture notes", "green", ""),
    "Silver ring": ("jewellery", "Thin silver ring with a small stone", "silver", ""),
    "Wrist watch": ("jewellery", "Brown leather watch with a round face", "brown", "Casio"),
    "Umbrella": ("other", "Large black umbrella with a wooden handle", "black", ""),
    "Glasses": ("other", "Black round glasses in a red case", "black", ""),
    "Calculator": ("other", "Scientific calculator with a scratched cover", "grey", "Casio"),
    "Sports shoes": ("other", "White running shoes in a plastic bag", "white", "Puma"),
    "Driving licence": ("documents", "Plastic driving licence in a brown leather holder", "brown", ""),
    "Bike lock key": ("keys", "Small key on a black rubber strap", "black", ""),
    "Tablet": ("electronics", "Tablet in a grey cover with a stylus", "grey", "Huawei"),
    "Headphones": ("electronics", "Over-ear headphones with a bent headband", "black", "Sony"),
    "USB flash drive": ("electronics", "Small red flash drive on a lanyard", "red", "Kingston"),
    "Blue jacket": ("clothing", "Light blue jacket with a zipper pocket", "blue", "Zara"),
    "Baseball cap": ("clothing", "Red baseball cap with a white logo", "red", ""),
    "Pencil case": ("bags", "Green pencil case with pens and a ruler", "green", ""),
    "Brown wallet": ("bags", "Brown leather wallet with a few coins", "brown", ""),
    "Blue sports bottle": ("bottles", "Blue plastic sports bottle with a loose cap", "blue", ""),
    "Physics textbook": ("books", "Physics textbook with a torn cover", "blue", "Halliday"),
    "Gold bracelet": ("jewellery", "Thin gold bracelet with a small charm", "yellow", ""),
    "Sunglasses": ("other", "Black sunglasses with a scratched lens", "black", "Ray-Ban"),
}  # fmt: skip

# Twelve lost/found pairs at different stages of the process.
# (item, stage, days ago it was lost, who created the suggestion)
BY = MatchSuggestion.CreatedBy
PAIRS = [  # (the order does not matter)
    ("Student ID card", "returned", 55, BY.SYSTEM),
    ("Dormitory keys", "returned", 48, BY.SYSTEM),
    ("iPhone 13", "returned", 42, BY.STAFF),
    ("Blue backpack", "returned", 6, BY.SYSTEM),
    ("Calculus textbook", "confirmed", 30, BY.SYSTEM),
    ("Silver ring", "confirmed", 26, BY.SYSTEM),
    ("Power bank", "confirmed", 22, BY.STAFF),
    ("Wireless earbuds", "suggested", 16, BY.SYSTEM),
    ("Black hoodie", "suggested", 12, BY.SYSTEM),  # the owner already answered "yes" in the bot
    ("Steel water bottle", "suggested", 9, BY.USER),  # the owner pressed "This is mine"
    ("Laptop bag", "worker", 7, None),  # no suggestion yet: the worker finds these two
    ("Wrist watch", "worker", 5, None),
]  # fmt: skip

NAMES = [
    "Aziz Karimov", "Dilnoza Rakhimova", "Jasur Tursunov", "Madina Yusupova", "Sherzod Abdullaev",
    "Nigora Ismoilova", "Bobur Saidov", "Malika Hamidova", "Otabek Nazarov", "Zarina Umarova",
    "Timur Ibragimov", "Kamola Sodiqova", "Eldor Rasulov", "Sevara Mirzaeva", "Doniyor Qodirov",
    "Lola Aliyeva", "Farrukh Tashmatov", "Shahzoda Norova", "Akmal Yuldashev", "Feruza Kholmatova",
    "Anvar Sobirov", "Gulnora Ergasheva", "Rustam Khasanov", "Nodira Abdurahmonova",
    "Sardor Mamatov", "Mohira Jurayeva", "Ilyos Botirov", "Barno Salimova", "Ulugbek Normatov",
    "Aziza Saidova",
]  # fmt: skip


def category_and_color(title):
    category, _description, color, _marks = KINDS[title]
    return category, color


def kinds_avoiding(titles):
    """Kinds that cannot match any of `titles` by accident (another category or another color).

    The demo should only contain the matches we planned, so random reports pick from these.
    """
    blocked = {category_and_color(title) for title in titles}
    return [title for title in KINDS if category_and_color(title) not in blocked]


class Command(BaseCommand):
    help = "Create demo data: reference data, an office login, reports, shelf items and matches."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Delete all existing data before seeding."
        )

    def handle(self, *args, **options):
        # The demo users are fake, so never try to message them, even if BOT_TOKEN is set.
        with override_settings(BOT_TOKEN=""), transaction.atomic():
            if options["reset"]:
                self.wipe()
            self.staff = self.ensure_staff()
            if LostReport.objects.exists():
                self.stdout.write("Demo data is already there. Use --reset to rebuild it.")
                return
            self.seed()
        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self.stdout.write("Office login:  office / office12345")
        for model in (LostReport, FoundReport, StoredItem, MatchSuggestion, Handover):
            self.stdout.write(f"  {model._meta.verbose_name_plural}: {model.objects.count()}")

    # ---------------------------------------------------------------- setup

    def wipe(self):
        for model in (
            MatchSuggestion, Handover, ItemStatusLog, StoredItem, FoundReport, LostReport,
            TelegramUser, Location, Category, Color, JobState,
        ):  # fmt: skip
            model.objects.all().delete()

    def ensure_staff(self):
        staff, created = get_user_model().objects.get_or_create(
            username="office", defaults={"is_staff": True, "is_superuser": True}
        )
        if created:
            staff.set_password("office12345")
            staff.save()
        return staff

    def seed(self):
        self.rng = random.Random(42)  # same data every time
        self.today = timezone.localdate()
        self.make_reference_data()
        self.users = self.make_users()
        self.make_pairs()
        kept_scarf = self.make_other_found()
        self.make_walk_ins()
        self.make_other_lost(kept_scarf)

    # ---------------------------------------------------------------- helpers

    def when(self, days_ago, hour):
        """A moment `days_ago` days before today at the given hour (local time)."""
        day = self.today - timedelta(days=days_ago)
        return timezone.make_aware(datetime.combine(day, time(hour, 0)))

    def backdate(self, obj, moment):
        type(obj).objects.filter(pk=obj.pk).update(created_at=moment)

    def place(self, building=None):
        areas = Location.objects.exclude(parent=None)
        if building:
            areas = areas.filter(parent=building)
        return self.rng.choice(list(areas))

    def make_lost(self, owner, title, days_ago, place, status=LostReport.Status.OPEN):
        category, description, color, marks = KINDS[title]
        lost = LostReport.objects.create(
            reporter=owner, category=self.categories[category], title=title,
            description=description, marks=marks, color=self.colors[color], location=place,
            date_lost=self.today - timedelta(days=days_ago), status=status,
        )  # fmt: skip
        self.backdate(lost, self.when(days_ago, 12))
        return lost

    def make_found(self, finder, title, days_ago, place, **extra):
        category, description, color, _marks = KINDS[title]
        found = FoundReport.objects.create(
            reporter=finder, category=self.categories[category], title=title,
            description=description, color=self.colors[color], location=place,
            date_found=self.today - timedelta(days=days_ago), **extra,
        )  # fmt: skip
        self.backdate(found, self.when(days_ago, 10))
        return found

    def shelve(self, title, days_ago, found=None):
        """Receive an item at the desk the way the office does, then set its date in the past."""
        category, description, color, _marks = KINDS[title]
        item = StoredItem(
            found_report=found, category=self.categories[category], title=title,
            description=description, color=self.colors[color],
            shelf_code=storage.next_free_shelf_code(), received_at=self.when(days_ago, 15),
            received_by=self.staff,
        )  # fmt: skip
        storage.register_item(item)
        ItemStatusLog.objects.filter(item=item).update(timestamp=item.received_at)
        return item

    def close(self, item, new_status, days_after):
        """Dispose of or transfer an item `days_after` days after it arrived."""
        storage.change_status(item, new_status, self.staff, note="Past its retention date")
        ItemStatusLog.objects.filter(item=item, new_status=new_status).update(
            timestamp=item.received_at + timedelta(days=days_after)
        )

    def hand_over(self, item, lost, days_after):
        handover = storage.return_item(
            item, self.staff, lost.reporter.display_name, f"{self.rng.randrange(10000):04d}", lost
        )
        moment = item.received_at + timedelta(days=days_after)
        Handover.objects.filter(pk=handover.pk).update(handed_at=moment)
        ItemStatusLog.objects.filter(item=item, new_status="returned").update(timestamp=moment)

    # ---------------------------------------------------------------- data

    def make_reference_data(self):
        self.categories = {}
        for key, (emoji, uz, ru, en, days) in CATEGORIES.items():
            self.categories[key], _ = Category.objects.get_or_create(
                name_en=en,
                defaults=dict(emoji=emoji, name_uz=uz, name_ru=ru, retention_days=days),
            )
        self.colors = {}
        for key, (uz, ru, en) in COLORS.items():
            self.colors[key], _ = Color.objects.get_or_create(
                name_en=en, defaults=dict(name_uz=uz, name_ru=ru)
            )
        for building_name, areas in BUILDINGS.items():
            building, _ = Location.objects.get_or_create(name=building_name, parent=None)
            for name, floor in areas:
                Location.objects.get_or_create(
                    name=name, parent=building, defaults={"floor": floor}
                )

    def make_users(self):
        languages = ["uz", "uz", "ru", "en"]
        users = [
            TelegramUser.objects.create(
                telegram_id=700_000_001 + i,
                username=name.split()[0].lower() + str(i),
                display_name=name,
                language=languages[i % 4],
            )
            for i, name in enumerate(NAMES)
        ]
        TelegramUser.objects.update(created_at=self.when(70, 9))
        return users

    def make_pairs(self):
        """Twelve owners who lost something that the office now holds."""
        buildings = list(Location.objects.filter(parent=None))
        for i, (title, stage, lost_ago, created_by) in enumerate(PAIRS):
            building = buildings[i % 3]
            lost_place = self.place(building)
            found_place = lost_place if i % 2 == 0 else self.place(building)
            found_ago = lost_ago - (1 + i % 3)  # found 1 to 3 days after it was lost

            lost = self.make_lost(self.users[i], title, lost_ago, lost_place)
            found = self.make_found(self.users[12 + i], title, found_ago, found_place)
            item = self.shelve(title, found_ago, found)
            if stage == "worker":
                continue  # the worker will suggest these when it first runs

            suggestion, _ = matching.create_suggestion(lost, item, created_by)
            changes = {"created_at": item.received_at + timedelta(hours=2)}
            if title == "Black hoodie":
                changes["reporter_answer"] = "yes"
            if stage in ("confirmed", "returned"):
                matching.review_suggestion(suggestion, MatchSuggestion.Status.CONFIRMED, self.staff)
                changes["reviewed_at"] = item.received_at + timedelta(days=1)
            MatchSuggestion.objects.filter(pk=suggestion.pk).update(**changes)
            if stage == "returned":
                self.hand_over(item, lost, days_after=min(2 + i, found_ago - 1))

    def make_other_found(self):
        """Found reports with no match yet. Returns the scarf the finder kept."""
        pool = kinds_avoiding(title for title, *_ in PAIRS)

        # Nine more items on the shelf. The first two are old enough to have left it again.
        for j in range(9):
            if j == 0:
                title, ago, end = "Grey scarf", 58, StoredItem.Status.DISPOSED
            elif j == 1:
                title, ago, end = "Umbrella", 50, StoredItem.Status.TRANSFERRED
            else:
                title, ago, end = self.rng.choice(pool), self.rng.randint(3, 20), None
            found = self.make_found(self.rng.choice(self.users), title, ago, self.place())
            item = self.shelve(title, ago, found)
            if end:
                self.close(item, end, days_after=31)

        # Five items the finder still has. Three finders agreed to share their contact.
        kept = []
        for j in range(5):
            title = "Grey scarf" if j == 0 else self.rng.choice(pool)
            kept.append(
                self.make_found(
                    self.rng.choice(self.users),
                    title,
                    self.rng.randint(2, 30),
                    self.place(),
                    kept_by_finder=True,
                    share_contact=j < 3,
                )  # fmt: skip
            )

        # Four reports where the item was handed to the office but not registered yet.
        for _ in range(4):
            self.make_found(
                self.rng.choice(self.users), self.rng.choice(pool),
                self.rng.randint(1, 3), self.place(),
            )  # fmt: skip
        return kept[0]

    def make_other_lost(self, kept_scarf):
        """Twenty-eight lost reports: most still open, a few cancelled or expired."""
        on_shelf = StoredItem.objects.filter(status=StoredItem.Status.IN_STORAGE)
        pool = kinds_avoiding(on_shelf.values_list("title", flat=True))
        for j in range(28):
            owner = self.rng.choice(self.users)
            if j == 0:
                # Staff noticed this one belongs to the scarf the finder kept.
                lost = self.make_lost(
                    owner, "Grey scarf", (self.today - kept_scarf.date_found).days + 1,
                    kept_scarf.location,
                )  # fmt: skip
                matching.create_suggestion(lost, kept_scarf, MatchSuggestion.CreatedBy.STAFF)
                continue
            title = self.rng.choice(pool)
            place = self.place() if self.rng.random() < 0.85 else None
            if j < 23:
                self.make_lost(owner, title, self.rng.randint(1, 55), place)
            elif j < 26:
                self.make_lost(
                    owner, title, self.rng.randint(20, 55), place, LostReport.Status.CANCELLED
                )
            else:
                self.make_lost(owner, title, 100 + j, place, LostReport.Status.EXPIRED)

    def make_walk_ins(self):
        """Items someone left at the desk without any report. Two will expire soon, two are overdue."""
        for title, days_ago in [
            ("Pink thermos", 26), ("Winter gloves", 27),  # 30-day items: 4 and 3 days left
            ("Yellow raincoat", 45), ("Sports shoes", 40),  # 30-day items: already past
        ]:  # fmt: skip
            self.shelve(title, days_ago)
