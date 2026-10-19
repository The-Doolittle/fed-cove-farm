from datetime import datetime, time, timedelta

from django import forms
from django.utils import timezone
from wagtail.admin.forms import WagtailAdminModelForm

from . import google_calendar

SYNCED_FIELDS = ("title", "start", "end", "all_day", "location", "description")
MAX_REPEATS = 52


class EventForm(WagtailAdminModelForm):
    """Plain date + time boxes (the phone's own pickers) instead of a combined date-time widget."""

    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    start_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        help_text="Leave both times blank for an all-day event.",
    )
    end_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    end_date = forms.DateField(
        required=False,
        label="Ends on (optional)",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        help_text="Only for events that run over several days.",
    )
    repeat_until = forms.DateField(
        required=False,
        label="Repeat every week until (optional)",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        help_text="Adds a copy of this event on the same weekday each week, up to and including this date.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        event = self.instance
        if event.start:
            start = timezone.localtime(event.start)
            end = timezone.localtime(event.effective_end)
            self.initial.setdefault("date", start.date())
            if event.all_day:
                last_day = (end - timedelta(days=1)).date()
                if last_day > start.date():
                    self.initial.setdefault("end_date", last_day)
            else:
                self.initial.setdefault("start_time", start.time())
                self.initial.setdefault("end_time", end.time())
                if end.date() > start.date():
                    self.initial.setdefault("end_date", end.date())
        if event.pk:
            self.fields.pop("repeat_until", None)  # repeats are made when an event is first added
        if not event.from_google or google_calendar.mode() == "api":
            self.fields.pop("sync_with_google", None)
        self._was_synced = event.sync_with_google
        self._before = tuple(getattr(event, f) for f in SYNCED_FIELDS) if event.pk else None

    def clean(self):
        cleaned = super().clean()
        day, start_t, end_t = cleaned.get("date"), cleaned.get("start_time"), cleaned.get("end_time")
        end_day = cleaned.get("end_date") or day
        if not day:
            return cleaned
        if end_day < day:
            self.add_error("end_date", "The end date is before the start date.")
            return cleaned
        if end_t and not start_t:
            self.add_error("start_time", "Add a start time too (or clear both for an all-day event).")
            return cleaned

        tz = timezone.get_current_timezone()
        event = self.instance
        if not start_t:
            event.all_day = True
            event.start = datetime.combine(day, time.min, tz)
            event.end = datetime.combine(end_day + timedelta(days=1), time.min, tz)
        else:
            event.all_day = False
            event.start = datetime.combine(day, start_t, tz)
            event.end = datetime.combine(end_day, end_t, tz) if end_t else event.start + timedelta(hours=2)
            if event.end <= event.start:
                self.add_error("end_time", "The end time is before the start time. If it runs past midnight, set “Ends on”.")

        repeat_until = cleaned.get("repeat_until")
        if repeat_until:
            if repeat_until <= day:
                self.add_error("repeat_until", "Pick a date after the event.")
            elif (repeat_until - day).days // 7 > MAX_REPEATS:
                self.add_error("repeat_until", "That's more than a year of weekly events — pick an earlier date.")
        return cleaned

    def save(self, commit=True):
        event = super().save(commit=False)
        # Editing an imported event here means the farm's version should win from now on —
        # unless they've just ticked "keep updating" to hand it back to Google.
        if self._before is not None and event.from_google and "sync_with_google" in self.fields:
            changed = tuple(getattr(event, f) for f in SYNCED_FIELDS) != self._before
            if changed and self._was_synced and event.sync_with_google:
                event.sync_with_google = False
        if commit:
            event.save()
            self.repeats = self.save_repeats(event)
        return event

    def save_repeats(self, event):
        repeat_until = self.cleaned_data.get("repeat_until")
        if not repeat_until:
            return []
        copies = []
        week = 1
        tz = timezone.get_current_timezone()
        start, end = timezone.localtime(event.start), timezone.localtime(event.end)
        while (start + timedelta(weeks=week)).date() <= repeat_until and week <= MAX_REPEATS:
            # Combine local date + time so repeats keep the same clock time across DST changes.
            new_start = datetime.combine((start + timedelta(weeks=week)).date(), start.time(), tz)
            new_end = datetime.combine((end + timedelta(weeks=week)).date(), end.time(), tz)
            copies.append(
                event.__class__.objects.create(
                    title=event.title, start=new_start, end=new_end, all_day=event.all_day,
                    location=event.location, description=event.description,
                )
            )
            week += 1
        return copies
