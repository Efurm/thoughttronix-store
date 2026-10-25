# PROMPTS.md — AI Usage Log

This file is the record of AI use on this codebase. At the end of every
agent session, direct the agent to write the session log with this prompt:

> Append a session log to PROMPTS.md at the repo root, under today's date,
> newest entry at the top. Record every prompt I gave you this session, in
> order, including any corrections. End the entry with a short summary:
> the outcome, any places where I deviated from a recommended answer or
> asked follow-up questions, and anything that went sideways.

Two rules:

- Entries are added only by that prompt, never unprompted.
- New entries go at the top. Never rewrite or delete an old entry — the
  log is part of your work, and an honest log of a session that went
  sideways is worth more than a tidy one.

Each entry has this shape:

    ## YYYY-MM-DD — <one-line summary>

    ### Prompts
    1. ...

    ### Summary
    - **Outcome:** what was built and what was kept
    - **Deviations:** recommendations overridden, follow-up questions asked
    - **Sideways:** failures, wrong turns, and how they were caught

## 2026-10-24 — Product reviews: implemented Phase 7 (documentation and polish)

### Prompts
1. /implement @prd/product-reviews.md @plans/product-reviews.md implement
   phase 7
2. How do I verify this phase or feature manually in the browser?
3. update PROMPTS.md, commit the completed phase, and push it to GitHub.

### Summary
- **Outcome:** Phase 7 changed docs only, on `feature/product-reviews`:
  - `CLAUDE.md` gained a `reviews/` entry in the project layout. It
    covers the rules on the model and queryset, inline staff moderation
    with the staff edit note, the admin being read-only plus delete, and
    the HTMX-only endpoints. The "exactly four deep modules" line is
    unchanged.
  - `README.md` gained a paragraph on product reviews and the seed's
    demo reviews. The `customer` demo login row now mentions their
    review, and the repo layout now says "five apps" and lists
    `reviews`. It had said "four apps" before this phase.
  Ruff is clean (`check` and `format --check`) and the suite stayed at
  463 passing. For the manual check, the agent cloned the repo into its
  scratchpad and followed only the README steps (`uv sync`, `migrate`,
  `seed`, which reported 18 reviews). Then, as `customer`, it
  created, edited and deleted a DreamWeaver review through the Django
  test client. Each step returned 200, create carried the out-of-band
  summary, and delete brought the form back.
- **Deviations:** No recommendations were overridden. Calls the agent
  made without asking:
  - The plan's task 3 (this PROMPTS.md entry) was held back until the
    user's log prompt, because this file's rules say entries are
    written only on that prompt. Writing it at the start would have
    left out the later prompts.
  - The plan says "CI passes", but the repo has no `.github/workflows`,
    so there was no CI to run. That was reported, not added.
  One follow-up question (browser verification) was answered with a
  walkthrough. The agent never opened the pages in a browser.
- **Sideways:**
  - In the test-client walkthrough, the edited review didn't show as
    edited. The agent checked and found that the edit landed within
    `EDIT_GRACE` (1 second) of the create, which is the intended
    behaviour, not a bug.
  - The full `pytest` run (about 6 minutes) was run in the background
    to avoid the tool timeout.
  - `db.sqlite3` and the deleted `media/products/*.webp` files still
    show as changed from earlier seed runs. They were left out of the
    commit again.

## 2026-10-24 — Product reviews: implemented Phase 6 (demo reviews in the seed)

### Prompts
1. /implement @prd/product-reviews.md @plans/product-reviews.md implement
   phase 6
2. How do I verify this phase or feature manually in the browser?
3. update PROMPTS.md, commit the completed phase, and push it to GitHub.

### Summary
- **Outcome:** Built Phase 6 on `feature/product-reviews`, all in
  `products/management/commands/seed.py`:
  - The wipe step deletes reviews first.
  - A `REVIEWS` table gives Veil, MindSync, DreamWeaver, RecallPro and
    Calm Collar 2–5 brand-voice reviews each, 17 in all. Reviewers are
    the background customers who bought the product on an order that
    wasn't cancelled, taken in username order; nobody is hard-coded.
  - Each review is dated 2–10 days after the reviewer's first purchase
    of the product. The dates come from their own `random.Random(2026)`,
    so the order history (and the dashboard) is exactly as before.
  - One Veil review is author-edited and one DreamWeaver review is
    staff-edited (`updated_by` = `employee`), so both edit notes show.
  - `customer` reviews MindSync (`CUSTOMER_REVIEW`). DreamWeaver,
    SyncRest, Veil and the rest of their purchases stay unreviewed, so
    the form shows.
  - The seed's summary line includes the review count (18).
  Verified by seeding twice (18 both times), checking the MindSync,
  DreamWeaver and Veil pages as `customer` with the Django test client,
  and loading the admin review list. The suite stayed at 463 passing,
  and Ruff is clean.
- **Deviations:** No recommendations were overridden. Calls the agent
  made without asking:
  - The SoulSear Authorization Case (an accessory that background
    customers do buy) was left unreviewed, to keep SoulSear out of
    the demo data.
  - If a product has fewer buyers than written reviews, the extras
    are dropped (`zip(..., strict=False)`).
  - Dashboard figures weren't compared by hand. The agent relied on
    the order code and its random seed being untouched.
  One follow-up question (browser verification) was answered with a
  walkthrough. The agent never opened the pages in a browser.
