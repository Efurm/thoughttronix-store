"""Order placement — one of the codebase's two deliberate deep modules.

The interface is the product: one function that turns a cart and a
validated checkout into an order, all-or-nothing. Callers never touch
``Order`` construction directly. ``quote_coupon`` is its companion: the
one place a discount code is judged and priced, shared by the checkout
preview and ``place_order`` itself.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db import IntegrityError, transaction

from .models import Cart, Coupon, CouponError, Order, OrderItem

CODE_FORMAT = re.compile(r"^[A-Z]{5}$")


@dataclass(frozen=True)
class CouponQuote:
    """A coupon priced against a cart: what it takes off, line by line.

    ``line_discounts`` maps product pk to that cart line's discount;
    lines the coupon doesn't cover are absent. ``discount`` is the sum
    of the line discounts, so the lines always add up to the order.
    """

    coupon: Coupon
    subtotal: Decimal
    line_discounts: dict[int, Decimal] = field(default_factory=dict)

    @property
    def discount(self) -> Decimal:
        return sum(self.line_discounts.values(), Decimal("0.00"))

    @property
    def total(self) -> Decimal:
        return self.subtotal - self.discount


def normalize_code(raw: str | None) -> str:
    """Trim and uppercase what the customer typed: ``" falls "`` → ``"FALLS"``."""
    return (raw or "").strip().upper()


def quote_coupon(
    code: str | None,
    cart: Cart,
    user: AbstractBaseUser,
    *,
    at: datetime | None = None,
) -> CouponQuote:
    """Price ``code`` against ``cart`` for ``user``, or say why it can't apply.

    The single source of truth for coupon eligibility: the checkout's
    live preview and ``place_order`` both call it, so they can never
    disagree. Each eligible line's discount is rounded half-up to the
    cent on its own.

    Raises ``CouponError`` — carrying the message to show the customer —
    when the code is malformed, unknown, retired, expired, not started,
    already used by this customer, or covers nothing in the cart.
    """
    code = normalize_code(code)
    if not CODE_FORMAT.match(code):
        raise CouponError("Codes are 5 letters.")
    coupon = Coupon.objects.filter(code=code).first()
    if coupon is None:
        raise CouponError("We don't recognize that code.")
    coupon.check_redeemable(at)
    if coupon.orders.filter(user=user).exists():
        raise CouponError("You've already used this code.")

    eligible = set(coupon.products.values_list("pk", flat=True))
    lines = list(cart.lines())
    line_discounts = {
        line.product_id: coupon.discount_on(line.line_total)
        for line in lines
        if not eligible or line.product_id in eligible
    }
    if not line_discounts:
        raise CouponError("This code doesn't apply to anything in your cart.")
    return CouponQuote(
        coupon=coupon,
        subtotal=sum((line.line_total for line in lines), Decimal("0.00")),
        line_discounts=line_discounts,
    )


ADDRESS_FIELDS = [
    "email",
    "shipping_name",
    "shipping_street",
    "shipping_line2",
    "shipping_city",
    "shipping_state",
    "shipping_zip",
    "billing_name",
    "billing_street",
    "billing_line2",
    "billing_city",
    "billing_state",
    "billing_zip",
]


@transaction.atomic
def place_order(
    cart: Cart,
    user: AbstractBaseUser,
    checkout_data: Mapping[str, Any],
    *,
    coupon_code: str | None = None,
) -> Order:
    """Create an order from the cart's contents, then empty the cart.

    ``checkout_data`` is the ``cleaned_data`` of a valid ``CheckoutForm``.
    Addresses and line prices are denormalized onto the order — an order
    is a snapshot, immune to later catalog or address edits. Of the card,
    only the last four digits are stored; the full number and CVV never
    touch the database.

    All-or-nothing: runs in a transaction, so a failure partway through
    leaves no partial order and the cart intact.

    ``coupon_code`` (blank or ``None`` for none) is re-checked here with
    ``quote_coupon`` even if the checkout previewed it — a code can
    expire or be retired in between. The code, percent, and per-line
    discounts are copied onto the order, and ``total`` is the amount
    after the discount.

    Raises ``ValueError`` if the cart is empty or holds a product that is
    no longer available, and its subclass ``CouponError`` if the coupon
    can't be used — in which case no order is placed, rather than
    charging a price the customer wasn't shown.
    """
    lines = list(cart.lines())
    if not lines:
        raise ValueError("Cannot place an order from an empty cart.")
    unavailable = [line.product.name for line in lines if not line.product.is_available]
    if unavailable:
        raise ValueError(
            f"No longer available: {', '.join(unavailable)}. "
            "Remove them from the cart to check out."
        )

    quote = (
        quote_coupon(coupon_code, cart, user) if normalize_code(coupon_code) else None
    )
    line_discounts = quote.line_discounts if quote else {}

    card_digits = checkout_data["card_number"].replace(" ", "").replace("-", "")
    try:
        # A savepoint, so a lost race on the once-per-customer constraint
        # surfaces as a CouponError rather than a broken transaction.
        with transaction.atomic():
            order = Order.objects.create(
                user=user,
                total=quote.total if quote else cart.total(),
                card_last4=card_digits[-4:],
                coupon=quote.coupon if quote else None,
                coupon_code=quote.coupon.code if quote else "",
                discount_percent=quote.coupon.percent_off if quote else None,
                discount_total=quote.discount if quote else Decimal("0.00"),
                **{name: checkout_data[name] for name in ADDRESS_FIELDS},
            )
    except IntegrityError as error:
        if quote is None:
            raise
        raise CouponError("You've already used this code.") from error
    for line in lines:
        OrderItem.objects.create(
            order=order,
            product=line.product,
            product_name=line.product.name,
            unit_price=line.product.price,
            quantity=line.quantity,
            discount=line_discounts.get(line.product_id, Decimal("0.00")),
        )
    cart.items.all().delete()
    return order
