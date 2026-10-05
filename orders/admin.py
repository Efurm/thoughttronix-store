from django.contrib import admin

from .models import Cart, CartItem, Coupon, Order, OrderItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "item_count", "total")
    search_fields = ("user__username",)
    inlines = [CartItemInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "user", "status", "total", "coupon_code", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username", "shipping_name")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "percent_off", "starts_at", "ends_at", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    filter_horizontal = ("products",)
    readonly_fields = ("created_by", "updated_by", "created_at", "updated_at")
