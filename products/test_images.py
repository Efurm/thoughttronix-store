"""Product images: the display rule, file naming, and the pages that show them.

The display rule is the first non-negotiable: every product shows its
uploaded image when the file is really there, otherwise its category
placeholder — never a broken image.
"""

import re

from django.urls import reverse

from .models import product_image_path

PLACEHOLDER_URL = "/static/images/placeholders/home-assistants.svg"


# --- File naming ----------------------------------------------------------


def test_image_path_uses_slug_suffix_and_extension(product):
    path = product_image_path(product, "Some Upload.WEBP")
    assert re.fullmatch(r"products/seraphine-home-hub-[a-z0-9]{6}\.webp", path)


def test_image_path_changes_on_every_upload(product):
    assert product_image_path(product, "a.webp") != product_image_path(
        product, "a.webp"
    )


# --- The display rule -----------------------------------------------------


def test_display_image_url_without_image_is_placeholder(product):
    assert product.display_image_url == PLACEHOLDER_URL


def test_display_image_url_with_image_is_media_url(product_with_image):
    url = product_with_image.display_image_url
    assert re.fullmatch(r"/media/products/seraphine-home-hub-[a-z0-9]{6}\.webp", url)


def test_display_image_url_with_missing_file_is_placeholder(product_with_image):
    product_with_image.image.storage.delete(product_with_image.image.name)
    assert product_with_image.image  # the field still names a file...
    assert product_with_image.display_image_url == PLACEHOLDER_URL  # ...but no


def test_unknown_category_falls_back_to_default_placeholder(product, category):
    category.slug = "brand-new-category"
    category.save()
    assert product.display_image_url.endswith("/placeholders/default.svg")


# --- Pages ----------------------------------------------------------------


def test_catalog_shows_uploaded_image(client, product_with_image):
    response = client.get(reverse("products:catalog"))
    assert product_with_image.image.url in response.content.decode()


def test_detail_shows_uploaded_image(client, product_with_image):
    response = client.get(product_with_image.get_absolute_url())
    assert product_with_image.image.url in response.content.decode()


def test_pages_show_placeholder_without_image(client, product):
    for url in (reverse("products:catalog"), product.get_absolute_url()):
        assert PLACEHOLDER_URL in client.get(url).content.decode()


def test_pages_never_link_a_missing_file(client, product_with_image):
    product_with_image.image.storage.delete(product_with_image.image.name)
    for url in (reverse("products:catalog"), product_with_image.get_absolute_url()):
        html = client.get(url).content.decode()
        assert "/media/" not in html
        assert PLACEHOLDER_URL in html


# --- The back-office product list -----------------------------------------


def manage_list(client, staff_user):
    client.force_login(staff_user)
    return client.get(reverse("products:manage_products")).content.decode()


def test_manage_list_shows_thumbnail(client, staff_user, product_with_image):
    assert product_with_image.image.url in manage_list(client, staff_user)


def test_manage_list_shows_placeholder_without_image(client, staff_user, product):
    assert PLACEHOLDER_URL in manage_list(client, staff_user)


def test_manage_list_never_links_a_missing_file(client, staff_user, product_with_image):
    product_with_image.image.storage.delete(product_with_image.image.name)
    html = manage_list(client, staff_user)
    assert "/media/" not in html
    assert PLACEHOLDER_URL in html
