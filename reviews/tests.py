from datetime import timedelta
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from orders.models import Order

from .models import Review

pytestmark = pytest.mark.django_db


# --- Who may write a review -----------------------------------------------


@pytest.mark.parametrize(
    ("status", "allowed"),
    [
        (Order.Status.PLACED, True),
        (Order.Status.SHIPPED, True),
        (Order.Status.DELIVERED, True),
        (Order.Status.CANCELLED, False),
    ],
)
def test_can_write_follows_the_order_status(
    customer, product, make_order, status, allowed
):
    make_order(customer, product, status)

    assert Review.objects.can_write(customer, product) is allowed


def test_signed_out_visitor_cannot_write(product):
    assert Review.objects.can_write(AnonymousUser(), product) is False


def test_customer_without_an_order_cannot_write(customer, product):
    assert Review.objects.can_write(customer, product) is False


def test_an_order_of_another_product_does_not_count(
    customer, product, unavailable_product, make_order
):
    make_order(customer, unavailable_product)

    assert Review.objects.can_write(customer, product) is False


def test_cancelled_order_does_not_hide_a_live_one(customer, product, make_order):
    make_order(customer, product, Order.Status.CANCELLED)
    make_order(customer, product, Order.Status.DELIVERED)

    assert Review.objects.can_write(customer, product) is True


def test_staff_cannot_write_even_with_an_order(staff_user, product, make_order):
    make_order(staff_user, product)

    assert Review.objects.can_write(staff_user, product) is False


def test_an_existing_review_blocks_a_second_until_deleted(
    customer, product, make_order
):
    make_order(customer, product)
    review = Review.objects.create(
        user=customer, product=product, rating=4, comment="Listens well."
    )

    assert Review.objects.can_write(customer, product) is False

    review.delete()

    assert Review.objects.can_write(customer, product) is True


def test_an_unavailable_product_can_be_reviewed(
    customer, unavailable_product, make_order
):
    make_order(customer, unavailable_product)

    assert Review.objects.can_write(customer, unavailable_product) is True


def test_a_review_survives_its_order_being_cancelled(customer, product, make_order):
    order = make_order(customer, product)
    review = Review.objects.create(
        user=customer, product=product, rating=5, comment="Never sleeps."
    )

    order.status = Order.Status.CANCELLED
    order.save()

    assert Review.objects.filter(pk=review.pk).exists()


def test_soulsear_buyer_can_write_but_next_of_kin_cannot(
    customer, soulsear, make_order
):
    make_order(customer, soulsear, Order.Status.DELIVERED)
    next_of_kin = get_user_model().objects.create_user(
        username="kin", email="kin@example.com", password="kin12345"
    )

    assert Review.objects.can_write(customer, soulsear) is True
    assert Review.objects.can_write(next_of_kin, soulsear) is False


# --- The summary ----------------------------------------------------------


@pytest.mark.parametrize(
    ("ratings", "average", "count"),
    [
        ([5, 4, 4], 4.3, 3),
        ([5, 4], 4.5, 2),
        ([3], 3.0, 1),
        ([], None, 0),
    ],
)
def test_summary_gives_the_average_to_one_decimal_and_the_count(
    product, ratings, average, count
):
    for number, rating in enumerate(ratings):
        reviewer = get_user_model().objects.create_user(username=f"reviewer{number}")
        Review.objects.create(
            user=reviewer, product=product, rating=rating, comment="Fine device."
        )

    assert Review.objects.summary(product) == {"average": average, "count": count}


# --- Edit marking ---------------------------------------------------------


@pytest.mark.parametrize(
    ("editor", "edited", "edited_by_staff"),
    [
        (None, False, False),
        ("customer", True, False),
        ("staff_user", True, True),
    ],
)
def test_edit_marking_reflects_who_made_the_last_edit(
    request, customer, product, editor, edited, edited_by_staff
):
    review = Review.objects.create(
        user=customer, product=product, rating=4, comment="Listens well."
    )
    if editor:
        an_hour_ago = timezone.now() - timedelta(hours=1)
        Review.objects.filter(pk=review.pk).update(
            created_at=an_hour_ago, updated_at=an_hour_ago
        )
        review.refresh_from_db()
        review.comment = "Listens a little too well."
        review.updated_by = request.getfixturevalue(editor)
        review.save()

    assert review.is_edited is edited
    assert review.is_edited_by_staff is edited_by_staff


