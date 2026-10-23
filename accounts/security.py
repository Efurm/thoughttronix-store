"""Account email workflows — the one judge of security mail.

The fourth deliberate deep module, alongside ``orders/services.py``,
``dashboard/queries.py`` and ``products/images.py``. Views never build
security mail themselves; they call in here.

Security notices always go to the account's *primary* address. The
customer cannot change the primary from the Security Center, so an
attacker holding a stolen session cannot silence the alarm.
"""

from enum import StrEnum

from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import User


class Notice(StrEnum):
    """A security-relevant event the account's owner is told about.

    Each value names its plain-text body template,
    ``accounts/email/notice_<value>.txt``.
    """

    PASSWORD_CHANGED = "password_changed"


_SUBJECTS = {
    Notice.PASSWORD_CHANGED: "Your ThoughtTronix password was changed",
}


def send_security_notice(user: User, notice: Notice) -> bool:
    """Tell the account's owner, at their primary email, that ``notice``
    happened.

    Returns whether a notice was sent: a user with no primary email (one
    made in the admin, the shell or a test) gets none, which is not an
    error.
    """
    if not user.email:
        return False
    body = render_to_string(f"accounts/email/notice_{notice}.txt", {"user": user})
    send_mail(_SUBJECTS[notice], body, None, [user.email])
    return True
