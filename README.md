# Fed Cove Farm and Nursery — website

Django + [Wagtail](https://wagtail.org) site. The farm logs in at `/admin/` to edit wording, photos,
events, weekly bakery drops, and reviews — from a phone or a computer.

## Run it

```sh
cp .env.example .env        # then fill in DJANGO_SECRET_KEY, hosts, etc.
docker compose up -d --build
docker compose exec web python manage.py seed_site          # first time only (--demo adds sample events + a drop)
docker compose exec web python manage.py createsuperuser
```

Site: `http://<host>:8020/` · Admin: `/admin/`. Two containers run: `web` (gunicorn) and
`worker` (pulls Google Calendar every `CALENDAR_SYNC_MINUTES`, refreshes the Hotplate menu every
`HOTPLATE_SYNC_MINUTES`, and Instagram/Facebook posts every `SOCIAL_SYNC_MINUTES`). Behind your reverse
proxy, set `DJANGO_BEHIND_PROXY=true` and add the public hostname to `DJANGO_ALLOWED_HOSTS` /
`DJANGO_CSRF_TRUSTED_ORIGINS` (e.g. `https://fedcove.farm`). Data lives in `./data`
(SQLite) and `./media` (uploaded photos) — back those two folders up.

After changing models: `docker compose run --rm -u $(id -u) -v "$PWD":/app web python manage.py makemigrations`.

## Layout

| Path | What |
| --- | --- |
| `home/` | Page types (home, baked goods, landscaping, calendar, contact, flexible pages), farm settings, reviews, `seed_site` |
| `events/` | Events, Google Calendar sync (`google_calendar.py`), month grid, `/api/events/` |
| `hotplate/` | Reads the farm's Hotplate drops and shows them on the Baked Goods page, `/api/hotplate/` |
| `social/` | Latest Instagram/Facebook posts for the home page (images stored locally) |
| `orders/` | On-site drops (alternative to Hotplate): products, pickup options, orders, prep lists |
| `templates/` | All HTML; `base.html` has the header/nav/footer |
| `fedcove/static/` | CSS, JS, hero video, logo |
| `seed/img/` | Original photos, imported into the image library by `seed_site` |

## What the farm edits (admin)

- **Pages** — every page's headline, text, and photos. Pages ticked "Show in menus" appear in the nav.
  The **More** page lists any published pages under it (Flowers/Vegetables are drafts there — publish when in season).
- **Events** — add/edit events (also synced with Google Calendar, below). **Calendar sync** shows status + "Sync now".
- **Bakery → Drops** — a weekly ordering window: items (with how many you're making), pickup options, open/close times.
  **Bakery → Orders** to mark ready/picked up; **Prep lists** totals what to bake per drop.
- **Bakery → Products / Reviews** — the menu and the reviews carousel (drag to reorder).
- **Settings → Farm settings** — phone, email, social links, and **Ordering**:
  *Hotplate* (default) shows their Hotplate drops on the Baked Goods page; *on this site* uses Bakery → Drops;
  *link* just sends order buttons to the outside link.
- **Hotplate** — when the menu was last updated, any errors, and a "Refresh now" button.
- **Social feed** (full admins only) — connect Instagram (and optionally Facebook) by pasting a token;
  step-by-step instructions are on that page.
- **Forms** — contact-form messages (also emailed).

## Google Calendar

Set `GOOGLE_CALENDAR_ICS_URL` in `.env` to the farm calendar's **Secret address in iCal format**
(Google Calendar → Settings → the calendar → Integrate calendar) and restart. Events added in Google
Calendar — e.g. from a phone — appear on the site within `CALENDAR_SYNC_MINUTES`. Events added in the
admin show on the site only. Events marked **Private** in Google never appear; repeating events are expanded.

Two-way sync is also supported (`GOOGLE_CALENDAR_ID` + a service-account key in `./secrets/`; see
`events/google_calendar.py`), but isn't set up or tested against a real account yet.

## Hotplate

Hotplate has no official API. Its storefront loads data from public, read-only endpoints at
`bets.hotplate.com/trpc/`; `hotplate/client.py` calls those (never cart or payment endpoints):
open drops + their menus and stock every few minutes, and the last few past drops (fetched once each,
then reused). The result is stored in the database, and a failed fetch keeps the last good menu.
Because it's undocumented it can change without notice — `manage.py test hotplate` covers the parsing
rules, and the admin Hotplate page shows if fetching starts failing. Customers always check out on Hotplate.

Respects the seller's Hotplate settings: private/draft drops are skipped, stock counts ("Only 2 left")
show only if they display counts on Hotplate, and menus hidden before opening stay hidden.

`manage.py refresh_hotplate --chef fortmillsourdough` is handy for testing with a seller that has drops open.

## Social feed

Instagram uses Meta's *Instagram API with Instagram Login* (needs a Business or Creator account, no
Facebook Page or app review). The token is pasted in admin → Social feed and renewed weekly by the worker
(tokens last 60 days; if it ever lapses — e.g. after an Instagram password change — the page shows the
error and the site keeps the posts it has). Facebook is optional: a Page access token + Page ID.
Facebook posts that duplicate an Instagram post are hidden. Images are downloaded and served from `/media/`.

## API

- `GET /api/events/?from=YYYY-MM-DD&to=YYYY-MM-DD` — events (defaults to upcoming)
- `GET /api/hotplate/` — stored Hotplate drops (live + recent past)
- `GET /api/drops/current/` — the featured on-site drop with stock remaining
- `GET /api/v2/pages/`, `/api/v2/images/` — Wagtail content API

## Old URLs

`seed_site` adds permanent redirects from the old static pages (`/baked-goods.html` etc.) to the new ones.
The old static site is on `main` in git history.
