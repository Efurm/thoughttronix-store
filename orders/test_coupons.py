"""Seasonal discount codes: pricing, every rejection, the order snapshot,
the checkout preview, and back-office management."""

from datetime import datetime, timedelta
from decimal import Decimal
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.urls import reverse
from django.utils import timezone

from products.models import Product

from . import services
from .models import Cart, CartItem, Coupon, CouponError, Order
from .services import place_order, quote_coupon
from .test_checkout_form import VALID_DATA

pytestmark = pytest.mark.django_db


@pytest.fixture
def clock(category):
    return Product.objects.create(
        name="Whisper Alarm Clock",
        slug="whisper-alarm-clock",
        price=Decimal("49.99"),
        category=category,
    )


@pytest.fixture
def mixed_cart(cart, cart_item, clock):
    """Two Seraphine hubs ($699.98) and one clock ($49.99)."""
    CartItem.objects.create(cart=cart, product=clock, quantity=1)
    return cart


@pytest.fixture
def other_customer(db):
    return get_user_model().objects.create_user(username="other", password="other123")


def rejection(code, cart, user):
    with pytest.raises(CouponError) as error:
        quote_coupon(code, cart, user)
    return str(error.value)


# --- Pricing --------------------------------------------------------------------


def test_an_order_wide_code_discounts_every_line(cart, cart_item, coupon):
    quote = quote_coupon("FALLS", cart, cart.user)

    # 15% of 699.98 = 104.997, rounded half-up to the cent.
    assert quote.subtotal == Decimal("699.98")
    assert quote.discount == Decimal("105.00")
    assert quote.total == Decimal("594.98")


def test_a_product_code_discounts_only_its_products(mixed_cart, coupon, clock):
    coupon.percent_off = 25
    coupon.save()
    coupon.products.set([clock])

    quote = quote_coupon("FALLS", mixed_cart, mixed_cart.user)

    # 25% of 49.99 = 12.4975 → 12.50; the hubs are untouched.
    assert quote.line_discounts == {clock.pk: Decimal("12.50")}
    assert quote.total == Decimal("737.47")


def test_each_line_rounds_half_up(cart, coupon, category):
    item = Product.objects.create(
        name="Gel", slug="gel", price=Decimal("10.10"), category=category
    )
    cart.add(item)
    coupon.percent_off = 25
    coupon.save()

    # 2.525 rounds up to 2.53, not to the even 2.52.
    assert quote_coupon("FALLS", cart, cart.user).discount == Decimal("2.53")


def test_a_100_percent_code_makes_the_order_free(cart, cart_item, coupon):
    coupon.percent_off = 100
    coupon.save()

    assert quote_coupon("FALLS", cart, cart.user).total == Decimal("0.00")


def test_codes_are_trimmed_and_uppercased(cart, cart_item, coupon):
    assert quote_coupon("  falls ", cart, cart.user).coupon == coupon


# --- Rejections -----------------------------------------------------------------


@pytest.mark.parametrize("code", ["FALL", "FALLSS", "FALL5", "FA LS", "FÄLLS"])
def test_malformed_codes_are_rejected(cart, cart_item, coupon, code):
    assert rejection(code, cart, cart.user) == "Codes are 5 letters."


def test_an_unknown_code_is_rejected(cart, cart_item, coupon):
    assert rejection("WINTR", cart, cart.user) == "We don't recognize that code."


def test_an_expired_code_says_when_it_expired(cart, cart_item, coupon):
    coupon.starts_at = None
    coupon.ends_at = timezone.make_aware(datetime(2026, 9, 30, 12, 0))
    coupon.save()

    assert rejection("FALLS", cart, cart.user) == "This code expired on Sep 30, 2026."


def test_a_scheduled_code_isnt_active_yet(cart, cart_item, coupon):
    coupon.starts_at = timezone.now() + timedelta(days=1)
    coupon.save()

    assert rejection("FALLS", cart, cart.user) == "This code isn't active yet."


def test_a_retired_code_has_its_own_message(cart, cart_item, coupon):
    coupon.is_active = False
    coupon.save()

    assert rejection("FALLS", cart, cart.user) == "This code is no longer available."


def test_a_code_that_covers_nothing_in_the_cart_is_rejected(
    cart, cart_item, coupon, clock
):
    coupon.products.set([clock])

    assert (
        rejection("FALLS", cart, cart.user)
        == "This code doesn't apply to anything in your cart."
    )


def test_a_code_works_once_per_customer(cart, cart_item, coupon, other_customer):
    place_order(cart, cart.user, dict(VALID_DATA), coupon_code="FALLS")
    cart.add(cart_item.product)

    assert rejection("FALLS", cart, cart.user) == "You've already used this code."
    other_cart = Cart.for_user(other_customer)
    other_cart.add(cart_item.product)
    assert quote_coupon("FALLS", other_cart, other_customer).coupon == coupon


def test_a_cancelled_order_still_spends_the_code(cart, cart_item, coupon):
    order = place_order(cart, cart.user, dict(VALID_DATA), coupon_code="FALLS")
    order.status = Order.Status.CANCELLED
    order.save()
    cart.add(cart_item.product)

    assert rejection("FALLS", cart, cart.user) == "You've already used this code."


