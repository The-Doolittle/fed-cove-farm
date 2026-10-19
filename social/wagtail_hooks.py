from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem

from . import views


@hooks.register("register_admin_urls")
def social_urls():
    return [
        path("social/", views.status, name="social_status"),
        path("social/refresh/", views.refresh_now, name="social_refresh"),
        path("social/<str:platform>/connect/", views.connect, name="social_connect"),
    ]


class SuperuserMenuItem(MenuItem):
    def is_shown(self, request):
        return request.user.is_superuser


@hooks.register("register_admin_menu_item")
def social_menu_item():
    return SuperuserMenuItem("Social feed", reverse("social_status"), icon_name="image", order=215)