# --- Constraints ----------------------------------------------------------


@pytest.mark.parametrize("rating", [0, 6])
def test_database_rejects_a_rating_outside_one_to_five(customer, product, rating):
    with pytest.raises(IntegrityError):
        Review.objects.create(
            user=customer, product=product, rating=rating, comment="Out of range."
        )


@pytest.mark.parametrize("rating", [0, 6])
def test_validators_reject_a_rating_outside_one_to_five(customer, product, rating):
    review = Review(user=customer, product=product, rating=rating, comment="Nope.")

    with pytest.raises(ValidationError) as error:
        review.full_clean()

    assert "rating" in error.value.message_dict


def test_database_rejects_a_second_review_of_the_same_product(customer, product):
    Review.objects.create(user=customer, product=product, rating=4, comment="First.")

    with pytest.raises(IntegrityError):
        Review.objects.create(
            user=customer, product=product, rating=1, comment="Second."
        )


def test_deleting_a_product_deletes_its_reviews(customer, product):
    Review.objects.create(user=customer, product=product, rating=4, comment="Gone.")

    product.delete()

    assert not Review.objects.exists()


def test_reviews_are_newest_first(customer, staff_user, product):
    older = Review.objects.create(
        user=customer, product=product, rating=4, comment="Older."
    )
    Review.objects.filter(pk=older.pk).update(
        created_at=timezone.now() - timedelta(days=1)
    )
    newer = Review.objects.create(
        user=staff_user, product=product, rating=5, comment="Newer."
    )

    assert list(Review.objects.all()) == [newer, older]


# --- Who may change a review ----------------------------------------------


def test_can_change_is_for_the_author_and_staff_only(customer, staff_user, product):
    review = Review.objects.create(
        user=customer, product=product, rating=4, comment="Listens well."
    )
    stranger = get_user_model().objects.create_user(username="stranger")

    assert review.can_change(customer) is True
    assert review.can_change(staff_user) is True
    assert review.can_change(stranger) is False
    assert review.can_change(AnonymousUser()) is False


def test_staff_edit_by_a_deleted_account_still_reads_as_edited(
    customer, staff_user, product
):
    review = Review.objects.create(
        user=customer, product=product, rating=4, comment="Listens well."
    )
    Review.objects.filter(pk=review.pk).update(
        created_at=timezone.now() - timedelta(hours=1), updated_by=staff_user
    )

    staff_user.delete()
    review.refresh_from_db()

    assert review.is_edited is True
    assert review.is_edited_by_staff is False


# --- The Django admin -----------------------------------------------------


def test_admin_lists_and_searches_reviews(admin_client, customer, product):
    Review.objects.create(user=customer, product=product, rating=4, comment="Hi.")
    url = reverse("admin:reviews_review_changelist")

    assert admin_client.get(url, {"q": "Seraphine"}).context["cl"].result_count == 1
    assert admin_client.get(url, {"q": "nobody"}).context["cl"].result_count == 0
    assert admin_client.get(url, {"rating": 4}).context["cl"].result_count == 1


def test_admin_shows_every_field_read_only(admin_client, customer, product):
    review = Review.objects.create(
        user=customer, product=product, rating=4, comment="Hi."
    )
    response = admin_client.get(
        reverse("admin:reviews_review_change", args=[review.pk])
    )

    assert response.status_code == HTTPStatus.OK
    assert not response.context["adminform"].form.fields


def test_admin_cannot_add_a_review(admin_client):
    response = admin_client.get(reverse("admin:reviews_review_add"))

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_admin_can_bulk_delete_reviews(admin_client, customer, staff_user, product):
    reviews = [
        Review.objects.create(user=user, product=product, rating=3, comment="Meh.")
        for user in (customer, staff_user)
    ]

    admin_client.post(
        reverse("admin:reviews_review_changelist"),
        {
            "action": "delete_selected",
            "_selected_action": [review.pk for review in reviews],
            "post": "yes",
        },
    )

    assert not Review.objects.exists()
