from decimal import Decimal
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.db import IntegrityError
from django.urls import reverse
from django.utils.html import escape

from orders.models import CartItem, Order, OrderItem

from .management.commands import seed
from .models import Category, Product, Tag

# --- Model behavior -------------------------------------------------------


def test_category_str(category):
    assert str(category) == "Home Assistants"


def test_product_str(product):
    assert str(product) == "Seraphine Home Hub"


def test_tag_str(tag):
    assert str(tag) == "bestseller"


def test_available_manager_excludes_unavailable(product, unavailable_product):
    available = Product.objects.available()

    assert product in available
    assert unavailable_product not in available


def test_featured_manager_returns_only_featured(product, unavailable_product):
    assert not product.is_featured  # products are not featured by default
    product.is_featured = True
    product.save()

    featured = Product.objects.featured()

    assert product in featured
    assert unavailable_product not in featured


def test_search_matches_name_and_description(product, unavailable_product):
    assert product in Product.objects.search("home hub")
    assert product in Product.objects.search("seven-microphone")
    assert product not in Product.objects.search("death ray")


def test_product_slug_unique(product, category):
    with pytest.raises(IntegrityError):
        Product.objects.create(
            name="Another Hub",
            slug=product.slug,
            price=Decimal("1.00"),
            category=category,
        )


def test_product_get_absolute_url(product):
    assert product.get_absolute_url() == "/products/seraphine-home-hub/"


def test_category_get_absolute_url(category):
    assert category.get_absolute_url() == "/categories/home-assistants/"


# --- Catalog views ---------------------------------------------------------


def test_catalog_displays_product(client, product):
    """The catalog shows a product's name, category, tagline, and price."""
    response = client.get(reverse("products:catalog"))

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert product.name in page
    assert product.category.name in page
    assert escape(product.tagline) in page
    assert str(product.price) in page
    assert product.get_absolute_url() in page


def test_detail_page(client, product):
    response = client.get(product.get_absolute_url())

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert product.name in page
    assert escape(product.description) in page


def test_detail_unknown_slug_404(client, db):
    response = client.get(reverse("products:detail", kwargs={"slug": "no-such-thing"}))

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_detail_shows_availability(client, unavailable_product):
    response = client.get(unavailable_product.get_absolute_url())

    assert "Unavailable" in response.content.decode()


def test_featured_badge_on_catalog_and_detail(client, product):
    """Featured products wear the badge in the catalog and on their own page."""
    assert "Featured" not in client.get(reverse("products:catalog")).content.decode()
    assert "Featured" not in client.get(product.get_absolute_url()).content.decode()

    product.is_featured = True
    product.save()

    assert "Featured" in client.get(reverse("products:catalog")).content.decode()
    assert "Featured" in client.get(product.get_absolute_url()).content.decode()


def test_category_page_lists_only_its_products(client, product):
    defense = Category.objects.create(name="Defense", slug="defense")
    Product.objects.create(
        name="SoulSear Mark II",
        slug="soulsear-mark-ii",
        price=Decimal("2400000.00"),
        category=defense,
    )

    response = client.get(defense.get_absolute_url())

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "SoulSear Mark II" in page
    assert product.name not in page


def test_category_unknown_slug_404(client, db):
    response = client.get(reverse("products:category", kwargs={"slug": "nope"}))

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_empty_category_shows_empty_state(client, db):
    empty = Category.objects.create(name="Defense", slug="defense")

    response = client.get(empty.get_absolute_url())

    assert "This shelf is empty" in response.content.decode()


# --- Search, filtering, and their composition ------------------------------


def test_search_filters_catalog(client, product, unavailable_product):
    response = client.get(reverse("products:catalog"), {"q": "home hub"})

    page = response.content.decode()
    assert product.name in page
    assert unavailable_product.name not in page


def test_search_no_results_shows_empty_state(client, product):
    response = client.get(reverse("products:catalog"), {"q": "death ray"})

    assert "Nothing matches" in response.content.decode()


def test_tag_filter(client, product, unavailable_product, tag):
    product.tags.add(tag)

    response = client.get(reverse("products:catalog"), {"tag": tag.slug})

    page = response.content.decode()
    assert product.name in page
    assert unavailable_product.name not in page


def test_search_and_tag_compose(client, product, unavailable_product, tag):
    product.tags.add(tag)
    unavailable_product.tags.add(tag)

    response = client.get(
        reverse("products:catalog"), {"tag": tag.slug, "q": "home hub"}
    )

    page = response.content.decode()
    assert product.name in page
    assert unavailable_product.name not in page