- **Sideways:**
  - The first reviewer query chained `.exclude()` across the orders
    relation. That would have dropped any customer with *any*
    cancelled order. The agent caught it before the first run and
    switched to an `OrderItem` subquery, the same shape as `can_write`.
  - The customer's comment first said "four months ago", which didn't
    match its date. It was reworded.
  - Ruff flagged `zip()` without `strict=` (B905); `strict=False` was
    added.
  - The full `pytest` run passed the tool timeout and finished in the
    background. The page check in that same command failed with
    `DisallowedHost` (the test client's `testserver` host). The agent
    re-ran it with `SERVER_NAME='localhost'`.
  - Each seed run deletes the files under `media/products/` and
    rewrites `db.sqlite3`. Both are still tracked in git even though
    `media/` is gitignored. That was already true before this phase.
    They were left out of the commit and reported to the user.

## 2026-10-24 — Product reviews: implemented Phase 5 (show more)

### Prompts
1. /implement @prd/product-reviews.md @plans/product-reviews.md implement
   phase 5
2. How do I verify this phase or feature manually in the browser?
3. update PROMPTS.md, commit the completed phase, and push it to GitHub.

### Summary
- **Outcome:** Built Phase 5 on `feature/product-reviews`:
  - `ShowMoreReviewsView` (`GET /reviews/product/<pk>/page/<n>/`,
    `reviews:more`). It is public because it only reads. It returns
    the next 10 other reviews newest first, without the viewer's own,
    using the same query as the product page's first batch (the
    existing `excluding_author` and `page` queryset methods).
  - A `_more_button.html` partial, the last item in `#review-list`. It
    replaces itself with the fetched batch (`_more.html`), so reviews
    append below and the page never navigates. Each batch carries a new
    button while more remain. The product page shows the button only
    when there are more than 10.
  The suite went from 453 to 463 passing (10 new tests in
  `reviews/test_show_more.py`), and Ruff is clean.
- **Deviations:** No recommendations were overridden. Calls the agent
  made without asking, listed back to the user:
  - Page 0 and an unknown product return 404. A page past the end
    returns an empty batch with no button.
  - `hx-disabled-elt` on the button stops a double-click from loading
    the same page twice.
  - Pages are counted by position, so a delete while the page is open
    makes the next batch skip one review, and an add makes one show
    twice. The plan doesn't cover this, so it was left as is and
    reported.
  One follow-up question (browser verification) was answered with a
  walkthrough, including a shell snippet that adds 25 throwaway
  reviews to Seraphine and a cleanup line. The agent didn't run it.
- **Sideways:**
  - The first edit script failed because bare `python` isn't on PATH
    (Windows sends it to the Microsoft Store). The template files in
    the same command had already been written. The agent checked
    `git diff --stat` and re-ran the edits through `uv run python`.
  - The full `pytest` run took longer than the tool timeout and moved
    to the background. The agent ran the new tests meanwhile (10
    passed). The full run finished green at 463, but
    `ruff format --check` flagged `reviews/test_show_more.py`, which
    was reformatted and re-tested.
  - The agent didn't view the pages in a browser; the user was given
    the manual walkthrough instead.

## 2026-10-24 — Product reviews: implemented Phase 4 (delete)

### Prompts
1. /implement @prd/product-reviews.md @plans/product-reviews.md implement
   phase 4
2. How do I verify this phase or feature manually in the browser?
3. update PROMPTS.md, commit the completed phase, and push it to GitHub.

### Summary
- **Outcome:** Built Phase 4 on `feature/product-reviews`:
  - A Delete button beside Edit on the review card. It is shown under
    the same `can_change` rule and uses `hx-confirm` (the browser's
    native dialog, per the PRD).
  - `DeleteReviewView` (`POST /reviews/<pk>/delete/`, `reviews:delete`).
    It goes through the shared `ChangeReviewMixin`, so it requires login
    and returns 403 unless the user is the author or staff. The author's
    own delete returns the slot in the card's place: the form, or the
    only-buyers line if their order has since been cancelled. A staff
    delete of someone else's review returns nothing in the card's place,
    which removes it. Every response carries the summary out-of-band.
  The suite went from 441 to 453 passing (12 new tests in
  `reviews/test_delete.py`), and Ruff is clean.
- **Deviations:** No recommendations were overridden. Calls the agent
  made without asking, listed back to the user:
  - The slot's state logic moved from `products/detail.html` into a new
    `_slot.html` partial, shared by the page and the delete response.
    Its sign-in link now builds `next` from the product's URL rather
    than the request path, which is the same address on the product
    page.
  - When staff delete the last review, the response appends the empty
    state to the list out-of-band (`beforeend:#review-list`), so the
    list never goes blank.
  - A GET to the delete URL returns 405, and a missing review 404.
  One follow-up question (browser verification) was answered with a
  step-by-step walkthrough. The agent read the dev database (no writes)
  to find `customer`'s purchases and a background buyer of MindSync.
- **Sideways:**
  - The first full `pytest` run took longer than the 5-minute tool
    timeout and moved to the background. The agent ran the reviews and
    products tests in the meantime (194 passed), then confirmed the full
    run finished green at 453.
  - `ruff format --check` flagged `reviews/urls.py`, and it was
    reformatted.
  - The walkthrough's 403 step was awkward. The seed has only one
    customer who can sign in, so the agent offered a console `fetch`
    that needs a second customer account. It said so and pointed to the
    automated 403 tests instead.
  - The agent didn't view the pages in a browser; the user was given
    the manual walkthrough instead.

## 2026-10-24 — Product reviews: implemented Phase 3 (edit)

### Prompts
1. /implement @prd/product-reviews.md @plans/product-reviews.md implement
   phase 3
2. How do I verify this phase or feature manually in the browser?
3. update PROMPTS.md, commit the completed phase, and push it to GitHub.

