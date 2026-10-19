"""Read-only client for Hotplate's public storefront API.

Hotplate has no documented API. Its storefront (hotplate.com/<chef>) loads its data from
these tRPC endpoints, which are public GETs that need no login. They can change without
notice, so everything here fails loudly and the caller keeps the last good data.
Only the shop.* read endpoints are used — never cart.* or anything payment-related.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

API = "https://bets.hotplate.com/trpc/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FedCoveFarmSite/1.0; +https://fedcove.farm)",
    "Accept": "application/json",
    "Origin": "https://www.hotplate.com",
    "Referer": "https://www.hotplate.com/",
}


class HotplateError(Exception):
    pass


def call(procedure, payload, timeout=20):
    query = urllib.parse.quote(json.dumps(payload, separators=(",", ":")))
    req = urllib.request.Request(f"{API}{procedure}?input={query}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as exc:
        raise HotplateError(f"{procedure}: HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HotplateError(f"{procedure}: {exc}") from exc
    try:
        return body["result"]["data"]
    except (KeyError, TypeError) as exc:
        raise HotplateError(f"{procedure}: unexpected response {str(body)[:200]}") from exc


def live_events(chef):
    return call("shop.getPublicLiveEvents", {"chefId": chef, "eventFilter": "regular"})


def past_events(chef):
    return call("shop.getPublicPastEvents", {"chefId": chef, "direction": "forward"})["pastEvents"]


def drop_shell(event_id):
    return call("shop.getDropShell", {"eventId": event_id, "fulfillmentType": "PICKUP"})


def inventory(event_id):
    return call("shop.getDropInventorySnapshot", {"eventId": event_id, "fulfillmentType": "PICKUP"})