def test_category_querystring_filter(client, product):
    defense = Category.objects.create(name="Defense", slug="defense")
    Product.objects.create(
        name="SoulSear Mark II",
        slug="soulsear-mark-ii",
        price=Decimal("2400000.00"),
        category=defense,
    )

    response = client.get(reverse("products:catalog"), {"category": "defense"})

    page = response.content.decode()
    assert "SoulSear Mark II" in page
    assert product.name not in page


def test_catalog_paginates_at_twelve(client, category):
    for n in range(13):
        Product.objects.create(
            name=f"Widget {n:02d}",
            slug=f"widget-{n:02d}",
            price=Decimal("9.99"),
            category=category,
        )

    first = client.get(reverse("products:catalog"))
    second = client.get(reverse("products:catalog"), {"page": 2})

    assert len(first.context["products"]) == 12
    assert len(second.context["products"]) == 1
    assert "Page 2 of 2" in second.content.decode()


# --- The seed command -------------------------------------------------------


def test_seed_builds_the_demo_world(db, media_root):
    call_command("seed")

    assert Category.objects.count() == 6
    assert Tag.objects.count() == 12
    assert Product.objects.count() == 34

    User = get_user_model()
    admin = User.objects.get(username="admin")
    employee = User.objects.get(username="employee")
    customer = User.objects.get(username="customer")
    assert admin.is_superuser
    assert employee.is_staff and not employee.is_superuser
    assert employee.job_title == "Junior Thought Curator"
    assert not customer.is_staff
    assert customer.cart.item_count() == 4
    assert customer.orders.count() == 4

    mark_one = Product.objects.get(slug="soulsear-mark-i")
    assert not mark_one.is_available
    assert mark_one.category.name == "Defense"

    # 40–60 orders across the trailing six months, per the PRD.
    assert Order.objects.count() == 52
    statuses = set(Order.objects.values_list("status", flat=True))
    assert statuses == set(Order.Status.values)

    # Marketing's 12 mapped images, prepared like any upload; the rest
    # of the catalog keeps its placeholders.
    with_images = [p for p in Product.objects.all() if p.has_image]
    assert len(with_images) == 12
    assert all(p.image.name.endswith(".webp") for p in with_images)
    assert Product.objects.get(slug="soulsear-mark-ii").has_image
    assert not Product.objects.get(slug="seraphine-mini").has_image


def test_seed_is_idempotent(db, media_root, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        call_command("seed")
    first = (
        Category.objects.count(),
        Tag.objects.count(),
        Product.objects.count(),
        get_user_model().objects.count(),
        CartItem.objects.count(),
        Order.objects.count(),
        OrderItem.objects.count(),
    )

    with django_capture_on_commit_callbacks(execute=True):
        call_command("seed")
    second = (
        Category.objects.count(),
        Tag.objects.count(),
        Product.objects.count(),
        get_user_model().objects.count(),
        CartItem.objects.count(),
        Order.objects.count(),
        OrderItem.objects.count(),
    )

    assert first == second
    # Reseeding empties media/products/ rather than piling up files.
    assert len(list((media_root / "products").iterdir())) == 12


def test_seed_stops_on_an_unusable_image_before_wiping(
    db, media_root, tmp_path, monkeypatch, product, make_image
):
    images_dir = tmp_path / "product-images"
    images_dir.mkdir()
    (images_dir / "tiny.png").write_bytes(make_image(150, 120).read())
    monkeypatch.setattr(seed, "PRODUCT_IMAGES_DIR", images_dir)
    monkeypatch.setattr(seed, "PRODUCT_IMAGES", {"tiny.png": "veil"})

    with pytest.raises(CommandError) as caught:
        call_command("seed")

    assert str(caught.value).startswith(
        'product-images/tiny.png: "tiny.png" is 150 × 120 pixels.'
    )
    assert list(Product.objects.all()) == [product]  # nothing was wiped


def test_seed_stops_on_a_missing_image(db, media_root, tmp_path, monkeypatch):
    monkeypatch.setattr(seed, "PRODUCT_IMAGES_DIR", tmp_path)
    monkeypatch.setattr(seed, "PRODUCT_IMAGES", {"gone.png": "veil"})

    with pytest.raises(CommandError, match="product-images/gone.png is missing."):
        call_command("seed")
