from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("product__name", "user__username")
    # Browse and delete only. A review's words change only on the product
    # page, which records updated_by and runs the form's validation; an
    # admin-made review would skip the purchase rule.
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