# --- place_order and the snapshot ----------------------------------------------


def test_place_order_snapshots_the_discount(mixed_cart, coupon, clock):
    coupon.products.set([clock])

    order = place_order(
        mixed_cart, mixed_cart.user, dict(VALID_DATA), coupon_code="falls"
    )

    assert order.coupon == coupon
    assert order.coupon_code == "FALLS"
    assert order.discount_percent == 15
    # 15% of 49.99 = 7.4985 → 7.50.
    assert order.discount_total == Decimal("7.50")
    assert order.total == Decimal("742.47")
    assert order.subtotal == Decimal("749.97")
    discounts = {item.product_name: item.discount for item in order.items.all()}
    assert discounts == {
        "Seraphine Home Hub": Decimal("0.00"),
        "Whisper Alarm Clock": Decimal("7.50"),
    }


def test_editing_or_retiring_a_code_never_changes_past_orders(cart, cart_item, coupon):
    order = place_order(cart, cart.user, dict(VALID_DATA), coupon_code="FALLS")

    coupon.percent_off = 50
    coupon.is_active = False
    coupon.save()
    order.refresh_from_db()

    assert order.total == Decimal("594.98")
    assert order.discount_total == Decimal("105.00")
    assert order.discount_percent == 15
    assert order.items.get().discount == Decimal("105.00")


def test_a_used_coupon_cant_be_deleted(cart, cart_item, coupon):
    place_order(cart, cart.user, dict(VALID_DATA), coupon_code="FALLS")

    with pytest.raises(ProtectedError):
        coupon.delete()


def test_a_code_that_went_bad_before_submit_places_no_order(cart, cart_item, coupon):
    quote_coupon("FALLS", cart, cart.user)  # the preview looked fine…
    coupon.is_active = False  # …then Marketing retired it.
    coupon.save()

    with pytest.raises(CouponError, match="no longer available"):
        place_order(cart, cart.user, dict(VALID_DATA), coupon_code="FALLS")
    assert not Order.objects.exists()
    assert cart.items.count() == 1


def test_losing_the_double_use_race_is_a_coupon_error(
    cart, cart_item, coupon, monkeypatch
):
    """Two checkouts at once both pass the quote; the constraint decides."""
    place_order(cart, cart.user, dict(VALID_DATA), coupon_code="FALLS")
    cart.add(cart_item.product)
    stale_quote = services.CouponQuote(
        coupon=coupon,
        subtotal=Decimal("349.99"),
        line_discounts={cart_item.product.pk: Decimal("52.50")},
    )
    monkeypatch.setattr(services, "quote_coupon", lambda *args, **kwargs: stale_quote)

    with pytest.raises(CouponError, match="already used"):
        place_order(cart, cart.user, dict(VALID_DATA), coupon_code="FALLS")
    assert Order.objects.count() == 1


# --- The checkout ---------------------------------------------------------------


def test_apply_previews_the_discount(client, cart, cart_item, coupon):
    client.force_login(cart.user)

    response = client.post(reverse("orders:apply_coupon"), {"coupon_code": "falls"})

    assert response.status_code == HTTPStatus.OK
    assert "orders/partials/_order_summary.html" in [t.name for t in response.templates]
    content = response.content.decode()
    assert "FALLS applied" in content
    assert "−$105.00" in content
    assert 'id="place-order-total" hx-swap-oob="true">$594.98' in content


@pytest.mark.parametrize("posted", [{"coupon_code": "SUMMR"}, {"coupon_code": "!!"}])
def test_apply_shows_a_message_never_an_error_page(
    client, cart, cart_item, coupon, posted
):
    client.force_login(cart.user)

    response = client.post(reverse("orders:apply_coupon"), posted)

    assert response.status_code == HTTPStatus.OK
    assert 'role="alert"' in response.content.decode()


def test_apply_with_no_code_clears_the_discount(client, cart, cart_item):
    client.force_login(cart.user)

    response = client.post(reverse("orders:apply_coupon"), {})

    assert response.status_code == HTTPStatus.OK
    assert response.context["quote"] is None
    assert response.context["coupon_error"] is None
    assert response.context["checkout_total"] == Decimal("699.98")


def test_apply_requires_login(client):
    response = client.post(reverse("orders:apply_coupon"), {"coupon_code": "FALLS"})

    assert response.status_code == HTTPStatus.FOUND


def test_checkout_with_a_code_places_a_discounted_order(
    client, cart, cart_item, coupon
):
    client.force_login(cart.user)

    response = client.post(
        reverse("orders:checkout"), {**VALID_DATA, "coupon_code": "FALLS"}
    )

    order = Order.objects.get()
    assert response.status_code == HTTPStatus.FOUND
    assert order.total == Decimal("594.98")
    assert order.coupon_code == "FALLS"


