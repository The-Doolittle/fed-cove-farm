from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .models import Drop, Order, OrderLine


@require_GET
def current_drop_json(request):
    drop = Drop.current()
    return JsonResponse({"drop": drop.as_json() if drop else None})


def order_confirmation(request, code):
    order = get_object_or_404(Order.objects.select_related("drop", "slot"), code=code)
    return render(request, "orders/confirmation.html", {"order": order})


def prep_list(request, drop_id):
    """Admin: what to bake and how to bag it for one drop."""
    drop = get_object_or_404(Drop, pk=drop_id)
    orders = (
        drop.orders.exclude(status=Order.CANCELLED).select_related("slot").prefetch_related("lines").order_by("slot", "name")
    )
    lines = OrderLine.objects.filter(order__in=orders)
    totals = lines.values("name").annotate(qty=Sum("quantity"), orders=Count("order", distinct=True)).order_by("name")
    by_slot = {}
    for order in orders:
        by_slot.setdefault(order.slot.label if order.slot else "No pickup option", []).append(order)
    return render(
        request,
        "orders/admin_prep_list.html",
        {
            "drop": drop,
            "totals": totals,
            "by_slot": by_slot,
            "order_count": orders.count(),
            "revenue": orders.aggregate(t=Sum("total"))["t"] or 0,
            "header_icon": "list-ul",
        },
    )


def prep_index(request):
    drops = Drop.objects.annotate(order_count=Count("orders"))[:30]
    return render(request, "orders/admin_prep_index.html", {"drops": drops, "header_icon": "list-ul"})
