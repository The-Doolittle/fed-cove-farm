from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from urllib.parse import urlencode

from django.db import models
from django.utils import timezone


class Event(models.Model):
    SOURCE_SITE = "site"
    SOURCE_GOOGLE = "google"
    SOURCE_CHOICES = [(SOURCE_SITE, "Added on the site"), (SOURCE_GOOGLE, "Google Calendar")]

    title = models.CharField(max_length=200)
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True, help_text="Optional. Leave blank for a 2-hour event.")
    all_day = models.BooleanField(default=False, help_text="Ignore the times and show the date only.")
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_SITE, editable=False)
    # Google event id (API mode) or iCal UID[+instance] (ICS mode). Empty = not on Google yet.
    google_id = models.CharField(max_length=1024, blank=True, db_index=True, editable=False)
    sync_error = models.TextField(blank=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start"]

    def __str__(self):
        return self.title

    @property
    def effective_end(self):
        if self.end and self.end > self.start:
            return self.end
        return self.start + (timedelta(days=1) if self.all_day else timedelta(hours=2))

    def local_dates(self):
        """Every local calendar date this event touches (all-day ends are exclusive)."""
        start = timezone.localtime(self.start).date()
        end_dt = timezone.localtime(self.effective_end)
        last = end_dt.date()
        if self.all_day or (end_dt.hour, end_dt.minute, end_dt.second) == (0, 0, 0):
            last -= timedelta(days=1)
        last = max(start, last)
        days = []
        day = start
        while day <= last and len(days) < 62:
            days.append(day)
            day += timedelta(days=1)
        return days

    def save(self, *args, **kwargs):
        if self.all_day:
            # Store all-day events as local midnight → midnight (end exclusive), like Google does.
            tz = timezone.get_current_timezone()
            start_day = timezone.localtime(self.start).date()
            end_day = timezone.localtime(self.end).date() if self.end else start_day
            if end_day <= start_day or (self.end and timezone.localtime(self.end).time() != datetime.min.time()):
                end_day = max(end_day, start_day) + timedelta(days=1)
            self.start = datetime.combine(start_day, datetime.min.time(), tz)
            self.end = datetime.combine(end_day, datetime.min.time(), tz)
        elif not self.end or self.end <= self.start:
            self.end = self.effective_end
        super().save(*args, **kwargs)

    @classmethod
    def upcoming(cls):
        """Events that haven't finished yet, soonest first."""
        return cls.objects.filter(end__gte=timezone.now())

    @property
    def google_add_url(self):
        fmt = "%Y%m%d" if self.all_day else "%Y%m%dT%H%M%SZ"
        start = timezone.localtime(self.start) if self.all_day else self.start.astimezone(dt_timezone.utc)
        end = timezone.localtime(self.effective_end) if self.all_day else self.effective_end.astimezone(dt_timezone.utc)
        params = {
            "action": "TEMPLATE",
            "text": self.title,
            "dates": f"{start.strftime(fmt)}/{end.strftime(fmt)}",
            "location": self.location,
            "details": self.description,
        }
        return "https://calendar.google.com/calendar/render?" + urlencode(params)

    def as_json(self):
        return {
            "id": self.pk,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.effective_end.isoformat(),
            "all_day": self.all_day,
            "location": self.location,
            "description": self.description,
            "source": self.source,
        }


class CalendarSyncRun(models.Model):
    ran_at = models.DateTimeField(auto_now_add=True)
    mode = models.CharField(max_length=10)
    ok = models.BooleanField(default=True)
    message = models.TextField(blank=True)

    class Meta:
        ordering = ["-ran_at"]
