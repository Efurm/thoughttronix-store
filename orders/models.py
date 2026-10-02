from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.utils import dateformat, timezone

from products.models import Product


class Cart(models.Model):
    """A customer's cart — one per user, created lazily on first touch."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
    )

    def __str__(self):
        return f"Cart for {self.user.username}"

    @classmethod
    def for_user(cls, user):
        """Return the user's cart, creating it on first touch."""
        cart, _ = cls.objects.get_or_create(user=user)
        return cart

    def add(self, product):
        """Add a product to the cart; a duplicate add increments its line."""
        item, created = self.items.get_or_create(product=product)
        if not created:
            item.quantity += 1
            item.save()
        return item

    def lines(self):
        """Line items with their products loaded, ready for display."""
        return self.items.select_related("product")

    def total(self):
        return sum((item.line_total for item in self.lines()), Decimal("0.00"))

    def item_count(self):
        """Total units across all lines — the navbar badge number."""
        return self.items.aggregate(count=models.Sum("quantity"))["count"] or 0


class CartItem(models.Model):
    """One product line in a cart; the cart–product pair is unique."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"], name="unique_cart_product"
            )
        ]

    def __str__(self):
        return f"{self.quantity} × {self.product.name}"

    @property
    def line_total(self):
        return self.product.price * self.quantity

    def increment(self):
        self.quantity += 1
        self.save()

    def decrement(self):
        """Step the quantity down, stopping at one — removal is explicit."""
        if self.quantity > 1:
            self.quantity -= 1
            self.save()


CENT = Decimal("0.01")


class CouponError(ValueError):
    """A code the customer can't use, carrying the message to show them."""


class Coupon(models.Model):
    """A seasonal discount code, managed by staff in the back office.

    A percentage off the products' own prices — of the whole order when
    ``products`` is empty, of just those products otherwise. Usable while
    active and inside its window (``starts_at`` inclusive, ``ends_at``
    exclusive), once per customer. Orders keep their own copy of the
    code and discount, so editing or retiring a coupon never rewrites
    an order that already used it.
    """

    code = models.CharField(
        max_length=5,
        unique=True,
        validators=[RegexValidator(r"^[A-Z]{5}$", "Codes are exactly 5 letters, A–Z.")],
        help_text="5 letters, A–Z. Locked once a customer has used it.",
    )
    name = models.CharField(
        "Promotion",
        max_length=100,
        blank=True,
        help_text="For staff only, e.g. “Fall 2026”.",
    )
    percent_off = models.PositiveSmallIntegerField(
        "Percent off",
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    products = models.ManyToManyField(
        Product,
        blank=True,
        related_name="coupons",
        help_text="Leave empty to discount the whole order.",
    )
    starts_at = models.DateTimeField(
        "Starts", null=True, blank=True, help_text="Optional — empty means now."
    )
    ends_at = models.DateTimeField("Ends", help_text="The code stops working here.")
    is_active = models.BooleanField(
        "Active", default=True, help_text="Turn off to retire the code early."
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ends_at", "code"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(percent_off__gte=1, percent_off__lte=100),
                name="coupon_percent_1_to_100",
            ),
            models.CheckConstraint(
                condition=models.Q(starts_at__isnull=True)
                | models.Q(starts_at__lt=models.F("ends_at")),
                name="coupon_starts_before_it_ends",
            ),
        ]

    def __str__(self):
        return self.code

    @property
    def is_used(self):
        """Whether any order has used the code. A used code can't be
        renamed or deleted — only retired."""
        return self.orders.exists()

    def status(self, at=None):
        """``"retired"``, ``"expired"``, ``"scheduled"``, or ``"live"``."""
        at = at or timezone.now()
        if not self.is_active:
            return "retired"
        if at >= self.ends_at:
            return "expired"
        if self.starts_at and at < self.starts_at:
            return "scheduled"
        return "live"

    def check_redeemable(self, at=None):
        """Raise ``CouponError`` with the customer-facing reason if the
        code can't be used at ``at`` (default now)."""
        status = self.status(at)
        if status == "retired":
            raise CouponError("This code is no longer available.")
        if status == "expired":
            ended = dateformat.format(timezone.localtime(self.ends_at), "M j, Y")
            raise CouponError(f"This code expired on {ended}.")
        if status == "scheduled":
            raise CouponError("This code isn't active yet.")

    def discount_on(self, amount):
        """The discount on ``amount``, rounded half-up to the cent."""
        return (amount * self.percent_off / 100).quantize(CENT, ROUND_HALF_UP)


class Order(models.Model):
    """A placed order — a snapshot, never a live view of the catalog.

    Addresses are flat denormalized fields: the order must not change if
    the customer later edits anything. Of the card, only the last four
    digits survive checkout. A coupon is snapshotted the same way:
    ``coupon_code``, ``discount_percent`` and ``discount_total`` are
    copies, and ``total`` is what the customer paid, after the discount.
    The ``coupon`` FK records the use (once per customer) and protects
    a used coupon from deletion.
    """

    class Status(models.TextChoices):
        PLACED = "PLACED", "Placed"
        SHIPPED = "SHIPPED", "Shipped"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PLACED
    )
    total = models.DecimalField(max_digits=10, decimal_places=2)
    email = models.EmailField()

    shipping_name = models.CharField(max_length=100)
    shipping_street = models.CharField(max_length=200)
    shipping_line2 = models.CharField(max_length=200, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=2)
    shipping_zip = models.CharField(max_length=10)

    billing_name = models.CharField(max_length=100)
    billing_street = models.CharField(max_length=200)
    billing_line2 = models.CharField(max_length=200, blank=True)
    billing_city = models.CharField(max_length=100)
    billing_state = models.CharField(max_length=2)
    billing_zip = models.CharField(max_length=10)

    card_last4 = models.CharField(max_length=4)

    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders",
    )
    coupon_code = models.CharField(max_length=5, blank=True)
    discount_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    discount_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    # default (not auto_now_add) so the seed can backdate orders.
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["coupon", "user"],
                condition=models.Q(coupon__isnull=False),
                name="coupon_once_per_customer",
            )
        ]

    def __str__(self):
        return self.number

    @property
    def subtotal(self):
        """The products' price before any discount."""
        return self.total + self.discount_total

    @property
    def number(self):
        """The customer-facing order number, e.g. ``TT-2026-00042``."""
        return f"TT-{self.created_at.year}-{self.pk:05d}"


class OrderItem(models.Model):
    """One line of an order, priced as of purchase time.

    Name and unit price are denormalized: order history must not change
    when the catalog does. The product FK survives for linking while the
    product exists.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"

    @property
    def line_total(self):
        """The line at its purchase-time price, before any discount."""
        return self.unit_price * self.quantity

    @property
    def net_total(self):
        """What the customer paid for the line, after its discount."""
        return self.line_total - self.discount
