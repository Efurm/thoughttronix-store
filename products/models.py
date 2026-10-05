from pathlib import PurePath

from django.db import models
from django.templatetags.static import static
from django.urls import reverse
from django.utils.crypto import get_random_string

# Categories with a dedicated placeholder illustration; anything else
# falls back to default.svg. A product without a usable uploaded image
# shows its category's placeholder (see Product.display_image_url).
PLACEHOLDER_CATEGORIES = {
    "home-assistants",
    "neural-implants",
    "neural-wearables",
    "accessories",
    "defense",
    "legacy-products",
}


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("products:category", kwargs={"slug": self.slug})

    @property
    def placeholder_image(self):
        """Static path of the placeholder image shown for this category's products."""
        if self.slug in PLACEHOLDER_CATEGORIES:
            return f"images/placeholders/{self.slug}.svg"
        return "images/placeholders/default.svg"


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


def product_image_path(product, filename):
    """Name an uploaded image ``products/<slug>-<random suffix><ext>``.

    The suffix keeps names unique and changes on every upload, so browsers
    never show a stale cached image after a replacement. The extension
    comes from the incoming file, which products/images.py always names
    ``.webp``.
    """
    suffix = get_random_string(6, allowed_chars="abcdefghijklmnopqrstuvwxyz0123456789")
    extension = PurePath(filename).suffix.lower()
    return f"products/{product.slug}-{suffix}{extension}"


class ProductQuerySet(models.QuerySet):
    def available(self):
        return self.filter(is_available=True)

    def featured(self):
        return self.filter(is_featured=True)

    def search(self, text):
        """Simple icontains search over name and description."""
        return self.filter(
            models.Q(name__icontains=text) | models.Q(description__icontains=text)
        )


class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    tagline = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="products")
    image = models.ImageField(upload_to=product_image_path, blank=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("products:detail", kwargs={"slug": self.slug})

    @property
    def display_image_url(self):
        """URL of the image to show for this product.

        The uploaded image only when one is set *and* its file is actually
        in storage; otherwise the category placeholder. Every template shows
        product images through this property, so a missing file can never
        reach the page as a broken image.
        """
        if self.image and self.image.storage.exists(self.image.name):
            return self.image.url
        return static(self.category.placeholder_image)