### Summary
- **Outcome:** Built Phase 3 on `feature/product-reviews`:
  - An Edit button on the review card, shown when the model's
    `can_change` allows it (the author's own card, and every card for
    staff). The template calls the rule through a new `can_change`
    filter in `reviews/templatetags/review_extras.py`, so the page and
    the server can't disagree.
  - `EditReviewView` (`GET`/`POST /reviews/<pk>/edit/`). GET swaps the
    card for the pre-filled form in the same spot. POST saves with
    `updated_by` set to the acting user and returns the updated card
    with the summary out-of-band. Invalid input re-renders the form
    in place, with errors, and leaves the review unchanged.
  - `ReviewCardView` (`GET /reviews/<pk>/`), which Cancel uses to
    restore the original card.
  - All three endpoints require login and return 403 when
    `can_change` fails, through a shared `ChangeReviewMixin`.
  The suite went from 424 to 441 passing (17 new tests in
  `reviews/test_edit.py`), and Ruff is clean.
- **Deviations:** No recommendations were overridden. Calls the agent
  made without asking, listed back to the user:
  - `_form.html` now serves create and edit, switching on an
    `editing` variable, rather than adding a second form partial. The
    edit form takes the card's id so it swaps itself.
  - The staff heading names whose review is being edited.
  - Each edit form gets per-review field ids (`auto_id`), so two open
    forms never share one.
  - A missing review returns 404.
  One follow-up question (browser verification) was answered with a
  step-by-step walkthrough. The agent read the dev database (no
  writes) to find which products `customer` has bought.
- **Sideways:**
  - The first run of the reviews tests had one failure, caused by the
    test fixture. It backdated `created_at` but not `updated_at`, so
    a fresh review already counted as edited. The fixture now
    backdates both.
  - A Python string-replace script missed one assertion because of
    `\n` escaping. Ruff caught the now-unused `re` import. The
    assertion was fixed with the Edit tool and replaced with a regex
    check on the checked star.
  - One shell command first tried `python3`, which isn't usable here,
    and fell back to `uv run python`. The edit was confirmed applied
    afterwards.
  - The agent didn't view the pages in a browser; the user was given
    the manual walkthrough instead.

## 2026-10-24 — Product reviews: implemented Phase 2 (create)

### Prompts
1. /implement @prd/product-reviews.md @plans/product-reviews.md implement
   phase 2
2. How do I verify this phase or feature manually in the browser?
3. update PROMPTS.md, commit the completed phase, and push it to GitHub.

### Summary
- **Outcome:** Built Phase 2 on `feature/product-reviews`:
  - `ReviewForm` in `reviews/forms.py`: a DaisyUI radio-star rating
    from 1 to 5 and a trimmed comment of 10 to 2,000 characters, each
    with its own error messages.
  - `CreateReviewView` (`POST /reviews/product/<pk>/`, namespace
    `reviews`). It requires login, re-runs `can_write` and returns 403
    on failure. If a simultaneous submission hits the unique
    constraint, that is also a 403. Valid input returns the new card
    with the summary as an out-of-band swap; invalid input returns the
    form partial with errors beside each field.
  - The form partial replaces the Phase 1 placeholder in the slot.
    `ProductDetailView` passes a blank form when the viewer can write.
  The suite went from 400 to 424 passing, and Ruff is clean.
- **Deviations:** No recommendations were overridden. Calls the agent
  made without asking, listed back to the user:
  - The form has `novalidate`, so the browser never blocks a submit and
    the server-side errors are what the customer sees.
  - The other-reviews empty state moved into its own partial. The
    create response refreshes it out-of-band, so it no longer says "No
    reviews yet" beside a fresh review. The plan only names the slot
    and summary.
  One follow-up question (browser verification) was answered with a
  step-by-step walkthrough using the seeded `customer`, `employee` and
  `admin` logins.
- **Sideways:**
  - Bare `python` isn't on the PATH here (again), so that edit was
    redone with the Edit tool.
  - The first full test run was started before the last edits and took
    over two minutes. It was stopped and re-run once the code was
    final.
  - Piping the manual check script into `manage.py shell` broke on
    indentation in the interactive console. It was re-run with
    `shell -c "exec(...)"`.
  - The dev database didn't have the Phase 1 migration, so the product
    page raised "no such table". Unlike Phase 1, the agent ran
    `migrate` on the real `db.sqlite3`, which only adds the empty
    reviews table. The check itself ran inside a rolled-back
    transaction, after a Windows console encoding error on "★", and
    left 0 reviews. The migrated `db.sqlite3` is committed with the
    phase so the tracked snapshot matches the code.
  - The browser walkthrough first included a garbled console snippet
    for testing the 403. It was replaced in the same answer by the
    two-tab double-submit check. The agent still never opened a real
    browser.

## 2026-10-24 — Product reviews: implemented Phase 1 (read-only tracer bullet)

### Prompts
1. /implement @prd/product-reviews.md @plans/product-reviews.md implement
   phase 1
2. How do I verify this phase or feature manually in the browser?
3. update PROMPTS.md, commit the completed phase, and push it to GitHub.

### Summary
- **Outcome:** Built Phase 1 on `feature/product-reviews`:
  - A new `reviews` app with the `Review` model (1–5 rating check
    constraint, unique per user and product, newest first) and one
    migration.
  - Rules on the queryset and model: `can_write`, `can_change`,
    `summary`, `is_edited`, `is_edited_by_staff`, plus
    `excluding_author` and `page(n)` for Phase 5 to reuse.
  - `ProductDetailView` gained the review context, and the product
    page a Reviews section (summary, your-review slot in each of its
    states, the list, an empty state), with the card and summary as
    partials under `templates/reviews/partials/`.
  - A read-only Django admin with adding disabled and bulk delete
    allowed.
  - `make_order` and `soulsear` fixtures in `conftest.py`.
  The suite went from 352 to 400 passing, and Ruff is clean.
- **Deviations:** No recommendations were overridden. Calls the agent
  made without asking, listed back to the user: a review counts as
  edited only when `updated_at` is more than 1 second after
  `created_at`; cards show the full name, falling back to the username;
  the CLAUDE.md layout entry waits for Phase 7, as the plan says. One
  follow-up question (browser verification) was answered with a
  walkthrough that creates reviews in the shell, since Phase 1 has no
  form.
