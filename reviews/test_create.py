import re
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from orders.models import Order

from .models import Review

pytestmark = pytest.mark.django_db

VALID = {"rating": 5, "comment": "Hears everything. Even the thoughts."}


def create(client, product, data=VALID):
    return client.post(reverse("reviews:create", args=[product.pk]), data)


@pytest.fixture
def ineligible(request, customer, staff_user, product, soulsear, make_order):
    """The (user, product) pair for each way of not being allowed to write."""
    if request.param == "no order":
        return customer, product
    if request.param == "cancelled order":
        make_order(customer, product, Order.Status.CANCELLED)
        return customer, product
    if request.param == "soulsear next of kin":
        make_order(customer, soulsear, Order.Status.DELIVERED)
        return get_user_model().objects.create_user(username="kin"), soulsear
    if request.param == "staff":
        make_order(staff_user, product)
        return staff_user, product
    if request.param == "already reviewed":
        make_order(customer, product)
        Review.objects.create(
            user=customer, product=product, rating=3, comment="My first take."
        )
        return customer, product
    raise ValueError(request.param)


@pytest.mark.parametrize(
    "ineligible",
    [
        "no order",
        "cancelled order",
        "soulsear next of kin",
        "staff",
        "already reviewed",
    ],
    indirect=True,
)
def test_create_is_forbidden_when_the_user_cannot_write(client, ineligible):
    user, product = ineligible
    before = Review.objects.count()
    client.force_login(user)

    response = create(client, product)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert Review.objects.count() == before


def test_valid_create_saves_the_review_and_returns_card_and_oob_summary(
    client, customer, product, make_order
):
    make_order(customer, product)
    someone_else = get_user_model().objects.create_user(username="someone")
    client.force_login(customer)

    response = create(client, product, {**VALID, "user": someone_else.pk})

    assert Review.objects.count() == 1
    review = Review.objects.get()
    content = response.content.decode()
    assert response.status_code == HTTPStatus.OK
    assert review.user == customer
    assert review.product == product
    assert (review.rating, review.comment) == (5, VALID["comment"])
    assert f'id="review-{review.pk}"' in content
    assert VALID["comment"] in content
    assert 'id="review-summary"' in content
    assert 'hx-swap-oob="true"' in content
    assert "1 review" in content


def test_signed_out_create_redirects_to_login(client, product):
    response = create(client, product)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(reverse("accounts:login"))
    assert not Review.objects.exists()


def test_create_for_a_missing_product_is_not_found(client, customer):
    client.force_login(customer)

    response = client.post(reverse("reviews:create", args=[999]), VALID)

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_create_only_accepts_post(client, customer, product, make_order):
    make_order(customer, product)
    client.force_login(customer)

    response = client.get(reverse("reviews:create", args=[product.pk]))

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


def test_created_card_sits_under_the_your_review_heading(
    client, customer, product, make_order
):
    make_order(customer, product)
    client.force_login(customer)

    content = create(client, product).content.decode()

    assert content.index("Your review") < content.index(VALID["comment"])
    assert "<form" not in content
    assert "<html" not in content


def test_comment_is_saved_trimmed(client, customer, product, make_order):
    make_order(customer, product)
    client.force_login(customer)

    create(client, product, {"rating": 3, "comment": "   Ten chars!   "})

    assert Review.objects.get().comment == "Ten chars!"


@pytest.mark.parametrize(
    ("data", "field_error"),
    [
        ({"rating": 4, "comment": "Too short"}, "at least 10 characters"),
        ({"rating": 4, "comment": "    "}, "Tell us what you thought."),
        ({"comment": VALID["comment"]}, "Pick a rating from 1 to 5 stars."),
        ({"rating": 0, "comment": VALID["comment"]}, "Pick a rating"),
        ({"rating": 6, "comment": VALID["comment"]}, "Pick a rating"),
    ],
    ids=["short", "blank", "no rating", "rating 0", "rating 6"],
)
def test_invalid_create_returns_the_form_with_errors_and_saves_nothing(
    client, customer, product, make_order, data, field_error
):
    make_order(customer, product)
    client.force_login(customer)

    response = create(client, product, data)
    content = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert not Review.objects.exists()
    assert field_error in content
    assert f'hx-post="{reverse("reviews:create", args=[product.pk])}"' in content
    assert "hx-swap-oob" not in content


def test_invalid_create_keeps_what_was_typed(client, customer, product, make_order):
    make_order(customer, product)
    client.force_login(customer)

    content = create(
        client, product, {"rating": 2, "comment": "Too short"}
    ).content.decode()

    assert re.search(r">\s*Too short</textarea>", content)
    assert re.search(r'value="2"[^>]*checked', content)
    assert content.count("checked") == 1


def test_buyer_of_an_unavailable_product_can_review_it(
    client, customer, unavailable_product, make_order
):
    make_order(customer, unavailable_product)
    client.force_login(customer)

    response = create(client, unavailable_product)

    assert response.status_code == HTTPStatus.OK
    assert Review.objects.filter(product=unavailable_product).exists()


def test_soulsear_buyer_can_review_it(client, customer, soulsear, make_order):
    make_order(customer, soulsear, Order.Status.SHIPPED)
    client.force_login(customer)

    response = create(client, soulsear)

    assert response.status_code == HTTPStatus.OK
    assert Review.objects.get().user == customer


def test_summary_in_the_response_counts_every_review(
    client, customer, product, make_order
):
    other = get_user_model().objects.create_user(username="other")
    Review.objects.create(user=other, product=product, rating=3, comment="Fine.")
    make_order(customer, product)
    client.force_login(customer)

    content = create(client, product).content.decode()

    assert "4.0" in content
    assert "2 reviews" in content
