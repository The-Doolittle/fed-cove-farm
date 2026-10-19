from django.conf import settings
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.static import serve as serve_static
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from events import views as event_views
from orders import views as order_views

from .api import api_router

urlpatterns = [
    path("healthz", lambda request: HttpResponse("ok")),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("api/v2/", api_router.urls),
    path("api/events/", event_views.events_json, name="events_json"),
    path("api/drops/current/", order_views.current_drop_json, name="current_drop_json"),
    path("order/confirmation/<str:code>/", order_views.order_confirmation, name="order_confirmation"),
    # Uploaded images. Fine for a small site; put a CDN/web server in front later if traffic grows.
    re_path(r"^media/(?P<path>.*)$", serve_static, {"document_root": settings.MEDIA_ROOT}),
    path("", include(wagtail_urls)),
]
