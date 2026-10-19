from django.db import models


class SocialAccount(models.Model):
    """A connected Instagram or Facebook account. Tokens are entered on the admin 'Social feed' page."""

    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    PLATFORM_CHOICES = [(INSTAGRAM, "Instagram"), (FACEBOOK, "Facebook")]

    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, unique=True)
    token = models.TextField(blank=True)
    # Facebook: the Page ID. Instagram: filled in from the API on first fetch.
    account_id = models.CharField(max_length=64, blank=True)
    username = models.CharField(max_length=120, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    token_refreshed_at = models.DateTimeField(null=True, blank=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    def __str__(self):
        return self.get_platform_display()

    @property
    def connected(self):
        return bool(self.token and (self.platform == self.INSTAGRAM or self.account_id))


class SocialPost(models.Model):
    platform = models.CharField(max_length=10, choices=SocialAccount.PLATFORM_CHOICES)
    post_id = models.CharField(max_length=128)
    permalink = models.URLField(max_length=500)
    caption = models.TextField(blank=True)
    posted_at = models.DateTimeField()
    is_video = models.BooleanField(default=False)
    image = models.ImageField(upload_to="social/", blank=True)

    class Meta:
        ordering = ["-posted_at"]
        constraints = [models.UniqueConstraint(fields=["platform", "post_id"], name="unique_social_post")]

    def __str__(self):
        return f"{self.platform}: {self.caption[:40]}"
