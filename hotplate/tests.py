from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from . import feed
from .client import HotplateError
from .models import HotplateFeed

CHEF = "testbakery"


def ms(delta):
    return int((timezone.now() + delta).timestamp() * 1000)


def shell(event_id="ev1", **overrides):
    data = {
        "id": event_id,
        "title": "10/21 Drop",
        "description": "Fall flavors!",
        "image": "https://x.ucarecd.net/cover-uuid/",
        "goLiveTime": ms(timedelta(hours=-2)),
        "orderCutoffTime": ms(timedelta(days=1)),
        "lastPickupTime": ms(timedelta(days=3)),
        "isEventMenuItemInventoryDisplayed": True,
        "updatedAt": 111,
        "eventMenuSections": [
            {"id": "s-bread", "title": "Bread", "index": 0, "eventMenuItems": [{"menuItemId": "cookie"}]},
            {"id": "s-sweet", "title": "Sweets", "index": 1},
            {"id": "s-gone", "title": "Old", "index": 2, "isDeleted": True},
        ],
        "eventMenuItems": [
            {"menuItemId": "loaf", "eventMenuSectionId": "s-bread", "sectionIndex": 0, "title": "Loaf",
             "price": "10", "description": "Crusty.\n\nIngredients: flour, water", "image": "https://x.ucarecd.net/loaf/"},
            # The Bread section claims this item, but the item itself says Sweets — the item wins.
            {"menuItemId": "cookie", "eventMenuSectionId": "s-sweet", "sectionIndex": 0, "title": "Cookie",
             "price": "3.50", "image": "https://x.ucarecd.net/c/-/crop/10x10/",
             "optionCategories": [{"title": "Double Up!"}, {"title": "Gone", "isDeleted": True}]},
            {"menuItemId": "muffin", "eventMenuSectionId": "s-sweet", "sectionIndex": 1, "title": "Muffin", "price": "0.00"},
            {"menuItemId": "deleted", "eventMenuSectionId": "s-bread", "title": "Nope", "price": "1", "isDeleted": True},
        ],
        "timeSlots": [
            {"humanReadableDate": {"large": "Wed, Oct 21"}, "humanReadableTime": "4:00 PM - 6:00 PM",
             "location": {"title": "Market"}, "startTime": ms(timedelta(days=3))},
            {"humanReadableDate": {"large": "Wed, Oct 21"}, "humanReadableTime": "12:00 PM - 7:00 PM",
             "location": {"title": "Farm"}, "startTime": ms(timedelta(days=2, hours=20))},
            {"humanReadableDate": {"large": "Thu"}, "isCanceled": True, "startTime": 1},
        ],
    }
    data.update(overrides)
    return data


INVENTORY = {"itemsById": {
    "loaf": {"inventoryInfo": {"available": 2}},
    "cookie": {"inventoryInfo": {"available": "Infinity"}},
    "muffin": {"inventoryInfo": {"available": 0}},
}}


def fake_api(live=None, past=None, shells=None):
    shells = shells or {}
    return {
        "live_events": mock.patch.object(feed.client, "live_events", return_value=live or []),
        "past_events": mock.patch.object(feed.client, "past_events", return_value=past or []),
        "drop_shell": mock.patch.object(feed.client, "drop_shell", side_effect=lambda eid: shells[eid]),
        "inventory": mock.patch.object(feed.client, "inventory", return_value=INVENTORY),
    }


