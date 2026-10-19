from datetime import date, datetime, time, timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from . import google_calendar
from .forms import EventForm
from .models import DismissedGoogleEvent, Event

TZ = timezone.get_current_timezone()


def local(d, t):
    return datetime.combine(d, t, TZ)


def form_for(instance=None, **data):
    from events.wagtail_hooks import EventViewSet

    form_class = EventViewSet().get_form_class()
    return form_class(data=data, instance=instance or Event())


class EventFormTests(TestCase):
    def test_timed_event(self):
        form = form_for(title="Market", date="2026-10-20", start_time="15:30", end_time="19:00")
        self.assertTrue(form.is_valid(), form.errors)
        event = form.save()
        self.assertEqual((event.start, event.end, event.all_day), (local(date(2026, 10, 20), time(15, 30)), local(date(2026, 10, 20), time(19)), False))

    def test_all_day_and_multi_day(self):
        event = form_for(title="Plant sale", date="2026-10-31", end_date="2026-11-01").save()
        self.assertTrue(event.all_day)
        self.assertEqual((timezone.localtime(event.start).date(), timezone.localtime(event.end).date()), (date(2026, 10, 31), date(2026, 11, 2)))
        # Re-opening the form shows what was entered.
        form = form_for(event)
        self.assertEqual((form.initial["date"], form.initial["end_date"]), (date(2026, 10, 31), date(2026, 11, 1)))

    def test_validation(self):
        self.assertIn("end_time", form_for(title="x", date="2026-10-20", start_time="15:00", end_time="14:00").errors)
        self.assertIn("start_time", form_for(title="x", date="2026-10-20", end_time="14:00").errors)
        self.assertIn("end_date", form_for(title="x", date="2026-10-20", end_date="2026-10-19").errors)

    def test_weekly_repeats_keep_clock_time_across_dst(self):
        # Daylight saving ends Nov 1, 2026.
        form = form_for(title="Cowee Market", date="2026-10-20", start_time="15:30", end_time="19:00", repeat_until="2026-11-10")
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        starts = [timezone.localtime(e.start) for e in Event.objects.order_by("start")]
        self.assertEqual([s.date() for s in starts], [date(2026, 10, 20), date(2026, 10, 27), date(2026, 11, 3), date(2026, 11, 10)])
        self.assertTrue(all(s.time() == time(15, 30) for s in starts))

    def test_repeat_option_only_on_new_events(self):
        event = form_for(title="x", date="2026-10-20").save()
        self.assertNotIn("repeat_until", form_for(event).fields)


@override_settings(GOOGLE_CALENDAR_ICS_URL="https://example.com/cal.ics", GOOGLE_CALENDAR_ID="")
class GoogleImportTests(TestCase):
    def google(self, *events):
        return mock.patch.object(google_calendar, "_fetch_ics", return_value=[dict(e) for e in events])

    def setUp(self):
        start = local(timezone.localdate() + timedelta(days=3), time(12))
        self.market = {"id": "uid1@x", "title": "Market", "start": start, "end": start + timedelta(hours=3),
                       "all_day": False, "location": "Cowee", "description": ""}

    def test_import_update_and_removal(self):
        with self.google(self.market):
            google_calendar.pull()
        event = Event.objects.get()
        self.assertEqual((event.source, event.title, event.status_label), ("google", "Market", "From Google"))

        with self.google({**self.market, "title": "Market (rain or shine)"}):
            google_calendar.pull()
        self.assertEqual(Event.objects.get().title, "Market (rain or shine)")

        with self.google():
            google_calendar.pull()
        self.assertFalse(Event.objects.exists())

    def test_edits_on_site_stick(self):
        with self.google(self.market):
            google_calendar.pull()
        event = Event.objects.get()
        local_start = timezone.localtime(event.start)
        form = form_for(event, title="Market — bring cash", date=local_start.date().isoformat(),
                        start_time=local_start.strftime("%H:%M"), end_time=timezone.localtime(event.end).strftime("%H:%M"),
                        location="Cowee", sync_with_google="on")
        self.assertIn("sync_with_google", form.fields)
        self.assertTrue(form.is_valid(), form.errors)
        event = form.save()
        self.assertFalse(event.sync_with_google)
        self.assertEqual(event.status_label, "From Google · edited here")

        with self.google({**self.market, "title": "Changed in Google"}):
            google_calendar.pull()
        self.assertEqual(Event.objects.get().title, "Market — bring cash")
        with self.google():  # even if removed from Google, the edited copy stays
            google_calendar.pull()
        self.assertTrue(Event.objects.exists())

    def test_retick_hands_back_to_google(self):
        with self.google(self.market):
            google_calendar.pull()
        Event.objects.update(sync_with_google=False, title="Mine")
        event = Event.objects.get()
        local_start = timezone.localtime(event.start)
        form = form_for(event, title="Mine", date=local_start.date().isoformat(), start_time=local_start.strftime("%H:%M"),
                        end_time=timezone.localtime(event.end).strftime("%H:%M"), location="Cowee", sync_with_google="on")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save().sync_with_google)
        with self.google(self.market):
            google_calendar.pull()
        self.assertEqual(Event.objects.get().title, "Market")

    def test_deleted_on_site_not_reimported(self):
        with self.google(self.market):
            google_calendar.pull()
        Event.objects.get().delete()
        self.assertTrue(DismissedGoogleEvent.objects.filter(google_id="uid1@x").exists())
        with self.google(self.market):
            google_calendar.pull()
        self.assertFalse(Event.objects.exists())

    def test_site_events_not_touched(self):
        Event.objects.create(title="Farm open day", start=timezone.now() + timedelta(days=5))
        with self.google():
            google_calendar.pull()
        self.assertEqual(Event.objects.get().title, "Farm open day")
