from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Browse, search and delete reviews; never write them.

    Every field is read-only, so the only way to change a review's words
    is the product page, which records ``updated_by`` and runs the
    form's validation. Adding is off, because an admin-made review would
    skip the purchase rule. Delete, bulk delete included, stays on.
    """

    list_display = ("product", "user", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("product__name", "user__username")
    date_hierarchy = "created_at"
    readonly_fields = (
        "user",
        "product",
        "rating",
        "comment",
        "created_at",
        "updated_at",
        "updated_by",
    )

    def has_add_permission(self, request):
        return False
