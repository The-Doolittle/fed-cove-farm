from django import template
from wagtail.models import Site

from home.models import BakedGoodsPage, FarmSettings

register = template.Library()


@register.simple_tag(takes_context=True)
def menu_items(context):
    """Home plus top-level pages ticked 'show in menus', minus the More page (it gets its own button)."""
    request = context["request"]
    site = Site.find_for_request(request)
    if site is None:
        return []
    root = site.root_page.specific
    more_id = FarmSettings.for_request(request).more_page_id
    pages = [root] + [p for p in root.get_children().live().in_menu() if p.pk != more_id]
    path = request.path
    items = []
    for page in pages:
        url = page.get_url(request)
        active = path == url if page.pk == root.pk else bool(url) and path.startswith(url)
        items.append({"title": "Home" if page.pk == root.pk else page.title, "url": url, "active": active})
    return items


@register.simple_tag(takes_context=True)
def more_link(context):
    request = context["request"]
    page = FarmSettings.for_request(request).more_page
    if not page or not page.live:
        return None
    url = page.get_url(request)
    if not url:
        return None
    return {"title": page.title, "url": url, "active": request.path.startswith(url)}


@register.simple_tag(takes_context=True)
def order_link(context):
    """Where 'Order' buttons go: the on-site drop, or the outside ordering link (Hotplate)."""
    request = context["request"]
    settings = FarmSettings.for_request(request)
    if settings.onsite_ordering:
        page = BakedGoodsPage.objects.live().first()
        if page:
            return {"url": page.get_url(request) + "#order", "label": "Order Now", "external": False}
    return {"url": settings.order_url, "label": settings.order_label, "external": True}
