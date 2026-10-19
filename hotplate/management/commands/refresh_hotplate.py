from django.core.management.base import BaseCommand, CommandError

from hotplate.feed import refresh
from hotplate.views import default_farm_settings


class Command(BaseCommand):
    help = "Fetch the farm's Hotplate drops now."

    def add_arguments(self, parser):
        parser.add_argument("--chef", help="Hotplate username (defaults to the one in Farm settings).")

    def handle(self, *args, chef=None, **options):
        chef = chef or default_farm_settings().hotplate_username
        feed = refresh(chef)
        if feed.last_error:
            raise CommandError(f"{chef}: {feed.last_error}")
        for drop in feed.data["live"]:
            self.stdout.write(f"open: {drop['title']} ({sum(len(s['items']) for s in drop['sections'])} items)")
        for drop in feed.data["past"]:
            self.stdout.write(f"past: {drop['title']} ({sum(len(s['items']) for s in drop['sections'])} items)")