class NormalizeTests(TestCase):
    def test_menu_parsing(self):
        drop = feed._normalize(CHEF, shell(), INVENTORY)
        self.assertEqual([s["title"] for s in drop["sections"]], ["Bread", "Sweets"])
        bread, sweets = drop["sections"]
        self.assertEqual([i["title"] for i in bread["items"]], ["Loaf"])
        self.assertEqual([i["title"] for i in sweets["items"]], ["Cookie", "Muffin"])

        loaf, cookie, muffin = bread["items"][0], *sweets["items"]
        self.assertEqual((loaf["blurb"], loaf["details"]), ("Crusty.", "Ingredients: flour, water"))
        self.assertEqual((loaf["price"], cookie["price"], muffin["price"]), ("10.00", "3.50", "0.00"))
        self.assertEqual((loaf["remaining"], cookie["remaining"], muffin["remaining"]), (2, None, 0))
        self.assertEqual(cookie["options"], ["Double Up!"])
        self.assertTrue(loaf["image"].endswith("/loaf/-/scale_crop/600x450/center/-/format/auto/-/quality/smart/"))
        self.assertEqual(cookie["image"], "https://x.ucarecd.net/c/-/crop/10x10/")  # already transformed: untouched

        self.assertEqual([s["location"] for s in drop["slots"]], ["Farm", "Market"])  # sorted, canceled dropped
        self.assertEqual(drop["url"], f"https://www.hotplate.com/{CHEF}/ev1")

    def test_iso_pickup_time(self):
        drop = feed._normalize(CHEF, shell(lastPickupTime="2026-10-21T23:00:00.000Z"), None)
        self.assertEqual(drop["last_pickup"], 1792623600000)


class RefreshAndPresentTests(TestCase):
    def refresh(self, **api):
        patches = fake_api(**api)
        for p in patches.values():
            p.start()
        try:
            return feed.refresh(CHEF)
        finally:
            mock.patch.stopall()

    def test_live_drop_states_and_badges(self):
        self.refresh(live=[{"id": "ev1"}, {"id": "ev2", "isPrivate": True}], shells={"ev1": shell()})
        menu = feed.present(CHEF)
        self.assertEqual(len(menu["live"]), 1)  # private drop skipped
        drop = menu["live"][0]
        self.assertEqual(drop["state"], "open")
        items = {i["title"]: i for s in drop["sections"] for i in s["items"]}
        self.assertTrue(items["Muffin"]["sold_out"])
        self.assertTrue(items["Loaf"]["low"])
        self.assertFalse(items["Cookie"]["low"])

    def test_counts_hidden_when_seller_hides_them(self):
        self.refresh(live=[{"id": "ev1"}], shells={"ev1": shell(isEventMenuItemInventoryDisplayed=False)})
        items = {i["title"]: i for s in feed.present(CHEF)["live"][0]["sections"] for i in s["items"]}
        self.assertFalse(items["Loaf"]["low"])
        self.assertTrue(items["Muffin"]["sold_out"])  # sold out is always shown

    def test_upcoming_drop_hides_menu_if_seller_does(self):
        self.refresh(live=[{"id": "ev1"}], shells={"ev1": shell(goLiveTime=ms(timedelta(days=1)), isMenuHiddenBeforeGoLive=True)})
        drop = feed.present(CHEF)["live"][0]
        self.assertEqual((drop["state"], drop["sections"]), ("upcoming", []))

    def test_past_drops_cached_and_closed(self):
        past = [{"id": "p1", "updatedAt": 111}, {"id": "p2", "isHiddenFromPastDrops": True}]
        self.refresh(past=past, shells={"p1": shell("p1", orderCutoffTime=ms(timedelta(hours=-1)))})
        with mock.patch.object(feed.client, "drop_shell") as shell_call, \
                mock.patch.object(feed.client, "live_events", return_value=[]), \
                mock.patch.object(feed.client, "past_events", return_value=past):
            feed.refresh(CHEF)
            shell_call.assert_not_called()  # unchanged past drop reused from the last fetch
        menu = feed.present(CHEF)
        self.assertEqual([d["id"] for d in menu["past"]], ["p1"])
        self.assertEqual(menu["past"][0]["state"], "closed")
        self.assertTrue(menu["past"][0]["pickup_upcoming"])

    def test_failure_keeps_last_good_menu(self):
        self.refresh(live=[{"id": "ev1"}], shells={"ev1": shell()})
        with mock.patch.object(feed.client, "live_events", side_effect=HotplateError("HTTP 500")):
            result = feed.refresh(CHEF)
        self.assertIn("HTTP 500", result.last_error)
        self.assertEqual(len(feed.present(CHEF)["live"]), 1)

    def test_never_fetched(self):
        self.assertIsNone(feed.present(CHEF))
        HotplateFeed.objects.create(chef=CHEF)
        self.assertIsNone(feed.present(CHEF))
