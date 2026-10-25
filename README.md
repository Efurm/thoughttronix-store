# The ThoughtTronix Store

*Your Thoughts, Our Business.*

A server-rendered Django 6 storefront and back office for the world's most
beloved consumer neural technology: browse the catalog, fill a cart, check
out through a fully validated form, review what you bought, and — if you're
staff — run the store from the back office, analytics dashboard included.

## Getting started

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/). No Node.js —
Tailwind runs as a standalone binary.

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py seed
uv run python manage.py tailwind runserver
```

Then open <http://127.0.0.1:8000/>. From clone to browsing the store, this
takes about two minutes.

The seed also loads marketing's product photos from `product-images/` into
`media/` (generated, gitignored). Staff upload, replace, and remove product
images from each product's edit page in the back office. Uploaded images are
served by the dev server only while `DEBUG` is on, as static files are;
serving them in production is not configured yet.

## Product reviews

Every product page has a Reviews section: the average rating and count,
then reviews newest first, ten at a time with a Show more button.
Customers who bought a product (on any order that wasn't cancelled) can
leave one review of it — 1 to 5 stars and a 10–2,000 character comment —
and edit or delete it in place. Staff can edit or delete any review right
on the page, and a staff edit is marked "Edited by ThoughtTronix staff".
The seed includes a few demo reviews, written by customers who bought the
products; `customer` has reviewed MindSync and can review their other
purchases.

## Demo logins

The `seed` command creates a fixed demo world — the same one every run:

| Username   | Password      | Who they are                                                  |
| ---------- | ------------- | ------------------------------------------------------------- |
| `admin`    | `admin123`    | Superuser: everything below, plus the Django admin at `/admin/` |
| `employee` | `employee123` | Staff: the back office (products, orders, dashboard)           |
| `customer` | `customer123` | A customer with order history, a live cart, and one review     |

## Commands

| Command                                     | What it does                             |
| ------------------------------------------- | ---------------------------------------- |
| `uv sync`                                    | Install dependencies                     |
| `uv run python manage.py migrate`            | Apply database migrations                |
| `uv run python manage.py seed`               | Reset the database to the demo world (destructive, idempotent) |
| `uv run python manage.py tailwind runserver` | Dev server + Tailwind watch              |
| `uv run python manage.py tailwind build`     | Compile production CSS                   |
| `uv run pytest`                              | Run the test suite                       |
| `uv run ruff check .`                        | Lint                                     |
| `uv run ruff format .`                       | Format                                   |

## Repo layout

`config/` is the project package (settings, root URLs); the five apps are
`accounts` (custom user model), `products` (the public catalog and its
back-office CRUD), `orders` (cart, checkout, orders — with the
`place_order` service in `orders/services.py`), `reviews` (product reviews
and their rules), and `dashboard` (staff analytics, with the aggregations
in `dashboard/queries.py`). Project-level
templates live in `templates/`, static sources in `assets/`, marketing's
product photos in `product-images/`. The product
requirements are in `prd/`, the phase-by-phase build plan in `plans/`, and
`PROMPTS.md` is where AI usage on this codebase gets logged.
