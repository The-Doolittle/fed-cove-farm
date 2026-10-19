from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST
from wagtail.models import Site

from home.models import FarmSettings

from . import feed
from .models import HotplateFeed


def _chef(request):
    return FarmSettings.for_request(request).hotplate_username


@require_GET
def hotplate_json(request):
    """GET /api/hotplate/ — the stored Hotplate drops (live + recent past)."""
    stored = HotplateFeed.objects.filter(chef=_chef(request)).first()
    if not stored or not stored.fetched_at:
        return JsonResponse({"fetched_at": None, "live": [], "past": []})
    return JsonResponse({"fetched_at": stored.fetched_at.isoformat(), **stored.data})


def status(request):
    chef = _chef(request)
    return render(
        request,
        "hotplate/admin_status.html",
        {
            "chef": chef,
            "mode": FarmSettings.for_request(request).ordering_mode,
            "stored": HotplateFeed.objects.filter(chef=chef).first(),
            "menu": feed.present(chef),
            "header_icon": "download",
        },
    )


@require_POST
def refresh_now(request):
    result = feed.refresh(_chef(request))
    if result.last_error:
        messages.error(request, f"Couldn't reach Hotplate: {result.last_error}")
    else:
        live, past = len(result.data.get("live", [])), len(result.data.get("past", []))
        messages.success(request, f"Updated from Hotplate: {live} open drop(s), {past} recent drop(s).")
    return redirect("hotplate_status")


def default_farm_settings():
    site = Site.objects.filter(is_default_site=True).first()
    return FarmSettings.for_site(site) if site else None
