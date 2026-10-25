from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from orders.models import Order, OrderItem
from products.models import Product

EDIT_GRACE = timedelta(seconds=1)

# How many reviews the product page lists at a time.
REVIEWS_PER_PAGE = 10


class ReviewQuerySet(models.QuerySet):
    def for_display(self):
        """Reviews with their authors and editors loaded, ready for cards."""
        return self.select_related("user", "updated_by")

    def excluding_author(self, user):
        """Everyone's reviews but ``user``'s (all of them when signed out)."""
        if not user.is_authenticated:
            return self
        return self.exclude(user=user)

    def can_write(self, user, product):
        """Whether ``user`` may write a new review of ``product``.

        Signed in, not staff, has the product on an order that isn't
        cancelled, and has no review of it yet. Availability doesn't
        matter, and a purchase never passes to another account.
        """
        if not user.is_authenticated or user.is_staff:
            return False
        return (
            OrderItem.objects.filter(order__user=user, product=product)
            .exclude(order__status=Order.Status.CANCELLED)
            .filter(~models.Exists(self.filter(user=user, product=product)))
            .exists()
        )

    def summary(self, product):
        """``{"average": ..., "count": ...}`` for ``product``'s reviews.

        One aggregate query. The average is rounded to one decimal place,
        and is ``None`` when the product has no reviews.
        """
        totals = self.filter(product=product).aggregate(
            average=models.Avg("rating"), count=models.Count("pk")
        )
        if totals["average"] is not None:
            totals["average"] = round(totals["average"], 1)
        return totals


class Review(models.Model):
    """One customer's rating and comment on a product they bought.

    One review per customer per product at a time; deleting it frees the
    slot. ``updated_by`` records who made the last edit, so a staff edit
    of a customer's words can be shown publicly.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    objects = ReviewQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="review_rating_1_to_5",
            ),
            models.UniqueConstraint(
                fields=["user", "product"], name="one_review_per_user_product"
            ),
        ]

    def __str__(self):
        return f"{self.rating}★ {self.product} by {self.user}"

    def can_change(self, user):
        """Whether ``user`` may edit or delete this review: its author,
        or any staff member."""
        return user.is_authenticated and (user.is_staff or user.pk == self.user_id)

    @property
    def reviewer_name(self):
        """The name shown on the card: full name, else username."""
        return self.user.get_full_name() or self.user.get_username()

    @property
    def is_edited(self):
        """Whether the review has been changed since it was written.

        Creating a review stamps ``created_at`` and ``updated_at`` a few
        microseconds apart, so only a gap beyond ``EDIT_GRACE`` counts.
        """
        return self.updated_at - self.created_at > EDIT_GRACE

    @property
    def is_edited_by_staff(self):
        """Whether ThoughtTronix staff made the last edit."""
        return (
            self.is_edited and self.updated_by is not None and self.updated_by.is_staff
        )
