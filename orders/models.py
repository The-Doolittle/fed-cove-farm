import secrets
from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.utils import timezone
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.models import Orderable


class Product(Orderable):
    """Something the farm sells. Reused across weekly drops and shown on the menu."""

    name = models.CharField(max_length=120)
    label = models.CharField(max_length=60, blank=True, help_text="Small gold text, e.g. 'Bakery favorite'")
    description = models.TextField(blank=True)
    image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    price = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    show_on_menu = models.BooleanField(default=True, help_text="Show on the Baked Goods 'What We Bake' menu.")

    panels = [
        FieldPanel("name"),
        FieldPanel("label"),
        FieldPanel("description"),
        FieldPanel("image"),
        FieldRowPanel([FieldPanel("price"), FieldPanel("show_on_menu")]),
    ]

    def __str__(self):
        return self.name


class Drop(ClusterableModel):
    """A weekly ordering window, like a Hotplate drop."""

    title = models.CharField(max_length=120, help_text="e.g. 'Saturday Market Bake – Oct 25'")
    description = models.TextField(blank=True)
    opens_at = models.DateTimeField()
    closes_at = models.DateTimeField()
    pickup_info = models.TextField(blank=True, help_text="Shown to customers and in confirmation emails.")
    published = models.BooleanField(default=True, help_text="Untick to hide this drop from the site.")
    created_at = models.DateTimeField(auto_now_add=True)

    panels = [
        FieldPanel("title"),
        FieldPanel("description"),
        FieldRowPanel([FieldPanel("opens_at"), FieldPanel("closes_at")]),
        FieldPanel("pickup_info"),
        InlinePanel("items", label="Item", heading="What's in this drop"),
        InlinePanel("slots", label="Pickup option", heading="Pickup options"),
        FieldPanel("published"),
    ]

    class Meta:
        ordering = ["-opens_at"]

    def __str__(self):
        return self.title

    @property
    def status(self):
        now = timezone.now()
        if now < self.opens_at:
            return "upcoming"
        if now <= self.closes_at:
            return "open"
        return "closed"

    @property
    def is_open(self):
        return self.status == "open"

    @classmethod
    def current(cls):
        """The drop to feature: open now, else the next one, else one that closed in the last 5 days."""
        now = timezone.now()
        live = cls.objects.filter(published=True)
        return (
            live.filter(opens_at__lte=now, closes_at__gte=now).order_by("closes_at").first()
            or live.filter(opens_at__gt=now).order_by("opens_at").first()
            or live.filter(closes_at__lt=now, closes_at__gte=now - timedelta(days=5)).first()
        )

    def as_json(self):
        return {
            "id": self.pk,
            "title": self.title,
            "status": self.status,
            "opens_at": self.opens_at.isoformat(),
            "closes_at": self.closes_at.isoformat(),
            "pickup_info": self.pickup_info,
            "items": [item.as_json() for item in self.items.select_related("product")],
            "pickup_options": [
                {"id": s.pk, "label": s.label, "remaining": s.remaining} for s in self.slots.all()
            ],
        }


class DropItem(Orderable):
    drop = ParentalKey(Drop, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")
    price = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True, help_text="Leave blank to use the product price."
    )
    quantity = models.PositiveIntegerField(null=True, blank=True, help_text="How many you're making. Blank = no limit.")
    max_per_order = models.PositiveIntegerField(default=6)

    panels = [
        FieldPanel("product"),
        FieldRowPanel([FieldPanel("price"), FieldPanel("quantity"), FieldPanel("max_per_order")]),
    ]

    def __str__(self):
        return str(self.product)

    @property
    def unit_price(self):
        return self.price if self.price is not None else self.product.price

    @property
    def sold(self):
        return (
            OrderLine.objects.filter(drop_item=self)
            .exclude(order__status=Order.CANCELLED)
            .aggregate(n=Sum("quantity"))["n"]
            or 0
        )

    @property
    def remaining(self):
        return None if self.quantity is None else max(0, self.quantity - self.sold)

    def as_json(self):
        return {
            "id": self.pk,
            "name": self.product.name,
            "description": self.product.description,
            "price": str(self.unit_price),
            "remaining": self.remaining,
            "max_per_order": self.max_per_order,
        }


class PickupSlot(Orderable):
    drop = ParentalKey(Drop, on_delete=models.CASCADE, related_name="slots")
    label = models.CharField(max_length=160, help_text="e.g. 'Sat Oct 25, 9am–12pm · Cowee Farmers’ Market'")
    capacity = models.PositiveIntegerField(null=True, blank=True, help_text="Max orders. Blank = no limit.")

    panels = [FieldRowPanel([FieldPanel("label"), FieldPanel("capacity")])]

    def __str__(self):
        return self.label

    @property
    def remaining(self):
        if self.capacity is None:
            return None
        taken = self.orders.exclude(status=Order.CANCELLED).count()
        return max(0, self.capacity - taken)


def _order_code():
    # Unguessable (it's the confirmation link) and readable: no 0/O or 1/I/L.
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(14))


class Order(models.Model):
    NEW = "new"
    READY = "ready"
    PICKED_UP = "picked_up"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [(NEW, "New"), (READY, "Ready"), (PICKED_UP, "Picked up"), (CANCELLED, "Cancelled")]

    UNPAID = "unpaid"
    PAID = "paid"
    PAYMENT_CHOICES = [(UNPAID, "Pay at pickup"), (PAID, "Paid")]

    code = models.CharField(max_length=20, unique=True, default=_order_code, editable=False)
    drop = models.ForeignKey(Drop, on_delete=models.PROTECT, related_name="orders")
    slot = models.ForeignKey(PickupSlot, null=True, on_delete=models.SET_NULL, related_name="orders")
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    note = models.TextField(blank=True)
    total = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=NEW)
    payment = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default=UNPAID)
    created_at = models.DateTimeField(auto_now_add=True)

    panels = [
        MultiFieldPanel(
            [FieldPanel("name"), FieldPanel("email"), FieldPanel("phone"), FieldPanel("note")], heading="Customer"
        ),
        FieldRowPanel([FieldPanel("status"), FieldPanel("payment")]),
        FieldPanel("slot"),
    ]

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} – {self.drop}"

    @property
    def short_code(self):
        return self.code[:6].upper()

    @property
    def summary(self):
        return ", ".join(f"{line.quantity}× {line.name}" for line in self.lines.all())


class OrderLine(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    drop_item = models.ForeignKey(DropItem, null=True, on_delete=models.SET_NULL, related_name="+")
    name = models.CharField(max_length=120)
    unit_price = models.DecimalField(max_digits=7, decimal_places=2)
    quantity = models.PositiveIntegerField()

    @property
    def line_total(self):
        return self.unit_price * self.quantity
