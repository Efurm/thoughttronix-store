"""Review endpoints — HTMX-only, thin, and each its own gatekeeper.

Every write re-runs the model's rule (``can_write``) and answers 403
when it fails, whatever the page showed, so the interface and the
server can never disagree. Responses are partials; each change also
carries the rating summary as an out-of-band swap.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, render
from django.views import View

from products.models import Product

from .forms import ReviewForm
from .models import Review


class ReviewCreateView(LoginRequiredMixin, View):
    """HTMX: write a review of a product, then re-render the slot.

    A valid post swaps in the new card (and the summary, out of band);
    an invalid one swaps the form back in with its errors.
    """

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        if not Review.objects.can_write(request.user, product):
            raise PermissionDenied
        form = ReviewForm(request.POST)
        if not form.is_valid():
            return self.slot(product, can_write_review=True, review_form=form)
        form.instance.user = request.user
        form.instance.product = product
        try:
            with transaction.atomic():
                review = form.save()
        except IntegrityError:
            # A simultaneous submission won the one-review slot.
            raise PermissionDenied from None
        return self.slot(
            product,
            own_review=review,
            oob_summary=True,
            summary=Review.objects.summary(product),
        )

    def slot(self, product, **context):
        return render(
            self.request,
            "reviews/partials/_slot.html",
            {"product": product, **context},
        )
