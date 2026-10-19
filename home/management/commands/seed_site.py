"""Build the site's pages and content from the original static site.

    python manage.py seed_site            # pages, photos, products, reviews
    python manage.py seed_site --demo     # also sample events + an open drop to try ordering
"""

from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from wagtail.contrib.redirects.models import Redirect
from wagtail.images.models import Image
from wagtail.models import Page, Site

from events.models import Event
from home.models import (
    BakedGoodsPage,
    ContactFormField,
    ContactPage,
    EventLocation,
    EventsPage,
    FarmSettings,
    HomePage,
    HomeTile,
    LandscapingGalleryImage,
    LandscapingPage,
    Review,
    StandardPage,
)
from orders.models import Drop, DropItem, PickupSlot, Product

SEED_DIR = Path(settings.BASE_DIR) / "seed" / "img"

IMAGE_TITLES = {
    "artisan-bread.jpg": "Artisan focaccia with fresh herbs, cherry tomatoes, and peppers",
    "cookies-honey.jpg": "Fed Cove Farm sourwood honey with sea-salt cookies",
    "farmers-market-1.jpg": "Fed Cove Farm at the farmers' market",
    "fed-cove-farm-01.jpg": "Fed Cove Farm and Nursery",
    "fed-cove-farm-02.jpg": "Fed Cove Farm",
    "fed-cove-farm-03.jpg": "Landscape perennials",
    "fed-cove-farm-04.jpg": "Fed Cove Farm",
    "muffins.jpg": "Blueberry muffins with a crumb streusel topping",
    "sandwich-bread.jpg": "Sliced sourdough sandwich loaf",
    "scones.jpg": "Fresh-baked scones with a sweet glaze drizzle",
    "sourdough.jpg": "Rustic sourdough loaves fresh from the oven",
    "shade-perennials.png": "Shade perennials",
    "perennials-2.png": "Perennials",
    "drone-high.png": "Aerial view of Fed Cove Farm",
}

PLANTS = [
    ("ferns.jpg", "Ferns", "Rows of potted ferns growing at Fed Cove Farm's nursery"),
    ("perennials.jpg", "Perennials", "Potted perennials growing at Fed Cove Farm's nursery"),
    ("20260624_141337.jpg", "Catmint", "Catmint in bloom"),
    ("20260629_200401.jpg", "Coral Bells", "Silver and red coral bells (Heuchera)"),
    ("20260629_200403.jpg", "Coral Bells", "Amber and cream coral bells (Heuchera)"),
    ("20260707_210856.jpg", "Sedum ‘Autumn Fire’", "Sedum Autumn Fire in pots"),
    ("20260707_210929.jpg", "Joe Pye Weed", "Joe Pye weed in bloom"),
    ("20260711_174216.jpg", "Threadleaf Coreopsis", "Threadleaf coreopsis with yellow flowers"),
    ("20260719_203336.jpg", "Coneflowers & Black-Eyed Susans", "Coneflowers and black-eyed Susans in a garden bed"),
    ("20260730_200655.jpg", "The Nursery at Sunrise", "Wide view of the nursery and hoop house at sunrise"),
    ("20260812_143046.jpg", "Black-Eyed Susans", "Black-eyed Susans in bloom"),
    ("20260812_182537.jpg", "Joe Pye Weed & Bees", "Bumblebees on Joe Pye weed blossoms"),
    ("20260820_195514.jpg", "Hardy Geraniums", "Hardy geraniums in bloom"),
]

PRODUCTS = [
    ("Sourwood Honey", "Farm product", "Raw honey harvested and bottled right here at Fed Cove Farm.", "cookies-honey.jpg"),
    ("Artisan Focaccia", "Savory favorite", "Baked with fresh herbs and a colorful mix of peppers and cherry tomatoes.", "artisan-bread.jpg"),
    ("Scones", "Bakery favorite", "Tender and flaky, finished with a sweet glaze drizzle.", "scones.jpg"),
    ("Sourdough Loaf (Sandwich)", "Sandwich ready", "Extra-tender and sturdy enough for lunch, toast, and paninis.", "sandwich-bread.jpg"),
    ("Blueberry Muffins", "Bakery favorite", "Packed with blueberries and topped with a crumb streusel.", "muffins.jpg"),
    ("Sourdough Loaf", "Classic favorite", "Naturally leavened, with a crackly crust and a soft, airy crumb.", "sourdough.jpg"),
]

