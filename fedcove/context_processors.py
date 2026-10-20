from django.conf import settings


def demo_site(request):
    return {"DEMO_SITE": settings.DEMO_SITE}
