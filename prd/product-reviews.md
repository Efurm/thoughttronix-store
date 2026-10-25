# PRD: The ThoughtTronix Store — Product Reviews

*Commissioned by ThoughtTronix Customer Trust. "Your Thoughts, Our Business."*

---

## Problem Statement

A shopper looking at a ThoughtTronix product has only the company's own word to go on: the tagline, the description, and the price. There is no way to hear from people who actually bought the Seraphine Home Hub or lived alongside a MindSync implant, so shoppers can't tell whether the product lives up to its copy.

Customers who did buy something have nowhere to say how it went. Their satisfaction (or warnings) stay private, and the store learns nothing it can act on.

The store also has no way to keep feedback honest. Without a purchase check, anyone could rate a product they've never owned. Without moderation, staff couldn't remove abusive or unsafe content.

## Solution

Every product page gains a **Reviews section**. It shows an average star rating and review count, then the reviews themselves, newest first.

A customer who has **bought a product** (on any order that wasn't cancelled) can leave **one review** of it: a rating from 1 to 5 whole stars and a written comment. They can edit or delete their review at any time. After deleting it, they may write a new one.

Eligibility belongs to the account that placed the order and can't be passed on. A SoulSear owner can review their SoulSear, but their next of kin, using their own accounts, cannot.

Staff can edit or delete **any** review, directly on the product page. When staff change a customer's words, the review says so publicly.

Creating, editing and deleting all happen **in place**: only the affected review and the summary change, so the page never reloads and the customer never loses their place.

## User Stories

**Shopper (signed out or signed in)**

1. As a shopper, I want to see a product's average star rating and number of reviews on its page, so that I can judge it at a glance.
2. As a shopper, I want to read reviews newest first, so that I see current opinions before old ones.
3. As a shopper, I want to load more reviews 10 at a time without leaving the page, so that a popular product's page stays fast and I keep my place.
4. As a shopper, I want a clear message when a product has no reviews yet, so that an empty list doesn't look broken.
5. As a shopper, I want to know when a review was edited, and whether ThoughtTronix staff edited it, so that I can trust the words are the reviewer's own.
6. As a signed-out visitor, I want a "Sign in to leave a review" prompt that returns me to the product after signing in, so that I know how to review and don't lose my place.

**Customer**

7. As a customer who bought a product, I want a review form on its page, so that I can share my experience.
8. As a customer, I want to give a rating of 1 to 5 whole stars, so that my opinion counts toward the average.
9. As a customer, I want to write a comment of 10 to 2,000 characters, with my line breaks kept, so that my review says something useful and stays readable.
10. As a customer, I want clear errors beside the field when my review is invalid, so that I can fix it without starting over.
11. As a customer, I want my new review to appear right away without the page reloading, so that I stay where I am.
12. As a customer, I want my own review shown at the top of the Reviews section, so that I can find it easily.
13. As a customer, I want to edit my review right where it is shown, so that I can update my opinion without losing my place.
14. As a customer, I want to delete my review after a confirmation prompt, so that I can remove it without deleting it by accident.
15. As a customer who deleted my review, I want to be able to write a new one, so that a change of heart isn't permanent.
16. As a customer, I can have only one review per product at a time, so that no one can stack ratings.
17. As a customer, I can review a product as soon as I've ordered it (Placed, Shipped or Delivered), so that I don't have to wait for delivery.
18. As a customer whose order was cancelled, I can't review a product from that order alone, so that reviews come from real buyers.
19. As a customer, my review stays up if my order is cancelled afterwards, so that my words aren't removed without warning.
20. As a customer who hasn't bought a product, I want to be told that only buyers can review it, so that I understand why there's no form.
21. As a customer, I can review a product the store no longer sells (including the recalled SoulSear Mark I) if I bought it, so that past owners can still be heard.
22. As a customer, I cannot edit or delete anyone else's review, so that my review can't be tampered with by other customers.

**SoulSear owner and next of kin**

23. As a SoulSear owner, I can review the SoulSear I bought under the same rules as any product, so that owners are heard.
24. As a SoulSear owner's next of kin, I cannot review a SoulSear bought on someone else's account, so that eligibility stays with the actual buyer.

**Staff**

25. As a staff member, I want Edit and Delete controls on every review on the product page, so that I can moderate where I find problems.
26. As a staff member, I want my edits recorded and marked "Edited by ThoughtTronix staff," so that the store is honest about changing a customer's words.
27. As a staff member, I don't see a review form, so that employees can't rate the company's own products.

**Admin**

28. As an admin, I want to browse, search and filter all reviews in the Django admin and bulk-delete abusive ones, so that I can clean up spam quickly.
29. As an admin, I cannot edit review text in the Django admin, so that every edit goes through the path that records who made it.

## Implementation Decisions

**A new `reviews` app**

- Reviews get their own Django app with its own model, URLs (namespace `reviews`), templates, partials and tests, following the existing app layout. CLAUDE.md's project layout gains an entry for it.
- No new deep module. Permission and summary rules are simple questions about one review or one product, so they live on the model and its manager, as CLAUDE.md prescribes. The "exactly four deep modules" convention stands.

**The `Review` model**

- Fields: `user` (foreign key to the user model), `product` (foreign key to `Product`, `CASCADE`, since a review has no meaning without its product), `rating`, `comment`, `created_at`, `updated_at`, and `updated_by` (nullable foreign key to the user model, `SET_NULL`). This follows the `created_by`/`updated_by` pattern `Coupon` uses.
- `rating` is a small positive integer from 1 to 5, held by validators and by a database check constraint, the same way `Coupon` holds `percent_off`.
- `comment` is plain text, with no HTML or formatting. Templates render it escaped, with line breaks kept.
- A **unique constraint on (user, product)** enforces one review per customer per product at a time, even under simultaneous submissions. Deleting is a real row delete, so it frees the slot.
- Default ordering is newest first.
- The model reports whether it has been edited (`updated_at` meaningfully later than `created_at`) and whether staff made the last edit (`updated_by` is a staff user).

**Rules on the manager and model**

- **Can write:** the user is signed in, is not staff, has an order item for this product on an order whose status is not Cancelled, and has no existing review of it. This is one read-only query against orders, held in a manager method.
- **Can change** (edit or delete): the user wrote the review, or the user is staff.
- **Summary:** the average rating (to one decimal place) and the review count for a product, from one aggregate query.
- Eligibility belongs to the account on the order. There is no next-of-kin, family or account-transfer concept. A different account never inherits a purchase, which is how "next of kin are not eligible" is satisfied. Defense and SoulSear products follow exactly the same rule as every other product, with no special case.
- Product availability (`is_available`) has no effect on reviews. Cancelling an order later leaves its reviews in place.

**Form**

- One `ModelForm` for create and edit with two fields: rating, as DaisyUI's radio-button star rating (no JavaScript), and comment.
- The form owns validation: the comment is trimmed of leading and trailing spaces, then must be 10 to 2,000 characters. Errors render beside the field inside the swapped partial.
- On save, the view sets `user` and `product` on create, and `updated_by` to the acting user on every edit.

**Views and URLs**

- Thin class-based views under the `reviews` namespace: create (by product), edit form, save edit, cancel edit, delete, and "show more" (by product and page). All changes use POST. Following the URL conventions, these endpoints use pks.
- Like the cart endpoints, they require login and return partials only.
- **The server is the gatekeeper.** Every create, edit and delete view re-runs the can-write or can-change rule and returns 403 Forbidden if it fails, whatever the template showed. Templates use the same rule methods to show or hide controls, so the interface and the server can't disagree.
- The product detail view gains the review context: the summary, the viewer's own review (if any), whether they can write one, the first 10 other reviews, and whether more exist.

**Page layout and HTMX behavior**

- The Reviews section sits below the product details on the product detail page and has three parts:
  1. **Summary:** "★ 4.3 · 12 reviews", or a no-reviews line.
  2. **Your review slot**, which shows one of:
     - the form, if you can write a review
     - your own review card with Edit and Delete, if you've written one
     - "Sign in to leave a review", linking to login with a `next` back to this product, if you're signed out
     - "Only customers who've bought the [product] can review it", if you haven't bought it
     - nothing, if you're staff
  3. **Other reviews:** newest first, 10 at a time, excluding the viewer's own review, with a designed empty state.
- Each review renders from its own underscore-prefixed partial with a unique element id, so HTMX swaps only that card.
- **Create:** submitting the form replaces the slot with the new review card.
- **Edit:** Edit swaps the card for a pre-filled form in the same spot. Save swaps the updated card back, and Cancel restores the original card.
- **Delete:** HTMX's `hx-confirm` asks the browser's native "Are you sure?" first. A customer's own delete brings the form back in their slot. A staff delete of someone else's review removes that card.
- **Summary refresh:** every create, edit and delete response also sends the summary as an out-of-band swap, the same technique the cart badge uses, so the average and count are always current.
- **Show more:** a button below the list fetches the next 10 and adds them below the existing reviews, and the new batch carries its own button if more remain. The button disappears on the last page. The page never navigates and the scroll position is kept.
- Tailwind and DaisyUI classes only. No JavaScript beyond HTMX.

**Django admin**

- Reviews are registered for browsing, with product, user, rating and date shown, search by product name and username, and a filter by rating.
- All fields are **read-only** in the admin. Delete (including bulk delete) is allowed. This follows the product-image precedent: the only way to change a review's words is the path that records `updated_by` and runs the form's validation.

**Data and seed**

- One migration creates the `Review` table with its check and unique constraints.
- The seed stays small. A few products get 2–6 reviews in the brand voice, written by background customers who actually bought them on non-cancelled orders. Reviewers are chosen from the seeded orders, not hard-coded, because background orders are generated randomly with a fixed random seed.
- The `customer` demo login gets one reviewed purchase and at least one purchased-but-unreviewed product, so both slot states are visible right after seeding.
- The seed adds no customers and no SoulSear orders, and the dashboard's revenue data is unchanged. The wipe step clears reviews with the rest of the domain data.

**Build order** (the suite is green at each boundary)

1. The `reviews` app, the model, constraints and migration, and the rules on the manager and model: can-write, can-change, summary, edited, edited-by-staff.
2. Read-only display on the product page: summary, list, empty state, the explanatory messages, and the admin registration.
3. Create: form, validation, the create endpoint, the slot swap and the out-of-band summary.
4. Edit and delete: in-place edit, cancel, `hx-confirm` delete, staff controls and edit marking, and 403s on every endpoint.
5. Show more, and demo reviews in the seed.

## Testing Decisions

- pytest + pytest-django, with plain fixtures in the project-level `conftest.py` (no factory-boy). A fixture builds an order for a user and product with a given status. Tests never invoke the seed command.
- **Model and constraint tests:** a rating outside 1–5 is rejected by the database check; a second review by the same user for the same product is rejected by the unique constraint; deleting a product deletes its reviews; the summary's average and count are correct, including with no reviews.
- **Eligibility tests:**
  - Each status: Placed, Shipped and Delivered allow a review, and Cancelled alone does not.
  - A user with no order can't review, and neither can a staff user even with an order.
  - A user who has already reviewed can't write another, but can after deleting.
  - An unavailable product can be reviewed.
  - An existing review survives its order being cancelled.
- **SoulSear test:** the account that ordered a SoulSear can review it. A different account, with no order of its own, cannot, both by the rule and through the endpoint (403).
- **Form tests:** a comment of fewer than 10 characters after trimming is rejected, including one made only of spaces; 2,001 characters is rejected; exactly 10 and exactly 2,000 are accepted.
- **Permission tests on every endpoint:** signed-out users are redirected to login; non-owners get 403 on edit and delete; staff can edit and delete any review; an ineligible user's POST to create gets 403.
- **Edit marking:** a customer's own edit marks the review edited but not staff-edited; a staff edit sets `updated_by` and shows the staff note.
- **HTMX responses:** create, edit and delete responses contain the out-of-band summary; show more returns the next 10 newest-first and omits the button on the last page. The 11-or-more case is built in tests, since the seed can't produce it.
- **Admin:** review fields are read-only, and delete is permitted.

## Out of Scope

- **A back-office Reviews tab** or moderation queue. Staff moderate inline on the product page, and admins can use the Django admin list. A tab is a likely next addition.
- **Next-of-kin, family, or deceased-account modeling.** Eligibility is personal to the ordering account, and nothing more is built.
- **Reviews by staff,** and employee badges.
- **Star summaries on catalog cards** or in search results. The summary appears on the product detail page only.
- **Sorting or filtering reviews** (by rating, most helpful, and so on).
- **Half stars, review titles, photos, rich text,** and "was this helpful?" voting.
- **Soft delete, review history, or banning customers** from re-reviewing after a staff delete.
- **Flagging or reporting reviews** by customers.
- **Seeding "Show more" or SoulSear demo data.** Both are covered by automated tests only, to keep the seed small and the dashboard unchanged.
- **Email notifications** about reviews.

## Further Notes

- **Why "next of kin" needs no code:** the business rule says the right to review belongs to the buyer and is not transferable. Because eligibility is checked against the user on the order, any other account, a relative's included, has no purchase and so no right to review. A relative who signs in *as* the owner can't be told apart from the owner by any login-based system, and that's accepted.
- **Why staff edits are visible:** changing words that appear under a customer's name is the riskiest power in this feature. Recording `updated_by` and showing "Edited by ThoughtTronix staff" keeps the store honest and makes disputes answerable. For the same reason, the Django admin can't edit review text.
- **Why reviews survive cancellation:** removing a customer's writing automatically is surprising. Staff can still delete a review by hand.
- **Seed limits:** the seed has 10 non-staff customers and sells no Defense products (so SoulSear doesn't flatten the revenue chart). With one review per customer per product, no seeded product can reach the 11 reviews "Show more" needs, which is why that case and SoulSear live in the tests.
- **`hx-confirm` uses the browser's native dialog,** which can't take the DaisyUI theme. An inline, themed confirmation is an easy later upgrade.