- **Sideways:**
  - The first fixture edit used bare `python`, which isn't on the PATH
    here; it was re-run with `uv run python`.
  - One test expected the apostrophe in "who've" as `&#x27;`, but it is
    template text and isn't escaped; the test was fixed.
  - The manual check script first used the test fixture's slug
    (`seraphine-home-hub`) instead of the seeded one (`seraphine`), and
    then hit a Windows console encoding error on "★". Both were fixed
    by re-running.
  - `db.sqlite3` turned out to be tracked even though `.gitignore`
    lists it, so the agent verified against a scratch copy rather than
    migrating the real one. The agent never opened a real browser; the
    pages were rendered with Django's test client.

## 2026-10-24 — Product reviews: turned the PRD into a phased plan

### Prompts
1. /prd-to-plan @prd/product-reviews.md
2. Answers to the agent's two breakdown questions: "Fold model into
   display" (granularity) and "Match existing plans (Recommended)"
   (format)
3. log the session and update PROMPTS.md with the standard prompt

### Summary
- **Outcome:** Wrote `plans/product-reviews.md` in the Goal / Tasks /
  Verification / Out of bounds format of `plans/product-images.md`, with
  a "Durable Decisions" header (the `reviews` app, the `Review` model, the
  rules, the URL paths under `/reviews/…` using pks, authorization, and
  how HTMX swaps the page). It has eight phases:
  0. Branch setup.
  1. A read-only tracer bullet: model, rules, product-page section, admin.
  2. Create.
  3. Edit.
  4. Delete.
  5. Show more.
  6. Seed demo reviews.
  7. Docs and polish.
  No code was written and nothing is committed. The work is still on
  `feature/account-security`, so Phase 0 (merge it, then branch
  `feature/product-reviews` from `main`) is still to do.
- **Deviations:** One recommendation overridden. The agent proposed Phases
  0–7 with the model and rules alone as Phase 1 (verified by tests only).
  The user chose to fold the model into the read-only display, so the
  first phase cuts through every layer. Edit/Delete and Show more/Seed
  stay split, thinner than the PRD's five-step build order. The format
  question went with the recommendation. Three calls the agent made
  without asking, flagged after writing:
  - "Show more" is public. The PRD says all review endpoints require
    login, but story 3 is for signed-out shoppers too.
  - Adding reviews in the Django admin is disabled, because it would skip
    the purchase rule.
  - An author's own delete brings back the "only buyers" line, not the
    form, if their order has since been cancelled.
  No follow-up questions were asked.
- **Sideways:** The first exploration command failed because it looked for
  a `plans/account-security*.md` that doesn't exist. The Account Security
  Center has a PRD but no plan file. The agent re-ran the exploration
  without it. Nothing else went wrong.

## 2026-10-24 — Product reviews: grilled the design, wrote the PRD

### Prompts
1. /grill-me ThoughtTronix wants customers to leave product reviews. The
   completed feature must include these business requirements: A customer
   can leave one review per product. Each review includes a rating and a
   written comment. A customer can leave a review only for a product they
   have purchased. SoulSear owners are eligible but their next of kin are
   not. Customers can edit and delete only their own reviews. Staff can
   edit and delete any review. Creating, editing, or deleting a review
   should update smoothly without reloading the full page or causing the
   customer to lose their place.
2. A (any order that isnt cancelled)
3. A
4. A (Whole stars, 1-5) and showing the average and count on the product page
5. A
6. A
7. A
8. A
9. A
10. A
11. A
12. A
13. A
14. A
15. A
16. Keep the seed small (A)
17. A
18. /to-prd
19. yes, add the session log to PROMPTS.md with the standard prompt

### Summary
- **Outcome:** A 16-question design interview, then
  `prd/product-reviews.md` (29 user stories, implementation and testing
  decisions, a five-phase build order, out of scope, further notes). The
  design: a new `reviews` app; any non-cancelled order counts as a
  purchase; whole stars 1–5 with an average and count on the product
  page; a required 10–2,000 character comment; one review per user and
  product at a time (unique constraint, real delete); staff moderate
  inline on the product page, with `updated_by` and a visible "Edited by
  ThoughtTronix staff" note; staff can't write reviews; in-place HTMX
  edit, `hx-confirm` delete, out-of-band summary refresh, and "Show more"
  10 at a time; the Django admin is read-only plus delete. "Next of kin"
  is satisfied by eligibility belonging to the ordering account, with no
  new modelling. No code was written and nothing is committed.
  `plans/product-reviews.md` is not written yet. The work is still on
  `feature/account-security`; a new branch from `main` is still needed.
- **Deviations:** One recommendation overridden. In question 15 the user
  kept the seed small (A) instead of the recommended extra background
  customers plus a SoulSear order dated outside the dashboard window. So
  "Show more" and the SoulSear rule are covered by tests only, not
  visible in the demo. In question 1 the user picked A but didn't answer
  the follow-up (keep a review if its order is cancelled later). The
  agent took its own recommendation (keep it) and said so. Question 3 was
  answered with the recommended option plus the suggested summary. The
  closing summary listed two small calls the agent made without asking:
  sign-in returns via `?next=`, and review endpoints are login-only and
  return partials, like the cart. The PRD added two more, reported after
  it was written: your own review is left out of the "other reviews"
  list, and Cancel restores the card while editing. No follow-up
  questions were asked.
- **Sideways:** The question 14 recommendation (give one product just
  over 10 reviews so "Show more" can be demoed) turned out to be
  impossible. A later look at the seed found only 10 non-staff customers
  (one review each per product means at most 10 per product), randomly
  generated background orders, and no Defense or SoulSear sales at all.
  The agent corrected this openly and turned it into question 15.
  Question 14 also included a muddled aside about "tests never invoke
  the seed" that wasn't needed. Question 15's option C was rewritten
  mid-answer ("Wait, no") after the agent realised a cancelled SoulSear
  order couldn't support a review. As with the earlier PRDs, this one adds
  a Testing Decisions section, names a few modules despite the
  template's no-paths rule, and reuses the invented "Commissioned by
  ThoughtTronix Customer Trust" line.

