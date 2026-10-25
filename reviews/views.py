"""Review endpoints — thin HTMX views that return partials only.

The server is the gatekeeper: every write re-runs the model's own rule
(``can_write``) and answers 403 when it fails, whatever the page showed.
Responses carry the summary as an out-of-band swap via the
``oob_summary`` context flag, as the cart responses carry the badge.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, render
from django.views import View

from products.models import Product

from .forms import ReviewForm
from .models import Review


class CreateReviewView(LoginRequiredMixin, View):
    """HTMX: write a review; the new card replaces the form in the slot.

    Invalid input re-renders the form with its errors in the same slot.
    """

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        if not Review.objects.can_write(request.user, product):
            raise PermissionDenied
        form = ReviewForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                "reviews/partials/_form.html",
                {"form": form, "product": product},
            )
        review = form.save(commit=False)
        review.user, review.product = request.user, product
        try:
            with transaction.atomic():
                review.save()
        except IntegrityError:
            # A simultaneous submission won the one-review slot first.
            raise PermissionDenied from None
        return render(
            request,
            "reviews/partials/_review.html",
            {
                "review": review,
                "review_summary": Review.objects.summary(product),
                "oob_summary": True,
                "oob_empty_state": True,
            },
        )
