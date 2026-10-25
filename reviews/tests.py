from datetime import timedelta
from decimal import Decimal
from http import HTTPStatus

import pytest
from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError
from django.test import RequestFactory
from django.urls import reverse

from orders.models import Order

from .admin import ReviewAdmin
from .models import Review

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_customer(db):
    return get_user_model().objects.create_user(
        username="other", email="other@example.com", password="other123"
    )


@pytest.fixture
def superuser(db):
    return get_user_model().objects.create_superuser(
        username="admin", email="admin@example.com", password="admin123"
    )


def review_of(product, user, rating=4, comment="Listens beautifully."):
    return Review.objects.create(
        product=product, user=user, rating=rating, comment=comment
    )


# --- Model and constraints --------------------------------------------------


@pytest.mark.parametrize("rating", [0, 6])
def test_ratings_outside_one_to_five_are_rejected(product, customer, rating):
    with pytest.raises(IntegrityError):
        review_of(product, customer, rating=rating)


def test_a_second_review_of_the_same_product_is_rejected(product, customer):
    review_of(product, customer)

    with pytest.raises(IntegrityError):
        review_of(product, customer)


def test_deleting_a_product_deletes_its_reviews(product, customer):
    review_of(product, customer)

    product.delete()

    assert not Review.objects.exists()


def test_reviews_come_newest_first(product, customer, other_customer):
    older = review_of(product, customer)
    newer = review_of(product, other_customer)

    assert list(Review.objects.all()) == [newer, older]


# --- Summary ------------------------------------------------------------------


def test_summary_averages_to_one_decimal_and_counts(
    product, customer, other_customer, staff_user
):
    review_of(product, customer, rating=5)
    review_of(product, other_customer, rating=4)
    review_of(product, staff_user, rating=4)

    summary = Review.objects.summary(product)

    assert summary.average == Decimal("4.3")
    assert summary.count == 3


def test_summary_counts_only_this_products_reviews(
    product, unavailable_product, customer
):
    review_of(product, customer, rating=2)
    review_of(unavailable_product, customer, rating=5)

    assert Review.objects.summary(product) == (Decimal("2.0"), 1)


def test_summary_with_no_reviews(product):
    summary = Review.objects.summary(product)

    assert summary.average is None
    assert summary.count == 0


# --- Can write ------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [Order.Status.PLACED, Order.Status.SHIPPED, Order.Status.DELIVERED],
)
def test_a_live_order_allows_a_review(product, customer, make_order, status):
    make_order(customer, product, status=status)

    assert Review.objects.can_write(customer, product)


def test_a_cancelled_order_alone_does_not(product, customer, make_order):
    make_order(customer, product, status=Order.Status.CANCELLED)

    assert not Review.objects.can_write(customer, product)


def test_a_live_order_beside_a_cancelled_one_still_allows_a_review(
    product, customer, make_order
):
    make_order(customer, product, status=Order.Status.CANCELLED)
    make_order(customer, product)

    assert Review.objects.can_write(customer, product)


def test_no_order_means_no_review(product, customer):
    assert not Review.objects.can_write(customer, product)


def test_an_order_of_another_product_does_not_count(
    product, unavailable_product, customer, make_order
):
    make_order(customer, unavailable_product)

    assert not Review.objects.can_write(customer, product)


def test_signed_out_visitors_cannot_review(product):
    assert not Review.objects.can_write(AnonymousUser(), product)


def test_staff_cannot_review_even_with_an_order(product, staff_user, make_order):
    make_order(staff_user, product)

    assert not Review.objects.can_write(staff_user, product)


def test_an_existing_review_blocks_a_second_until_deleted(
    product, customer, make_order
):
    make_order(customer, product)
    review = review_of(product, customer)

    assert not Review.objects.can_write(customer, product)

    review.delete()

    assert Review.objects.can_write(customer, product)


def test_an_unavailable_product_can_be_reviewed(
    unavailable_product, customer, make_order
):
    make_order(customer, unavailable_product)

    assert Review.objects.can_write(customer, unavailable_product)