## 2026-10-23 — Account Security Center: built Phase 4 (secondary email)

### Prompts
1. @prd/account-security.md @plans/account-security.md Do Phase 4.
2. how can I manually verify this in the broswer
3. log the session in PROMPTS.md with the standard prompt

### Summary
- **Outcome:** Built step 4 of the PRD's build order on
  `feature/account-security`. `accounts.User` gained a nullable
  `secondary_email` and a `secondary_email_verified` flag. Migration
  `0003` adds them, plus a conditional unique constraint on the
  lowercased secondary that applies only where it is verified, so a
  pending address reserves nothing. A `UserQuerySet.with_address` lookup
  (primary or verified secondary, ignoring capitals) is now shared by
  signup, the new secondary form, `User.clean`, confirmation and
  password reset. Reset now matches verified secondaries too, never
  pending ones, and still mails the address typed. `User.clean` holds
  the two cross-field rules. Model methods set (always unverified),
  remove and confirm the secondary. Confirmation runs in a transaction,
  re-checks for a claim by another account, and turns an
  `IntegrityError` from the constraint into a plain error.
  `accounts/security.py` gained signed confirmation tokens (`signing`
  with a salt and `SECONDARY_EMAIL_CONFIRM_MAX_AGE`, read through
  environs, default 24 hours, listed in `.env.example`), the request,
  resend, confirm and remove workflows, and four new notices (added,
  replaced, confirmed, removed) that name the address. New pages: a
  password-guarded add/replace form, Remove and "Send the link again"
  POST buttons on the hub, and a confirmation page that works signed
  out, where GET only shows a Confirm button and POST confirms. The hub
  shows the secondary with a Pending or Verified badge. The admin shows
  the secondary fields read-only; the primary stays editable there.
  Forty-seven new tests were added. The full suite passes (352) and ruff
  is clean. The migration was applied to the tracked `db.sqlite3`, as in
  Phases 1 and 2. Nothing is committed.
- **Deviations:** No recommendations were offered, so none were
  overridden. Small calls the agent made without asking: replacing the
  secondary with the address it already holds is refused (the resend
  button covers that case), the admin shows the secondary read-only so
  every change goes through the password check and the primary notice,
  and a link that has already been used shows "no longer works" rather
  than a second success page. The one follow-up question asked how to
  verify the phase in the browser. It was answered with a ten-step
  walkthrough using the seeded `customer` account and the console email
  output: adding with a wrong and then a right password, the refused
  addresses, resend and the cooldown, opening the link signed out
  without confirming, confirming, resetting through the secondary,
  replacing (old link dies, reset ignores the pending address), a
  pending address not blocking someone else's signup and then failing
  to confirm, removing, and staff and admin access.
- **Sideways:** `plans/account-security.md` still does not exist. The
  agent worked from the PRD's build order again and said so. The first
  migration attempt failed because a manager built with
  `UserManager.from_queryset(...)` cannot be serialized. The agent fixed
  it with a named `StoreUserManager` subclass. Two Bash heredocs (the
  security module and the tests) failed with a shell quoting error
  before writing anything. The agent checked `git status`, then used the
  Write tool and a scratch file appended with `cat`. While writing the
  confirmation view, the agent noticed that merging fresh context into
  the POST response would keep a stale "no longer works" error after a
  successful confirmation. It fixed this before any test ran. The full
  suite outlasted the foreground limit and ran in the background. The
  agent answered the browser question before that run finished and said
  it was still running; it later reported 352 passing. The agent never
  viewed the pages in a browser. The walkthrough lists expected results,
  not ones the agent observed.

## 2026-10-23 — Account Security Center: built Phase 3 (forgotten password)

### Prompts
1. @prd/account-security.md @plans/account-security.md Do Phase 3.
2. How can I manually verify this phase in the browser?
3. log the session in PROMTPS.md with the standard prompt

### Summary
- **Outcome:** Built step 3 of the PRD's build order on
  `feature/account-security`. Django's stock four-step reset flow now
  lives under `/accounts/password-reset/` (request, "check your inbox",
  the emailed link, complete). It works signed out, is styled with
  DaisyUI and has a "This link no longer works" state for bad links.
  `ResetPasswordForm` matches the typed address against active users'
  primary emails, ignoring capitals (primaries only at this stage). It
  sends the link to the address as typed and applies the cooldown.
  Unknown addresses get the same response. `accounts/security.py` gained
  `claim_mail_cooldown`, an atomic 60-second `cache.add` per lowercased
  address, and a `PASSWORD_RESET` notice that is sent when the reset
  completes. `PASSWORD_RESET_TIMEOUT` is read through environs, defaults
  to one hour, and is listed in `.env.example`. The login page links to
  "Forgot your password?". There is no auto-login after a reset. An
  autouse fixture in `conftest.py` clears the cache around every test.
  Seventeen new tests were added. The full suite passes (305) and ruff is
  clean. Nothing is committed.
- **Deviations:** No recommendations were offered, so none were
  overridden. The one follow-up question asked how to verify the phase in
  the browser. It was answered with a nine-step walkthrough using the
  seeded `customer` account and the console email output: the login
  link, matching ignoring capitals, the cooldown, unknown addresses,
  using the link, signing in with the new password, a reused link, and a
  link killed by a password change. It also told the user how to restore
  the demo password and how to shorten the timeout through `.env` to see
  expiry.
