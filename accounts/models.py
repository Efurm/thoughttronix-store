from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class User(AbstractUser):
    """The store's user model.

    Roles use Django's own vocabulary and nothing else: customers are
    plain users, employees are ``is_staff``, the admin is ``is_superuser``.

    The inherited ``email`` is the account's primary address. It is never
    a login credential. The database keeps it optional (admin-, shell- and
    test-made users may have none) but unique among non-blank values,
    ignoring capitals; the signup form is what makes it required.
    """

    # Nullable per the PRD: an absent job title is unknown, not empty.
    job_title = models.CharField(max_length=150, null=True, blank=True)  # noqa: DJ001

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                condition=~Q(email=""),
                name="accounts_user_unique_primary_email",
                violation_error_message="That email address is already in use.",
            ),
        ]
