# PRD: The ThoughtTronix Store — Account Security Center

*Commissioned by ThoughtTronix Customer Trust. "Your Thoughts, Our Business."*

---

## Problem Statement

A ThoughtTronix account holds a customer's order history and their shipping and billing addresses. Today, protecting that account is entirely up to the customer, who has almost nothing to work with:

- **Signup collects no email address.** The core platform deliberately asked for only a username and password, so the store has no way to reach a customer about their own account.
- **A forgotten password is a dead end.** There is no reset flow. A customer who forgets their password has lost their account.
- **There is no way to change a password.** A customer who suspects their password has leaked cannot rotate it.
- **There is no backup.** A customer who loses access to their main inbox has no second route back in.

Customers also get no warning when something about their account's security changes, so a hijacked account would go unnoticed.

## Solution

Signup asks for an email address, and every address belongs to exactly one account.

Every signed-in user gets an **Account Security Center**: a hub page, linked from the navbar, that shows the account's email addresses and links to focused one-form pages. From there a customer can:

- **Change their password** by confirming the old one.
- **Add a secondary email address** as a recovery backup. Adding or replacing it requires the current password. The address only starts working after the customer clicks a confirmation link sent to it. The customer can replace or remove it, or have the confirmation sent again.

A signed-out customer who has forgotten their password can **reset it through email**. They type either their primary or their verified secondary address, and a one-hour reset link goes to the address they typed. The page never reveals whether an account exists.

Every security-relevant change (password changed, password reset, secondary email added, replaced, confirmed or removed) triggers a short notice to the account's **primary** address. The primary cannot be changed by the customer, so the alert always reaches the real owner.

## User Stories

**Visitor**

1. As a visitor, I must provide an email address when I sign up, so that I can recover my account if I forget my password.
2. As a visitor, I am told plainly when the email I chose is already in use (ignoring capitals), so that I know to sign in or use a different address.
3. As a visitor, I still sign in with my username, so that signing in works the same way as before.

**Customer: Security Center**

4. As a signed-in customer, I can reach the Account Security Center from the navbar, so that I can find my security settings without hunting.
5. As a signed-in customer, I see my primary email and my secondary email (marked Pending or Verified) on the Security Center hub, so that I know which addresses can recover my account.
6. As a signed-in customer, I see a designed empty state where the secondary email would be when I have not added one, so that I understand I can add a backup.

**Customer: changing a password**

7. As a signed-in customer, I can change my password by entering my current password and a new one twice, so that I can rotate a password I think has leaked.
8. As a signed-in customer, I stay signed in on this device after changing my password, while every other session is signed out, so that a thief using an old session is locked out.
9. As a customer, I receive a notice at my primary email when my password is changed, so that I notice a change I did not make.

**Customer: forgotten password**

10. As a signed-out customer, I can request a password reset by typing my primary email or my verified secondary email, so that I can get back into my account.
11. As a signed-out customer, I receive the reset link only at the address I typed, so that links never land in an inbox I did not ask about.
12. As a signed-out customer, I see the same "if an account matches, we've sent a link" message whatever I type, so that nobody can use the page to find out which addresses have accounts.
13. As a customer, my reset link expires after one hour, stops working once used, and stops working if my password changes, so that a leaked email is only briefly dangerous.
14. As a customer, I can set a new password from the reset link and then sign in, so that the recovery finishes cleanly.
15. As a customer, I receive a notice at my primary email when my password is reset, so that I notice a reset I did not request.
16. As a customer, repeated reset requests for my address are limited to one email per minute, so that nobody can flood my inbox.

**Customer: secondary email**