REVIEWS = [
    ("Your items are always delicious!", "Kristi R.", "Cowee Farmers’ Market customer"),
    ("Fed Cove makes the best sourdough around! I love that they use organic ingredients and avocado oil instead of seed oils. I love all the different varieties, and they always taste amazing. The scones, muffins, and sandwich loaves are favorites at our house.", "Grace S.", ""),
    ("Beautiful crumb and excellent flavor. Great customer service too!", "Kelly R.", ""),
    ("Everything Fed Cove puts out is incredible, and they are such kind and thoughtful people on top of it. I’d tell you the rosemary is one of my favorites, but really everything is my favorite.", "Emily G.", ""),
    ("The focaccia bread is soft and delicious. I’m single so the size is perfect to last a few days, and warmed up it’s still wonderful. The chocolate zucchini scones are to die for — the chocolate is soft and the scones are soft and tasty, and you can tell yourself you’re eating vegetables and avoid the guilt of such pleasure!", "Jo Anne T.", ""),
    ("Amazing muffins! More blueberries than muffin! So good!", "Debbie R.", ""),
    ("YUM! YUM!! YUM!!!", "Renee M.", ""),
    ("Delicious baked goods. Never had anything that wasn’t great from Fed Cove!", "Reba H.", ""),
    ("All of these baked goods are outstanding!", "Patty R.", ""),
    ("It’s beyond words how incredibly delicious the rhubarb cherry sourdough rolls are! Yum yum yum yum 😋", "Kelly S.", ""),
]


