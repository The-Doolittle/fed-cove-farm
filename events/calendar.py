import calendar
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from .models import Event


def _parse_month(value):
    today = timezone.localdate()
    try:
        year, month = (int(p) for p in (value or "").split("-"))
        return date(year, month, 1)
    except (ValueError, TypeError):
        return today.replace(day=1)


def month_context(month_param):
    """Context for a Sunday-first month grid plus the upcoming-events list."""
    first = _parse_month(month_param)
    weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(first.year, first.month)
    grid_start, grid_end = weeks[0][0], weeks[-1][-1] + timedelta(days=1)

    tz = timezone.get_current_timezone()
    events = Event.objects.filter(
        start__lt=datetime.combine(grid_end, time.min, tz),
        end__gt=datetime.combine(grid_start, time.min, tz),
    )
    by_day = {}
    for event in events:
        for day in event.local_dates():
            by_day.setdefault(day, []).append(event)

    today = timezone.localdate()
    prev_month = (first - timedelta(days=1)).replace(day=1)
    next_month = (first + timedelta(days=32)).replace(day=1)
    return {
        "month": first,
        "prev_month": prev_month.strftime("%Y-%m"),
        "next_month": next_month.strftime("%Y-%m"),
        "weekday_names": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "weeks": [
            [
                {
                    "date": day,
                    "in_month": day.month == first.month,
                    "is_today": day == today,
                    "events": by_day.get(day, []),
                }
                for day in week
            ]
            for week in weeks
        ],
        "upcoming_events": Event.upcoming()[:12],
    }
