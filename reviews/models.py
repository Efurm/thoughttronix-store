from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from orders.models import Order, OrderItem
from products.models import Product

# How many reviews the product page shows at a time.
REVIEWS_PER_PAGE = 10

# auto_now_add and auto_now stamp a new row microseconds apart; a review
# counts as edited only once updated_at is later than this.
EDIT_GRACE = timedelta(seconds=1)


class ReviewSummary(NamedTuple):
    """A product's average rating (one decimal, ``None`` with no reviews)
    and its review count."""

    average: Decimal | None
    count: int


class ReviewQuerySet(models.QuerySet):
    def can_write(self, user, product: Product) -> bool:
        """Whether ``user`` may write a new review of ``product``.

        They must be signed in and not staff, must have bought the product
        on an order that wasn't cancelled, and must have no review of it
        already. Eligibility belongs to the account on the order, so no
        other account (a relative's included) inherits a purchase.
        Availability and the product's category make no difference.
        """
        if not user.is_authenticated or user.is_staff:
            return False
        bought = (
            OrderItem.objects.filter(order__user=user, product=product)
            .exclude(order__status=Order.Status.CANCELLED)
            .exists()
        )
        return bought and not self.filter(user=user, product=product).exists()

    def summary(self, product: Product) -> ReviewSummary:
        """The average rating and count of ``product``'s reviews, from one
        aggregate query."""
        totals = self.filter(product=product).aggregate(
            average=models.Avg("rating"), count=models.Count("pk")
        )
        average = totals["average"]
        if average is not None:
            average = Decimal(str(average)).quantize(Decimal("0.1"), ROUND_HALF_UP)
        return ReviewSummary(average=average, count=totals["count"])

    def excluding_author(self, user):
        """Reviews not written by ``user`` — everyone's, when signed out."""
        if not user.is_authenticated:
            return self
        return self.exclude(user=user)

    def page(self, number: int, size: int = REVIEWS_PER_PAGE):
        """Page ``number`` (from 1) of these reviews, and whether more follow."""
        start = (number - 1) * size
        batch = list(self[start : start + size + 1])
        return batch[:size], len(batch) > size


class Review(models.Model):
    """A customer's star rating and comment on a product they bought.

    One per customer per product at a time; deleting it frees the slot.
    ``comment`` is plain text, rendered escaped with its line breaks kept.
    ``updated_by`` records who last edited it, so a staff edit can be
    shown as one.
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
                fields=["user", "product"], name="one_review_per_customer_product"
            ),
        ]

    def __str__(self):
        return f"{self.user} on {self.product}: {self.rating}★"

    def can_change(self, user) -> bool:
        """Whether ``user`` may edit or delete this review: its author, or
        any staff member."""
        return user.is_authenticated and (user.pk == self.user_id or user.is_staff)

    @property
    def is_edited(self) -> bool:
        """True once the review has been changed after it was written."""
        return self.updated_at - self.created_at > EDIT_GRACE

    @property
    def is_edited_by_staff(self) -> bool:
        """True when a staff member made the last edit."""
        return self.updated_by is not None and self.updated_by.is_staff