class Command(BaseCommand):
    help = "Create the Fed Cove Farm pages and content from the original static site."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Add sample events and an open drop.")

    @transaction.atomic
    def handle(self, *args, demo=False, **options):
        if HomePage.objects.exists():
            raise CommandError("Site already seeded (a HomePage exists). Nothing changed.")

        self.images = {}
        for name, title in IMAGE_TITLES.items():
            self.images[name] = self._image(SEED_DIR / name, title)
        for filename, _caption, alt in PLANTS:
            self.images[filename] = self._image(SEED_DIR / "plants" / filename, alt)

        home = self._pages()
        self._products_and_reviews()
        self._redirects(home)
        if demo:
            self._demo()
        self.stdout.write(self.style.SUCCESS("Seeded. Log in at /admin/ to edit."))

    def _image(self, path, title):
        existing = Image.objects.filter(title=title, file__contains=path.stem).first()
        if existing:
            return existing
        with path.open("rb") as f:
            return Image.objects.create(title=title, file=ImageFile(f, name=path.name))

    def _publish(self, parent, page, live=True):
        parent.add_child(instance=page)
        revision = page.save_revision()
        if live:
            revision.publish()
        else:
            page.unpublish()
        return page

    def _pages(self):
        root = Page.get_first_root_node()
        img = self.images
        home = HomePage(
            title="Home",
            slug="fed-cove-home",
            hero_image=img["fed-cove-farm-01.jpg"],
            hero_eyebrow="Cowee, North Carolina",
            hero_title="From our family to yours.",
            hero_text="As eighth-generation stewards of land in the scenic mountains of North Carolina, we're dedicated to delivering top-tier products — from landscape perennials to delectable baked goods.",
            card_heading="This way to the bakery.",
            card_button_label="Order Now",
            follow_text="The latest from the greenhouse, the market table, and the kitchen.",
        )
        root.add_child(instance=home)

        # Point the site at the new home page and remove Wagtail's placeholder page.
        site = Site.objects.filter(is_default_site=True).first()
        if site:
            site.root_page = home
            site.site_name = "Fed Cove Farm and Nursery"
            site.save()
        else:
            site = Site.objects.create(hostname="localhost", root_page=home, is_default_site=True, site_name="Fed Cove Farm and Nursery")
        for page in root.get_children().exclude(pk=home.pk):
            if page.specific_class is Page:
                page.delete()
        home.refresh_from_db()
        home.slug = "home"
        home.save_revision().publish()
        home = HomePage.objects.get(pk=home.pk)  # pick up the new url_path before adding children

        baked = BakedGoodsPage(
            title="Baked Goods",
            slug="baked-goods",
            show_in_menus=True,
            hero_image=img["artisan-bread.jpg"],
            hero_eyebrow="Baked Goods",
            hero_title="From our kitchen to yours.",
            hero_text="Limited-quantity homemade goods baked fresh each week. Ordered ahead, picked up fresh.",
            card_heading="See what we’re baking.",
            menu_text="Availability rotates with the season and each week’s drop — order ahead to see what’s open right now.",
        )
        self._publish(home, baked)

        landscaping = LandscapingPage(
            title="Landscaping",
            slug="landscaping",
            show_in_menus=True,
            hero_image=img["fed-cove-farm-01.jpg"],
            hero_eyebrow="Landscape Perennials",
            hero_title="From our farm to you.",
            hero_text="Landscaping perennials — ground cover, flowering, and animal-resistant varieties, available seasonally.",
            card_heading="Drop us a line, we don’t bite.",
            card_button_label="Request a Quote",
            intro_text="Ground cover, flowering, and animal-resistant varieties selected to hold up to Western North Carolina’s slopes, shade, and deer pressure.",
            notice="Reach out via Instagram for current availability — stock changes with the season.",
        )
        landscaping.gallery_images = [
            LandscapingGalleryImage(image=img[f], caption=caption) for f, caption, _alt in PLANTS
        ]
        self._publish(home, landscaping)

        events = EventsPage(
            title="Calendar",
            slug="calendar",
            show_in_menus=True,
            hero_image=img["fed-cove-farm-01.jpg"],
            hero_eyebrow="Farmers’ Markets & Events",
            hero_title="Come see us in our natural habitat.",
            hero_text="Western North Carolina is our home. Come see what we have to offer at one of our region’s many local farmers’ markets.",
        )
        events.locations = [
            EventLocation(name="Cowee Farmers’ Market", address="51 Cowee School Drive, Franklin, NC"),
            EventLocation(name="Highlands Farmers’ Market", address="545 Pierson Drive, Highlands, NC"),
        ]
        self._publish(home, events)

        contact = ContactPage(
            title="Contact",
            slug="contact",
            show_in_menus=True,
            hero_image=img["fed-cove-farm-01.jpg"],
            hero_eyebrow="Get In Touch",
            hero_title="Send us a message",
            hero_text="Questions about availability, custom orders, or where to find us next? We’d love to hear from you.",
            thank_you_text="<p>Thanks for reaching out — we’ll get back to you soon.</p>",
            to_address=settings.FARM_NOTIFY_EMAIL,
            from_address="hello@fedcove.farm",
            subject="New inquiry from the Fed Cove Farm website",
        )
        contact.form_fields = [
            ContactFormField(label="Name", field_type="singleline", required=True, sort_order=0),
            ContactFormField(label="Email", field_type="email", required=True, sort_order=1),
            ContactFormField(label="Phone", field_type="singleline", required=False, sort_order=2),
            ContactFormField(label="Message", field_type="multiline", required=True, sort_order=3),
        ]
        self._publish(home, contact)

        more = StandardPage(
            title="More",
            slug="more",
            hero_image=img["fed-cove-farm-01.jpg"],
            hero_eyebrow="More",
            hero_title="Occasional offerings.",
            hero_text="Seasonal extras from the farm, when we have them.",
            empty_message="Hmmm, nothing extra going on right now. We promise this page isn’t broken — check back later.",
        )
        self._publish(home, more)
        for title, slug, eyebrow, headline, text in [
            ("Flowers", "flowers", "Flowers", "From our garden to you.",
             "Beautiful bouquets and arrangements — available seasonally at our farmers’ market stands."),
            ("Vegetables", "vegetables", "Vegetables", "From our fields to your table.",
             "Seasonal, farm-grown vegetables raised in the same mountain soil our family has tended for eight generations. Look for us at the Cowee and Highlands farmers’ markets."),
        ]:
            # Drafts: publish them from the admin when they're in season.
            self._publish(
                more,
                StandardPage(title=title, slug=slug, hero_image=img["fed-cove-farm-01.jpg"], hero_eyebrow=eyebrow,
                             hero_title=headline, hero_text=text),
                live=False,
            )

        home.tiles = [
            HomeTile(title="Landscape Perennials", image=img["fed-cove-farm-03.jpg"], link_page=landscaping, sort_order=0),
            HomeTile(title="Baked Goods", image=img["sourdough.jpg"], link_page=baked, sort_order=1),
        ]
        home.save_revision().publish()

        farm = FarmSettings.for_site(site)
        farm.more_page = more
        farm.save()
        return home

    def _products_and_reviews(self):
        for i, (name, label, description, image) in enumerate(PRODUCTS):
            Product.objects.create(name=name, label=label, description=description, image=self.images[image], sort_order=i)
        for i, (quote, name, detail) in enumerate(REVIEWS):
            Review.objects.create(quote=quote, name=name, detail=detail, sort_order=i)

    def _redirects(self, home):
        targets = {
            "/index.html": home,
            "/baked-goods.html": BakedGoodsPage.objects.get(),
            "/landscaping.html": LandscapingPage.objects.get(),
            "/contact.html": ContactPage.objects.get(),
            "/market-schedule.html": EventsPage.objects.get(),
            "/more.html": StandardPage.objects.get(slug="more"),
            "/flowers.html": StandardPage.objects.get(slug="more"),
            "/vegetables.html": StandardPage.objects.get(slug="more"),
        }
        for old_path, page in targets.items():
            Redirect.add_redirect(old_path, redirect_to=page, is_permanent=True)

    def _demo(self):
        tz = timezone.get_current_timezone()
        today = timezone.localdate()

        def next_weekday(weekday, weeks=0):
            return today + timedelta(days=(weekday - today.weekday()) % 7 + 7 * weeks)

        for w in range(3):
            tue = next_weekday(1, w)
            Event.objects.create(
                title="[Sample] Cowee Farmers’ Market",
                start=datetime.combine(tue, time(15, 30), tz),
                end=datetime.combine(tue, time(19, 0), tz),
                location="51 Cowee School Drive, Franklin, NC",
                description="Sourdough, scones, and fall perennials.",
            )
        sat = next_weekday(5)
        Event.objects.create(
            title="[Sample] Highlands Farmers’ Market",
            start=datetime.combine(sat, time(9, 0), tz),
            end=datetime.combine(sat, time(12, 0), tz),
            location="545 Pierson Drive, Highlands, NC",
        )
        Event.objects.create(
            title="[Sample] Fall plant sale at the farm",
            start=datetime.combine(next_weekday(5, 2), time.min, tz),
            all_day=True,
            location="Fed Cove Farm, Cowee, NC",
        )

        now = timezone.now()
        drop = Drop.objects.create(
            title="[Sample] Saturday Market Bake",
            description="A sample drop so you can try ordering. Delete it under Bakery → Drops.",
            opens_at=now - timedelta(hours=1),
            closes_at=max(datetime.combine(sat - timedelta(days=2), time(20, 0), tz), now + timedelta(days=2)),
            pickup_info="Pick up at our booth, or at the farm stand.",
        )
        sample_prices = {"Sourdough Loaf": "10", "Sourdough Loaf (Sandwich)": "10", "Scones": "14", "Blueberry Muffins": "15", "Artisan Focaccia": "12", "Sourwood Honey": "18"}
        for i, product in enumerate(Product.objects.all()):
            DropItem.objects.create(
                drop=drop, product=product, price=Decimal(sample_prices.get(product.name, "10")),
                quantity=3 if product.name == "Scones" else 20, max_per_order=4, sort_order=i,
            )
        PickupSlot.objects.create(drop=drop, label=f"{sat:%a %b} {sat.day}, 9am–12pm · Highlands Farmers’ Market", sort_order=0)
        PickupSlot.objects.create(drop=drop, label=f"{sat:%a %b} {sat.day}, 1–4pm · Farm stand (Cowee)", capacity=10, sort_order=1)
