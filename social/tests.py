import shutil
import tempfile
from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from . import feed
from .models import SocialAccount, SocialPost

MEDIA = tempfile.mkdtemp()


def ig_time(delta):
    return (timezone.now() + delta).strftime("%Y-%m-%dT%H:%M:%S+0000")


IG_MEDIA = {
    "data": [
        {"id": "1", "caption": "Fresh sourdough today!", "media_type": "IMAGE", "media_url": "https://cdn/1.jpg",
         "permalink": "https://instagram.com/p/1", "timestamp": ig_time(timedelta(hours=-1))},
        {"id": "2", "caption": "Greenhouse tour", "media_type": "VIDEO", "media_url": "https://cdn/2.mp4",
         "thumbnail_url": "https://cdn/2.jpg", "permalink": "https://instagram.com/p/2", "timestamp": ig_time(timedelta(days=-1))},
        {"id": "3", "media_type": "CAROUSEL_ALBUM", "permalink": "https://instagram.com/p/3",
         "timestamp": ig_time(timedelta(days=-2)), "children": {"data": [{"media_type": "IMAGE", "media_url": "https://cdn/3a.jpg"}]}},
    ]
}
FB_POSTS = {
    "data": [
        # Cross-post of IG post 1: should be hidden.
        {"id": "p_1", "message": "Fresh sourdough today!", "created_time": ig_time(timedelta(minutes=-50)),
         "permalink_url": "https://facebook.com/1", "full_picture": "https://fbcdn/1.jpg"},
        {"id": "p_2", "message": "Market is rained out this week.", "created_time": ig_time(timedelta(hours=-3)),
         "permalink_url": "https://facebook.com/2"},
        {"id": "p_3", "created_time": ig_time(timedelta(hours=-4)), "permalink_url": "https://facebook.com/3"},
    ]
}


def fake_get_json(url, params):
    if url.endswith("/refresh_access_token"):
        return {"access_token": "renewed", "expires_in": 5184000}
    if url.endswith("/me"):
        return {"user_id": "999", "username": "fedcove_farm.nursery"}
    if url.endswith("/me/media"):
        return IG_MEDIA
    if url.endswith("/posts"):
        return FB_POSTS
    return {"name": "Fed Cove Farm and Nursery"}


@override_settings(MEDIA_ROOT=MEDIA)
class SocialFeedTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        patches = [
            mock.patch.object(feed, "_get_json", side_effect=fake_get_json),
            mock.patch.object(feed, "_download_tile", return_value=b"RIFF....WEBP"),
        ]
        self.get_json, self.download = [p.start() for p in patches]
        self.addCleanup(mock.patch.stopall)
        self.ig = SocialAccount.objects.create(platform=SocialAccount.INSTAGRAM)
        self.fb = SocialAccount.objects.create(platform=SocialAccount.FACEBOOK)

    def test_instagram_posts_and_images(self):
        feed.set_token(self.ig, " tok ")
        account = feed.refresh(self.ig)
        self.assertEqual((account.last_error, account.username, account.token), ("", "fedcove_farm.nursery", "tok"))
        posts = {p.post_id: p for p in SocialPost.objects.filter(platform="instagram")}
        self.assertEqual(set(posts), {"1", "2", "3"})
        self.assertTrue(posts["2"].is_video)
        downloaded = [c.args[0] for c in self.download.call_args_list]
        self.assertEqual(downloaded, ["https://cdn/1.jpg", "https://cdn/2.jpg", "https://cdn/3a.jpg"])
        # Images are only downloaded once.
        feed.refresh(self.ig)
        self.assertEqual(self.download.call_count, 3)

    def test_token_renewal_schedule(self):
        feed.set_token(self.ig, "tok")
        feed.refresh(self.ig)
        self.assertEqual(self.ig.token, "tok")  # too new to renew
        self.ig.token_refreshed_at = timezone.now() - timedelta(days=8)
        feed.refresh(self.ig)
        self.assertEqual(self.ig.token, "renewed")
        self.assertGreater(self.ig.token_expires_at, timezone.now() + timedelta(days=59))

    def test_merged_feed_hides_cross_posts_and_empty_posts(self):
        feed.set_token(self.ig, "tok")
        feed.set_token(self.fb, "page-tok", "12345")
        feed.refresh_all()
        shown = [(p.platform, p.post_id) for p in feed.latest()]
        self.assertEqual(shown, [("instagram", "1"), ("facebook", "p_2"), ("instagram", "2"), ("instagram", "3")])

    def test_old_posts_pruned(self):
        feed.set_token(self.ig, "tok")
        SocialPost.objects.create(platform="instagram", post_id="old", permalink="https://x", posted_at=timezone.now())
        feed.refresh(self.ig)
        self.assertFalse(SocialPost.objects.filter(post_id="old").exists())

    def test_error_keeps_posts(self):
        feed.set_token(self.ig, "tok")
        feed.refresh(self.ig)
        self.get_json.side_effect = feed.SocialError("HTTP 400 Error validating access token")
        account = feed.refresh(self.ig)
        self.assertIn("validating access token", account.last_error)
        self.assertEqual(SocialPost.objects.count(), 3)

    def test_not_connected_does_nothing(self):
        feed.refresh_all()
        self.get_json.assert_not_called()
