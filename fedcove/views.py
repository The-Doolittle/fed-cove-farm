from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.http import Http404, HttpResponse
from django.shortcuts import redirect


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /order/confirmation/",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def legacy_image(request, path):
    """The old GitHub Pages site served images from /img/; old link previews
    (Facebook, Google Messages) still ask for them there."""
    name = f"img/{path}"
    if ".." in path or not staticfiles_storage.exists(name):
        raise Http404
    return redirect(f"{settings.STATIC_URL}{name}", permanent=True)
