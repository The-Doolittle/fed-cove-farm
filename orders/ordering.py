import logging
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.template.loader import render_to_string

from .models import Drop, Order, OrderLine

log = logging.getLogger(__name__)


def place_order(drop_id, data):
    """Validate and create an order from POSTed form data.

    Returns (order, errors). Runs in one transaction so stock limits hold even when
    two people order the last item at the same moment.
    """
    errors = {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    note = data.get("note", "").strip()[:1000]
    if not name:
        errors["name"] = "Please tell us your name."
    try:
        validate_email(email)
    except ValidationError:
        errors["email"] = "Please enter a valid email so we can confirm your order."

    with transaction.atomic():
        drop = Drop.objects.select_for_update().filter(pk=drop_id, published=True).first()
        if drop is None or not drop.is_open:
            return None, {"form": "Sorry — this drop isn't taking orders right now."}

        wanted = []
        for item in drop.items.select_related("product"):
            raw = data.get(f"qty_{item.pk}", "").strip() or "0"
            try:
                qty = int(raw)
            except ValueError:
                qty = -1
            if qty < 0:
                errors[f"qty_{item.pk}"] = "Enter a whole number."
                continue
            if qty == 0:
                continue
            if qty > item.max_per_order:
                errors[f"qty_{item.pk}"] = f"Limit {item.max_per_order} per order."
            remaining = item.remaining
            if remaining is not None and qty > remaining:
                errors[f"qty_{item.pk}"] = f"Only {remaining} left." if remaining else "Sold out."
            wanted.append((item, qty))
        if not wanted and not any(k.startswith("qty_") for k in errors):
            errors["no_items"] = "Choose at least one item."

        slot = None
        slots = list(drop.slots.all())
        if slots:
            slot = next((s for s in slots if str(s.pk) == data.get("slot")), None)
            if slot is None:
                errors["slot"] = "Choose a pickup option."
            elif slot.remaining == 0:
                errors["slot"] = "That pickup option is full — please pick another."

        if errors:
            transaction.set_rollback(True)
            return None, errors

        order = Order.objects.create(drop=drop, slot=slot, name=name, email=email, phone=phone, note=note)
        total = Decimal("0.00")
        for item, qty in wanted:
            OrderLine.objects.create(
                order=order, drop_item=item, name=item.product.name, unit_price=item.unit_price, quantity=qty
            )
            total += item.unit_price * qty
        order.total = total
        order.save(update_fields=["total"])

    transaction.on_commit(lambda: send_order_emails(order))
    return order, {}


def send_order_emails(order, base_url=None):
    context = {"order": order, "base_url": base_url or settings.WAGTAILADMIN_BASE_URL}
    try:
        send_mail(
            f"Your Fed Cove Farm order ({order.short_code})",
            render_to_string("orders/email_customer.txt", context),
            settings.DEFAULT_FROM_EMAIL,
            [order.email],
        )
        send_mail(
            f"New order: {order.name} – {order.drop.title}",
            render_to_string("orders/email_farm.txt", context),
            settings.DEFAULT_FROM_EMAIL,
            [settings.FARM_NOTIFY_EMAIL],
        )
    except Exception:
        log.exception("Sending order emails for %s failed", order.pk)