17. As a signed-in customer, I can add a secondary email by typing it and confirming my current password, so that someone using my unattended session cannot plant their own recovery address.
18. As a signed-in customer, I am told plainly when the secondary I type is my own primary, or is already a primary or verified secondary on another account, so that I pick an address that will work.
19. As a customer, I receive a confirmation link at the new secondary address, valid for 24 hours, so that I can prove I control that inbox.
20. As a customer, I can open the confirmation link on any device, even when I am not signed in, and confirm by clicking a button, so that I can confirm from my phone, and so that email scanners that follow links cannot confirm for me.
21. As a customer, my secondary email is ignored by password reset until it is confirmed, so that a typo never receives a reset link.
22. As a signed-in customer, I can replace my secondary email (with my current password), which makes the old one stop counting at once and starts a new confirmation, so that I can fix a typo or switch addresses.
23. As a signed-in customer, I can remove my secondary email, so that an address I no longer use cannot recover my account.
24. As a signed-in customer, I can have the confirmation link sent again for a pending secondary, limited to one email per minute, so that an expired or lost link does not leave me stuck.
25. As a customer, a confirmation link for an address I have since replaced no longer works, so that only my current pending address can be confirmed.
26. As a customer, if someone else claims my pending address before I confirm it, my confirmation fails with a plain explanation, so that two accounts never share a verified address.
27. As a customer, typing an address as a pending secondary never blocks anyone else from signing up with it or verifying it, so that nobody can squat on someone else's email.
28. As a customer, I receive a notice at my primary email when a secondary email is added, replaced, confirmed or removed, so that I notice a change I did not make.

**Employee / admin**

29. As an employee or admin, I can use the same Security Center as customers, so that I can manage my own password and recovery email.
30. As an admin, I can still change any user's primary email through the Django admin, so that a customer with a dead primary inbox can be helped.

## Implementation Decisions

**User model**

- `accounts.User` keeps Django's username-based authentication unchanged. Email is never a login credential.
- The inherited `email` field becomes the **primary** email. It is unique among non-blank values, ignoring capitals, through a conditional unique constraint on the lowercased address. The database does not require it; the signup form does. Users created in the Django admin, the shell or tests may still have no email, and such a user simply cannot reset a password.
- Two new fields: a nullable `secondary_email` and a `secondary_email_verified` flag.
- A second conditional unique constraint covers lowercased `secondary_email` **only where it is verified**. Pending secondaries reserve nothing, which prevents squatting.
- `User.clean` checks the rules a single database constraint cannot: a secondary may not equal the user's own primary, and an address may not be both one user's primary and another user's verified secondary.
- Model methods own the data rules: setting a secondary (always resets it to unverified), removing it, and confirming it. Confirmation runs inside a transaction, re-checks that no other account has claimed the address as a primary or verified secondary, and leaves the database constraint as the final judge of a race.
- The primary email is not editable by the customer anywhere in the Security Center. It stays editable in the Django admin.

**The `accounts/security.py` deep module**

- The fourth deliberate deep module, alongside `orders/services.py`, `dashboard/queries.py` and `products/images.py`. It is the one judge of account email workflows. Every public function has a docstring and type hints, and `CLAUDE.md` is updated from "exactly three" to "exactly four".
- Responsibilities: requesting a secondary email (set it, then send the confirmation), building and checking the signed confirmation token, confirming it, sending security notices, and the mail cooldown.
- **Confirmation tokens** use Django's `signing` module with a salt. The token carries the user's id and the pending address, and is checked with a `max_age`. A token for an address that is no longer the user's pending secondary is rejected.
- **Security notices:** one helper sends a short notice to the user's primary for each event (password changed, password reset, secondary added/replaced, secondary confirmed, secondary removed). There is one plain-text email template per event. A user with no primary gets no notice.
- **Cooldown:** before sending a reset or confirmation email, the module atomically claims a cache key for that address with a 60-second timeout. If the key already exists, the email is skipped silently and the user sees the same message as usual. The cooldown uses Django's default cache.

**Signup**

- The signup form adds a required email field and rejects an address already used as any account's primary or verified secondary, ignoring capitals, with a plain-language error. Addresses are stored as typed; comparisons ignore capitals.
- Signup still ends at the login page; auto-login stays out of scope.

**Change password**

- Django's stock `PasswordChangeView` and its done page, styled with DaisyUI and extended to send the "password changed" notice. Django's session-hash behavior keeps the current session and signs out every other one.

**Password reset**

- Django's stock four-step flow: request → done → confirm → complete.
- A custom form subclasses `PasswordResetForm` and overrides `get_users` to match the typed address, ignoring capitals, against the primary **or** a verified secondary. The email is sent to the address typed, not automatically to the primary.
- The request applies the cooldown. The complete step sends the "password reset" notice.
- `PASSWORD_RESET_TIMEOUT` is read through environs and defaults to one hour.

**Secondary email**

