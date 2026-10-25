"""Review endpoints — thin HTMX views that return partials only.

The server is the gatekeeper: every endpoint re-runs the model's own
rule (``can_write`` or ``can_change``) and answers 403 when it fails,
whatever the page showed.
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


class ChangeReviewMixin(LoginRequiredMixin):
    """Load the review in the URL and re-run ``can_change``: its author or
    any staff member, else 403."""

    def get_review(self, request, pk) -> Review:
        review = get_object_or_404(
            Review.objects.select_related("user", "updated_by", "product"), pk=pk
        )
        if not review.can_change(request.user):
            raise PermissionDenied
        return review


class ReviewCardView(ChangeReviewMixin, View):
    """HTMX: one review's card — Cancel uses it to restore the card the
    edit form stood in for."""

    def get(self, request, pk):
        return render(
            request,
            "reviews/partials/_review.html",
            {"review": self.get_review(request, pk)},
        )


class EditReviewView(ChangeReviewMixin, View):
    """HTMX: edit a review in place.

    GET swaps the card for the pre-filled form; POST saves it as the
    acting user's edit and swaps the updated card back, with the summary
    out-of-band. Invalid input re-renders the form with its errors.
    """

    template_name = "reviews/partials/_form.html"

    def get_form(self, review, data=None) -> ReviewForm:
        # Per-review ids, so several open edit forms never share one.
        return ReviewForm(data, instance=review, auto_id=f"id_review{review.pk}_%s")

    def get(self, request, pk):
        review = self.get_review(request, pk)
        return render(
            request,
            self.template_name,
            {"form": self.get_form(review), "editing": review},
        )

    def post(self, request, pk):
        review = self.get_review(request, pk)
        form = self.get_form(review, request.POST)
        if not form.is_valid():
            return render(
                request, self.template_name, {"form": form, "editing": review}
            )
        review = form.save(commit=False)
        review.updated_by = request.user
        review.save()
        return render(
            request,
            "reviews/partials/_review.html",
            {
                "review": review,
                "review_summary": Review.objects.summary(review.product),
                "oob_summary": True,
            },
        )
