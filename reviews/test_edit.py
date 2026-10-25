"""Editing a review in place: the edit form, saving, and Cancel."""

import re
from datetime import timedelta
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import Review

pytestmark = pytest.mark.django_db

SUMMARY_OOB = 'id="review-summary"'
STAFF_NOTE = "Edited by ThoughtTronix staff"


@pytest.fixture
def other_customer(db):
    return get_user_model().objects.create_user(
        username="other", email="other@example.com", password="other123"
    )


@pytest.fixture
def review(product, customer):
    """The customer's review, written an hour ago so a later save counts as
    an edit."""
    review = Review.objects.create(
        user=customer, product=product, rating=3, comment="Hears me, mostly."
    )
    an_hour_ago = review.created_at - timedelta(hours=1)
    Review.objects.filter(pk=review.pk).update(
        created_at=an_hour_ago, updated_at=an_hour_ago
    )
    review.refresh_from_db()
    return review


def edit_url(review):
    return reverse("reviews:edit", args=[review.pk])


def card_url(review):
    return reverse("reviews:detail", args=[review.pk])


def save(client, review, rating=5, comment="Hears me before I speak."):
    return client.post(edit_url(review), {"rating": rating, "comment": comment})


# --- Login and 403s ---------------------------------------------------------------


@pytest.mark.parametrize("url", [edit_url, card_url], ids=["edit", "cancel"])
def test_signed_out_visitors_are_redirected_to_login(client, review, url):
    response = client.get(url(review))

    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(reverse("accounts:login"))


def test_a_signed_out_save_is_redirected_and_changes_nothing(client, review):
    response = save(client, review)

    assert response.status_code == HTTPStatus.FOUND
    review.refresh_from_db()
    assert review.rating == 3


@pytest.mark.parametrize("url", [edit_url, card_url], ids=["edit", "cancel"])
def test_another_customer_is_forbidden_to_view_the_form_or_card(
    client, review, other_customer, url
):
    client.force_login(other_customer)

    assert client.get(url(review)).status_code == HTTPStatus.FORBIDDEN


def test_another_customer_is_forbidden_to_save(client, review, other_customer):
    client.force_login(other_customer)

    assert save(client, review).status_code == HTTPStatus.FORBIDDEN
    review.refresh_from_db()
    assert (review.rating, review.comment) == (3, "Hears me, mostly.")
    assert review.updated_by is None


def test_a_missing_review_is_not_found(client, customer):
    client.force_login(customer)

    response = client.get(reverse("reviews:edit", args=[999999]))

    assert response.status_code == HTTPStatus.NOT_FOUND


# --- The edit form and Cancel ----------------------------------------------------


def test_the_edit_form_is_prefilled_in_the_cards_spot(client, review, customer):
    client.force_login(customer)

    html = client.get(edit_url(review)).content.decode()

    assert f'id="review-{review.pk}"' in html
    assert f'hx-post="{edit_url(review)}"' in html
    assert re.search(r'value="3"[^>]*checked', html)
    assert not re.search(r'value="5"[^>]*checked', html)
    assert "Hears me, mostly.</textarea>" in html
    assert "Edit your review" in html
    assert f'hx-get="{card_url(review)}"' in html  # Cancel


def test_staff_see_whose_review_they_are_editing(client, review, staff_user):
    client.force_login(staff_user)

    html = client.get(edit_url(review)).content.decode()

    assert "Edit customer's review" in html


def test_cancel_restores_the_original_card(client, review, customer):
    client.force_login(customer)

    html = client.get(card_url(review)).content.decode()

    assert f'id="review-{review.pk}"' in html
    assert "Hears me, mostly." in html
    assert "<form" not in html
    assert SUMMARY_OOB not in html


# --- Saving ---------------------------------------------------------------------


def test_an_authors_edit_is_marked_edited_but_not_by_staff(client, review, customer):
    client.force_login(customer)

    response = save(client, review, rating=5, comment="Hears me\nbefore I speak.")

    review.refresh_from_db()
    assert (review.rating, review.comment) == (5, "Hears me\nbefore I speak.")
    assert review.updated_by == customer
    assert review.is_edited
    assert not review.is_edited_by_staff
    html = response.content.decode()
    assert f'id="review-{review.pk}"' in html
    assert "Hears me<br>before I speak." in html
    assert "<form" not in html
    assert ">Edited</p>" in html
    assert STAFF_NOTE not in html
    assert SUMMARY_OOB in html
    assert 'hx-swap-oob="true"' in html
    assert "5.0</span>" in html


def test_staff_can_edit_any_review_and_it_is_marked(
    client, review, product, staff_user
):
    client.force_login(staff_user)

    response = save(client, review, comment="Hears me. [Edited for tone.]")

    review.refresh_from_db()
    assert review.comment == "Hears me. [Edited for tone.]"
    assert review.updated_by == staff_user
    assert review.is_edited_by_staff
    assert STAFF_NOTE in response.content.decode()
    assert SUMMARY_OOB in response.content.decode()


def test_the_staff_note_shows_on_the_page_signed_out(client, review, staff_user):
    client.force_login(staff_user)
    save(client, review)
    client.logout()

    html = client.get(review.product.get_absolute_url()).content.decode()

    assert STAFF_NOTE in html
    assert edit_url(review) not in html


def test_an_invalid_edit_leaves_the_review_unchanged(client, review, customer):
    client.force_login(customer)

    response = save(client, review, rating=5, comment="Too short")

    assert response.status_code == HTTPStatus.OK
    review.refresh_from_db()
    assert (review.rating, review.comment) == (3, "Hears me, mostly.")
    assert not review.is_edited
    html = response.content.decode()
    assert "<form" in html
    assert f'id="review-{review.pk}"' in html
    assert "Write at least 10 characters" in html
    assert "Too short</textarea>" in html
    assert SUMMARY_OOB not in html


# --- Edit controls on the product page ---------------------------------------------


def test_the_author_sees_edit_on_their_own_card(client, review, customer):
    client.force_login(customer)

    html = client.get(review.product.get_absolute_url()).content.decode()

    assert edit_url(review) in html


def test_another_customer_sees_no_edit_control(client, review, other_customer):
    client.force_login(other_customer)

    html = client.get(review.product.get_absolute_url()).content.decode()

    assert "Hears me, mostly." in html
    assert edit_url(review) not in html


def test_staff_see_edit_on_every_card(
    client, review, product, other_customer, staff_user
):
    second = Review.objects.create(
        user=other_customer, product=product, rating=4, comment="Quietly attentive."
    )
    client.force_login(staff_user)

    html = client.get(product.get_absolute_url()).content.decode()

    assert edit_url(review) in html
    assert edit_url(second) in html
