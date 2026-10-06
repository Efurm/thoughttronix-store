"""The back-office image card: upload, replace, remove, and file lifecycle.

The second non-negotiable end to end: an unusable file is rejected in
plain language and changes nothing; a good file is never lost; an old
file is deleted only after its replacement has committed.
"""

from http import HTTPStatus

import pytest
from django.contrib import admin
from django.urls import reverse
from django.utils.html import escape

from .models import Product

pytestmark = pytest.mark.django_db


def upload_url(product):
    return reverse("products:manage_product_image", kwargs={"pk": product.pk})


def remove_url(product):
    return reverse("products:manage_product_image_remove", kwargs={"pk": product.pk})


def stored_files(media_root):
    folder = media_root / "products"
    return sorted(path.name for path in folder.iterdir()) if folder.exists() else []


# --- Access control ----------------------------------------------------------


def test_anonymous_users_are_sent_to_login(client, product):
    for url in (upload_url(product), remove_url(product)):
        response = client.post(url)

        assert response.status_code == HTTPStatus.FOUND, url
        assert reverse("accounts:login") in response.url


def test_customers_get_403(client, customer, product):
    client.force_login(customer)

    for url in (upload_url(product), remove_url(product)):
        assert client.post(url).status_code == HTTPStatus.FORBIDDEN, url


def test_image_endpoints_are_post_only(client, staff_user, product):
    client.force_login(staff_user)

    for url in (upload_url(product), remove_url(product)):
        assert client.get(url).status_code == HTTPStatus.METHOD_NOT_ALLOWED, url


# --- Upload ------------------------------------------------------------------


def test_upload_stores_a_webp_and_returns_the_card(
    client, staff_user, product, media_root, make_image
):
    client.force_login(staff_user)

    response = client.post(upload_url(product), {"image": make_image()})

    product.refresh_from_db()
    assert product.has_image
    assert product.image.name.endswith(".webp")
    html = response.content.decode()
    assert response.status_code == HTTPStatus.OK
    assert "Image saved." in html
    assert product.image.url in html
    assert "<html" not in html  # a partial, never a full page
    assert 'name="price"' not in html  # only the card swaps; details untouched


@pytest.mark.parametrize(
    "build, message",
    [
        (
            lambda make_image: make_image(format="TIFF", name="scan.tiff"),
            '"scan.tiff" is a TIFF image.',
        ),
        (
            lambda make_image: make_image(width=150, height=120, name="logo.png"),
            '"logo.png" is 150 × 120 pixels.',
        ),
    ],
)
def test_rejection_explains_and_stores_nothing(
    client, staff_user, product, media_root, make_image, build, message
):
    client.force_login(staff_user)

    response = client.post(upload_url(product), {"image": build(make_image)})

    product.refresh_from_db()
    assert not product.image
    assert stored_files(media_root) == []
    assert escape(message) in response.content.decode()


def test_no_file_chosen(client, staff_user, product, media_root):
    client.force_login(staff_user)

    response = client.post(upload_url(product), {})

    assert "Choose an image file to upload." in response.content.decode()


def test_rejected_replacement_keeps_the_current_image(
    client, staff_user, product_with_image, media_root, make_image
):
    client.force_login(staff_user)
    current = product_with_image.image.name

    response = client.post(
        upload_url(product_with_image),
        {"image": make_image(width=150, height=120, name="logo.png")},
    )

    product_with_image.refresh_from_db()
    assert product_with_image.image.name == current
    assert product_with_image.has_image
    assert escape('"logo.png" is 150 × 120 pixels.') in response.content.decode()


# --- Replace and remove: the old file goes only after commit -----------------


def test_replace_deletes_the_old_file_only_after_commit(
    client,
    staff_user,
    product_with_image,
    media_root,
    make_image,
    django_capture_on_commit_callbacks,
):
    client.force_login(staff_user)
    old_name = product_with_image.image.name
    storage = product_with_image.image.storage

    with django_capture_on_commit_callbacks() as callbacks:
        client.post(upload_url(product_with_image), {"image": make_image()})

        # Committed? Not yet: both files exist, the row names the new one.
        product_with_image.refresh_from_db()
        assert product_with_image.image.name != old_name
        assert storage.exists(old_name)
        assert product_with_image.has_image

    for callback in callbacks:
        callback()
    assert not storage.exists(old_name)
    assert stored_files(media_root) == [product_with_image.image.name.split("/")[1]]


def test_remove_returns_to_the_placeholder_and_deletes_the_file(
    client,
    staff_user,
    product_with_image,
    media_root,
    django_capture_on_commit_callbacks,
):
    client.force_login(staff_user)

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(remove_url(product_with_image))

    product_with_image.refresh_from_db()
    html = response.content.decode()
    assert not product_with_image.image
    assert stored_files(media_root) == []
    assert "Image removed." in html
    assert "/static/images/placeholders/home-assistants.svg" in html
    assert "Upload image" in html


def test_deleting_a_product_deletes_its_file(
    client,
    staff_user,
    product_with_image,
    media_root,
    django_capture_on_commit_callbacks,
):
    client.force_login(staff_user)

    with django_capture_on_commit_callbacks(execute=True):
        client.post(
            reverse(
                "products:manage_product_delete", kwargs={"pk": product_with_image.pk}
            )
        )

    assert not Product.objects.exists()
    assert stored_files(media_root) == []


def test_bulk_delete_deletes_files_too(
    product_with_image, media_root, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        Product.objects.all().delete()

    assert stored_files(media_root) == []


# --- The edit and create pages -----------------------------------------------


def test_create_redirects_to_the_edit_page(client, staff_user, category):
    client.force_login(staff_user)

    response = client.post(
        reverse("products:manage_product_create"),
        {"name": "Veil", "slug": "veil", "price": "89.00", "category": category.pk},
    )

    product = Product.objects.get(slug="veil")
    assert response.url == reverse(
        "products:manage_product_update", kwargs={"pk": product.pk}
    )


def test_edit_page_has_the_image_card(client, staff_user, product):
    client.force_login(staff_user)

    html = client.get(
        reverse("products:manage_product_update", kwargs={"pk": product.pk})
    ).content.decode()

    assert 'id="product-image"' in html
    assert 'hx-encoding="multipart/form-data"' in html
    assert "Upload image" in html
    assert "Remove image" not in html  # nothing to remove yet


def test_edit_page_offers_replace_and_remove_with_an_image(
    client, staff_user, product_with_image
):
    client.force_login(staff_user)

    html = client.get(
        reverse("products:manage_product_update", kwargs={"pk": product_with_image.pk})
    ).content.decode()

    assert "Replace image" in html
    assert 'hx-confirm="Remove this image?"' in html


def test_create_page_explains_images_come_after_saving(client, staff_user):
    client.force_login(staff_user)

    html = client.get(reverse("products:manage_product_create")).content.decode()

    assert "Save the product first, then add its image here." in html
    assert 'id="product-image"' not in html


# --- Django admin --------------------------------------------------------------


def test_image_is_read_only_in_the_admin():
    assert "image" in admin.site._registry[Product].readonly_fields
