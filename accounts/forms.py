from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserCreationForm,
)

from .models import User


class SignupForm(UserCreationForm):
    """Django's stock signup fields plus a required primary email.

    The email is stored as typed but compared ignoring capitals, so an
    address already on another account is turned away with a plain error
    rather than a database error. The widgets carry DaisyUI classes
    because plain Django forms own their own styling here.
    """

    email = forms.EmailField(
        label="Email",
        help_text="We only use it to help you recover your account.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "That email address is already in use. Sign in instead, "
                "or use a different address."
            )
        return email


class SignInForm(AuthenticationForm):
    """The stock authentication form, dressed in DaisyUI."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"


class ChangePasswordForm(PasswordChangeForm):
    """The stock change-password form (old password, new one twice),
    dressed in DaisyUI."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"
