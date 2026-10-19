from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from home.models import Review

from . import views
from .models import Drop, Order, Product


class ProductViewSet(SnippetViewSet):
    model = Product
    icon = "tag"
    list_display = ["name", "price", "show_on_menu"]
    search_fields = ["name", "description"]
    sort_order_field = "sort_order"


class DropViewSet(SnippetViewSet):
    model = Drop
    icon = "calendar-alt"
    list_display = ["title", "opens_at", "closes_at", "status", "published"]
    list_filter = ["published"]


class OrderViewSet(SnippetViewSet):
    model = Order
    icon = "list-ul"
    list_display = ["name", "drop", "slot", "summary", "total", "status", "payment", "created_at"]
    list_filter = ["drop", "status", "payment"]
    search_fields = ["name", "email", "phone"]
    list_per_page = 50


class ReviewViewSet(SnippetViewSet):
    model = Review
    icon = "openquote"
    list_display = ["name", "quote", "stars"]
    sort_order_field = "sort_order"


class ShopGroup(SnippetViewSetGroup):
    menu_label = "Bakery"
    menu_icon = "pick"
    menu_order = 190
    items = (DropViewSet, OrderViewSet, ProductViewSet, ReviewViewSet)


register_snippet(ShopGroup)


@hooks.register("register_admin_urls")
def prep_list_urls():
    return [
        path("prep-lists/", views.prep_index, name="prep_index"),
        path("prep-lists/<int:drop_id>/", views.prep_list, name="prep_list"),
    ]


@hooks.register("register_admin_menu_item")
def prep_list_menu_item():
    return MenuItem("Prep lists", reverse("prep_index"), icon_name="clipboard-list", order=195)
