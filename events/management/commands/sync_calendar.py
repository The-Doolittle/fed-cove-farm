from django.core.management.base import BaseCommand

from events.google_calendar import pull


class Command(BaseCommand):
    help = "Pull the farm's Google Calendar into the site now (the worker also does this on a timer)."

    def handle(self, *args, **options):
        run = pull()
        self.stdout.write(f"[{run.mode}] {'ok' if run.ok else 'FAILED'}: {run.message}")
