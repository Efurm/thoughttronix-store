"""Writing a review: the form's rules and the create endpoint."""

from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from orders.models import Order

from .forms import ReviewForm
from .models import Review

pytestmark = pytest.mark.django_db

SUMMARY_OOB = 'id="review-summary"'


@pytest.fixture
def next_of_kin(db):
    return get_user_model().objects.create_user(
        username="kin", email="kin@example.com", password="kin123"
    )


def form_with(comment, rating=5):
    return ReviewForm(data={"rating": rating, "comment": comment})


def create(client, product, rating=5, comment="Hears me before I speak."):
    return client.post(
        reverse("reviews:create", args=[product.pk]),
        {"rating": rating, "comment": comment},
    )


# --- Form ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "comment",
    [
        "x" * 9,
        " " * 20,
        "   " + "x" * 9 + "   ",  # padded to look long enough
        "x" * 2001,
    ],
    ids=["nine", "whitespace-only", "nine-padded", "2001"],
)
def test_comments_outside_ten_to_two_thousand_are_rejected(comment):
    form = form_with(comment)

    assert not form.is_valid()
    assert "comment" in form.errors


@pytest.mark.parametrize("length", [10, 2000])
def test_comments_at_the_limits_are_accepted(length):
    assert form_with("x" * length).is_valid()


def test_the_comment_is_trimmed():
    form = form_with("  Listens beautifully.  ")

    assert form.is_valid()
    assert form.cleaned_data["comment"] == "Listens beautifully."


@pytest.mark.parametrize("rating", ["", 0, 6, "five"])
def test_a_rating_must_be_one_to_five_whole_stars(rating):
    form = form_with("Listens beautifully.", rating=rating)

    assert not form.is_valid()
    assert "rating" in form.errors


# --- The create endpoint ----------------------------------------------------------


def test_signed_out_visitors_are_redirected_to_login(client, product):
    response = create(client, product)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(reverse("accounts:login"))
    assert not Review.objects.exists()


def test_a_customer_who_never_bought_it_is_forbidden(client, product, customer):
    client.force_login(customer)

    assert create(client, product).status_code == HTTPStatus.FORBIDDEN
    assert not Review.objects.exists()


def test_a_cancelled_order_alone_is_forbidden(client, product, customer, make_order):
    make_order(customer, product, status=Order.Status.CANCELLED)
    client.force_login(customer)

    assert create(client, product).status_code == HTTPStatus.FORBIDDEN


def test_soulsear_next_of_kin_is_forbidden(
    client, soulsear, customer, next_of_kin, make_order
):
    make_order(customer, soulsear, status=Order.Status.DELIVERED)
    client.force_login(next_of_kin)

    assert create(client, soulsear).status_code == HTTPStatus.FORBIDDEN
    assert not Review.objects.exists()


def test_the_soulsear_owner_can_review_it(client, soulsear, customer, make_order):
    make_order(customer, soulsear, status=Order.Status.DELIVERED)
    client.force_login(customer)

    assert create(client, soulsear).status_code == HTTPStatus.OK
    assert Review.objects.filter(user=customer, product=soulsear).exists()


def test_staff_are_forbidden_even_with_an_order(
    client, product, staff_user, make_order
):
    make_order(staff_user, product)
    client.force_login(staff_user)

    assert create(client, product).status_code == HTTPStatus.FORBIDDEN


def test_a_second_review_is_forbidden(client, product, customer, make_order):
    make_order(customer, product)
    client.force_login(customer)
    create(client, product)

    response = create(client, product, comment="Second thoughts, stacked.")

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert Review.objects.count() == 1


def test_an_unavailable_product_can_be_reviewed(
    client, unavailable_product, customer, make_order
):
    make_order(customer, unavailable_product)
    client.force_login(customer)

    assert create(client, unavailable_product).status_code == HTTPStatus.OK


def test_a_missing_product_is_not_found(client, customer):
    client.force_login(customer)

    response = client.post(reverse("reviews:create", args=[999999]), {})

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_a_valid_review_is_created_and_returns_the_card_and_summary(
    client, product, customer, make_order
):
    make_order(customer, product, status=Order.Status.SHIPPED)
    client.force_login(customer)

    response = create(client, product, rating=4, comment="Hears me\nbefore I speak.")

    review = Review.objects.get()
    assert (review.user, review.product, review.rating) == (customer, product, 4)
    assert review.updated_by is None
    html = response.content.decode()
    assert f'id="review-{review.pk}"' in html
    assert "Hears me<br>before I speak." in html
    assert SUMMARY_OOB in html
    assert 'hx-swap-oob="true"' in html
    assert "1 review</span>" in html
    assert "No one else has weighed in yet" in html  # empty state, OOB
    assert "<form" not in html


def test_an_invalid_review_returns_errors_and_creates_nothing(
    client, product, customer, make_order
):
    make_order(customer, product)
    client.force_login(customer)

    response = create(client, product, rating="", comment="Too short")

    assert response.status_code == HTTPStatus.OK
    assert not Review.objects.exists()
    html = response.content.decode()
    assert "<form" in html
    assert "Choose a rating from 1 to 5 stars." in html
    assert "Write at least 10 characters" in html
    assert 'value="Too short"' not in html  # textarea, not an input
    assert "Too short</textarea>" in html
    assert SUMMARY_OOB not in html


def test_the_product_page_shows_the_form_to_a_buyer(
    client, product, customer, make_order
):
    make_order(customer, product)
    client.force_login(customer)

    html = client.get(product.get_absolute_url()).content.decode()

    assert reverse("reviews:create", args=[product.pk]) in html
    assert 'name="rating"' in html
    assert 'name="comment"' in html


def test_the_product_page_shows_no_form_to_a_non_buyer(client, product, customer):
    client.force_login(customer)

    html = client.get(product.get_absolute_url()).content.decode()

    assert reverse("reviews:create", args=[product.pk]) not in html
