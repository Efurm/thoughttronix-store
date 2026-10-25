# Implementation Plan: The ThoughtTronix Store — Product Reviews

*Companion to `prd/product-reviews.md`. The PRD owns the requirements; this plan owns the sequence. Where a task says "per the PRD," the PRD's wording is authoritative. Do not improvise alternatives. The suite must be green at every phase boundary.*

## Durable Decisions

These hold across every phase.

- **Owning app:** a new `reviews` app (URL namespace `reviews`), laid out like the existing apps: model, manager, form, views, `templates/reviews/` and `templates/reviews/partials/_<name>.html`, tests. No new deep module; the rules live on the model and its manager, so "exactly four deep modules" stands.
- **Model:** `Review` with `user` (FK to the user model), `product` (FK to `Product`, `CASCADE`), `rating` (small positive integer, 1–5 by validators **and** a check constraint, like `Coupon.percent_off`), `comment` (plain text), `created_at`, `updated_at`, `updated_by` (nullable FK to the user model, `SET_NULL`, like `Coupon`). Unique constraint on (`user`, `product`). Default ordering newest first. One migration.
- **Rules (on the model/manager, used by templates and views alike):**
  - *can write:* signed in, not staff, has an `OrderItem` for the product on an order whose status is not `Order.Status.CANCELLED`, and no existing review of it. One read-only query.
  - *can change:* the author, or any staff user.
  - *summary:* average rating (one decimal) and count, from one aggregate query.
  - *edited* / *edited by staff:* computed from `updated_at` vs `created_at` and from `updated_by.is_staff`.
  - Product availability and later cancellation have no effect. SoulSear and Defense products get no special case.
- **URLs (pks, per the URL conventions):**
  - `POST /reviews/product/<pk>/`: create
  - `GET /reviews/product/<pk>/page/<n>/`: show more
  - `GET /reviews/<pk>/`: a single card (Cancel restores it)
  - `GET`/`POST /reviews/<pk>/edit/`: edit form / save edit
  - `POST /reviews/<pk>/delete/`: delete
- **Authorization:** create, edit, cancel and delete require login, as the cart endpoints do; signed-out requests redirect to `accounts:login`. The view itself re-runs *can write* or *can change* and returns **403** on failure, whatever the page showed. **Show more is public**: story 3 is for signed-out shoppers too, and it only reads.
- **HTMX shape:** every review card renders from one partial with a unique element id, and the summary renders from another partial with a fixed id. Every create, edit and delete response carries the summary as an out-of-band swap, the same way the cart badge's `oob_badge` works. Only Tailwind and DaisyUI classes are used, and there's no JavaScript beyond HTMX.

---

## Phase 0 — Branch Setup

**Goal:** Work starts from a `main` that contains the finished Account Security Center.

**Tasks:**
1. Merge `feature/account-security` into `main` via a GitHub pull request.
2. Pull `main` locally and create `feature/product-reviews` from it. Bring along (and commit first) `prd/product-reviews.md` and this plan.

**Verification.** *Automated:* `uv run pytest` green on the new branch before any change. *Manual:* `git log` shows the account-security commits on the branch.

**Out of bounds:** any code change.

---

## Phase 1 — Tracer Bullet: A Review, Every Layer (Read-Only)

**User stories:** 1, 2, 4, 5, 6, 12, 16–24 (at the rule level), 20, 27, 28, 29

**Goal:** A review that exists in the database appears on its product's page, under a correct summary, and every rule that decides who may write or change one is proven. Nothing is writable from the page yet.

