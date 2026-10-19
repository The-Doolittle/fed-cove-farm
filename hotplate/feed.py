"""Turn Hotplate's raw API responses into the menu data the site renders.

refresh(chef)  — fetch from Hotplate and store (called by the worker every few minutes)
present(chef)  — the stored data with dates parsed and open/closed worked out for *now*
"""

import logging
import re
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from . import client
from .models import HotplateFeed

log = logging.getLogger(__name__)

PAST_LIMIT = 4  # how many previous drops to keep (each costs one request the first time only)
FORMAT = 2  # bump when _normalize's output changes, so cached past drops get rebuilt
LOW_STOCK = 3


# --- Fetch + normalize ----------------------------------------------------------


def refresh(chef):
    feed, _ = HotplateFeed.objects.get_or_create(chef=chef)
    feed.last_attempt_at = timezone.now()
    try:
        data = _build(chef, previous=feed.data or {})
    except Exception as exc:
        log.warning("Hotplate refresh for %s failed: %s", chef, exc)
        feed.last_error = str(exc)[:1000]
        feed.save(update_fields=["last_attempt_at", "last_error"])
        return feed
    feed.data = data
    feed.fetched_at = feed.last_attempt_at
    feed.last_error = ""
    feed.save()
    return feed


def _skip(event):
    return any(event.get(k) for k in ("isPrivate", "private", "isDraft", "draft", "isArchived", "archived"))


def _build(chef, previous):
    live = []
    for event in client.live_events(chef):
        if _skip(event):
            continue
        live.append(_normalize(chef, client.drop_shell(event["id"]), client.inventory(event["id"])))

    live_ids = {d["id"] for d in live}
    cached = {d["id"]: d for d in previous.get("past", [])} if previous.get("format") == FORMAT else {}
    past = []
    for event in client.past_events(chef):
        if len(past) >= PAST_LIMIT:
            break
        if _skip(event) or event.get("isHiddenFromPastDrops") or event["id"] in live_ids:
            continue
        old = cached.get(event["id"])
        if old and old.get("updated_at") == event.get("updatedAt"):
            past.append(old)  # finished drops don't change; don't re-fetch them
        else:
            past.append(_normalize(chef, client.drop_shell(event["id"]), None))
    return {"format": FORMAT, "chef": chef, "live": live, "past": past}


