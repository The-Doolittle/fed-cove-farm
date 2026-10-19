from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem

from . import views


@hooks.register("register_admin_urls")
def hotplate_urls():
    return [
        path("hotplate/", views.status, name="hotplate_status"),
        path("hotplate/refresh/", views.refresh_now, name="hotplate_refresh"),
    ]


@hooks.register("register_admin_menu_item")
def hotplate_menu_item():
    return MenuItem("Hotplate", reverse("hotplate_status"), icon_name="download", order=192)
