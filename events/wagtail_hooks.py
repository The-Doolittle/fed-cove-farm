import django_filters
from django.conf import settings
from django.urls import path, reverse
from django.utils import timezone
from wagtail import hooks
from wagtail.admin.filters import WagtailFilterSet
from wagtail.admin.menu import MenuItem
from wagtail.admin.panels import FieldPanel, FieldRowPanel, HelpPanel, ObjectList
from wagtail.admin.ui.tables import Column
from wagtail.snippets.models import register_snippet
from django.contrib import messages
from wagtail.snippets.views.snippets import CreateView, SnippetViewSet

from . import google_calendar, views
from .forms import EventForm
from .models import Event


def _help_text():
    current = google_calendar.mode()
    if current == "api":
        return "Saving here also updates the farm's Google Calendar, and changes there show up here within minutes."
    if current == "ics":
        return (
            "Events added to the farm's Google Calendar (e.g. from your phone) appear here automatically within "
            f"{settings.CALENDAR_SYNC_MINUTES} minutes, and you can edit them like any other event — once you do, "
            "your version is kept. Events added here show on the website only."
        )
    return "Add the farm's events here and they'll appear on the website's calendar."


class EventFilterSet(WagtailFilterSet):
    when = django_filters.ChoiceFilter(
        label="Show",
        choices=[("upcoming", "Upcoming"), ("past", "Past"), ("all", "All")],
        empty_label=None,
        method="filter_when",
    )
    source = django_filters.ChoiceFilter(choices=Event.SOURCE_CHOICES, label="Added")

    class Meta:
        model = Event
        fields = ["when", "source"]

    def __init__(self, data=None, *args, **kwargs):
        # Upcoming unless chosen otherwise: that's what the farm looks for 9 times out of 10.
        if data is not None and not data.get("when"):
            data = data.copy()
            data["when"] = "upcoming"
        super().__init__(data, *args, **kwargs)

    def filter_when(self, queryset, name, value):
        now = timezone.now()
        if value == "past":
            return queryset.filter(end__lt=now).order_by("-start")
        if value == "upcoming":
            return queryset.filter(end__gte=now)
        return queryset


class EventCreateView(CreateView):
    def save_instance(self):
        instance = super().save_instance()
        repeats = getattr(self.form, "repeats", [])
        if repeats:
            last = repeats[-1].when_label.split(" · ")[0]
            messages.info(self.request, f"Also added {len(repeats)} weekly repeat{'s' if len(repeats) != 1 else ''}, through {last}.")
        return instance


class EventViewSet(SnippetViewSet):
    add_view_class = EventCreateView
    model = Event
    icon = "date"
    menu_label = "Events"
    menu_order = 200
    add_to_admin_menu = True
    list_display = ["title", Column("when_label", label="When", sort_key="start"), "location",
                    Column("status_label", label="From")]
    filterset_class = EventFilterSet
    search_fields = ["title", "location", "description"]
    ordering = ["start"]
    edit_handler = ObjectList(
        [
            HelpPanel(content=f"<p>{_help_text()}</p>"),
            FieldPanel("title"),
            FieldRowPanel([FieldPanel("date"), FieldPanel("start_time"), FieldPanel("end_time")], heading="When"),
            FieldPanel("end_date"),
            FieldPanel("location"),
            FieldPanel("description"),
            FieldPanel("repeat_until"),
            FieldPanel("sync_with_google"),
        ],
        base_form_class=EventForm,
    )


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
