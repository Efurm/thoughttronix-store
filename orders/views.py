"""Cart and checkout views — thin per the architecture convention.

The three HTMX interactions of the core live here: add-to-cart, quantity
change, and line removal. Each renders a partial (never ``base.html``);
the responses carry the navbar badge as an out-of-band swap via the
``oob_badge`` context flag. Checkout is conventional full-page work:
validate the form, hand everything to ``place_order``.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from accounts.mixins import StaffRequiredMixin
from products.models import Product

from .forms import CheckoutForm, CouponForm, OrderStatusForm
from .models import Cart, CartItem, Coupon, CouponError, Order
from .services import normalize_code, place_order, quote_coupon


def order_summary_context(cart, user, code, error=None):
    """Context for the checkout's order summary, with ``code`` priced in.

    ``error`` overrides the quote — used when ``place_order`` itself
    rejected the code, so the page shows exactly why the order didn't go
    through.
    """
    code = normalize_code(code)
    quote = None
    if error is None and code:
        try:
            quote = quote_coupon(code, cart, user)
        except CouponError as rejection:
            error = str(rejection)
    discounts = quote.line_discounts if quote else {}
    return {
        "cart": cart,
        "coupon_code": code,
        "coupon_error": error,
        "quote": quote,
        "summary_lines": [
            (line, discounts.get(line.product_id)) for line in cart.lines()
        ],
        "checkout_total": quote.total if quote else cart.total(),
    }


class CartView(LoginRequiredMixin, TemplateView):
    """The customer's cart page."""

    template_name = "orders/cart.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cart"] = Cart.for_user(self.request.user)
        return context


class AddToCartView(LoginRequiredMixin, View):
    """HTMX: add a product; the button swaps and the badge updates OOB.

    Looks the product up through ``available()``, so adding an
    unavailable product 404s — the same not-for-sale semantics as the
    public catalog.
    """

    def post(self, request, pk):
        product = get_object_or_404(Product.objects.available(), pk=pk)
        item = Cart.for_user(request.user).add(product)
        return render(
            request,
            "orders/partials/_add_button.html",
            {"product": product, "in_cart": item.quantity, "oob_badge": True},
        )


class CartItemActionView(LoginRequiredMixin, View):
    """Base for HTMX line mutations: act, then re-render the cart contents.

    Items are always fetched through the owner's cart — never by bare pk.
    """

    def post(self, request, pk):
        item = get_object_or_404(CartItem, pk=pk, cart__user=request.user)
        self.act(item)
        return render(
            request,
            "orders/partials/_cart_contents.html",
            {"cart": item.cart, "oob_badge": True},
        )

    def act(self, item):
        raise NotImplementedError


class IncrementCartItemView(CartItemActionView):
    def act(self, item):
        item.increment()


class DecrementCartItemView(CartItemActionView):
    def act(self, item):
        item.decrement()


class RemoveCartItemView(CartItemActionView):
    def act(self, item):
        item.delete()


class CheckoutView(LoginRequiredMixin, FormView):
    """The single checkout page: validate the form, hand off to the service.

    A cart that can't check out (empty, or holding a product that has
    since become unavailable) is sent back to the cart page to be fixed —
    ``place_order`` enforces the same rules transactionally as the
    backstop.
    """

    template_name = "orders/checkout.html"
    form_class = CheckoutForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        cart = Cart.for_user(request.user)
        if not cart.items.exists():
            messages.info(request, "Your cart is empty — add something first.")
            return redirect("orders:cart")
        unavailable = [
            line.product.name for line in cart.lines() if not line.product.is_available
        ]
        if unavailable:
            messages.warning(
                request,
                f"No longer available: {', '.join(unavailable)}. "
                "Remove them from the cart to check out.",
            )
            return redirect("orders:cart")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = context["form"]
        code = form["coupon_code"].value() if form.is_bound else ""
        errors = form.errors.get("coupon_code")
        context.update(
            order_summary_context(
                Cart.for_user(self.request.user),
                self.request.user,
                code,
                error=errors[0] if errors else None,
            )
        )
        return context

    def form_valid(self, form):
        """Place the order. A coupon that went bad since it was previewed
        stops the order and re-renders the page with the reason — the
        customer is never charged a total they weren't shown."""
        cart = Cart.for_user(self.request.user)
        try:
            order = place_order(
                cart,
                self.request.user,
                form.cleaned_data,
                coupon_code=form.cleaned_data["coupon_code"],
            )
        except CouponError as error:
            form.add_error("coupon_code", str(error))
            return self.form_invalid(form)
        messages.success(self.request, f"Order {order.number} placed. Thank you!")
        return redirect(reverse("orders:confirmation", kwargs={"pk": order.pk}))


class ApplyCouponView(LoginRequiredMixin, View):
    """HTMX: price the typed code into the checkout summary.

    Every outcome — a discount, a rejection, a blank code that clears
    the discount — renders the summary partial; the place-order button's
    total follows as an out-of-band swap.
    """

    def post(self, request):
        context = order_summary_context(
            Cart.for_user(request.user),
            request.user,
            request.POST.get("coupon_code", ""),
        )
        context["oob_total"] = True
        return render(request, "orders/partials/_order_summary.html", context)


