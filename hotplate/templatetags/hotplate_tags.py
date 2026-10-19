from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def money(value):
    """'17.00' → '$17', '8.50' → '$8.50', '0.00' → 'Free'."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return ""
    if amount == 0:
        return "Free"
    return f"${amount:.0f}" if amount == amount.to_integral() else f"${amount:.2f}"