def test_a_review_survives_its_order_being_cancelled(product, customer, make_order):
    order = make_order(customer, product)
    review = review_of(product, customer)

    order.status = Order.Status.CANCELLED
    order.save()

    assert Review.objects.filter(pk=review.pk).exists()


# --- SoulSear ------------------------------------------------------------------


def test_the_soulsear_owner_can_review_it(soulsear, customer, make_order):
    make_order(customer, soulsear, status=Order.Status.DELIVERED)

    assert Review.objects.can_write(customer, soulsear)


def test_next_of_kin_cannot_review_a_soulsear_bought_on_another_account(
    soulsear, customer, other_customer, make_order
):
    make_order(customer, soulsear, status=Order.Status.DELIVERED)

    assert not Review.objects.can_write(other_customer, soulsear)


# --- Can change ----------------------------------------------------------------


def test_the_author_can_change_their_review(product, customer):
    assert review_of(product, customer).can_change(customer)


def test_staff_can_change_any_review(product, customer, staff_user):
    assert review_of(product, customer).can_change(staff_user)


def test_another_customer_cannot_change_a_review(product, customer, other_customer):
    assert not review_of(product, customer).can_change(other_customer)


def test_signed_out_visitors_cannot_change_a_review(product, customer):
    assert not review_of(product, customer).can_change(AnonymousUser())


# --- Edit marking --------------------------------------------------------------


def edit(review, by):
    """Stand in for an edit made later: move updated_at on and record ``by``."""
    Review.objects.filter(pk=review.pk).update(
        updated_at=review.created_at + timedelta(minutes=5), updated_by=by
    )
    review.refresh_from_db()
    return review


def test_a_new_review_is_not_edited(product, customer):
    review = review_of(product, customer)

    assert not review.is_edited
    assert not review.is_edited_by_staff


def test_an_authors_edit_is_edited_but_not_by_staff(product, customer):
    review = edit(review_of(product, customer), by=customer)

    assert review.is_edited
    assert not review.is_edited_by_staff


def test_a_staff_edit_is_marked_as_one(product, customer, staff_user):
    review = edit(review_of(product, customer), by=staff_user)

    assert review.is_edited
    assert review.is_edited_by_staff


# --- Admin ------------------------------------------------------------------------


@pytest.fixture
def admin_request(superuser):
    request = RequestFactory().get("/admin/")
    request.user = superuser
    return request


def test_every_review_field_is_read_only_in_the_admin(admin_request):
    model_admin = ReviewAdmin(Review, site)
    fields = {
        field.name
        for field in Review._meta.get_fields()
        if field.concrete and not field.primary_key
    }

    assert fields <= set(model_admin.get_readonly_fields(admin_request))


def test_the_admin_cannot_add_reviews_but_can_delete_them(admin_request):
    model_admin = ReviewAdmin(Review, site)

    assert not model_admin.has_add_permission(admin_request)
    assert model_admin.has_delete_permission(admin_request)


def test_the_admin_lists_searches_and_filters_reviews(
    client, superuser, product, unavailable_product, customer
):
    review_of(product, customer, rating=5)
    review_of(unavailable_product, customer, rating=2)
    client.force_login(superuser)
    url = reverse("admin:reviews_review_changelist")

    assert client.get(url).context["cl"].result_count == 2
    assert client.get(url, {"q": "seraphine"}).context["cl"].result_count == 1
    assert client.get(url, {"rating": "2"}).context["cl"].result_count == 1


def test_the_admin_can_bulk_delete_reviews(client, superuser, product, customer):
    review = review_of(product, customer)
    client.force_login(superuser)

    response = client.post(
        reverse("admin:reviews_review_changelist"),
        {"action": "delete_selected", "_selected_action": [review.pk], "post": "yes"},
    )

    assert response.status_code == HTTPStatus.FOUND
    assert not Review.objects.exists()
