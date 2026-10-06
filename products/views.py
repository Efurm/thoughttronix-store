from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from accounts.mixins import StaffRequiredMixin

from .forms import CategoryForm, ProductForm, ProductImageForm, TagForm
from .models import Category, Product, Tag


class CatalogView(ListView):
    """The public product catalog: search, tag and category filters, pagination.

    Filters arrive as querystring parameters (``q``, ``tag``, ``category``)
    and compose freely.
    """

    template_name = "products/catalog.html"
    context_object_name = "products"
    paginate_by = 12

    def get_queryset(self):
        products = Product.objects.select_related("category").prefetch_related("tags")
        query = self.request.GET.get("q", "").strip()
        if query:
            products = products.search(query)
        tag_slug = self.request.GET.get("tag", "")
        if tag_slug:
            products = products.filter(tags__slug=tag_slug)
        category_slug = self.request.GET.get("category", "")
        if category_slug:
            products = products.filter(category__slug=category_slug)
        return products

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "").strip()
        context["active_tag"] = self.request.GET.get("tag", "")
        context["categories"] = Category.objects.all()
        context["tags"] = Tag.objects.all()
        return context


class CategoryView(CatalogView):
    """Browse a single category — the catalog scoped to one shelf."""

    def get_queryset(self):
        self.category = get_object_or_404(Category, slug=self.kwargs["slug"])
        return super().get_queryset().filter(category=self.category)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category"] = self.category
        return context


class ProductDetailView(DetailView):
    """A single product at its slug URL."""

    template_name = "products/detail.html"
    context_object_name = "product"
    queryset = Product.objects.select_related("category").prefetch_related("tags")


# --- The back office --------------------------------------------------------
#
# Staff-only catalog management. Every view gates on StaffRequiredMixin;
# URLs use pks per the URL conventions. The ``section`` context entry
# drives the active tab in the staff shell (backoffice/base.html).


class ManageProductListView(StaffRequiredMixin, ListView):
    """The back-office product list — every product, available or not."""

    template_name = "products/manage_products.html"
    context_object_name = "products"
    extra_context = {"section": "products"}

    def get_queryset(self):
        return Product.objects.select_related("category")


class ManageProductCreateView(StaffRequiredMixin, SuccessMessageMixin, CreateView):
    """Create a product, then land on its edit page, where its image goes."""

    model = Product
    form_class = ProductForm
    template_name = "products/manage_product_form.html"
    success_message = "“%(name)s” created. Add its image below."
    extra_context = {"section": "products"}

    def get_success_url(self):
        return reverse("products:manage_product_update", kwargs={"pk": self.object.pk})


class ManageProductUpdateView(StaffRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "products/manage_product_form.html"
    success_url = reverse_lazy("products:manage_products")
    success_message = "“%(name)s” saved."
    extra_context = {"section": "products"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["image_form"] = ProductImageForm()
        return context


class ProductImageActionView(StaffRequiredMixin, View):
    """Base for the HTMX image card: act, then re-render the card.

    The card is its own form, separate from the product details, so an
    upload has exactly two outcomes — saved, or rejected with a plain
    explanation — and no other field can make a good file get lost.
    """

    def post(self, request, pk):
        product = get_object_or_404(Product.objects.select_related("category"), pk=pk)
        context = self.act(product)
        context.setdefault("image_form", ProductImageForm())
        context["product"] = product
        return render(request, "products/partials/_product_image.html", context)

    def act(self, product):
        raise NotImplementedError


class ManageProductImageUploadView(ProductImageActionView):
    """Upload or replace: store the prepared image, or show why not."""

    def act(self, product):
        form = ProductImageForm(self.request.POST, self.request.FILES)
        if not form.is_valid():
            return {"image_form": form}
        product.replace_image(form.cleaned_data["image"])
        return {"status": "Image saved."}


class ManageProductImageRemoveView(ProductImageActionView):
    """Remove: back to the category placeholder."""

    def act(self, product):
        if product.image:
            product.remove_image()
        return {"status": "Image removed."}


class ManageProductDeleteView(StaffRequiredMixin, SuccessMessageMixin, DeleteView):
    model = Product
    context_object_name = "product"
    template_name = "products/manage_product_confirm_delete.html"
    success_url = reverse_lazy("products:manage_products")
    success_message = "Product deleted."
    extra_context = {"section": "products"}


class ManageCatalogView(StaffRequiredMixin, TemplateView):
    """Categories and tags on one management page."""

    template_name = "products/manage_catalog.html"
    extra_context = {"section": "catalog"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.annotate(
            product_count=Count("products")
        )
        context["tags"] = Tag.objects.annotate(product_count=Count("products"))
        return context


class ManageCategoryCreateView(StaffRequiredMixin, SuccessMessageMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "products/manage_catalog_form.html"
    success_url = reverse_lazy("products:manage_catalog")
    success_message = "“%(name)s” created."
    extra_context = {"section": "catalog", "kind": "category"}


class ManageCategoryUpdateView(StaffRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "products/manage_catalog_form.html"
    success_url = reverse_lazy("products:manage_catalog")
    success_message = "“%(name)s” saved."
    extra_context = {"section": "catalog", "kind": "category"}


class ManageTagCreateView(StaffRequiredMixin, SuccessMessageMixin, CreateView):
    model = Tag
    form_class = TagForm
    template_name = "products/manage_catalog_form.html"
    success_url = reverse_lazy("products:manage_catalog")
    success_message = "“%(name)s” created."
    extra_context = {"section": "catalog", "kind": "tag"}


class ManageTagUpdateView(StaffRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Tag
    form_class = TagForm
    template_name = "products/manage_catalog_form.html"
    success_url = reverse_lazy("products:manage_catalog")
    success_message = "“%(name)s” saved."
    extra_context = {"section": "catalog", "kind": "tag"}
