"""Account email workflows — the one judge of security mail.

The fourth deliberate deep module, alongside ``orders/services.py``,
``dashboard/queries.py`` and ``products/images.py``. Views never build
security mail themselves; they call in here.

Security notices always go to the account's *primary* address. The
customer cannot change the primary from the Security Center, so an
attacker holding a stolen session cannot silence the alarm.

A secondary email proves who owns the *inbox* through a signed
confirmation link; the forms that set one prove who owns the *account*
by asking for the current password.
"""

import hashlib
from enum import StrEnum

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse

from .models import User


class Notice(StrEnum):
    """A security-relevant event the account's owner is told about.

    Each value names its plain-text body template,
    ``accounts/email/notice_<value>.txt``.
    """

    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"
    SECONDARY_ADDED = "secondary_added"
    SECONDARY_REPLACED = "secondary_replaced"
    SECONDARY_CONFIRMED = "secondary_confirmed"
    SECONDARY_REMOVED = "secondary_removed"


_SUBJECTS = {
    Notice.PASSWORD_CHANGED: "Your ThoughtTronix password was changed",
    Notice.PASSWORD_RESET: "Your ThoughtTronix password was reset",
    Notice.SECONDARY_ADDED: "A secondary email was added to your ThoughtTronix account",
    Notice.SECONDARY_REPLACED: (
        "The secondary email on your ThoughtTronix account was replaced"
    ),
    Notice.SECONDARY_CONFIRMED: (
        "A secondary email was confirmed on your ThoughtTronix account"
    ),
    Notice.SECONDARY_REMOVED: (
        "The secondary email was removed from your ThoughtTronix account"
    ),
}

#: Seconds an address must wait between reset or confirmation emails.
MAIL_COOLDOWN_SECONDS = 60

_CONFIRM_SALT = "accounts.security.secondary-email-confirm"

LINK_NO_LONGER_WORKS = (
    "This confirmation link no longer works. It may have expired, or the "
    "address may have been replaced. Sign in and send a fresh link from "
    "your Account Security Center."
)
ADDRESS_CLAIMED = (
    "Another account has already claimed this address, so it can't be "
    "confirmed for yours. Sign in and choose a different secondary email."
)


class ConfirmationError(Exception):
    """A secondary-email confirmation that cannot go through. The message
    is plain language, fit to show the visitor."""


def send_security_notice(
    user: User, notice: Notice, *, address: str | None = None
) -> bool:
    """Tell the account's owner, at their primary email, that ``notice``
    happened. ``address`` is the secondary email the notice is about, if
    any, and appears in the body.

    Returns whether a notice was sent: a user with no primary email (one
    made in the admin, the shell or a test) gets none, which is not an
    error.
    """
    if not user.email:
        return False
    body = render_to_string(
        f"accounts/email/notice_{notice}.txt", {"user": user, "address": address}
    )
    send_mail(_SUBJECTS[notice], body, None, [user.email])
    return True


def claim_mail_cooldown(address: str) -> bool:
    """Claim the right to send a reset or confirmation email to ``address``.

    Returns ``True`` at most once per ``MAIL_COOLDOWN_SECONDS`` for an
    address, ignoring capitals; a caller that gets ``False`` skips the
    email silently and shows its usual message. The claim is a single
    atomic ``cache.add`` on Django's default cache, which is per process
    in development, so a multi-process deployment needs a shared cache
    for the limit to hold.
    """
    digest = hashlib.sha256(address.strip().lower().encode()).hexdigest()
    return cache.add(f"accounts:mail-cooldown:{digest}", True, MAIL_COOLDOWN_SECONDS)


# --- Secondary email ----------------------------------------------------------


def make_confirmation_token(user: User) -> str:
    """A signed, timestamped token naming ``user`` and their current pending
    secondary. It is checked against ``SECONDARY_EMAIL_CONFIRM_MAX_AGE``."""
    return signing.dumps(
        {"user": user.pk, "email": user.secondary_email}, salt=_CONFIRM_SALT
    )


def check_confirmation_token(token: str) -> tuple[User, str]:
    """Return the user and pending address a confirmation token is for.

    Raises ``ConfirmationError`` if the token is forged or expired, or if
    its address is no longer the user's pending secondary (replaced,
    removed or already confirmed). Changes nothing, so a GET may call it.
    """
    try:
        data = signing.loads(
            token,
            salt=_CONFIRM_SALT,
            max_age=settings.SECONDARY_EMAIL_CONFIRM_MAX_AGE,
        )
    except signing.BadSignature:
        raise ConfirmationError(LINK_NO_LONGER_WORKS) from None
    user = User.objects.filter(pk=data.get("user")).first()
    if (
        user is None
        or not user.has_pending_secondary_email
        or user.secondary_email != data.get("email")
    ):
        raise ConfirmationError(LINK_NO_LONGER_WORKS)
    return user, user.secondary_email


def send_secondary_confirmation(user: User, request: HttpRequest) -> bool:
    """Mail a confirmation link to ``user``'s pending secondary.

    Returns whether an email went out: nothing is sent when there is no
    pending secondary, or when the address is inside its mail cooldown.
    Either way the caller shows its usual message.
    """
    if not user.has_pending_secondary_email:
        return False
    if not claim_mail_cooldown(user.secondary_email):
        return False
    path = reverse(
        "accounts:secondary_email_confirm",
        kwargs={"token": make_confirmation_token(user)},
    )
    body = render_to_string(
        "accounts/email/secondary_confirm.txt",
        {
            "user": user,
            "address": user.secondary_email,
            "link": request.build_absolute_uri(path),
            "hours": settings.SECONDARY_EMAIL_CONFIRM_MAX_AGE // 3600,
        },
    )
    send_mail(
        "Confirm your ThoughtTronix secondary email",
        body,
        None,
        [user.secondary_email],
    )
    return True


def request_secondary_email(user: User, address: str, request: HttpRequest) -> bool:
    """Add or replace ``user``'s secondary with ``address``, unverified.

    The old secondary stops counting at once. Sends the confirmation link
    to ``address`` (subject to the cooldown) and the "added" or "replaced"
    notice to the primary. The caller has already checked the current
    password and the uniqueness rules. Returns whether the confirmation
    email went out.
    """
    if user.secondary_email:
        notice = Notice.SECONDARY_REPLACED
    else:
        notice = Notice.SECONDARY_ADDED
    user.set_secondary_email(address)
    sent = send_secondary_confirmation(user, request)
    send_security_notice(user, notice, address=address)
    return sent


def confirm_secondary_email(token: str) -> User:
    """Confirm the pending secondary a token is for, then tell the primary.

    Raises ``ConfirmationError`` if the token does not check out, or if
    another account has meanwhile claimed the address as a primary or
    verified secondary; the address then stays pending.
    """
    user, address = check_confirmation_token(token)
    try:
        user.confirm_secondary_email()
    except ValidationError:
        raise ConfirmationError(ADDRESS_CLAIMED) from None
    send_security_notice(user, Notice.SECONDARY_CONFIRMED, address=address)
    return user


def remove_secondary_email(user: User) -> bool:
    """Remove ``user``'s secondary, pending or verified, and tell the
    primary. Returns ``False`` (and sends nothing) if there was none."""
    address = user.secondary_email
    if not address:
        return False
    user.remove_secondary_email()
    send_security_notice(user, Notice.SECONDARY_REMOVED, address=address)
    return True
