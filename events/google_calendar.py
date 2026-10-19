"""Keep the site's events in step with the farm's Google Calendar.

Modes (picked from settings, see .env.example):
  api  - service account with access to the calendar: pull Google → site, and push
         events added/edited/deleted on the site → Google. Fully two-way.
  ics  - the calendar's secret iCal address: pull only. Events added on the site
         show on the site but don't appear in Google Calendar.
  off  - nothing configured; only events added on the site are shown.

Events marked "Private" in Google Calendar are never pulled onto the public site.
"""

import logging
import os
import re
import urllib.request
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from .models import CalendarSyncRun, DismissedGoogleEvent, Event

log = logging.getLogger(__name__)

PAST_DAYS = 30
FUTURE_DAYS = 400
SYNCED_FIELDS = ("title", "start", "end", "all_day", "location", "description")


def mode():
    if settings.GOOGLE_CALENDAR_ID and settings.GOOGLE_SERVICE_ACCOUNT_FILE:
        if os.path.exists(settings.GOOGLE_SERVICE_ACCOUNT_FILE):
            return "api"
        log.warning("GOOGLE_SERVICE_ACCOUNT_FILE %s not found", settings.GOOGLE_SERVICE_ACCOUNT_FILE)
    if settings.GOOGLE_CALENDAR_ICS_URL:
        return "ics"
    return "off"


def _service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/calendar.events"]
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _window():
    now = timezone.now()
    return now - timedelta(days=PAST_DAYS), now + timedelta(days=FUTURE_DAYS)


def _aware(value):
    tz = timezone.get_current_timezone()
    if isinstance(value, datetime):
        return value if timezone.is_aware(value) else value.replace(tzinfo=tz)
    return datetime.combine(value, time.min, tz)


def _clean_description(text):
    # Google stores descriptions as light HTML; keep line breaks, drop tags.
    text = re.sub(r"<br\s*/?>|</p>", "\n", text or "", flags=re.I)
    return strip_tags(text).strip()


# --- Fetching -----------------------------------------------------------------


def _fetch_api():
    service = _service()
    tmin, tmax = _window()
    token = None
    while True:
        resp = (
            service.events()
            .list(
                calendarId=settings.GOOGLE_CALENDAR_ID,
                timeMin=tmin.isoformat(),
                timeMax=tmax.isoformat(),
                singleEvents=True,  # expands repeating events into individual dates
                orderBy="startTime",
                maxResults=2500,
                pageToken=token,
            )
            .execute()
        )
        for item in resp.get("items", []):
            if item.get("status") == "cancelled" or item.get("visibility") in ("private", "confidential"):
                continue
            start, end = item["start"], item.get("end", {})
            all_day = "date" in start
            if all_day:
                start_v = _aware(date.fromisoformat(start["date"]))
                end_v = _aware(date.fromisoformat(end["date"])) if end.get("date") else None
            else:
                start_v = datetime.fromisoformat(start["dateTime"])
                end_v = datetime.fromisoformat(end["dateTime"]) if end.get("dateTime") else None
            yield {
                "id": item["id"],
                "title": item.get("summary") or "(untitled)",
                "start": start_v,
                "end": end_v,
                "all_day": all_day,
                "location": item.get("location", ""),
                "description": _clean_description(item.get("description")),
            }
        token = resp.get("nextPageToken")
        if not token:
            break


