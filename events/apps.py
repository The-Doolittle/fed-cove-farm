from django.apps import AppConfig


class EventsConfig(AppConfig):
    name = "events"

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from . import google_calendar
        from .models import Event

        def on_save(sender, instance, **kwargs):
            if not getattr(instance, "_from_sync", False):
                google_calendar.push(instance)

        def on_delete(sender, instance, **kwargs):
            if not getattr(instance, "_from_sync", False):
                google_calendar.delete_remote(instance.google_id)

        post_save.connect(on_save, sender=Event, weak=False, dispatch_uid="event_push")
        post_delete.connect(on_delete, sender=Event, weak=False, dispatch_uid="event_delete_remote")