def _ms(value):
    """Hotplate sends times as epoch milliseconds, or occasionally as ISO strings."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def _image(url, transform):
    """Ask Uploadcare for a smaller, modern-format copy (only safe on bare /<uuid>/ URLs)."""
    if not url:
        return None
    if "/-/" in url or not url.endswith("/"):
        return url
    return url + transform


CARD_IMAGE = "-/scale_crop/600x450/center/-/format/auto/-/quality/smart/"
# Covers are often graphics with text on them, so shrink without cropping.
COVER_IMAGE = "-/preview/1200x1200/-/format/auto/-/quality/smart/"


def _price(value):
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError):
        return None


def _split_description(text):
    """First paragraph is the blurb; the rest is usually ingredients/allergens."""
    parts = [p.strip() for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]
    if not parts:
        return "", ""
    return parts[0], "\n\n".join(parts[1:])


def _normalize(chef, shell, inv):
    available = {}
    for item_id, info in ((inv or {}).get("itemsById") or {}).items():
        value = (info.get("inventoryInfo") or {}).get("available")
        available[item_id] = int(value) if isinstance(value, (int, float)) else None  # "Infinity" → no limit

    sections = {}
    for sec in sorted(shell.get("eventMenuSections") or [], key=lambda s: s.get("index", 0)):
        if not sec.get("isDeleted"):
            sections[sec["id"]] = {"title": sec.get("title") or "", "items": []}
    fallback = {"title": "Menu", "items": []}

    # Group by each item's own section id; the sections' item lists include items not on this drop.
    for item in sorted(shell.get("eventMenuItems") or [], key=lambda i: i.get("sectionIndex", 0)):
        if item.get("isDeleted"):
            continue
        blurb, details = _split_description(item.get("description"))
        item_id = item.get("menuItemId") or item.get("id")
        (sections.get(item.get("eventMenuSectionId")) or fallback)["items"].append(
            {
                "id": item_id,
                "title": item.get("title") or "",
                "price": _price(item.get("price")),
                "blurb": blurb,
                "details": details,
                "image": _image(item.get("image"), CARD_IMAGE),
                "options": [c["title"] for c in item.get("optionCategories") or [] if c.get("title") and not c.get("isDeleted")],
                "remaining": available.get(item_id),
            }
        )

    slots = [
        {
            "date": (slot.get("humanReadableDate") or {}).get("large") or "",
            "time": slot.get("humanReadableTime") or "",
            "location": (slot.get("location") or {}).get("title") or "",
            "start": _ms(slot.get("startTime")),
        }
        for slot in shell.get("timeSlots") or []
        if not slot.get("disabled") and not slot.get("isCanceled")
    ]
    slots.sort(key=lambda s: s["start"] or 0)

    return {
        "id": shell["id"],
        "title": shell.get("title") or "",
        "description": (shell.get("description") or "").strip(),
        "image": _image(shell.get("image"), COVER_IMAGE),
        "url": f"https://www.hotplate.com/{chef}/{shell['id']}",
        "go_live": _ms(shell.get("goLiveTime")),
        "cutoff": _ms(shell.get("orderCutoffTime")),
        "last_pickup": _ms(shell.get("lastPickupTime")) or (slots[-1]["start"] if slots else None),
        "show_counts": bool(shell.get("isEventMenuItemInventoryDisplayed")),
        "menu_hidden_before_live": bool(shell.get("isMenuHiddenBeforeGoLive")),
        "open_time_hidden": bool(shell.get("isOrderOpenTimeHidden") or shell.get("hideOrdersOpenTime")),
        "updated_at": shell.get("updatedAt"),
        "slots": slots,
        "sections": [s for s in [*sections.values(), fallback] if s["items"]],
    }


# --- Present ----------------------------------------------------------------------


def _dt(ms):
    return datetime.fromtimestamp(ms / 1000, tz=dt_timezone.utc) if ms else None


def _present_drop(drop, now, live):
    go_live, cutoff, last_pickup = _dt(drop["go_live"]), _dt(drop["cutoff"]), _dt(drop["last_pickup"])
    if live and go_live and now < go_live:
        state = "upcoming"
    elif live and (not cutoff or now <= cutoff):
        state = "open"
    else:
        state = "closed"
    hide_menu = state == "upcoming" and drop.get("menu_hidden_before_live")
    sections = []
    if not hide_menu:
        for sec in drop["sections"]:
            items = []
            for item in sec["items"]:
                remaining = item.get("remaining") if live else None
                items.append(
                    {
                        **item,
                        "sold_out": remaining == 0,
                        "low": bool(drop.get("show_counts") and remaining and remaining <= LOW_STOCK),
                    }
                )
            sections.append({"title": sec["title"], "items": items})
    return {
        **drop,
        "state": state,
        "go_live": go_live,
        "cutoff": cutoff,
        "last_pickup": last_pickup,
        "pickup_upcoming": bool(last_pickup and now < last_pickup),
        "sections": sections,
        "item_count": sum(len(s["items"]) for s in drop["sections"]),
    }


def present(chef):
    """Render-ready data, or None if we've never managed to fetch anything."""
    feed = HotplateFeed.objects.filter(chef=chef).first()
    if not feed or not feed.fetched_at:
        return None
    now = timezone.now()
    live = [_present_drop(d, now, live=True) for d in feed.data.get("live", [])]
    past = [_present_drop(d, now, live=False) for d in feed.data.get("past", [])]
    return {
        "storefront": f"https://www.hotplate.com/{chef}",
        "live": live,
        "past": past,
        "fetched_at": feed.fetched_at,
        # Stock counts go stale fast; if the worker has been failing for a while, say so.
        "stale": now - feed.fetched_at > timedelta(hours=1),
    }
