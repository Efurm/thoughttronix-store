import re
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from orders.models import Order

from .models import Review

pytestmark = pytest.mark.django_db


def delete(client, review):
    return client.post(reverse("reviews:delete", args=[review.pk]))


@pytest.mark.parametrize(
    ("status", "slot_text"),
    [
        (Order.Status.DELIVERED, 'name="comment"'),
        (
            Order.Status.CANCELLED,
            "Only customers who've bought the Seraphine Home Hub can review it",
        ),
    ],
    ids=["can still write", "order since cancelled"],
)
def test_authors_own_delete_brings_their_slot_back(
    client, customer, product, make_order, status, slot_text
):
    order = make_order(customer, product)
    review = Review.objects.create(
        user=customer, product=product, rating=4, comment="Listens well."
    )
    order.status = status
    order.save()
    client.force_login(customer)

    response = delete(client, review)

    content = response.content.decode()
    assert not Review.objects.filter(pk=review.pk).exists()
    assert response.status_code == HTTPStatus.OK
    assert slot_text in content
    assert "Listens well." not in content
    assert 'id="review-summary"' in content
    assert 'hx-swap-oob="true"' in content
    assert "No reviews yet." in content


def test_staff_delete_of_someone_elses_review_just_removes_that_card(
    client, customer, staff_user, product, make_order
):
    make_order(customer, product)
    review = Review.objects.create(
        user=customer, product=product, rating=4, comment="Listens well."
    )
    client.force_login(staff_user)

    response = delete(client, review)

    content = response.content.decode()
    without_summary = re.sub(
        r'<p id="review-summary".*?</p>', "", content, flags=re.DOTALL
    )
    assert not Review.objects.filter(pk=review.pk).exists()
    assert response.status_code == HTTPStatus.OK
    assert 'id="review-summary"' in content
    assert 'hx-swap-oob="true"' in content
    assert "No reviews yet." in content
    assert without_summary.strip() == ""


def delete_button(review):
    return f'hx-post="{reverse("reviews:delete", args=[review.pk])}"'


@pytest.fixture
def review(customer, product):
    return Review.objects.create(
        user=customer, product=product, rating=4, comment="Listens well."
    )


def test_signed_out_delete_redirects_to_login(client, review):
    response = delete(client, review)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(reverse("accounts:login"))
    assert Review.objects.filter(pk=review.pk).exists()


def test_another_customer_is_forbidden_and_the_review_stays(client, review):
    client.force_login(get_user_model().objects.create_user(username="stranger"))

    response = delete(client, review)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert Review.objects.filter(pk=review.pk).exists()


def test_delete_only_accepts_post(client, customer, review):
    client.force_login(customer)

    response = client.get(reverse("reviews:delete", args=[review.pk]))

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert Review.objects.filter(pk=review.pk).exists()


def test_deleting_a_missing_review_is_not_found(client, customer):
    client.force_login(customer)

    response = client.post(reverse("reviews:delete", args=[999]))

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_author_can_write_a_new_review_after_deleting(
    client, customer, product, make_order, review
):
    make_order(customer, product)
    client.force_login(customer)
    delete(client, review)

    response = client.post(
        reverse("reviews:create", args=[product.pk]),
        {"rating": 2, "comment": "Second thoughts, as promised."},
    )

    assert response.status_code == HTTPStatus.OK
    assert Review.objects.get().comment == "Second thoughts, as promised."


def test_staff_delete_leaves_the_other_reviews_in_the_summary(
    client, staff_user, product, review
):
    Review.objects.create(
        user=get_user_model().objects.create_user(username="other"),
        product=product,
        rating=2,
        comment="Too attentive.",
    )
    client.force_login(staff_user)

    content = delete(client, review).content.decode()

    assert "2.0" in content
    assert "1 review" in content


# --- Delete controls on the page ------------------------------------------


def test_authors_delete_confirms_and_targets_their_slot(client, customer, review):
    client.force_login(customer)

    content = client.get(review.product.get_absolute_url()).content.decode()

    assert delete_button(review) in content
    assert 'hx-confirm="Delete your review?' in content
    assert 'hx-target="#review-slot"' in content


def test_staff_delete_confirms_and_targets_the_card(client, staff_user, review):
    client.force_login(staff_user)

    content = client.get(review.product.get_absolute_url()).content.decode()

    assert delete_button(review) in content
    assert "hx-confirm=\"Delete customer's review?" in content
    assert f'hx-target="#review-{review.pk}" hx-swap="outerHTML">Delete' in content


@pytest.mark.parametrize("viewer", [None, "stranger"])
def test_others_see_no_delete_control(request, client, review, viewer):
    if viewer == "stranger":
        client.force_login(get_user_model().objects.create_user(username="stranger"))

    content = client.get(review.product.get_absolute_url()).content.decode()

    assert delete_button(review) not in content