def test_checkout_with_an_expired_code_keeps_the_form_and_says_why(
    client, cart, cart_item, coupon
):
    coupon.starts_at = None
    coupon.ends_at = timezone.now() - timedelta(hours=1)
    coupon.save()
    client.force_login(cart.user)

    response = client.post(
        reverse("orders:checkout"), {**VALID_DATA, "coupon_code": "FALLS"}
    )

    assert response.status_code == HTTPStatus.OK
    assert not Order.objects.exists()
    content = response.content.decode()
    assert "This code expired on" in content
    assert "12 Cortex Lane" in content  # what they typed is still there


def test_the_checkout_page_explains_the_once_per_account_rule(client, cart, cart_item):
    client.force_login(cart.user)

    response = client.get(reverse("orders:checkout"))

    assert "Each code can be used once per account." in response.content.decode()


def test_the_order_pages_show_the_discount(client, cart, cart_item, coupon):
    order = place_order(cart, cart.user, dict(VALID_DATA), coupon_code="FALLS")
    client.force_login(cart.user)

    detail = client.get(reverse("orders:detail", args=[order.pk])).content.decode()
    confirmation = client.get(
        reverse("orders:confirmation", args=[order.pk])
    ).content.decode()

    assert "FALLS −$105.00" in detail
    assert "FALLS saved you $105.00" in confirmation


# --- The back office ------------------------------------------------------------


def coupon_form_data(**overrides):
    return {
        "code": "WINTR",
        "name": "Winter",
        "percent_off": "10",
        "starts_at": "",
        "ends_at": "2027-01-31T23:59",
        "is_active": "on",
        **overrides,
    }


def test_customers_cant_manage_coupons(client, customer):
    client.force_login(customer)

    response = client.get(reverse("orders:manage_coupons"))

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_the_coupon_list_has_a_designed_empty_state(client, staff_user):
    client.force_login(staff_user)

    response = client.get(reverse("orders:manage_coupons"))

    assert "No coupons yet" in response.content.decode()


def test_staff_create_a_coupon_without_engineering(client, staff_user, clock):
    client.force_login(staff_user)

    response = client.post(
        reverse("orders:manage_coupon_create"),
        coupon_form_data(code=" wintr ", products=[clock.pk]),
    )

    assert response.status_code == HTTPStatus.FOUND
    coupon = Coupon.objects.get()
    assert coupon.code == "WINTR"
    assert list(coupon.products.all()) == [clock]
    assert coupon.created_by == staff_user
    assert coupon.updated_by == staff_user


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"code": "WIN7R"}, "code"),
        ({"code": "WINTER"}, "code"),
        ({"percent_off": "0"}, "percent_off"),
        ({"percent_off": "101"}, "percent_off"),
        ({"ends_at": ""}, "ends_at"),
        ({"starts_at": "2027-02-01T00:00"}, "ends_at"),
    ],
)
def test_the_coupon_form_rejects_bad_input(client, staff_user, overrides, field):
    client.force_login(staff_user)

    response = client.post(
        reverse("orders:manage_coupon_create"), coupon_form_data(**overrides)
    )

    assert response.status_code == HTTPStatus.OK
    assert field in response.context["form"].errors
    assert not Coupon.objects.exists()


def test_codes_are_unique_across_retired_ones(client, staff_user, coupon):
    coupon.is_active = False
    coupon.save()
    client.force_login(staff_user)

    response = client.post(
        reverse("orders:manage_coupon_create"), coupon_form_data(code="FALLS")
    )

    assert "code" in response.context["form"].errors


def test_a_used_codes_text_is_locked(client, staff_user, cart, cart_item, coupon):
    place_order(cart, cart.user, dict(VALID_DATA), coupon_code="FALLS")
    client.force_login(staff_user)

    response = client.post(
        reverse("orders:manage_coupon_update", args=[coupon.pk]),
        coupon_form_data(code="AUTMN", percent_off="20"),
    )

    coupon.refresh_from_db()
    assert response.status_code == HTTPStatus.FOUND
    assert coupon.code == "FALLS"
    assert coupon.percent_off == 20
    assert coupon.updated_by == staff_user


def test_an_unused_code_can_be_deleted(client, staff_user, coupon):
    client.force_login(staff_user)

    client.post(reverse("orders:manage_coupon_delete", args=[coupon.pk]))

    assert not Coupon.objects.exists()


def test_deleting_a_used_code_points_to_retiring(
    client, staff_user, cart, cart_item, coupon
):
    place_order(cart, cart.user, dict(VALID_DATA), coupon_code="FALLS")
    client.force_login(staff_user)

    response = client.post(
        reverse("orders:manage_coupon_delete", args=[coupon.pk]), follow=True
    )

    assert Coupon.objects.filter(pk=coupon.pk).exists()
    assert "retire it instead" in response.content.decode()


def test_retiring_a_code_leaves_its_orders_alone(
    client, staff_user, cart, cart_item, coupon
):
    order = place_order(cart, cart.user, dict(VALID_DATA), coupon_code="FALLS")
    client.force_login(staff_user)

    client.post(reverse("orders:manage_coupon_retire", args=[coupon.pk]))

    coupon.refresh_from_db()
    order.refresh_from_db()
    assert not coupon.is_active
    assert coupon.updated_by == staff_user
    assert order.total == Decimal("594.98")
    assert order.coupon_code == "FALLS"
