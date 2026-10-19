from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import feed
from .models import SocialAccount, SocialPost


def _accounts():
    return {p: SocialAccount.objects.get_or_create(platform=p)[0] for p, _ in SocialAccount.PLATFORM_CHOICES}


def _require_superuser(request):
    # Tokens are credentials for the farm's accounts; only full admins can see or change them.
    if not request.user.is_superuser:
        raise PermissionDenied


def status(request):
    _require_superuser(request)
    accounts = _accounts()
    return render(
        request,
        "social/admin_status.html",
        {
            "instagram": accounts[SocialAccount.INSTAGRAM],
            "facebook": accounts[SocialAccount.FACEBOOK],
            "posts": feed.latest(limit=8),
            "post_count": SocialPost.objects.count(),
            "header_icon": "image",
        },
    )


@require_POST
def connect(request, platform):
    _require_superuser(request)
    if platform not in dict(SocialAccount.PLATFORM_CHOICES):
        raise Http404
    account = _accounts()[platform]
    if request.POST.get("disconnect"):
        account.token = ""
        account.save()
        for post in SocialPost.objects.filter(platform=platform):
            post.image.delete(save=False)
            post.delete()
        messages.success(request, f"{account} disconnected and its posts removed from the site.")
        return redirect("social_status")
    token = request.POST.get("token", "")
    if not token.strip():
        messages.error(request, "Paste a token first.")
        return redirect("social_status")
    feed.set_token(account, token, request.POST.get("account_id", ""))
    account = feed.refresh(account)
    if account.last_error:
        messages.error(request, f"Saved, but {account} said: {account.last_error}")
    else:
        messages.success(request, f"Connected {account} ({account.username}).")
    return redirect("social_status")


@require_POST
def refresh_now(request):
    _require_superuser(request)
    errors = [f"{a}: {a.last_error}" for a in feed.refresh_all() if a.connected and a.last_error]
    if errors:
        messages.error(request, " · ".join(errors))
    else:
        messages.success(request, "Social posts updated.")
    return redirect("social_status")
