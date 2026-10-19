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
`calendar-sync` (pulls Google Calendar every `CALENDAR_SYNC_MINUTES`). Data lives in `./data`
(SQLite) and `./media` (uploaded photos) — back those two folders up.

After changing models: `docker compose run --rm -u $(id -u) -v "$PWD":/app web python manage.py makemigrations`.

## Layout

| Path | What |
| --- | --- |
| `home/` | Page types (home, baked goods, landscaping, calendar, contact, flexible pages), farm settings, reviews, `seed_site` |
| `events/` | Events, Google Calendar sync (`google_calendar.py`), month grid, `/api/events/` |
| `orders/` | Products, weekly drops, pickup options, orders, prep lists, `/api/drops/current/` |
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
- **Settings → Farm settings** — phone, email, social links, and the ordering switch:
  *Take orders on this site* on = the drop's order form; off = order buttons go to the outside link (Hotplate).
- **Forms** — contact-form messages (also emailed).

## Google Calendar

Set `GOOGLE_CALENDAR_ICS_URL` in `.env` to the farm calendar's **Secret address in iCal format**
(Google Calendar → Settings → the calendar → Integrate calendar) and restart. Events added in Google
Calendar — e.g. from a phone — appear on the site within `CALENDAR_SYNC_MINUTES`. Events added in the
admin show on the site only. Events marked **Private** in Google never appear; repeating events are expanded.

Two-way sync is also supported (`GOOGLE_CALENDAR_ID` + a service-account key in `./secrets/`; see
`events/google_calendar.py`), but isn't set up or tested against a real account yet.

## API

- `GET /api/events/?from=YYYY-MM-DD&to=YYYY-MM-DD` — events (defaults to upcoming)
- `GET /api/drops/current/` — the featured drop with stock remaining
- `GET /api/v2/pages/`, `/api/v2/images/` — Wagtail content API

## Old URLs

`seed_site` adds permanent redirects from the old static pages (`/baked-goods.html` etc.) to the new ones.
The old static site is on `main` in git history.
