import re
from datetime import timedelta
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from orders.models import Order

from .models import Review

pytestmark = pytest.mark.django_db

ORIGINAL = "Listens well. Maybe too well."
CHANGED = {"rating": 2, "comment": "On reflection, it listens far too well."}


@pytest.fixture
def review(customer, product):
    return Review.objects.create(
        user=customer, product=product, rating=4, comment=ORIGINAL
    )


@pytest.fixture
def stranger(db):
    return get_user_model().objects.create_user(username="stranger")


@pytest.mark.parametrize(
    ("method", "route", "data"),
    [
        ("get", "reviews:edit", None),
        ("post", "reviews:edit", CHANGED),
        ("get", "reviews:card", None),
    ],
    ids=["edit form", "save edit", "cancel"],
)
def test_another_customer_is_forbidden_from_every_edit_endpoint(
    client, review, stranger, method, route, data
):
    client.force_login(stranger)

    response = getattr(client, method)(reverse(route, args=[review.pk]), data)

    review.refresh_from_db()
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert (review.rating, review.comment, review.updated_by) == (4, ORIGINAL, None)


@pytest.mark.parametrize(
    ("editor", "note"),
    [("customer", "Edited"), ("staff_user", "Edited by ThoughtTronix staff")],
)
def test_valid_edit_records_the_editor_and_returns_the_marked_card(
    request, client, review, editor, note
):
    an_hour_ago = timezone.now() - timedelta(hours=1)
    Review.objects.filter(pk=review.pk).update(
        created_at=an_hour_ago, updated_at=an_hour_ago
    )
    acting_user = request.getfixturevalue(editor)
    client.force_login(acting_user)

    response = client.post(reverse("reviews:edit", args=[review.pk]), CHANGED)

    review.refresh_from_db()
    content = response.content.decode()
    assert (review.rating, review.comment) == (CHANGED["rating"], CHANGED["comment"])
    assert review.updated_by == acting_user
    assert response.status_code == HTTPStatus.OK
    assert f'id="review-{review.pk}"' in content
    assert CHANGED["comment"] in content
    assert note in content
    if editor == "customer":
        assert "Edited by ThoughtTronix staff" not in content
    assert 'id="review-summary"' in content
    assert 'hx-swap-oob="true"' in content
    assert "2.0" in content


def test_invalid_edit_changes_nothing_and_returns_the_form_in_place(
    client, customer, review
):
    client.force_login(customer)

    response = client.post(
        reverse("reviews:edit", args=[review.pk]),
        {"rating": 2, "comment": "Too short"},
    )

    review.refresh_from_db()
    content = response.content.decode()
    assert (review.rating, review.comment, review.updated_by) == (4, ORIGINAL, None)
    assert response.status_code == HTTPStatus.OK
    assert re.search(rf'<form[^>]*id="review-{review.pk}"', content)
    assert f'hx-post="{reverse("reviews:edit", args=[review.pk])}"' in content
    assert "at least 10 characters" in content
    assert re.search(r">\s*Too short</textarea>", content)
    assert "hx-swap-oob" not in content


def edit_button(review):
    return f'hx-get="{reverse("reviews:edit", args=[review.pk])}"'


@pytest.mark.parametrize(
    ("method", "route"),
    [("get", "reviews:edit"), ("post", "reviews:edit"), ("get", "reviews:card")],
    ids=["edit form", "save edit", "cancel"],
)
def test_signed_out_requests_redirect_to_login(client, review, method, route):
    response = getattr(client, method)(reverse(route, args=[review.pk]), CHANGED)

    review.refresh_from_db()
    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(reverse("accounts:login"))
    assert review.comment == ORIGINAL


@pytest.mark.parametrize("route", ["reviews:edit", "reviews:card"])
def test_a_missing_review_is_not_found(client, customer, route):
    client.force_login(customer)

    assert client.get(reverse(route, args=[999])).status_code == HTTPStatus.NOT_FOUND


def test_edit_form_is_prefilled_in_the_cards_place(client, customer, review):
    client.force_login(customer)

    response = client.get(reverse("reviews:edit", args=[review.pk]))
    content = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert re.search(rf'<form[^>]*id="review-{review.pk}"', content)
    assert re.search(r'value="4"[^>]*checked', content)
    assert content.count("checked") == 1
    assert ORIGINAL in content
    assert "Edit your review" in content
    assert f'hx-get="{reverse("reviews:card", args=[review.pk])}"' in content
    assert "<html" not in content


def test_staff_edit_form_names_whose_review_it_is(client, staff_user, review):
    client.force_login(staff_user)

    content = client.get(reverse("reviews:edit", args=[review.pk])).content.decode()

    assert "Edit customer's review" in content


def test_cancel_restores_the_unchanged_card(client, customer, review):
    client.force_login(customer)

    response = client.get(reverse("reviews:card", args=[review.pk]))
    content = response.content.decode()

    assert response.status_code == HTTPStatus.OK
    assert f'<article id="review-{review.pk}"' in content
    assert ORIGINAL in content
    assert "<form" not in content
    assert "hx-swap-oob" not in content


def test_customer_edit_never_shows_the_staff_note_on_the_page(client, customer, review):
    Review.objects.filter(pk=review.pk).update(
        created_at=timezone.now() - timedelta(hours=1)
    )
    client.force_login(customer)
    client.post(reverse("reviews:edit", args=[review.pk]), CHANGED)
    client.logout()

    content = client.get(review.product.get_absolute_url()).content.decode()

    assert "Edited" in content
    assert "Edited by ThoughtTronix staff" not in content


def test_staff_edit_shows_the_staff_note_to_signed_out_shoppers(
    client, staff_user, review
):
    Review.objects.filter(pk=review.pk).update(
        created_at=timezone.now() - timedelta(hours=1)
    )
    client.force_login(staff_user)
    client.post(reverse("reviews:edit", args=[review.pk]), CHANGED)
    client.logout()

    content = client.get(review.product.get_absolute_url()).content.decode()

    assert CHANGED["comment"] in content
    assert "Edited by ThoughtTronix staff" in content


def test_author_can_still_edit_after_the_order_is_cancelled(
    client, customer, review, make_order
):
    order = make_order(customer, review.product)
    order.status = Order.Status.CANCELLED
    order.save()
    client.force_login(customer)

    client.post(reverse("reviews:edit", args=[review.pk]), CHANGED)

    review.refresh_from_db()
    assert review.comment == CHANGED["comment"]


# --- Edit controls on the page --------------------------------------------


def test_author_sees_edit_on_their_own_card(client, customer, review):
    client.force_login(customer)

    content = client.get(review.product.get_absolute_url()).content.decode()

    assert edit_button(review) in content


@pytest.mark.parametrize("viewer", [None, "stranger"])
def test_others_see_no_edit_control(request, client, review, viewer):
    if viewer:
        client.force_login(request.getfixturevalue(viewer))

    content = client.get(review.product.get_absolute_url()).content.decode()

    assert edit_button(review) not in content


def test_staff_see_edit_on_every_card(client, staff_user, review, product):
    second = Review.objects.create(
        user=get_user_model().objects.create_user(username="second"),
        product=product,
        rating=1,
        comment="Too quiet, somehow.",
    )
    client.force_login(staff_user)

    content = client.get(product.get_absolute_url()).content.decode()

    assert edit_button(review) in content
    assert edit_button(second) in content
