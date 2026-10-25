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

## 2026-10-25 — Product reviews: rebuilt Phase 2 (create) test-first

### Prompts
1. yes (start Phase 2)
2. yes (the three TDD behaviors)
3. yes (behavior 1's failing test)
4. yes (behavior 1 green; on to behavior 2)
5. run the test
6. the 5 red results are confirmed
7. approved (behavior 2's failing test)
8. yes (behavior 2 green; on to behavior 3)
9. yes (behavior 3's failing test)
10. yes (behavior 3 green; finish the phase)
11. do it (retry after the shell outage)

### Summary
- **Outcome:**
  - The user approved three behaviors, and each went through an
    approved failing test before any code:
    1. `ReviewForm` trims the comment, then requires 10–2,000
       characters, with its own messages.
    2. The create endpoint answers 403, and saves nothing, whenever
       `can_write` fails: no order, a cancelled order only, a SoulSear
       next-of-kin account, staff, or an existing review.
    3. A valid create saves a review owned by the requester (a forged
       `user` field is ignored) and returns the card under its
       `review-<pk>` id plus the out-of-band summary.
  - The rest was built and tested normally:
    - `POST /reviews/product/<pk>/` (`reviews:create`), login required
    - a `_slot.html` partial shared by the page and the create response
    - a `_form.html` partial with DaisyUI star radios, errors beside
      each field, and an HTMX post that swaps `#review-slot`
    - invalid posts re-render the form with what was typed and send no
      out-of-band summary
    - a losing simultaneous submission gets 403
    - "Pick a rating from 1 to 5 stars." for a missing or out-of-range
      rating
    - the form replaces the Phase 1 placeholder
  - The suite went from 402 to 428 passing, and Ruff is clean.
- **Deviations:** No recommendations were overridden. Made without
  asking: invalid posts answer 200, so HTMX swaps the errors in; a lost
  simultaneous submission answers 403 rather than a form error; the
  slot states moved from `detail.html` into `_slot.html`.
- **Sideways:**
  - The auto-mode safety check failed with "no verdict" on every shell
    command, twice. The first time, behavior 2's failing run had to be
    confirmed by the user before the agent could see it. Files were
    written with the file tools until the shell came back.
  - Behavior 1's first run failed on database access, not an
    assertion, because a ModelForm checks model constraints; the test
    got the `django_db` mark.
  - Behavior 3's first run failed on `DoesNotExist`, not an assertion;
    a count check was put ahead of the lookup.
  - A test expected the textarea's text right after `>`, but Django
    adds a newline there. A scripted fix silently didn't apply because
    of escaping, so it was redone with the Edit tool and checks a regex.
  - The real `db.sqlite3` was never migrated, and no real browser was
    opened.

## 2026-10-25 — Product reviews: wiped Phases 1–7 and rebuilt Phase 1 test-first

### Prompts
1. /implement @prd/product-reviews.md @plans/product-reviews.md implement
   phase 1
2. was /tdd properly used to check the phase
3. delete the implemented phase 1 through 7 and re implement them and
   update PROMPTS.md, commit the completed phase, and push it to GitHub
   between each phase
4. Answers to the agent's two questions: "Rewrite history, force-push"
   (how to delete) and "Stash and restore (Recommended)" (local edits)
5. approved,go ahead (the three TDD behaviors)
6. approved, go ahead (behavior 1's failing test)
7. approved, go ahead (behavior 1 green; finish `can_write`)
8. approved, go ahead (behavior 2's failing test)
9. approved,go ahead (behavior 2 green)
10. approved,go ahead (behavior 3's failing test)
11. approved, go ahead (behavior 3 green; finish the phase)

### Summary
- **Outcome:**
  - Prompt 1 found Phases 1–7 already built, merged to `main` (PR #5)
    and green (463 tests), so nothing was changed.
  - Prompt 2's answer: no. The earlier phase logs show no TDD selection,
    no failing tests and no approval stops. The `implement` skill's file
    was last changed after the Phase 1 commit, so the earlier run
    probably never called `tdd`.
  - After prompt 3, both `main` and `feature/product-reviews` were reset
    and force-pushed: `main` to `0db4e4d` (the account-security merge),
    and the branch to `9bb9f77` (PRD and plan only). Local backup
    branches `backup/main-with-pr5` and `backup/product-reviews-original`
    keep the old work. The user's uncommitted edits (`REFLECTION.md`,
    `db.sqlite3`, `media/products/`) are in `stash@{0}`, to be restored
    after the rebuild.
  - Phase 1 was rebuilt with the `tdd` skill. The user approved three
    behaviors, and each one went through an approved failing test
    before any code was written:
    1. `can_write` by order status.
    2. `summary`: average to one decimal and the count, with `None`
       when there are no reviews.
    3. `is_edited` / `is_edited_by_staff`.
  - The rest of the phase was built and tested normally:
    - the remaining `can_write` conditions (signed in, not staff, no
      existing review), in one query
    - `can_change`, `reviewer_name`, `for_display`, `excluding_author`
    - the constraints and migration
    - the `make_order` and `soulsear` fixtures
    - `ProductDetailView`'s review context
    - the Reviews section with each slot state and the empty state
    - the `_summary` and `_review` partials
    - the read-only admin with adding disabled
  - The suite went from 352 to 402 passing, and Ruff is clean.
- **Deviations:**
  - The user overrode the recommendation to revert on a new branch.
    They chose to rewrite history and force-push `main`, which also
    deleted the earlier PROMPTS.md entries for Phases 1–7, despite the
    log's never-delete rule.
  - Two choices were put to the user at the failing-test stops and
    accepted: the summary is a dict, and an edit counts after a gap of
    more than 1 second (`EDIT_GRACE`).
  - Made without asking: cards show the full name, falling back to the
    username; the slot states live inline in `detail.html`; the
    can-write placeholder reads "Reviews open here soon".
- **Sideways:**
  - The first test run passed the two-minute limit and finished in the
    background.
  - The reset left `reviews/` behind with only `__pycache__` in it,
    which was removed.
  - The sign-in link test expected `/` in `next` to be percent-encoded.
    Django's `urlencode` keeps it, as the add-to-cart link does, so the
    test was fixed.
  - Ruff reformatted `reviews/models.py`.
  - The real `db.sqlite3` was never migrated, and no real browser was
    opened.

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
