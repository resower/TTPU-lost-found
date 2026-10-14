from django.core.management.base import BaseCommand

from worker.scheduler import main


class Command(BaseCommand):
    help = "Run the background worker (match suggestions, expiry, daily digest)."

    def handle(self, *args, **options):
        main()
