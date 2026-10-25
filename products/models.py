from pathlib import PurePath

from django.core.files.base import ContentFile
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
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
    def has_image(self):
        """True when an image is set *and* its file is actually in storage."""
        return bool(self.image) and self.image.storage.exists(self.image.name)

    @property
    def display_image_url(self):
        """URL of the image to show for this product.

        The uploaded image when ``has_image``; otherwise the category
        placeholder. Every template shows product images through this
        property, so a missing file can never reach the page as a broken
        image.
        """
        if self.has_image:
            return self.image.url
        return static(self.category.placeholder_image)

    def replace_image(self, content: ContentFile) -> None:
        """Store ``content`` (from products/images.py) as this product's image.

        The new file is written and the row saved first; the previous file
        is deleted only once that has committed, so the product always
        points at a file that exists.
        """
        old_name = self.image.name
        with transaction.atomic():
            self.image.save(content.name, content, save=False)
            self.save(update_fields=["image"])
            _delete_file_on_commit(self.image.storage, old_name)

    def remove_image(self) -> None:
        """Return this product to its placeholder, deleting the file on commit."""
        old_name = self.image.name
        with transaction.atomic():
            self.image = ""
            self.save(update_fields=["image"])
            _delete_file_on_commit(self.image.storage, old_name)


def _delete_file_on_commit(storage, name):
    if name:
        transaction.on_commit(lambda: storage.delete(name))


@receiver(post_delete, sender=Product)
def delete_product_image_file(sender, instance, **kwargs):
    """Delete a deleted product's image file once the delete commits.

    A signal rather than a ``delete()`` override, so bulk deletes — the
    Django admin's "delete selected", ``queryset.delete()`` — are covered.
    """
    _delete_file_on_commit(instance.image.storage, instance.image.name)