**Tasks:**
1. Create the `reviews` app and register it. Add the `Review` model, constraints and ordering as in Durable Decisions, and generate the one migration.
2. Add the rules to the manager and model: *can write*, *can change*, *summary*, *edited*, *edited by staff*. Each public method gets a docstring.
3. In `conftest.py`, add a plain fixture that builds an order for a given user, product and status. It returns a builder, as `make_image` does. Add a SoulSear (Defense) product fixture if no existing fixture fits.
4. Extend `ProductDetailView`'s context per the PRD: the summary, the viewer's own review, whether they can write, the first 10 *other* reviews (excluding the viewer's own), and whether more exist.
5. Add the Reviews section to `templates/products/detail.html`, below the product details:
   - **Summary:** "★ 4.3 · 12 reviews" or a no-reviews line.
   - **Your-review slot**, in one of these states: the viewer's own card; "Sign in to leave a review" linking to login with `next` back to this product; "Only customers who've bought the [product] can review it"; or nothing for staff. In this phase the *can write* state shows a placeholder line. The form arrives in Phase 2.
   - **Other reviews:** newest first, with a designed empty state.
6. Add the review card partial: stars, reviewer name, date, and the comment rendered escaped with line breaks kept (`linebreaksbr`). It also shows "Edited" or "Edited by ThoughtTronix staff" when that applies.
7. Register `Review` in the Django admin. The list shows product, user, rating and date. Search covers product name and username, and there's a rating filter. Every field is read-only. Adding is disabled, because an admin-made review would skip the purchase rule. Delete and bulk delete stay allowed.

**Verification.** *Automated:*
- **Model and constraints:** rating 0 and 6 are rejected by the database check; a second (user, product) review is rejected by the unique constraint; deleting a product deletes its reviews.
- **Summary:** the summary is correct for several reviews and for none.
- **Eligibility:** Placed, Shipped and Delivered allow a review and Cancelled alone does not; no order means no review; staff with an order can't review; an existing review blocks a second one, and deleting the row frees the slot; an unavailable product is reviewable; a review survives its order being cancelled.
- **SoulSear:** the ordering account can review it, and a different account can't.
- **Can change:** true for the author and for staff, false for another customer.
- **Edit marking:** the edited and staff-edited flags are correct.
- **Detail page:** the page renders each slot state, the summary, newest-first order, the empty state, escaped comments with `<br>`, and the `next` parameter on the sign-in link.
- **Admin:** all fields are read-only, adding is forbidden, and delete is allowed.

*Manual:* in `manage.py shell`, create two reviews on Seraphine (one of them by `customer` on a placed order). Then view the page signed out, as `customer`, as another customer, and as `employee`. Browse, search and bulk-delete them in `/admin/`.

**Out of bounds:** forms, write endpoints, show more, the seed.

---

## Phase 2 — Create

**User stories:** 7, 8, 9, 10, 11, 16, 17, 18, 21, 23, 24

**Goal:** An eligible customer writes a review on the product page and sees it appear in their slot, along with an updated summary, without the page reloading.

**Tasks:**
1. Add one `ModelForm` (rating, comment) for create and edit. Rating uses DaisyUI's radio-button star rating. The form trims the comment and enforces 10–2,000 characters with its own messages.
2. Add the review form partial: field errors render beside each field, and it posts with HTMX to the create URL, swapping the slot.
3. Add the create view, login required. It re-runs *can write* and returns 403 on failure. Valid input sets `user` and `product`, saves, and returns the new card plus the out-of-band summary. Invalid input returns the form partial with its errors.
4. Replace the Phase 1 placeholder with the form.

**Verification.** *Automated:*
- **Form:** 9 characters, whitespace only, and 10 characters padded with spaces to look longer are rejected; exactly 10 and exactly 2,000 are accepted; 2,001 is rejected.
- **Create endpoint:** signed-out requests redirect to login; an ineligible customer gets 403, and so does a SoulSear next-of-kin account (no order of its own), staff, and a customer who already has a review; a valid post creates a review owned by the requester and its response contains the card and the out-of-band summary; an invalid post returns errors without creating anything.

*Manual:* as `customer`, submit a 5-character comment and see the error beside the field. Then submit a valid review and watch the slot and summary update in place.

**Out of bounds:** edit, delete, show more.

---

## Phase 3 — Edit

**User stories:** 5, 13, 22, 25, 26

**Goal:** The author or any staff member edits a review in place. Staff edits are marked publicly.

**Tasks:**
1. Add Edit controls to the card, shown when *can change* is true. That means the author's own card in the slot, and every card for staff.
2. The edit view (login required, *can change* or 403) works as follows:
   - **GET** swaps the card for the pre-filled form in the same spot.
   - **POST** validates, sets `updated_by` to the acting user, and returns the updated card plus the out-of-band summary. Errors re-render the form in place.
3. Add the single-card view (login required, *can change* or 403). Cancel uses it to restore the original card.

**Verification.** *Automated:*
- **Login:** signed-out requests to edit and cancel redirect to login.
- **403s:** another customer gets 403 on the edit GET, the edit POST and cancel.
- **Customer edit:** the author's edit saves, marks the review edited but not staff-edited, and the response carries the out-of-band summary.
- **Staff edit:** staff can edit any review, `updated_by` is set to them, and the card shows "Edited by ThoughtTronix staff".
- **Invalid edit:** the review stays unchanged.

*Manual:* as `customer`, edit your review, then cancel a second edit and see the original card. As `employee`, edit it and see the staff note, both on the page and signed out.

**Out of bounds:** delete, show more.

---

## Phase 4 — Delete

**User stories:** 14, 15, 22, 25

**Goal:** The author or any staff member deletes a review after confirming, and an author can then write a new one.

**Tasks:**
1. Add Delete controls beside Edit, using `hx-confirm` (the browser's native dialog, per the PRD).
2. The delete view (POST, login required, *can change* or 403) deletes the row and responds with the out-of-band summary plus one of two things:
   - **The author's own delete:** the slot re-rendered. That is the form if they can still write, or the "only buyers" line if their order has since been cancelled.
   - **A staff delete of someone else's review:** an empty swap that removes that card.

**Verification.** *Automated:*
- **Login:** a signed-out request redirects to login.
- **Non-owner:** another customer gets 403, and the review stays.
- **Author:** the author's delete removes the row, the response contains the form and the summary, and a new review can then be created.
- **Staff:** a staff delete removes any review, and the response contains no form.
- **Summary:** every response carries the out-of-band summary.

*Manual:* as `customer`, delete your review, cancel the browser prompt once, then confirm. The form returns, and you write a new review. As `employee`, delete another customer's review and watch only that card disappear.

**Out of bounds:** show more, the seed.

---

## Phase 5 — Show More

**User stories:** 3

**Goal:** A product with many reviews loads them 10 at a time, appended in place.

**Tasks:**
1. Add the show-more view, which is public. It returns the next 10 other reviews newest first, excluding the viewer's own, computed the same way as the detail page's first batch. When more remain, the batch ends with its own button.
2. Add the button below the list on the detail page, shown when more exist. It fetches page 2 and replaces itself with the returned batch, so reviews append below and the scroll position holds.

**Verification.** *Automated:* with 25 reviews built in the test, the detail page shows 10 newest-first reviews and a button. Page 2 returns the next 10 and a button, page 3 returns the last 5 with no button, and an out-of-range page returns no button. When a customer has their own review, it never appears in any page. A product with exactly 10 reviews shows no button.

*Manual:* in the shell, add 25 reviews to one product. Scroll down, click Show more twice, and confirm the page never navigates.

**Out of bounds:** the seed (per the PRD, it cannot produce 11 reviews).

---

## Phase 6 — Demo Reviews in the Seed

**User stories:** shows 1, 2, 5 and 12 with real data

**Goal:** A fresh seed shows a lived-in Reviews section in the brand voice, and leaves the dashboard as it was.

**Tasks:**
1. The wipe step deletes reviews along with the other domain data.
2. After the orders are created, pick a few products and give each 2–6 brand-voice reviews. Reviewers are chosen from background customers who actually bought the product on non-cancelled orders, not hard-coded, per the PRD.
3. The `customer` demo login gets one reviewed purchase and at least one purchased-but-unreviewed product. If no unreviewed purchase exists, write the review on one of `customer`'s purchases and leave another unreviewed.
4. Add no customers and no SoulSear or Defense orders, and leave the revenue data untouched. Include reviews in the seed's summary line.

**Verification.** *Automated:* the existing suite stays green (tests never invoke the seed, per CLAUDE.md). *Manual:*
- **Seed twice:** run `seed` twice and get the same review count each time.
- **As `customer`:** one product page shows your review card, and another you bought shows the form.
- **Dashboard:** the figures match the pre-feature seed.
- **Admin:** the seeded reviews are listed.

**Out of bounds:** reviews reaching 11 on any product, SoulSear demo data.

---

## Phase 7 — Documentation and Polish

**Goal:** The repository describes the feature as built.

**Tasks:**
1. `CLAUDE.md`: add a `reviews/` entry to the project layout (reviews, their rules on the model and manager, inline staff moderation). The "exactly four deep modules" line stays as it is.
2. README: mention product reviews and that the seed includes demo reviews.
3. Append a PROMPTS.md entry for this session (append only; never rewrite earlier entries).
4. Full `ruff check`, `ruff format`, and `pytest` pass.

**Verification.** *Automated:* full suite green, Ruff clean, CI passes. *Manual:* a fresh clone, README steps only, then seed, sign in as `customer`, and write, edit and delete a review.

**Out of bounds:** nothing new. This phase adds no features.
