from django.db import models
from modelcluster.fields import ParentalKey
from wagtail import blocks
from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.contrib.forms.models import AbstractEmailForm, AbstractFormField
from wagtail.contrib.forms.panels import FormSubmissionsPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import RichTextField, StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Orderable, Page


@register_setting(icon="cog")
class FarmSettings(BaseSiteSetting):
    """Contact details and links used across every page (Settings → Farm settings)."""

    phone = models.CharField(max_length=30, default="(828) 371-8018")
    email = models.EmailField(default="hello@fedcove.farm")
    location = models.CharField(max_length=120, default="Cowee Valley · Franklin, NC")
    facebook_url = models.URLField(
        blank=True, default="https://www.facebook.com/p/Fed-Cove-Farm-and-Nursery-100083734903683/"
    )
    instagram_url = models.URLField(blank=True, default="https://www.instagram.com/fedcove_farm.nursery/")
    instagram_handle = models.CharField(max_length=60, blank=True, default="@fedcove_farm.nursery")

    ORDERING_HOTPLATE = "hotplate"
    ORDERING_SITE = "site"
    ORDERING_LINK = "link"
    ORDERING_CHOICES = [
        (ORDERING_HOTPLATE, "Show our Hotplate drops on the site (checkout on Hotplate)"),
        (ORDERING_SITE, "Take orders on this site (Bakery → Drops)"),
        (ORDERING_LINK, "Just link to the ordering page below"),
    ]
    ordering_mode = models.CharField("Ordering", max_length=10, choices=ORDERING_CHOICES, default=ORDERING_HOTPLATE)
    hotplate_username = models.CharField(
        max_length=80,
        default="fedcovefarmandnursery",
        help_text="The name in your Hotplate link: hotplate.com/<this>",
    )
    order_url = models.URLField(
        "Outside ordering link", blank=True, default="https://www.hotplate.com/fedcovefarmandnursery"
    )
    order_label = models.CharField("Outside ordering button text", max_length=40, default="Order on Hotplate")

    more_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Shown as the dark 'More' button instead of a normal menu link.",
    )

    panels = [
        MultiFieldPanel(
            [FieldPanel("phone"), FieldPanel("email"), FieldPanel("location")], heading="Contact"
        ),
        MultiFieldPanel(
            [FieldPanel("facebook_url"), FieldPanel("instagram_url"), FieldPanel("instagram_handle")],
            heading="Social",
        ),
        MultiFieldPanel(
            [
                FieldPanel("ordering_mode"),
                FieldPanel("hotplate_username"),
                FieldPanel("order_url"),
                FieldPanel("order_label"),
            ],
            heading="Ordering",
        ),
        FieldPanel("more_page"),
    ]

    class Meta:
        verbose_name = "Farm settings"

    @property
    def hotplate_url(self):
        return f"https://www.hotplate.com/{self.hotplate_username}"

    @property
    def phone_href(self):
        digits = "".join(c for c in self.phone if c.isdigit())
        if len(digits) == 10:
            digits = "1" + digits
        return f"tel:+{digits}"


# ---------------------------------------------------------------------------
# Shared hero fields


class HeroFields(models.Model):
    hero_image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    hero_eyebrow = models.CharField("Small heading", max_length=80, blank=True)
    hero_title = models.CharField("Headline", max_length=160, blank=True)
    hero_text = models.TextField("Intro", blank=True)

    card_heading = models.CharField(
        "Side card heading", max_length=120, blank=True, help_text="Leave blank to hide the dark side card."
    )
    card_button_label = models.CharField("Side card button", max_length=60, blank=True)
    card_button_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Side card links to",
        help_text="Leave blank to link to the ordering page/link.",
    )

    hero_panels = [
        MultiFieldPanel(
            [
                FieldPanel("hero_image"),
                FieldPanel("hero_eyebrow"),
                FieldPanel("hero_title"),
                FieldPanel("hero_text"),
            ],
            heading="Top banner",
        ),
        MultiFieldPanel(
            [FieldPanel("card_heading"), FieldPanel("card_button_label"), FieldPanel("card_button_page")],
            heading="Dark side card",
            classname="collapsed",
        ),
    ]

    class Meta:
        abstract = True


