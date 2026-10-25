from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from orders.models import Order

from .models import Review

pytestmark = pytest.mark.django_db


def make_review(product, username, rating=4, comment="Listens well.", days_ago=0):
    """A review by a fresh customer, backdated ``days_ago``."""
    user = get_user_model().objects.create_user(username=username)
    review = Review.objects.create(
        user=user, product=product, rating=rating, comment=comment
    )
    if days_ago:
        Review.objects.filter(pk=review.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago)
        )
        review.refresh_from_db()
    return review


def detail(client, product):
    return client.get(product.get_absolute_url())


# --- Summary and list -----------------------------------------------------


def test_page_shows_the_summary(client, product):
    make_review(product, "ada", rating=5)
    make_review(product, "bo", rating=4)
    make_review(product, "cy", rating=4)

    response = detail(client, product)

    assert response.context["review_summary"] == {"average": 4.3, "count": 3}
    assert "4.3" in response.content.decode()
    assert "3 reviews" in response.content.decode()


def test_page_with_no_reviews_shows_the_empty_state(client, product):
    content = detail(client, product).content.decode()

    assert "No reviews yet" in content
    assert "★ 0" not in content


def test_reviews_are_listed_newest_first(client, product):
    oldest = make_review(product, "ada", comment="The oldest thought.", days_ago=3)
    newest = make_review(product, "bo", comment="The newest thought.")
    middle = make_review(product, "cy", comment="A middling thought.", days_ago=1)

    response = detail(client, product)
    content = response.content.decode()

    assert response.context["reviews"] == [newest, middle, oldest]
    assert (
        content.index("The newest thought.")
        < content.index("A middling thought.")
        < content.index("The oldest thought.")
    )


def test_page_lists_the_first_ten_and_knows_more_exist(client, product):
    for number in range(11):
        make_review(product, f"reviewer{number}", days_ago=number)

    response = detail(client, product)

    assert len(response.context["reviews"]) == 10
    assert response.context["has_more_reviews"] is True


def test_exactly_ten_reviews_means_no_more(client, product):
    for number in range(10):
        make_review(product, f"reviewer{number}")

    assert detail(client, product).context["has_more_reviews"] is False


def test_comment_is_escaped_with_line_breaks_kept(client, product):
    make_review(product, "ada", comment="<script>alert('x')</script>\nSecond line")

    content = detail(client, product).content.decode()

    assert "<script>alert" not in content
    assert "&lt;script&gt;" in content
    assert "<br>Second line" in content


@pytest.mark.parametrize(
    ("editor_is_staff", "note"),
    [(False, "Edited"), (True, "Edited by ThoughtTronix staff")],
)
def test_card_shows_the_edit_note(client, product, editor_is_staff, note):
    review = make_review(product, "ada")
    editor = (
        get_user_model().objects.create_user(username="mod", is_staff=True)
        if editor_is_staff
        else review.user
    )
    Review.objects.filter(pk=review.pk).update(
        created_at=timezone.now() - timedelta(hours=1), updated_by=editor
    )

    content = detail(client, product).content.decode()

    assert note in content
    if not editor_is_staff:
        assert "Edited by ThoughtTronix staff" not in content


def test_unedited_card_shows_no_edit_note(client, product):
    make_review(product, "ada")

    assert "Edited" not in detail(client, product).content.decode()


# --- The your-review slot -------------------------------------------------


def test_signed_out_visitor_is_asked_to_sign_in_and_come_back(client, product):
    content = detail(client, product).content.decode()

    assert "Sign in to leave a review" in content
    login = reverse("accounts:login")
    assert f'href="{login}?next={product.get_absolute_url()}"' in content


def test_buyer_who_has_not_reviewed_sees_the_writing_placeholder(
    client, customer, product, make_order
):
    make_order(customer, product)
    client.force_login(customer)

    response = detail(client, product)

    assert response.context["can_write_review"] is True
    assert "Reviews open here soon" in response.content.decode()


def test_customer_who_has_not_bought_is_told_only_buyers_review(
    client, customer, product
):
    client.force_login(customer)

    content = detail(client, product).content.decode()

    assert "Only customers who've bought the Seraphine Home Hub can review it" in (
        content
    )


def test_cancelled_buyer_is_told_only_buyers_review(
    client, customer, product, make_order
):
    make_order(customer, product, Order.Status.CANCELLED)
    client.force_login(customer)

    content = detail(client, product).content.decode()

    assert "Only customers who've bought" in content


def test_staff_see_no_slot_message(client, staff_user, product, make_order):
    make_order(staff_user, product)
    client.force_login(staff_user)

    content = detail(client, product).content.decode()

    assert "Sign in to leave a review" not in content
    assert "Only customers who've bought" not in content
    assert "Reviews open here soon" not in content


def test_own_review_sits_in_the_slot_and_not_in_the_list(
    client, customer, product, make_order
):
    make_order(customer, product)
    own = Review.objects.create(
        user=customer, product=product, rating=5, comment="My own thought."
    )
    other = make_review(product, "ada", comment="Someone else's thought.")
    client.force_login(customer)

    response = detail(client, product)
    content = response.content.decode()

    assert response.context["own_review"] == own
    assert response.context["reviews"] == [other]
    assert content.index("Your review") < content.index("My own thought.")
    assert content.count("My own thought.") == 1
    assert "Reviews open here soon" not in content


def test_own_review_shows_even_after_the_order_is_cancelled(
    client, customer, product, make_order
):
    order = make_order(customer, product)
    Review.objects.create(
        user=customer, product=product, rating=5, comment="Still my thought."
    )
    order.status = Order.Status.CANCELLED
    order.save()
    client.force_login(customer)

    content = detail(client, product).content.decode()

    assert "Still my thought." in content
    assert "Only customers who've bought" not in content


def test_soulsear_next_of_kin_is_told_only_buyers_review(
    client, customer, soulsear, make_order
):
    make_order(customer, soulsear, Order.Status.DELIVERED)
    next_of_kin = get_user_model().objects.create_user(username="kin")
    client.force_login(next_of_kin)

    content = detail(client, soulsear).content.decode()

    assert "Only customers who've bought the SoulSear Mark II can review it" in (
        content
    )
