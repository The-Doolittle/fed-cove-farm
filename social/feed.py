"""Pull the farm's latest Instagram and Facebook posts into the site.

Instagram: "Instagram API with Instagram Login" (Business or Creator account, no Facebook Page
needed). Long-lived tokens last 60 days and are renewed here automatically about weekly.
Facebook: a Page access token for the farm's Page (these don't expire).

Post images are downloaded and resized locally because the API's image URLs are temporary,
and so visitors' browsers never load anything from Meta.
"""

import io
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps

from .models import SocialAccount, SocialPost

log = logging.getLogger(__name__)

KEEP = 12  # posts kept per platform
TILE = 640  # px, square
TOKEN_REFRESH_EVERY = timedelta(days=7)

IG_API = "https://graph.instagram.com"
FB_API = "https://graph.facebook.com"


class SocialError(Exception):
    pass


def _get_json(url, params):
    full = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(full, timeout=20) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        # Meta puts the useful part in the body: {"error": {"message": ...}}
        try:
            message = json.load(exc).get("error", {}).get("message", "")
        except Exception:
            message = ""
        raise SocialError(f"HTTP {exc.code} {message}".strip()) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SocialError(str(exc)) from exc


def _download_tile(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            raw = resp.read(25 * 1024 * 1024)
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    except Exception as exc:
        raise SocialError(f"image download failed: {exc}") from exc
    img = ImageOps.fit(img, (TILE, TILE), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "WEBP", quality=80, method=5)
    return out.getvalue()


def _parse_time(value):
    # Instagram: 2026-10-18T14:03:11+0000 · Facebook: same format
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")


# --- Instagram ---------------------------------------------------------------------


def _instagram_posts(account):
    if not account.username:
        me = _get_json(f"{IG_API}/me", {"fields": "user_id,username", "access_token": account.token})
        account.username, account.account_id = me.get("username", ""), str(me.get("user_id") or me.get("id", ""))
    data = _get_json(
        f"{IG_API}/me/media",
        {
            "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,children{media_type,media_url,thumbnail_url}",
            "limit": KEEP,
            "access_token": account.token,
        },
    )
    for item in data.get("data", []):
        kind = item.get("media_type")
        image = item.get("thumbnail_url") if kind == "VIDEO" else item.get("media_url")
        if kind == "CAROUSEL_ALBUM" and not image:
            first = ((item.get("children") or {}).get("data") or [{}])[0]
            image = first.get("thumbnail_url") or first.get("media_url")
        yield {
            "post_id": item["id"],
            "permalink": item.get("permalink", ""),
            "caption": item.get("caption", ""),
            "posted_at": _parse_time(item["timestamp"]),
            "is_video": kind == "VIDEO",
            "image_url": image,
        }


def _maybe_refresh_instagram_token(account):
    now = timezone.now()
    if account.token_refreshed_at and now - account.token_refreshed_at < TOKEN_REFRESH_EVERY:
        return
    data = _get_json(f"{IG_API}/refresh_access_token", {"grant_type": "ig_refresh_token", "access_token": account.token})
    account.token = data["access_token"]
    account.token_expires_at = now + timedelta(seconds=int(data.get("expires_in", 60 * 24 * 3600)))
    account.token_refreshed_at = now


def set_token(account, token, account_id=""):
    """Save a newly pasted token. Instagram only renews tokens 24h+ old, so first renewal is in a day."""
    account.token = token.strip()
    account.account_id = account_id.strip() or (account.account_id if account.platform == SocialAccount.FACEBOOK else "")
    account.username = ""
    account.last_error = ""
    account.token_expires_at = None
    account.token_refreshed_at = timezone.now() - TOKEN_REFRESH_EVERY + timedelta(days=1)
    account.save()


# --- Facebook ----------------------------------------------------------------------


def _facebook_posts(account):
    if not account.username:
        page = _get_json(f"{FB_API}/{account.account_id}", {"fields": "name", "access_token": account.token})
        account.username = page.get("name", "")
    data = _get_json(
        f"{FB_API}/{account.account_id}/posts",
        {"fields": "id,message,created_time,permalink_url,full_picture", "limit": KEEP, "access_token": account.token},
    )
    for item in data.get("data", []):
        if not item.get("message") and not item.get("full_picture"):
            continue  # e.g. "updated their cover photo" with nothing to show
        yield {
            "post_id": item["id"],
            "permalink": item.get("permalink_url", ""),
            "caption": item.get("message", ""),
            "posted_at": _parse_time(item["created_time"]),
            "is_video": False,
            "image_url": item.get("full_picture"),
        }


# --- Sync ----------------------------------------------------------------------------


FETCHERS = {SocialAccount.INSTAGRAM: _instagram_posts, SocialAccount.FACEBOOK: _facebook_posts}


def refresh(account):
    """Fetch one account's latest posts. Errors are saved on the account; existing posts are kept."""
    if not account.connected:
        return account
    try:
        if account.platform == SocialAccount.INSTAGRAM:
            _maybe_refresh_instagram_token(account)
        posts = list(FETCHERS[account.platform](account))
        _store(account.platform, posts)
    except Exception as exc:
        log.warning("Social refresh for %s failed: %s", account.platform, exc)
        account.last_error = str(exc)[:1000]
        account.save()
        return account
    account.fetched_at = timezone.now()
    account.last_error = ""
    account.save()
    return account


def refresh_all():
    return [refresh(account) for account in SocialAccount.objects.all()]


def _store(platform, posts):
    existing = {p.post_id: p for p in SocialPost.objects.filter(platform=platform)}
    keep = set()
    for data in posts[:KEEP]:
        keep.add(data["post_id"])
        post = existing.get(data["post_id"]) or SocialPost(platform=platform, post_id=data["post_id"])
        for field in ("permalink", "caption", "posted_at", "is_video"):
            setattr(post, field, data[field])
        if not post.image and data["image_url"]:
            try:
                post.image.save(f"{platform}-{re.sub(r'[^A-Za-z0-9_-]', '', data['post_id'])}.webp",
                                ContentFile(_download_tile(data["image_url"])), save=False)
            except SocialError as exc:
                log.warning("Skipping image for %s post %s: %s", platform, data["post_id"], exc)
        post.save()
    with transaction.atomic():
        for post in SocialPost.objects.filter(platform=platform).exclude(post_id__in=keep):
            post.image.delete(save=False)
            post.delete()


# --- Display -------------------------------------------------------------------------


def _key(text):
    return re.sub(r"\W+", " ", (text or "").lower()).strip()[:60]


def latest(limit=8):
    """Newest posts across both platforms, minus Facebook copies of Instagram cross-posts."""
    posts = list(SocialPost.objects.all()[: KEEP * 2])
    instagram = [p for p in posts if p.platform == SocialAccount.INSTAGRAM]
    shown = []
    for post in posts:
        if post.platform == SocialAccount.FACEBOOK and post.caption:
            key = _key(post.caption)
            if any(_key(ig.caption) == key and abs(ig.posted_at - post.posted_at) < timedelta(days=2) for ig in instagram):
                continue
        if post.image or post.caption:
            shown.append(post)
        if len(shown) >= limit:
            break
    return shown
