"""Review endpoints — HTMX-only, thin, and each its own gatekeeper.

Every write re-runs the model's rule (``can_write``) and answers 403
when it fails, whatever the page showed, so the interface and the
server can never disagree. Responses are partials; each change also
carries the rating summary as an out-of-band swap.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import Http404
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
            return render_slot(
                request, product, can_write_review=True, review_form=form
            )
        form.instance.user = request.user
        form.instance.product = product
        try:
            with transaction.atomic():
                review = form.save()
        except IntegrityError:
            # A simultaneous submission won the one-review slot.
            raise PermissionDenied from None
        return render_slot(
            request,
            product,
            own_review=review,
            oob_summary=True,
            summary=Review.objects.summary(product),
        )


class ReviewMoreView(View):
    """HTMX: the next batch of reviews. Public — it only reads."""

    def get(self, request, pk, page):
        if page < 1:
            raise Http404("Pages start at 1.")
        product = get_object_or_404(Product, pk=pk)
        reviews, has_more = (
            Review.objects.filter(product=product)
            .excluding_author(request.user)
            .for_display()
            .page(page)
        )
        return render(
            request,
            "reviews/partials/_more.html",
            {
                "product": product,
                "reviews": reviews,
                "has_more_reviews": has_more,
                "next_page": page + 1,
            },
        )


class ChangeReviewMixin(LoginRequiredMixin):
    """Base for endpoints that act on one review: its author or staff only."""

    def get_review(self):
        """The review at ``pk``, or 403 unless the user ``can_change`` it."""
        review = get_object_or_404(Review.objects.for_display(), pk=self.kwargs["pk"])
        if not review.can_change(self.request.user):
            raise PermissionDenied
        return review


class ReviewCardView(ChangeReviewMixin, View):
    """HTMX: one review's card — what Cancel restores."""

    def get(self, request, pk):
        return render_card(request, self.get_review())


class ReviewEditView(ChangeReviewMixin, View):
    """HTMX: the edit form in the card's place, and saving it.

    GET swaps the card for the pre-filled form. A valid POST records the
    editor in ``updated_by`` and swaps the saved card back, with the
    summary out of band; an invalid one swaps the form back with its
    errors and changes nothing.
    """

    def get(self, request, pk):
        review = self.get_review()
        return render_form(request, ReviewForm(instance=review), review)

    def post(self, request, pk):
        review = self.get_review()
        form = ReviewForm(request.POST, instance=review)
        if not form.is_valid():
            return render_form(request, form, review)
        form.instance.updated_by = request.user
        review = form.save()
        return render_card(
            request,
            review,
            oob_summary=True,
            summary=Review.objects.summary(review.product),
        )


class ReviewDeleteView(ChangeReviewMixin, View):
    """HTMX: delete a review after the browser's confirm prompt.

    The author's own delete re-renders their slot: the form if they can
    write again, else why not. Anyone else's delete (staff moderating)
    answers with only the summary, out of band, so the card's own swap
    removes it.
    """

    def post(self, request, pk):
        review = self.get_review()
        product = review.product
        own = review.user_id == request.user.pk
        review.delete()
        summary = Review.objects.summary(product)
        if not own:
            return render(
                request,
                "reviews/partials/_summary.html",
                {"summary": summary, "oob": True},
            )
        can_write = Review.objects.can_write(request.user, product)
        return render_slot(
            request,
            product,
            can_write_review=can_write,
            review_form=ReviewForm() if can_write else None,
            oob_summary=True,
            summary=summary,
        )


def render_slot(request, product, **context):
    return render(
        request, "reviews/partials/_slot.html", {"product": product, **context}
    )


def render_card(request, review, **context):
    return render(
        request, "reviews/partials/_review.html", {"review": review, **context}
    )


def render_form(request, form, review):
    return render(
        request, "reviews/partials/_form.html", {"form": form, "editing": review}
    )