- **Sideways:** `plans/account-security.md` still does not exist. The
  agent again worked from the PRD's build order and said so. The agent's
  first draft of a cooldown "lapses" test was muddled. The agent caught it
  before running anything and replaced it with a test that the claim uses
  a 60-second timeout. The full-suite run went over the two-minute
  foreground limit and finished in the background, all passing. An
  attempt to wait on it with `sleep` was blocked by the harness, and the
  agent waited for the completion notice instead. The editing script
  printed a harmless `SyntaxWarning` about an escape sequence. The agent
  checked that the regex in the test file came out correct. The test of
  the one-hour default fails if a local `.env` sets
  `PASSWORD_RESET_TIMEOUT`, and the user was warned. The agent never
  viewed the pages in a browser. The walkthrough lists expected results,
  not ones the agent observed.

## 2026-10-23 — Account Security Center: built Phase 2 (hub and change password)

### Prompts
1. @prd/account-security.md @plans/account-security.md Do Phase 2.
2. How can I manually verify this phase in the browser?
3. log the session and update PROMPTS.md with the standard prompt

### Summary
- **Outcome:** Built step 2 of the PRD's build order on
  `feature/account-security`. Added `accounts/security.py`, the fourth
  deep module. So far it holds a `Notice` enum (one value,
  `PASSWORD_CHANGED`) and `send_security_notice`, which mails the primary
  email using one plain-text template per notice
  (`templates/accounts/email/notice_password_changed.txt`). A user with
  no primary gets no notice. Added the Account Security Center hub at
  `/accounts/security/`. It shows the primary email (or a "No primary
  email on file" state), a designed "No backup email yet" empty state
  where the secondary will go, and a link to change password. Change
  password uses Django's stock `PasswordChangeView`, its form and its
  done page, styled with DaisyUI. It sends the "password changed" notice
  and keeps the current session while signing out the others. The
  navbar now shows a "Security" link to every signed-in user. `CLAUDE.md`
  now says "exactly four" deep modules and mentions the Security Center
  under `accounts/`. Sixteen new tests were added. The full suite passes
  (288) and ruff is clean. Nothing is committed.
- **Deviations:** No recommendations were offered, so none were
  overridden. The one follow-up question asked how to verify the phase in
  the browser. It was answered with a six-part walkthrough using the
  seeded demo accounts: signed-out redirects, the hub, a wrong current
  password, other sessions signed out after a change, staff on the
  storefront page, and a user with no email.
- **Sideways:** `plans/account-security.md` still does not exist. As in
  Phase 1, the agent worked from the PRD's build order and told the user
  so. The first attempt to add imports to the test file used an inline
  `python` heredoc, which failed because `python` is not on the PATH in
  Git Bash. Ruff caught the undefined names, and the imports were then
  added with the Edit tool. Clearing the cache between tests was left
  for Phase 3, where the cooldown first needs it. The agent never viewed
  the pages in a browser. The walkthrough lists expected results, not
  ones the agent observed.

## 2026-10-22 — Account Security Center: built Phase 1 (email at signup)

### Prompts
1. @prd/account-security.md @plans/account-security.md Do Phase 1.
2. How can I manually verify this phase in the browser?
3. write the session log and update PROMPTS.md with the standard prompt

### Summary
- **Outcome:** Built step 1 of the PRD's build order on
  `feature/account-security`. The signup form has a required Email
  field and rejects an address already in use, ignoring capitals, with
  a plain-language error. `User` gained a conditional unique constraint
  on the lowercased `email` (blank emails are exempt), with migration
  `0002_user_unique_primary_email`, applied to the dev database. The
  `customer` and `employee` fixtures now carry `customer@example.com`
  and `employee@example.com`. The "other" users in the orders tests keep
  blank emails, which shows that case stays valid. Four new tests were
  added: email required, duplicate rejected ignoring capitals, the
  database rejecting a capitals-only duplicate, and two blank emails
  coexisting. The accounts tests pass (13/13) and ruff is clean. Nothing
  is committed.
- **Deviations:** No recommendations were offered, so none were
  overridden. The one follow-up question asked how to verify the phase in
  the browser, and was answered with a seven-step walkthrough covering
  signup and the Django admin.
- **Sideways:** `plans/account-security.md` does not exist (the
  2026-10-19 session never wrote it). The agent did not stop to ask: it
  worked from the PRD's build order and told the user so. The first
  full-suite run went over the two-minute foreground limit and finished
  in the background with 272 passed and 1 failed. The failing test
  expected `Fresh@Example.com` to be stored exactly as typed, but
  Django's `AbstractUser.clean()` lowercases the domain. The test was
  changed to expect `Fresh@example.com`, and only the accounts tests were
  rerun afterwards, not the full suite. Applying the migration changed
  the tracked `db.sqlite3` grading snapshot, which now shows as modified.
  The phase was never checked in a browser by the agent. The admin step
  in the walkthrough (a duplicate email showing a form error rather than
  a crash) is an expectation based on Django's constraint validation,
  not something the agent tested.

## 2026-10-19 — Account Security Center: grilled the design, wrote the PRD

### Prompts
1. /grill-me design a Account Security Center where Customers should be
   able to: provide an email address when they create an account,change
   their password,reset a forgotten password through email,and add a
   secondary email address to their account.
2. A (email required at signup)
3. A (unique, ignoring capitals)
4. A (one `secondary_email` field on `User`)
5. A (secondary is a recovery address; the link goes to the address typed)
6. B (verify the secondary only)
7. C (primary fixed after signup)
8. A (add, replace, remove, resend)
9. A (current password to add or replace the secondary)
10. A (security notices to the primary)
11. A (every signed-in user, storefront layout)
12. A (hub page plus focused pages)
13. A (reset link 1 hour, confirmation 24 hours)
14. A, combined with C (confirmation without sign-in, by POST button)
15. C (conditional unique constraint, plus emails on the shared fixtures)
16. B (only verified secondaries reserve an address)
17. A (60-second per-address cooldown through the cache)
18. A (fourth deep module, `accounts/security.py`)
19. A (four build phases)
20. /to-prd
21. Append a session log to PROMPTS.md at the repo root, under today's
    date, newest entry at the top. Record every prompt I gave you this
    session, in order, including any corrections. End the entry with a
    short summary: the outcome, any places where I deviated from a
    recommended answer or asked follow-up questions, and anything that
    went sideways.

### Summary
- **Outcome:** An 18-question design interview, then
  `prd/account-security.md` (30 user stories, implementation and testing
  decisions, out of scope, further notes). Neither file is committed, and
  no code was written. `plans/account-security.md` is not written yet.
  The work is still on `feature/product-images`; a new branch from
  `main` is still needed.
- **Deviations:** None. Every answer took the recommended option,
  including "A, combined with C" in question 13, which was the combined
  recommendation. No follow-up questions were asked. The closing offer to
  write both the PRD and the plan got a `/to-prd` instead, so only the
  PRD was written.
- **Sideways:** Question 2 settled "unique across primary and secondary"
  before the storage was chosen. One database constraint cannot span two
  fields, so cross-field uniqueness moved into `User.clean` in question 3.
  Question 14 was added mid-interview after a codebase check found that
  the `conftest.py` fixtures and `orders/tests.py` create users with blank
  emails, which a plain unique constraint would reject. That is why the
  constraint is conditional. The PRD departs from the `/to-prd` template
  in three ways: it adds a Testing Decisions section (matching the
  product-images PRD), it names a few files despite the template's
  no-paths rule, and its "Commissioned by ThoughtTronix Customer Trust"
  line was invented for flavor. The session began on 2026-10-18 and
  crossed midnight; the entry uses the date it was written.

## 2026-10-05 — Session-log request only (no code work this session)

### Prompts
1. write the session log with the standard prompt in the PROMPTS.md header.

### Summary
- **Outcome:** This entry is the only change. The session opened with the
  log request, so there was no other work to record. The uncommitted edit
  to `REFLECTION.md` was already in the working tree when the session
  started; this session did not make it or touch it.
- **Deviations:** None. No recommendations were made and no follow-up
  questions were asked.
- **Sideways:** Nothing went wrong.

## 2026-10-05 — Product images: grilled the design, built all six phases, PR #2 open

### Prompts
1. /grill-me ThoughtTronix marketing wants real images on the catalog. Two
   things are not negotiable. Every product must display either its
   uploaded image when one is available, or the existing placeholder.
   Missing files and broken image icons are not part of the approved
   visual identity. Employees will also upload product images through the
   back office. When an employee provides a file the site cannot use,
   reject it and explain the problem in plain language. Do not accept the
   file first and then lose it. The images are in the repository in a
   folder named product-images
2. https://github.com/Efurm/thoughttronix-store/tree/main/product-images this
   is the way though git hub to the images
3. A, one image per product
4. A, files on disk
5. A,server-side existence
6. A
7. A, 5MB
8. B
9. A
10. C
11. A
12. B
13. A
14. A
15. A
16. A
17. B
18. A
19. A
20. A
21. A
22. C
23. B
24. Yes
25. Yes
26. go
27. merged, continue
28. yes start phase 1
29. yes start phase 2
30. yes
31. yes
32. yes
33. yes
34. yes
35. fix the handoff skill path
36. handoff skill does not work
37. merged, bring main into this branch
38. /handoff the next session implements the design we just agreed
39. write the session log with the standard prompt in the PROMPTS.md header

### Summary
- **Outcome:** A 21-question grilling settled the design, which was
  recorded in `prd/product-images.md` and sequenced in
  `plans/product-images.md`. All six phases were built on
  `feature/product-images` (one commit per phase, pushed, open as PR #2,
  not merged). The work covers: `Product.image` and
  `display_image_url`, which falls back to the placeholder whenever the
  file is missing; `products/images.py` as the single upload gatekeeper
  (PNG/JPEG/WebP by content, 5 MB, 600–8000 px, resized to WebP), shared
  by the back-office HTMX image card and the seed; save-then-delete-on-commit
  file handling; the image read-only in the admin; list thumbnails; the
  seed loading 12 of marketing's 13 files (26 MB of PNGs became 1.95 MB of
  WebP); and docs in `CLAUDE.md`, the README, and the PRD. The suite went
  from 216 to 269 passing. Also: PR #1 (coupons) was opened and the user
  merged it; PR #3 moved the handoff skill to the right path and the user
  merged it; `main` was merged into the feature branch; `HANDOFF.md` was
  written (left uncommitted).