def _fetch_ics():
    import icalendar
    import recurring_ical_events

    req = urllib.request.Request(settings.GOOGLE_CALENDAR_ICS_URL, headers={"User-Agent": "FedCoveFarmSite/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        cal = icalendar.Calendar.from_ical(resp.read())
    tmin, tmax = _window()
    for comp in recurring_ical_events.of(cal).between(tmin, tmax):
        if str(comp.get("CLASS", "PUBLIC")).upper() in ("PRIVATE", "CONFIDENTIAL"):
            continue
        if str(comp.get("STATUS", "")).upper() == "CANCELLED":
            continue
        dtstart = comp.decoded("DTSTART")
        dtend = comp.decoded("DTEND") if "DTEND" in comp else None
        all_day = not isinstance(dtstart, datetime)
        # One UID covers every repeat of a recurring event, so key each occurrence by its start too.
        yield {
            "id": f"{comp.get('UID')}@{dtstart.isoformat()}",
            "title": str(comp.get("SUMMARY") or "(untitled)"),
            "start": _aware(dtstart),
            "end": _aware(dtend) if dtend else None,
            "all_day": all_day,
            "location": str(comp.get("LOCATION") or ""),
            "description": _clean_description(str(comp.get("DESCRIPTION") or "")),
        }


# --- Pull ---------------------------------------------------------------------


def pull():
    """Bring the site in line with Google. Returns the CalendarSyncRun record."""
    current = mode()
    if current == "off":
        return _record(current, True, "Google Calendar not configured; showing site events only.")
    try:
        fetched = list(_fetch_api() if current == "api" else _fetch_ics())
    except Exception as exc:  # network/auth problems: keep what we have, report it
        log.exception("Calendar fetch failed")
        return _record(current, False, f"Couldn't read Google Calendar: {exc}")

    tmin, tmax = _window()
    created = updated = removed = 0
    seen = set()
    with transaction.atomic():
        existing = {e.google_id: e for e in Event.objects.exclude(google_id="")}
        dismissed = set(DismissedGoogleEvent.objects.values_list("google_id", flat=True))
        for data in fetched:
            gid = data.pop("id")
            seen.add(gid)
            if gid in dismissed:
                continue  # deleted on the site; don't re-import
            event = existing.get(gid)
            if event is not None and not event.sync_with_google:
                continue  # edited on the site; the site's version wins
            if event is None:
                event = Event(google_id=gid, source=Event.SOURCE_GOOGLE)
                created += 1
            else:
                before = tuple(getattr(event, f) for f in SYNCED_FIELDS)
                for key, value in data.items():
                    setattr(event, key, value)
                event._from_sync = True
                event.save()
                if tuple(getattr(event, f) for f in SYNCED_FIELDS) != before:
                    updated += 1
                continue
            for key, value in data.items():
                setattr(event, key, value)
            event._from_sync = True
            event.save()

        stale = (
            Event.objects.exclude(google_id="")
            .exclude(google_id__in=seen)
            .filter(start__gte=tmin, start__lte=tmax, sync_with_google=True)
        )
        for event in stale:
            event._from_sync = True
            event.delete()
            removed += 1

        DismissedGoogleEvent.objects.exclude(google_id__in=seen).filter(
            dismissed_at__lt=timezone.now() - timedelta(days=PAST_DAYS)
        ).delete()

    if current == "api":
        _retry_failed_pushes()

    return _record(current, True, f"{len(fetched)} events in Google · {created} new, {updated} changed, {removed} removed")


def _record(current, ok, message):
    run = CalendarSyncRun.objects.create(mode=current, ok=ok, message=message)
    old = CalendarSyncRun.objects.values_list("pk", flat=True)[50:]
    CalendarSyncRun.objects.filter(pk__in=list(old)).delete()
    return run


# --- Push (api mode only) -----------------------------------------------------


def _google_body(event):
    if event.all_day:
        start = {"date": timezone.localtime(event.start).date().isoformat()}
        end = {"date": timezone.localtime(event.effective_end).date().isoformat()}
    else:
        start = {"dateTime": event.start.isoformat(), "timeZone": settings.TIME_ZONE}
        end = {"dateTime": event.effective_end.isoformat(), "timeZone": settings.TIME_ZONE}
    return {
        "summary": event.title,
        "location": event.location,
        "description": event.description,
        "start": start,
        "end": end,
    }


def push(event):
    """Create or update the matching Google event. Errors are saved on the event, not raised."""
    if mode() != "api":
        return
    try:
        events = _service().events()
        if event.google_id:
            events.patch(
                calendarId=settings.GOOGLE_CALENDAR_ID, eventId=event.google_id, body=_google_body(event)
            ).execute()
            gid = event.google_id
        else:
            gid = events.insert(calendarId=settings.GOOGLE_CALENDAR_ID, body=_google_body(event)).execute()["id"]
        Event.objects.filter(pk=event.pk).update(google_id=gid, sync_error="")
    except Exception as exc:
        log.exception("Pushing event %s to Google failed", event.pk)
        Event.objects.filter(pk=event.pk).update(sync_error=str(exc)[:500])


def delete_remote(google_id):
    if mode() != "api" or not google_id:
        return
    from googleapiclient.errors import HttpError

    try:
        _service().events().delete(calendarId=settings.GOOGLE_CALENDAR_ID, eventId=google_id).execute()
    except HttpError as exc:
        if exc.resp.status not in (404, 410):  # already gone is fine
            log.exception("Deleting Google event %s failed", google_id)


def _retry_failed_pushes():
    for event in Event.objects.filter(source=Event.SOURCE_SITE, google_id="").exclude(sync_error=""):
        push(event)
