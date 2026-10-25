"""Back-office forms for the catalog models.

ModelForms inherit the models' own rules (name required, slug unique);
the explicit ``price`` declaration adds the one rule the model doesn't
carry — the price must be positive. Widgets get their DaisyUI classes
in one shared ``__init__`` loop, as on ``CheckoutForm``.
"""

from decimal import Decimal

from django import forms

from .images import prepare_product_image
from .models import Category, Product, Tag


class StyledModelForm(forms.ModelForm):
    """Base form that dresses every widget in DaisyUI classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "toggle toggle-primary"
            elif isinstance(widget, forms.Textarea):
                widget.attrs["class"] = "textarea w-full"
                widget.attrs.setdefault("rows", 6)
            elif isinstance(widget, forms.SelectMultiple):
                widget.attrs["class"] = "select h-auto w-full"
                widget.attrs.setdefault("size", 8)
            elif isinstance(widget, forms.Select):
                widget.attrs["class"] = "select w-full"
            else:
                widget.attrs["class"] = "input w-full"


class ProductForm(StyledModelForm):
    price = forms.DecimalField(
        label="Price (USD)",
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "slug",
            "tagline",
            "description",
            "price",
            "category",
            "tags",
            "is_available",
            "is_featured",
        ]


class ProductImageForm(forms.Form):
    """The back-office image card's one field.

    A plain ``FileField``, not ``forms.ImageField``: Django's own image
    check would answer first with its generic message. Every rule — and
    every plain-language rejection — comes from products/images.py, and
    a valid form's cleaned ``image`` is the prepared WebP, ready to store.
    """

    image = forms.FileField(
        label="Image file",
        help_text="PNG, JPEG, or WebP · up to 5 MB · at least 600 × 600 pixels.",
        error_messages={"required": "Choose an image file to upload."},
        widget=forms.FileInput(
            attrs={
                "class": "file-input w-full",
                "accept": "image/png,image/jpeg,image/webp",
            }
        ),
    )

    def clean_image(self):
        return prepare_product_image(self.cleaned_data["image"])


class CategoryForm(StyledModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug"]


class TagForm(StyledModelForm):
    class Meta:
        model = Tag
        fields = ["name", "slug"]