- **Deviations:** None overridden. The user took the recommended option on
  every question (one image; files on disk; a server-side existence check;
  PNG/JPEG/WebP; 5 MB; 4:3 contain; 600–8000 px; a separate image form;
  save then delete; slug-plus-suffix names; the seed copies from
  `product-images/`; SyncRest "No Text"; SoulSear image on Mark II;
  DEBUG-only media; shrink to WebP; admin read-only; a shared gatekeeper;
  merge coupons first; the seven specific messages; an HTMX card; a list
  thumbnail). Follow-ups: the user supplied the GitHub link when the
  folder wasn't found locally, and reported the handoff skill still not
  working after the fix. The `/handoff` arguments said the next session
  would "implement the design", but it was already built, so the agent
  wrote the handoff as verify-and-close-out instead and said so.
  Calls made without asking: four small departures recorded in the PRD
  (no lazy loading on the detail page, a numberless message for images
  too big for Pillow to measure, damaged files getting the "can't open"
  message, MPO accepted as JPEG), plus `alt=""` on list thumbnails.
- **Sideways:**
  - *The images folder.* `product-images/` existed only on GitHub's
    `main`, uploaded through the web UI, so the agent couldn't find it
    locally and had to ask.
  - *A wrong count.* The agent first said 11 of 13 images would be used,
    then corrected it to 12 (and 22 placeholders, not 23).
  - *Merge blocked.* Claude Code's auto-mode classifier blocked
    `gh pr merge` on PR #1, so the user merged it by hand.
  - *Tests wrong, not the code.* A shrink test used an image that already
    fit (fixed); one test was misnamed and one assertion meaningless (both
    fixed before committing); three image-card tests failed because Django
    HTML-escapes the quotes in messages (fixed by comparing escaped text).
  - *Edits fixed before running.* A seed edit referenced a nonexistent
    attribute and a `sed` edit mangled a docstring; both were fixed before
    anything ran.
  - *A test-safety gap.* The agent noticed the existing seed tests would
    have written into the real `media/` folder and gave them a temporary
    one.
  - *A conflicting plan task.* The plan's task to write this log entry
    conflicted with the PROMPTS.md header, so it was skipped until this
    prompt.
  - *The handoff fix, twice.* The first `git mv` left the file nested
    inside the `SKILL.md` folder and was committed that way; it was caught
    in `git status` and amended before pushing. When the user then said
    the skill didn't work, the cause was that the fix lived on another,
    unmerged branch, which the agent hadn't flagged when switching back.
  - *The dev database was changed without asking.* It was edited by hand
    in Phase 1 and reseeded in Phase 5; this was reported afterwards, not
    before.
  - *Never seen in a browser.* Checks used tests and `curl` against a
    running dev server, never a browser, so the click-through is still
    open in PR #2 and in `HANDOFF.md`.

