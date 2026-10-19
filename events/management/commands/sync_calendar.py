import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.utils import OperationalError

from events.google_calendar import pull


class Command(BaseCommand):
    help = "Pull the farm's Google Calendar into the site."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Keep running every CALENDAR_SYNC_MINUTES.")

    def handle(self, *args, loop=False, **options):
        while True:
            try:
                run = pull()
                self.stdout.write(f"[{run.mode}] {'ok' if run.ok else 'FAILED'}: {run.message}")
            except OperationalError as exc:  # e.g. migrations not applied yet on first boot
                self.stderr.write(f"Database not ready: {exc}")
            if not loop:
                break
            time.sleep(max(1, settings.CALENDAR_SYNC_MINUTES) * 60)