class GalleryBlock(blocks.StructBlock):
    images = blocks.ListBlock(
        blocks.StructBlock(
            [("image", ImageChooserBlock()), ("caption", blocks.CharBlock(required=False))],
            icon="image",
        )
    )
    scrolling = blocks.BooleanBlock(
        required=False, default=False, help_text="Slowly scroll the photos sideways instead of a grid."
    )

    class Meta:
        icon = "image"
        template = "blocks/gallery.html"


class BodyBlock(blocks.StreamBlock):
    heading = blocks.CharBlock(icon="title", template="blocks/heading.html")
    text = blocks.RichTextBlock(features=["bold", "italic", "link", "ol", "ul"], template="blocks/text.html")
    image = blocks.StructBlock(
        [("image", ImageChooserBlock()), ("caption", blocks.CharBlock(required=False))],
        icon="image",
        template="blocks/image.html",
    )
    gallery = GalleryBlock()
    button = blocks.StructBlock(
        [
            ("label", blocks.CharBlock()),
            ("page", blocks.PageChooserBlock(required=False)),
            ("url", blocks.URLBlock(required=False)),
        ],
        icon="link",
        template="blocks/button.html",
    )


def open_drop_banner(request):
    """{'title', 'cutoff'} for a drop that's taking orders right now, whichever system is in use."""
    farm = FarmSettings.for_request(request)
    if farm.ordering_mode == FarmSettings.ORDERING_HOTPLATE:
        from hotplate.feed import present

        menu = present(farm.hotplate_username)
        drop = next((d for d in (menu or {}).get("live", []) if d["state"] == "open"), None)
        return {"title": drop["title"], "cutoff": drop["cutoff"]} if drop else None
    if farm.ordering_mode == FarmSettings.ORDERING_SITE:
        from orders.models import Drop

        drop = Drop.current()
        return {"title": drop.title, "cutoff": drop.closes_at} if drop and drop.is_open else None
    return None


# ---------------------------------------------------------------------------
# Pages