## 2026-10-01 — Seasonal discount codes: grilled the design, built, pushed

### Prompts
1. grill me Seasonal discount codes where a customer types a code at
   checkout and the order total drops and the codes expire when a
   promotion ends. when a customer types in a expired code a message
   should show saying so.Marketing will create and retire codes
   themselves, without filing a ticket with engineering. Retiring a code
   must not change any order that already used it. Do not produce a
   server error, a blank page, or an opportunity for the customer to
   contact Legal. The coupon system must support both order-wide
   discounts and discounts limited to specific products. A discount
   should be calculated based off the price of the products themselves.
   A code can only be used once. A code should be a string of 5
   letters.Marketing should be able to manage the codes whenever they
   want
2. A, once per customer
3. A, any staff member
4. A, percentage only
5. A, show the seperate message
6. A, live preview
7. A, reject with that message
8. yes, accept all four rules
9. A,final, and one code per order
10. B, net everywhere plus discounts given
11. yes, implement this feature
12. commit this
13. push it
14. how can i manually verify the feature in browser
15. Make the coupon codes a actual word
    - Answer to the agent's clarifying question (rule vs. demo data):
      "Rename demo codes (Recommended)"
16. commit and push it
17. write the session log with the standard prompt in the PROMPTS.md header

### Summary
- **Outcome:** Built seasonal discount codes end to end on branch
  `feature/seasonal-coupons` (commits `c24e869`, `f23bcb8`, pushed; not
  merged to `main`). Includes a `Coupon` model; `quote_coupon` in
  `orders/services.py` as the single eligibility check, used by both the
  HTMX checkout preview and `place_order` (which refuses the order if the
  code went bad). Orders snapshot the code, percent, and per-line
  discounts, and orders `PROTECT` used coupons from deletion. Staff get
  a back-office Coupons tab (create, edit, retire, delete-if-unused).
  Dashboard revenue is now net of discounts, with a "Discounts given"
  tile. The seed makes one demo code per state (FALLS, QUIET, SUNNY,
  FROST, ERROR). Suite went from 166 to 216 passing; `CLAUDE.md`
  updated where it called the coupon seam "dormant".
- **Deviations:** None overridden. The user took the recommended answer
  to all nine grilling questions (once per customer; any staff; percent
  only; per-code dates with a separate retired message; live preview;
  pick individual products and reject when nothing qualifies; the four
  edit/delete/uniqueness rules; uses are final and one code per order;
  net revenue plus a discounts tile). Small calls the agent made without
  asking (listed back to the user): per-line half-up rounding, the year in
  the "expired on" message, and keeping coupons inside the `orders` app.
  Follow-up questions: how to verify in the browser (answered with a
  step-by-step walkthrough), and "make the codes an actual word", which
  was ambiguous — the agent asked whether to enforce a real-word rule or
  rename the demo codes; the user chose renaming only.
- **Sideways:** The first attempt to edit `orders/models.py` through an
  inline Python heredoc failed with a shell parse error before touching
  anything; the agent checked `git status` and switched to the Edit tool.
  An existing test asserting the old dormant `coupon_code` seam was
  ignored failed as expected and was replaced with tests that a bad code
  places no order and a blank code means no coupon. A clumsy one-liner in
  a new dashboard test was spotted and rewritten before the run. The seed
  was verified against a throwaway test database, not the user's dev
  database, and the agent never viewed the pages in a browser — the user
  was given a manual walkthrough instead. Because the session started on
  `main`, the commit went to a new feature branch.

## 2026-09-30 — Session-log request only (no code work this session)

### Prompts
1. Append a session log to PROMPTS.md at the repo root, under today's date,
   newest entry at the top. Record every prompt I gave you this session, in
   order, including any corrections. End the entry with a short summary:
   the outcome, any places where I deviated from a recommended answer or
   asked follow-up questions, and anything that went sideways.

### Summary
- **Outcome:** This entry is the only change. The session opened with the
  log request, so there was no other work to record. It is the first entry
  in the log.
- **Deviations:** None. No recommendations were made and no follow-up
  questions were asked.
- **Sideways:** Nothing went wrong. Earlier commits (e.g. the featured badge
  and its migration) came from previous sessions that were never logged here,
  so this log doesn't cover them.