class OwnOrdersMixin(LoginRequiredMixin):
    """Orders are always fetched through the owner — never by bare pk."""

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)


class OrderConfirmationView(OwnOrdersMixin, DetailView):
    template_name = "orders/confirmation.html"
    context_object_name = "order"


class OrderHistoryView(OwnOrdersMixin, ListView):
    """The customer's orders, most recent first per the model ordering."""

    template_name = "orders/order_history.html"
    context_object_name = "orders"


class OrderDetailView(OwnOrdersMixin, DetailView):
    template_name = "orders/order_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("items")


# --- The back office --------------------------------------------------------
#
# Staff-only order oversight: every customer's orders, filterable by
# status, with the status dropdown on the detail page. The ``section``
# context entry drives the active tab in the staff shell.


class ManageOrderListView(StaffRequiredMixin, ListView):
    """All orders, most recent first, filterable via ``?status=``."""

    template_name = "orders/manage_orders.html"
    context_object_name = "orders"
    paginate_by = 20
    extra_context = {"section": "orders"}

    def get_queryset(self):
        orders = Order.objects.select_related("user")
        status = self.request.GET.get("status", "")
        if status in Order.Status.values:
            orders = orders.filter(status=status)
        return orders

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = Order.Status.choices
        context["active_status"] = self.request.GET.get("status", "")
        return context


class ManageOrderDetailView(StaffRequiredMixin, DetailView):
    """Any order's detail, with the status form alongside."""

    template_name = "orders/manage_order_detail.html"
    context_object_name = "order"
    queryset = Order.objects.select_related("user").prefetch_related("items")
    extra_context = {"section": "orders"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_form"] = OrderStatusForm(instance=self.object)
        return context


class UpdateOrderStatusView(StaffRequiredMixin, View):
    """POST-only: set an order's status from the back-office dropdown."""

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"{order.number} is now {order.get_status_display().lower()}.",
            )
        else:
            messages.error(request, "That isn't a status an order can have.")
        return redirect("orders:manage_order_detail", pk=order.pk)


# Coupons: staff create, edit, and retire discount codes with no help
# from engineering. A used coupon can't be deleted (orders PROTECT it) —
# retiring it is the way out, and past orders keep their own copy.


class CouponAuditMixin:
    """Stamp who created and who last changed a coupon."""

    def form_valid(self, form):
        if form.instance.pk is None:
            form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        return super().form_valid(form)


class ManageCouponListView(StaffRequiredMixin, ListView):
    """Every coupon — live, scheduled, expired, and retired — with its uses."""

    template_name = "orders/manage_coupons.html"
    context_object_name = "coupons"
    extra_context = {"section": "coupons"}

    def get_queryset(self):
        return Coupon.objects.annotate(
            use_count=Count("orders", distinct=True),
            product_count=Count("products", distinct=True),
        )


class ManageCouponCreateView(
    StaffRequiredMixin, CouponAuditMixin, SuccessMessageMixin, CreateView
):
    model = Coupon
    form_class = CouponForm
    template_name = "orders/manage_coupon_form.html"
    success_url = reverse_lazy("orders:manage_coupons")
    success_message = "%(code)s created."
    extra_context = {"section": "coupons"}


class ManageCouponUpdateView(
    StaffRequiredMixin, CouponAuditMixin, SuccessMessageMixin, UpdateView
):
    model = Coupon
    form_class = CouponForm
    template_name = "orders/manage_coupon_form.html"
    success_url = reverse_lazy("orders:manage_coupons")
    success_message = "%(code)s saved."
    extra_context = {"section": "coupons"}


class ManageCouponDeleteView(StaffRequiredMixin, DeleteView):
    """Delete a coupon no order has used — a typo, a false start.

    A used coupon is turned away with a pointer to retiring it instead.
    """

    model = Coupon
    context_object_name = "coupon"
    template_name = "orders/manage_coupon_confirm_delete.html"
    success_url = reverse_lazy("orders:manage_coupons")
    extra_context = {"section": "coupons"}

    def form_valid(self, form):
        coupon = self.object
        if coupon.is_used:
            messages.error(
                self.request,
                f"{coupon.code} has been used, so it can't be deleted — retire it instead.",
            )
            return redirect("orders:manage_coupons")
        messages.success(self.request, f"{coupon.code} deleted.")
        return super().form_valid(form)


class RetireCouponView(StaffRequiredMixin, View):
    """POST-only: switch a coupon off. Orders that used it are untouched."""

    def post(self, request, pk):
        coupon = get_object_or_404(Coupon, pk=pk)
        coupon.is_active = False
        coupon.updated_by = request.user
        coupon.save(update_fields=["is_active", "updated_by", "updated_at"])
        messages.success(
            request,
            f"{coupon.code} retired. Orders that already used it are unchanged.",
        )
        return redirect("orders:manage_coupons")
