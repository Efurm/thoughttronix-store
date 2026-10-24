from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)

from . import security
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


class ResetPasswordForm(PasswordResetForm):
    """Django's stock reset request, matched and mailed our way.

    The typed address is matched, ignoring capitals, against active users'
    primary emails. The link goes to the address typed, never somewhere
    the visitor did not ask about, and at most once a minute per address.
    Whatever happens, the view shows the same "if an account matches"
    message, so the page never reveals who has an account.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs["class"] = "input w-full"

    def get_users(self, email):
        users = User.objects.filter(email__iexact=email, is_active=True)
        return (user for user in users if user.has_usable_password())

    def save(self, *args, **kwargs):
        if security.claim_mail_cooldown(self.cleaned_data["email"]):
            super().save(*args, **kwargs)

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        typed = self.cleaned_data["email"]
        context["email"] = typed
        super().send_mail(
            subject_template_name,
            email_template_name,
            context,
            from_email,
            typed,
            html_email_template_name=html_email_template_name,
        )


class SetNewPasswordForm(SetPasswordForm):
    """The stock "new password twice" form behind a reset link, dressed in
    DaisyUI."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"
