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
