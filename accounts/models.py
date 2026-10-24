from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Q
from django.db.models.functions import Lower


class UserQuerySet(models.QuerySet):
    def with_address(self, address):
        """Users who hold ``address``, ignoring capitals, as their primary
        or as a *verified* secondary.

        These are the addresses that recover an account and that no two
        accounts may share. A pending secondary reserves nothing.
        """
        return self.filter(
            Q(email__iexact=address)
            | Q(secondary_email__iexact=address, secondary_email_verified=True)
        )


class StoreUserManager(UserManager.from_queryset(UserQuerySet)):
    """Django's user manager with the address lookups of ``UserQuerySet``."""


class User(AbstractUser):
    """The store's user model.

    Roles use Django's own vocabulary and nothing else: customers are
    plain users, employees are ``is_staff``, the admin is ``is_superuser``.

    The inherited ``email`` is the account's primary address. It is never
    a login credential. The database keeps it optional (admin-, shell- and
    test-made users may have none) but unique among non-blank values,
    ignoring capitals; the signup form is what makes it required.

    ``secondary_email`` is an optional recovery backup. It counts only once
    ``secondary_email_verified`` is set, and only verified secondaries are
    unique, so typing someone else's address as a pending secondary never
    blocks them.
    """

    # Nullable per the PRD: an absent job title is unknown, not empty.
    job_title = models.CharField(max_length=150, null=True, blank=True)  # noqa: DJ001
    # Nullable per the PRD: no secondary is absent, not an empty address.
    secondary_email = models.EmailField(null=True, blank=True)  # noqa: DJ001
    secondary_email_verified = models.BooleanField(default=False)

    objects = StoreUserManager()

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                condition=~Q(email=""),
                name="accounts_user_unique_primary_email",
                violation_error_message="That email address is already in use.",
            ),
            models.UniqueConstraint(
                Lower("secondary_email"),
                condition=Q(secondary_email_verified=True),
                name="accounts_user_unique_verified_secondary_email",
                violation_error_message="That email address is already in use.",
            ),
        ]

    def clean(self):
        """The cross-field rules a single database constraint cannot hold:
        a secondary is never the user's own primary, and no address is one
        user's primary and another user's verified secondary."""
        super().clean()
        others = type(self).objects.exclude(pk=self.pk)
        if self.secondary_email and self.email:
            if self.secondary_email.lower() == self.email.lower():
                raise ValidationError(
                    {"secondary_email": "Your secondary email can't be your primary."}
                )
        if (
            self.email
            and others.filter(
                secondary_email__iexact=self.email, secondary_email_verified=True
            ).exists()
        ):
            raise ValidationError(
                {"email": "That email address is another account's secondary."}
            )
        if (
            self.secondary_email
            and self.secondary_email_verified
            and others.filter(email__iexact=self.secondary_email).exists()
        ):
            raise ValidationError(
                {"secondary_email": "That email address is another account's primary."}
            )

    @property
    def has_pending_secondary_email(self):
        return bool(self.secondary_email) and not self.secondary_email_verified

    def set_secondary_email(self, address):
        """Add or replace the secondary. It always starts unverified, so the
        old address stops counting at once."""
        self.secondary_email = address
        self.secondary_email_verified = False
        self.save(update_fields=["secondary_email", "secondary_email_verified"])

    def remove_secondary_email(self):
        self.secondary_email = None
        self.secondary_email_verified = False
        self.save(update_fields=["secondary_email", "secondary_email_verified"])

    def confirm_secondary_email(self):
        """Mark the pending secondary verified.

        Raises ``ValidationError`` if another account already holds the
        address as a primary or verified secondary. The check runs in a
        transaction, and the verified-secondary constraint is the final
        judge of a race the check cannot see.
        """
        taken = ValidationError("Another account has already claimed that address.")
        try:
            with transaction.atomic():
                others = type(self).objects.exclude(pk=self.pk)
                if others.with_address(self.secondary_email).exists():
                    raise taken
                self.secondary_email_verified = True
                self.save(update_fields=["secondary_email_verified"])
        except IntegrityError:
            self.secondary_email_verified = False
            raise taken from None
        except ValidationError:
            self.secondary_email_verified = False
            raise