- An add/replace form with the address and the current password. The form validates the password and the uniqueness rules, and the view hands off to the security module.
- Remove and resend are single POST buttons on the hub, with no password required. Resend only works while a secondary is pending and applies the cooldown.
- The confirmation link opens a page that does not require sign-in and shows the address with a **Confirm** button that POSTs. A GET never changes data.
- The confirmation lifetime is read through environs as `SECONDARY_EMAIL_CONFIRM_MAX_AGE` and defaults to 24 hours.

**URLs and views**

- Every view is a thin class-based view. The Security Center views use `LoginRequiredMixin`, except the reset flow and the confirmation page.
- All URLs are named under the `accounts` namespace and live under `/accounts/`: the hub at `/accounts/security/`, plus change password, secondary add/replace, remove, resend, confirm, and the four reset steps.
- The navbar shows a link to the Security Center next to "Hi, username" for every signed-in user. The login page links to "Forgot your password?".

**Templates**

- Every page extends `templates/base.html` (storefront shell, not the back-office shell), even for staff.
- Hub plus focused pages, one form per page. No HTMX is needed.
- Tailwind + DaisyUI classes only; form widgets carry DaisyUI classes the same way the existing signup and login forms do.

**Email**

- The console backend stays. Every reset link, confirmation link and notice appears in the `runserver` terminal.

**Data and seed**

- One migration adds the two fields and the two conditional unique constraints. Existing data already satisfies them: every seeded user has a distinct `username@example.com` address.
- The seed's demo users keep their primaries and get no secondary.

**Build order** (the suite is green at each boundary)

1. Email at signup: required field, primary constraint, migration, fixtures given emails.
2. Security Center hub, change password, the notice helper and the "password changed" notice.
3. Forgotten password: reset views, the custom `get_users` (primary only at this stage), timeout setting, cooldown, "password reset" notice, login-page link.
4. Secondary email: fields, verified-only constraint, add/replace, the POST confirmation, remove, resend, notices, and reset extended to verified secondaries.

## Testing Decisions

- pytest + pytest-django, with plain fixtures in the project-level `conftest.py`. The shared `customer` and `staff_user` fixtures gain realistic primaries matching the seed (`customer@example.com`, `employee@example.com`). At least one existing test keeps creating a user with no email, to show that case stays valid.
- Mail is asserted through Django's test outbox (`mail.outbox`): the recipient, the presence of a link, and the notice for each event.
- Constraint tests: duplicate primaries that differ only in capitals are rejected; two blank primaries are allowed; two users may hold the same pending secondary; a second verified copy of an address is rejected.
- Workflow tests cover the security module directly: an expired token, a token for a replaced address, the confirmation race, and the cooldown. A second send within the window sends nothing.
- Reset tests: matching by primary, by verified secondary, not by pending secondary; the link goes to the typed address; the response is identical for unknown addresses.
- Access tests: the hub and its forms redirect signed-out users to login; the confirmation page works signed out; GET on the confirmation page changes nothing.
- The cache is cleared between tests, so cooldowns never leak across them.
- Tests never invoke the seed command.

## Out of Scope

- **Changing the primary email** from the Security Center. A future extension: promoting a verified secondary to primary (swapping the two).
- **Verifying the primary email** at signup.
- **More than one secondary email**, and any separate email-address table.
- **Signing in with an email address.** Authentication stays username-based.
- **django-allauth, django-ratelimit** or any other auth or rate-limit dependency.
- **Real email delivery.** The console backend stays; configuring SMTP or a mail service is a deployment task.
- **Two-factor authentication**, login history, active-session lists, and account deletion.
- **Auto-login after signup or after password reset.**
- **A back-office copy** of the Security Center.

## Further Notes

- **This revises the core platform PRD.** Story 6 there ("no email — Django's stock signup fields") is superseded by stories 1–2 here.
- **The cooldown is a speed bump in development.** Django's default in-memory cache is per process, so a multi-process deployment needs a shared cache (Redis or the database cache) for the 60-second limit to hold. This joins media serving as an open deployment task.
- **Why the primary is the alarm bell:** the customer cannot change it, so an attacker in a stolen session cannot silence the notices. Verification of the secondary proves who owns the *inbox*; requiring the current password proves who owns the *account*. The design needs both.
- **Staff recovery:** staff use the same flow, so a staff account can be recovered through a verified secondary. Adding one requires the password and alerts the primary, which is judged enough for this project.
