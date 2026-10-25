"""Deleting a review: the author's own delete and a staff delete."""

from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from orders.models import Order

from .models import Review

pytestmark = pytest.mark.django_db

SUMMARY_OOB = 'id="review-summary"'
EMPTY_STATE = 'id="review-empty-state"'


@pytest.fixture
def other_customer(db):
    return get_user_model().objects.create_user(
        username="other", email="other@example.com", password="other123"
    )


@pytest.fixture
def order(make_order, customer, product):
    return make_order(customer, product)


@pytest.fixture
def review(order, product, customer):
    """The customer's review of a product they bought."""
    return Review.objects.create(
        user=customer, product=product, rating=3, comment="Hears me, mostly."
    )


def delete_url(review):
    return reverse("reviews:delete", args=[review.pk])


def delete(client, review):
    return client.post(delete_url(review))


# --- Login and 403s ---------------------------------------------------------------


def test_a_signed_out_delete_is_redirected_and_changes_nothing(client, review):
    response = delete(client, review)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(reverse("accounts:login"))
    assert Review.objects.filter(pk=review.pk).exists()


def test_another_customer_is_forbidden_and_the_review_stays(
    client, review, other_customer
):
    client.force_login(other_customer)

    assert delete(client, review).status_code == HTTPStatus.FORBIDDEN
    assert Review.objects.filter(pk=review.pk).exists()


def test_delete_needs_a_post(client, review, customer):
    client.force_login(customer)

    response = client.get(delete_url(review))

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert Review.objects.filter(pk=review.pk).exists()


def test_a_missing_review_is_not_found(client, customer):
    client.force_login(customer)

    response = client.post(reverse("reviews:delete", args=[999999]))

    assert response.status_code == HTTPStatus.NOT_FOUND


# --- The author's delete -----------------------------------------------------------


def test_the_authors_delete_brings_back_the_form(client, review, product, customer):
    client.force_login(customer)

    response = delete(client, review)

    assert response.status_code == HTTPStatus.OK
    assert not Review.objects.filter(pk=review.pk).exists()
    html = response.content.decode()
    assert "<form" in html
    assert f'hx-post="{reverse("reviews:create", args=[product.pk])}"' in html
    assert SUMMARY_OOB in html
    assert "No reviews yet." in html
    # The empty state drops "no one else" now the author has no review.
    assert EMPTY_STATE in html
    assert "No reviews yet</p>" in html


def test_after_deleting_the_author_can_write_a_new_review(
    client, review, product, customer
):
    client.force_login(customer)
    delete(client, review)

    response = client.post(
        reverse("reviews:create", args=[product.pk]),
        {"rating": 5, "comment": "Second thoughts, better ones."},
    )

    assert response.status_code == HTTPStatus.OK
    assert Review.objects.get(user=customer, product=product).rating == 5


def test_an_author_whose_order_was_cancelled_gets_the_only_buyers_line(
    client, review, order, product, customer
):
    order.status = Order.Status.CANCELLED
    order.save()
    client.force_login(customer)

    html = delete(client, review).content.decode()

    assert not Review.objects.filter(pk=review.pk).exists()
    assert "<form" not in html
    assert f"Only customers who've bought the {product.name} can review it." in html
    assert SUMMARY_OOB in html


# --- Staff deletes -------------------------------------------------------------------


def test_staff_can_delete_any_review_leaving_no_form(
    client, review, product, other_customer, staff_user
):
    Review.objects.create(
        user=other_customer, product=product, rating=5, comment="Quietly attentive."
    )
    client.force_login(staff_user)

    response = delete(client, review)

    assert response.status_code == HTTPStatus.OK
    assert not Review.objects.filter(pk=review.pk).exists()
    html = response.content.decode()
    assert "<form" not in html
    assert f'id="review-{review.pk}"' not in html
    assert SUMMARY_OOB in html
    assert "5.0</span>" in html
    assert "1 review</span>" in html
    assert EMPTY_STATE not in html  # another review is still listed


def test_a_staff_delete_of_the_last_review_brings_the_empty_state(
    client, review, staff_user
):
    client.force_login(staff_user)

    html = delete(client, review).content.decode()

    assert 'hx-swap-oob="beforeend:#review-list"' in html
    assert EMPTY_STATE in html
    assert "No reviews yet." in html


# --- Delete controls on the product page ---------------------------------------------


def test_the_delete_control_asks_for_confirmation(client, review, customer):
    client.force_login(customer)

    html = client.get(review.product.get_absolute_url()).content.decode()

    assert f'hx-post="{delete_url(review)}"' in html
    assert "hx-confirm=" in html


def test_another_customer_sees_no_delete_control(client, review, other_customer):
    client.force_login(other_customer)

    html = client.get(review.product.get_absolute_url()).content.decode()

    assert "Hears me, mostly." in html
    assert delete_url(review) not in html


def test_staff_see_delete_on_every_card(
    client, review, product, other_customer, staff_user
):
    second = Review.objects.create(
        user=other_customer, product=product, rating=4, comment="Quietly attentive."
    )
    client.force_login(staff_user)

    html = client.get(product.get_absolute_url()).content.decode()

    assert delete_url(review) in html
    assert delete_url(second) in html
