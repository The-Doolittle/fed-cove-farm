from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.panels import FieldPanel, FieldRowPanel, HelpPanel
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from . import google_calendar, views
from .models import Event


def _help_text():
    current = google_calendar.mode()
    if current == "api":
        return "Saving here also updates the farm's Google Calendar, and changes there show up here within minutes."
    if current == "ics":
        return (
            "Events added here show on the website only. Events from Google Calendar should be edited in "
            "Google Calendar — changes made here to those would be overwritten on the next sync."
        )
    return "Google Calendar isn't connected yet, so events added here are the only ones on the site."


class EventViewSet(SnippetViewSet):
    model = Event
    icon = "date"
    menu_label = "Events"
    menu_order = 200
    add_to_admin_menu = True
    list_display = ["title", "start", "location", "source"]
    list_filter = ["source", "all_day"]
    search_fields = ["title", "location", "description"]
    ordering = ["-start"]
    panels = [
        HelpPanel(content=f"<p>{_help_text()}</p>"),
        FieldPanel("title"),
        FieldRowPanel([FieldPanel("start"), FieldPanel("end")]),
        FieldPanel("all_day"),
        FieldPanel("location"),
        FieldPanel("description"),
    ]


register_snippet(EventViewSet)


@hooks.register("register_admin_urls")
def calendar_sync_urls():
    return [
        path("calendar-sync/", views.sync_status, name="calendar_sync"),
        path("calendar-sync/run/", views.sync_now, name="calendar_sync_run"),
    ]


@hooks.register("register_admin_menu_item")
def calendar_sync_menu_item():
    return MenuItem("Calendar sync", reverse("calendar_sync"), icon_name="rotate", order=210)
