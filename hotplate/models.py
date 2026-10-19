from django.db import models


class HotplateFeed(models.Model):
    """The last good copy of a Hotplate storefront's drops, refreshed by the worker.

    `data` is only replaced after a fully successful fetch, so a Hotplate outage or
    API change leaves the site showing the previous menu instead of nothing.
    """

    chef = models.CharField(max_length=80, unique=True)
    data = models.JSONField(default=dict)
    fetched_at = models.DateTimeField(null=True)
    last_attempt_at = models.DateTimeField(null=True)
    last_error = models.TextField(blank=True)

    def __str__(self):
        return self.chef