class HomePage(HeroFields, Page):
    tiles_eyebrow = models.CharField(max_length=80, default="What We Do")
    tiles_title = models.CharField(max_length=160, default="Grown, gathered, and baked on the farm")
    more_button_label = models.CharField(max_length=80, blank=True, default="Occasional Offerings (Limited)")

    events_eyebrow = models.CharField(max_length=80, default="Upcoming")
    events_title = models.CharField(max_length=160, default="Farm calendar")

    cta_title = models.CharField("Banner title", max_length=120, blank=True)
    cta_text = models.CharField("Banner text", max_length=255, blank=True)
    cta_button_label = models.CharField("Banner button", max_length=40, blank=True)
    cta_page = models.ForeignKey(
        "wagtailcore.Page", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    follow_title = models.CharField(max_length=120, default="Follow Along")
    follow_text = models.TextField(blank=True)
    show_facebook_feed = models.BooleanField(default=True)

    content_panels = (
        Page.content_panels
        + HeroFields.hero_panels
        + [
            MultiFieldPanel(
                [
                    FieldPanel("tiles_eyebrow"),
                    FieldPanel("tiles_title"),
                    InlinePanel("tiles", label="Tile", min_num=1),
                    FieldPanel("more_button_label"),
                ],
                heading="What we do",
            ),
            MultiFieldPanel([FieldPanel("events_eyebrow"), FieldPanel("events_title")], heading="Calendar"),
            MultiFieldPanel(
                [
                    FieldPanel("cta_title"),
                    FieldPanel("cta_text"),
                    FieldPanel("cta_button_label"),
                    FieldPanel("cta_page"),
                ],
                heading="Dark banner",
            ),
            MultiFieldPanel(
                [FieldPanel("follow_title"), FieldPanel("follow_text"), FieldPanel("show_facebook_feed")],
                heading="Follow along",
            ),
        ]
    )

    max_count = 1
    parent_page_types = ["wagtailcore.Page"]

    def get_context(self, request, *args, **kwargs):
        from events.models import Event

        context = super().get_context(request, *args, **kwargs)
        context["drop_banner"] = open_drop_banner(request)
        context["upcoming_events"] = Event.upcoming()[:4]
        context["events_page"] = EventsPage.objects.live().first()
        return context


class HomeTile(Orderable):
    page = ParentalKey(HomePage, on_delete=models.CASCADE, related_name="tiles")
    title = models.CharField(max_length=80)
    image = models.ForeignKey("wagtailimages.Image", on_delete=models.CASCADE, related_name="+")
    link_page = models.ForeignKey("wagtailcore.Page", on_delete=models.CASCADE, related_name="+")

    panels = [FieldPanel("title"), FieldPanel("image"), FieldPanel("link_page")]


class StandardPage(HeroFields, Page):
    """A flexible page: banner, then any mix of text, photos, galleries and buttons."""

    body = StreamField(BodyBlock(), blank=True)
    show_child_pages = models.BooleanField(
        default=True, help_text="List published pages beneath this one as cards (e.g. seasonal offerings)."
    )
    empty_message = models.CharField(
        max_length=255, blank=True, help_text="Shown when there's no body and no published child pages."
    )

    content_panels = (
        Page.content_panels
        + HeroFields.hero_panels
        + [FieldPanel("body"), FieldPanel("show_child_pages"), FieldPanel("empty_message")]
    )

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["child_pages"] = (
            self.get_children().live().specific() if self.show_child_pages else Page.objects.none()
        )
        return context


class BakedGoodsPage(HeroFields, Page):
    menu_eyebrow = models.CharField(max_length=80, default="Regular Menu")
    menu_title = models.CharField(max_length=160, default="What We Bake")
    menu_text = models.TextField(blank=True)
    reviews_eyebrow = models.CharField(max_length=80, default="Kind Words")
    reviews_title = models.CharField(max_length=160, default="What Folks Are Saying")

    content_panels = (
        Page.content_panels
        + HeroFields.hero_panels
        + [
            MultiFieldPanel(
                [FieldPanel("menu_eyebrow"), FieldPanel("menu_title"), FieldPanel("menu_text")],
                heading="Menu (items come from Products marked 'show on menu')",
            ),
            MultiFieldPanel(
                [FieldPanel("reviews_eyebrow"), FieldPanel("reviews_title")],
                heading="Reviews (edit under Snippets → Reviews)",
            ),
        ]
    )
    max_count = 1

    def get_context(self, request, *args, order_data=None, order_errors=None, **kwargs):
        from orders.models import Drop, Product

        context = super().get_context(request, *args, **kwargs)
        context["menu_items"] = Product.objects.filter(show_on_menu=True).select_related("image")
        context["reviews"] = Review.objects.all()
        farm = FarmSettings.for_request(request)
        context["ordering_mode"] = farm.ordering_mode
        if farm.ordering_mode == FarmSettings.ORDERING_HOTPLATE:
            from hotplate.feed import present

            context["hotplate"] = present(farm.hotplate_username)
            context["hotplate_url"] = farm.hotplate_url
            return context
        drop = context["drop"] = Drop.current() if farm.ordering_mode == FarmSettings.ORDERING_SITE else None
        if drop:
            data, errors = order_data or {}, order_errors or {}
            rows = []
            for item in drop.items.select_related("product", "product__image"):
                remaining = item.remaining
                limit = item.max_per_order if remaining is None else min(item.max_per_order, remaining)
                key = f"qty_{item.pk}"
                rows.append(
                    {"item": item, "remaining": remaining, "max": limit, "field": key,
                     "value": data.get(key, ""), "error": errors.get(key)}
                )
            context["drop_rows"] = rows
            context["drop_slots"] = [
                {"slot": slot, "remaining": slot.remaining, "checked": data.get("slot") == str(slot.pk)}
                for slot in drop.slots.all()
            ]
            context["order_data"], context["order_errors"] = data, errors
        return context

    def serve(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        from django.template.response import TemplateResponse

        from orders.ordering import place_order

        if request.method == "POST" and FarmSettings.for_request(request).ordering_mode == FarmSettings.ORDERING_SITE:
            order, errors = place_order(request.POST.get("drop"), request.POST)
            if order:
                return redirect("order_confirmation", code=order.code)
            context = self.get_context(request, *args, order_data=request.POST, order_errors=errors, **kwargs)
            return TemplateResponse(request, self.get_template(request, *args, **kwargs), context, status=400)
        return super().serve(request, *args, **kwargs)


class LandscapingPage(HeroFields, Page):
    intro_eyebrow = models.CharField(max_length=80, default="Available Seasonally")
    intro_title = models.CharField(max_length=160, default="Perennials for the mountain garden")
    intro_text = models.TextField(blank=True)
    notice = models.CharField(max_length=255, blank=True)

    content_panels = (
        Page.content_panels
        + HeroFields.hero_panels
        + [
            MultiFieldPanel(
                [FieldPanel("intro_eyebrow"), FieldPanel("intro_title"), FieldPanel("intro_text")],
                heading="Intro",
            ),
            InlinePanel("gallery_images", label="Gallery photo", heading="Scrolling photo gallery"),
            FieldPanel("notice"),
        ]
    )
    max_count = 1


class LandscapingGalleryImage(Orderable):
    page = ParentalKey(LandscapingPage, on_delete=models.CASCADE, related_name="gallery_images")
    image = models.ForeignKey("wagtailimages.Image", on_delete=models.CASCADE, related_name="+")
    caption = models.CharField(max_length=120, blank=True)

    panels = [FieldPanel("image"), FieldPanel("caption")]


class EventsPage(HeroFields, Page):
    """Calendar + market locations. Events themselves live under Snippets → Events / Google Calendar."""

    intro_text = models.TextField(blank=True)
    locations_eyebrow = models.CharField(max_length=80, default="Where To Find Us")
    locations_title = models.CharField(max_length=160, default="Our Frequent Locations")

    content_panels = (
        Page.content_panels
        + HeroFields.hero_panels
        + [
            FieldPanel("intro_text"),
            MultiFieldPanel(
                [
                    FieldPanel("locations_eyebrow"),
                    FieldPanel("locations_title"),
                    InlinePanel("locations", label="Location"),
                ],
                heading="Locations",
            ),
        ]
    )
    max_count = 1

    def get_context(self, request, *args, **kwargs):
        from events.calendar import month_context

        context = super().get_context(request, *args, **kwargs)
        context.update(month_context(request.GET.get("month")))
        return context


class EventLocation(Orderable):
    page = ParentalKey(EventsPage, on_delete=models.CASCADE, related_name="locations")
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=255, blank=True)
    image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    panels = [FieldPanel("name"), FieldPanel("address"), FieldPanel("image")]


class ContactFormField(AbstractFormField):
    page = ParentalKey("ContactPage", on_delete=models.CASCADE, related_name="form_fields")


class ContactPage(HeroFields, AbstractEmailForm):
    """Contact form. Submissions are saved (Forms in the admin) and emailed to the 'to address'."""

    thank_you_text = RichTextField(blank=True)
    social_text = models.CharField(
        max_length=255,
        blank=True,
        default="The fastest way to reach us for day-to-day questions is usually Facebook or Instagram.",
    )

    content_panels = (
        AbstractEmailForm.content_panels
        + [FormSubmissionsPanel()]
        + HeroFields.hero_panels
        + [
            InlinePanel("form_fields", label="Form field"),
            FieldPanel("thank_you_text"),
            FieldPanel("social_text"),
            MultiFieldPanel(
                [
                    FieldRowPanel([FieldPanel("from_address"), FieldPanel("to_address")]),
                    FieldPanel("subject"),
                ],
                heading="Email",
            ),
        ]
    )
    max_count = 1

    HONEYPOT = "website"

    def get_form(self, *args, **kwargs):
        from django import forms

        form = super().get_form(*args, **kwargs)
        form.fields[self.HONEYPOT] = forms.CharField(
            required=False,
            label="Leave this field empty",
            widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
        )
        return form

    def process_form_submission(self, form):
        if form.cleaned_data.pop(self.HONEYPOT, ""):
            return None  # a bot filled the hidden field; pretend it worked
        form.fields.pop(self.HONEYPOT, None)
        return super().process_form_submission(form)


class Review(Orderable):
    quote = models.TextField()
    name = models.CharField(max_length=80)
    detail = models.CharField(max_length=120, blank=True, help_text="e.g. 'Cowee Farmers’ Market customer'")
    stars = models.PositiveSmallIntegerField(default=5, choices=[(n, f"{n} stars") for n in range(1, 6)])

    panels = [FieldPanel("quote"), FieldPanel("name"), FieldPanel("detail"), FieldPanel("stars")]

    class Meta(Orderable.Meta):
        verbose_name = "review"

    def __str__(self):
        return f"{self.name}: {self.quote[:50]}"

    @property
    def star_string(self):
        return "★" * self.stars
