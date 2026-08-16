# Fed Cove Farm and Nursery — website

Static site recreating the Google Sites page, ready for GitHub Pages (no build step).

## Files
- `index.html`, `landscaping.html`, `baked-goods.html`, `contact.html`, `market-schedule.html`, `more.html`
- `css/style.css` — all styling
- `js/main.js` — footer year + testimonial carousel
- `img/` — put your three images here (see `img/README.txt`)

## Publish on GitHub Pages
1. Create a new GitHub repo and push these files to the root (or to a `docs/` folder).
2. Repo → **Settings → Pages** → Source: deploy from branch → pick `main` and `/ (root)` (or `/docs`).
3. Save. Your site will be live at `https://<username>.github.io/<repo-name>/` in a minute or two.

## Notes
- **Images**: currently hotlinked from Google's `lh3.googleusercontent.com` CDN (your original site photos). This works today but Google can change/expire those URLs without notice. For a durable site, download the photos and put them in an `img/` folder, then update the `src` paths in `css/style.css`... actually in the HTML files' `<img>` tags.
- **Google Map**: embedded via the same iframe URL your Google Site used.
- **Vegetables page copy**: your original Google Site had the *Landscaping* paragraph duplicated on the Vegetables page (likely a copy/paste slip). I rewrote it with a Vegetables-appropriate blurb — edit `vegetables.html` if you'd like different wording.
- **Baked Goods "Order" links** point to your existing Square store.

## What's new since the last version
- **Contact page** (`contact.html`) — phone, email, and location as tap-to-call / tap-to-email buttons, plus links to Facebook, Instagram, and Hotplate. No backend form (this site has no server), so contact is handled via `tel:`/`mailto:` links instead of a submit-able form.
- **Facebook feed** — embedded on the home page ("Follow Along") via Meta's official Page Plugin (an iframe, no API key needed). Meta occasionally throttles or blocks these embeds for logged-out visitors; if it shows blank, there's a "View on Facebook" fallback button right below it.
- **Hotplate link** — I found via search that the farm also takes pre-orders through Hotplate (`hotplate.com/fedcovefarmandnursery`), so I added an "Order Ahead" button on the home and contact pages. Worth double-checking with them whether Square or Hotplate is their current preferred ordering platform — easy to remove either one in `build.py`/the HTML if not needed.
- Nav and footer updated on all 7 pages to include Contact, plus a Facebook icon next to Instagram in the footer.

## Contact info used
Phone `(828) 371-8018`, email `fedcove.farm.nursery@gmail.com`, Facebook and Instagram — all pulled from their existing public Facebook/Hotplate listings. Worth confirming these are still current before publishing.

## Baked Goods page — weekly editing

**"This Week's Drop"** — edit the `DROP` block near the top of `baked-goods.html` (search for `EDIT THIS EVERY WEEK`). It's plain text: status (OPEN/CLOSED), the ordering window, pickup info, and the item list. Save the file and refresh the browser — no build step needed since these are plain HTML files.

**Reviews carousel** — same idea, search `EDIT THIS AS NEW REVIEWS COME IN`. There are three quote blocks; two are placeholders clearly marked `PLACEHOLDER — replace me`. Copy real reviews from Hotplate's Customers → Reviews tab and swap the placeholder text/name in. The carousel auto-fades between quotes every 6 seconds and has click-able dots; it pauses on hover and won't auto-rotate for visitors with reduced-motion preferences turned on.

Note: I couldn't find a way to embed Hotplate's live reviews or drop calendar directly (they don't offer a public embed/API for it), so both of the above are manually updated instead of auto-syncing. It's a 30-second edit each week but won't ever show a broken embed.

If you regenerated the site using `build.py` at some point (optional — the plain HTML files work fine without it), the same `DROP` and `TESTIMONIALS` variables live there instead, near the top of the "BAKED GOODS" section.

## Nav restructure (latest round)
- Primary nav is now **Home, Baked Goods, Landscaping, Contact** — the four things that matter day-to-day.
- A separate **"More"** button (visually inverted — solid dark pill instead of a plain nav link) sits apart from the rest of the nav. It goes to `more.html`, a new "leftovers" page with:
  - A real, working link to the **Farmers' Market Schedule** (unchanged, still fully functional — it just moved out of primary nav)
  - Placeholder cards for **Flowers** (seasonal) and **Vegetables** (rare, farmers'-market only) — dashed borders, no photos yet, just a label and a short note. Swap these for real `category-card` blocks (see `landscaping.html` for the markup pattern) whenever it's the season to bring them back.
- Vegetables and Flowers as standalone pages are removed entirely, per your request — that content now only exists as the two placeholders above.
- The homepage "What We Do" grid now shows 3 tiles: Landscaping, Baked Goods, and a dark "More From The Farm" tile linking to the same leftovers page — so it's reachable from two spots.

## Hero card consistency
Every hero card across all pages now shares the same minimum height and vertical position, so clicking between pages feels like one continuous card sliding its content rather than a resize. The homepage's second "You know why you're here" card matches the height of the main card next to it. If a page's hero paragraph runs unusually long it can still grow taller than the rest — the fixed height is a floor, not a hard cap.

## Page-load motion
The header fades in and the hero card(s) fade + slide up slightly on every page load — quick (under a second), consistent site-wide, and automatically disabled for visitors with "reduce motion" turned on in their OS.

## Images
Local image paths are wired in per your folder:
- Hero banner: `img/fed-cove-farm-01.jpg`
- Full logo (used as the social-share preview image): `img/fed-cove-logo-large.png`
- Small icon (nav bar + browser favicon): `img/fed-cove-icon.jpg`

The other photos (perennials, market locations, baked goods teaser image on the old grid) are still hotlinked from Google's CDN from the original site — swap those in too whenever convenient, same as noted earlier in this README.

## Mobile nav (side drawer)
Below 820px window width, the top nav and "More" pill disappear and a hamburger button appears instead. Tapping it slides in a right-hand drawer with all nav links (including More) stacked vertically, plus a dimmed backdrop behind it. It closes on: tapping the backdrop, the × button, any link, the Escape key, or resizing the window back past 820px. This is a pure width-based breakpoint (matches the existing responsive breakpoint used elsewhere on the site) — it reacts to how wide the browser window is, not the device's physical orientation, so resizing a desktop browser window narrow enough will trigger it too.
