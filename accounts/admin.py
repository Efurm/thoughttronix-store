from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = (
        *DjangoUserAdmin.fieldsets,
        (
            "ThoughtTronix",
            {"fields": ("job_title", "secondary_email", "secondary_email_verified")},
        ),
    )
    # The secondary changes only through the Security Center, which asks for
    # the password and alerts the primary. The primary stays editable here.
    readonly_fields = ("secondary_email", "secondary_email_verified")
    list_display = ("username", "email", "job_title", "is_staff")
