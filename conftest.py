"""Project-wide pytest fixtures.

Shared test data lives here as plain fixtures — no factories. The suite
grows with the project; tests never invoke the seed command.
"""

from datetime import timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from orders.models import Cart, CartItem, Coupon
from products.models import Category, Product, Tag


@pytest.fixture
def customer(db):
    return get_user_model().objects.create_user(
        username="customer", password="customer123"
    )


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_user(
        username="employee",
        password="employee123",
        is_staff=True,
        job_title="Junior Thought Curator",
    )


@pytest.fixture
def category(db):
    return Category.objects.create(name="Home Assistants", slug="home-assistants")


@pytest.fixture
def product(category):
    return Product.objects.create(
        name="Seraphine Home Hub",
        slug="seraphine-home-hub",
        tagline="She's always listening. In a good way.",
        description="The flagship Seraphine hub with a seven-microphone array.",
        price=Decimal("349.99"),
        category=category,
    )


@pytest.fixture
def media_root(settings, tmp_path):
    """Point MEDIA_ROOT at a throwaway folder so tests never touch media/."""
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


@pytest.fixture
def make_image():
    """Build an in-memory image upload: ``make_image(width, height, ...)``."""

    def build(width=800, height=1000, format="PNG", name="photo.png", mode="RGB"):
        buffer = BytesIO()
        Image.new(mode, (width, height), "steelblue").save(buffer, format=format)
        return SimpleUploadedFile(name, buffer.getvalue())

    return build


@pytest.fixture
def product_with_image(product, media_root, make_image):
    """The Seraphine Home Hub with an image file saved in media_root."""
    product.image.save("seraphine.webp", make_image(format="WEBP", name="x.webp"))
    return product


@pytest.fixture
def unavailable_product(category):
    return Product.objects.create(
        name="EchoPatch",
        slug="echopatch",
        tagline="Never miss a word. Anyone's.",
        price=Decimal("139.00"),
        is_available=False,
        category=category,
    )


@pytest.fixture
def tag(db):
    return Tag.objects.create(name="bestseller", slug="bestseller")


@pytest.fixture
def cart(customer):
    return Cart.for_user(customer)


@pytest.fixture
def cart_item(cart, product):
    return CartItem.objects.create(cart=cart, product=product, quantity=2)


@pytest.fixture
def coupon(db):
    """A live, order-wide 15%-off code that ran from yesterday to next month."""
    now = timezone.now()
    return Coupon.objects.create(
        code="FALLS",
        name="Fall 2026",
        percent_off=15,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=30),
    )
