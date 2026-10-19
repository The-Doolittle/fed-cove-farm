from datetime import datetime, time

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST

from . import google_calendar
from .models import CalendarSyncRun, Event


@require_GET
def events_json(request):
    """GET /api/events/?from=YYYY-MM-DD&to=YYYY-MM-DD (defaults to upcoming)."""
    tz = timezone.get_current_timezone()
    start, end = parse_date(request.GET.get("from", "")), parse_date(request.GET.get("to", ""))
    events = Event.upcoming() if not start else Event.objects.filter(end__gte=datetime.combine(start, time.min, tz))
    if end:
        events = events.filter(start__lt=datetime.combine(end, time.max, tz))
    return JsonResponse({"events": [e.as_json() for e in events[:500]]})


def sync_status(request):
    return render(
        request,
        "events/admin_sync.html",
        {
            "mode": google_calendar.mode(),
            "runs": CalendarSyncRun.objects.all()[:10],
            "failed_pushes": Event.objects.exclude(sync_error=""),
            "header_icon": "date",
        },
    )


@require_POST
def sync_now(request):
    run = google_calendar.pull()
    (messages.success if run.ok else messages.error)(request, run.message)
    return redirect("calendar_sync")
