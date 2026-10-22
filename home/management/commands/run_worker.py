import logging
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.utils import OperationalError

from events.google_calendar import pull as pull_calendar
from hotplate.feed import refresh as refresh_hotplate
from hotplate.views import default_farm_settings
from social.feed import refresh_all as refresh_social

from home.models import FarmSettings

log = logging.getLogger(__name__)

# Touched every loop; the container healthcheck fails if it goes stale.
HEARTBEAT = Path("/tmp/worker-heartbeat")


class Command(BaseCommand):
    help = "Background jobs: pull Google Calendar and refresh Hotplate drops on their own intervals."

    def handle(self, *args, **options):
        jobs = [
            ("calendar", settings.CALENDAR_SYNC_MINUTES, self.calendar),
            ("hotplate", settings.HOTPLATE_SYNC_MINUTES, self.hotplate),
            ("social", settings.SOCIAL_SYNC_MINUTES, self.social),
        ]
        next_run = {name: 0.0 for name, _, _ in jobs}
        while True:
            for name, minutes, job in jobs:
                if time.monotonic() >= next_run[name]:
                    delay = max(1, minutes) * 60
                    try:
                        job()
                    except OperationalError as exc:  # e.g. web hasn't finished migrating on first boot
                        self.stderr.write(f"{name}: database not ready, retrying in a minute: {exc}")
                        delay = 60
                    except Exception:
                        log.exception("%s job failed", name)
                    next_run[name] = time.monotonic() + delay
            HEARTBEAT.touch()
            time.sleep(15)

    def calendar(self):
        run = pull_calendar()
        self.stdout.write(f"calendar [{run.mode}] {'ok' if run.ok else 'FAILED'}: {run.message}")

    def hotplate(self):
        farm = default_farm_settings()
        if not farm or farm.ordering_mode != FarmSettings.ORDERING_HOTPLATE:
            return
        feed = refresh_hotplate(farm.hotplate_username)
        if feed.last_error:
            self.stdout.write(f"hotplate FAILED (keeping last good data): {feed.last_error}")
        else:
            self.stdout.write(
                f"hotplate ok: {len(feed.data['live'])} open, {len(feed.data['past'])} recent"
            )

    def social(self):
        for account in refresh_social():
            if account.connected:
                status = f"FAILED: {account.last_error}" if account.last_error else "ok"
                self.stdout.write(f"social {account.platform} {status}")
