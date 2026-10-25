from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, FormView, TemplateView

from . import security
from .forms import (
    ChangePasswordForm,
    ResetPasswordForm,
    SecondaryEmailForm,
    SetNewPasswordForm,
    SignInForm,
    SignupForm,
)


class SignupView(SuccessMessageMixin, CreateView):
    """Create a customer account, then hand off to the login page.

    New users sign in themselves — auto-login after signup is left as a
    student exercise.
    """

    form_class = SignupForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("accounts:login")
    success_message = "Account created — you can now sign in."


class SignInView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = SignInForm


class SignOutView(LogoutView):
    def post(self, request, *args, **kwargs):
        # Flash after super() has flushed the session, or the message
        # would be wiped along with it.
        response = super().post(request, *args, **kwargs)
        messages.info(request, "You have signed out.")
        return response


# --- Account Security Center ---------------------------------------------------


class SecurityCenterView(LoginRequiredMixin, TemplateView):
    """The hub: the account's email addresses and links to the focused
    one-form pages. Staff use this same storefront page."""

    template_name = "accounts/security.html"


class ChangePasswordView(PasswordChangeView):
    """Django's stock change-password view, plus the "password changed"
    notice.

    The stock view already requires sign-in and refreshes the session
    hash, so this device stays signed in while every other session is
    signed out.
    """

    form_class = ChangePasswordForm
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:password_change_done")

    def form_valid(self, form):
        response = super().form_valid(form)
        security.send_security_notice(form.user, security.Notice.PASSWORD_CHANGED)
        return response


class ChangePasswordDoneView(PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"


# --- Secondary email ----------------------------------------------------------


def _confirmation_sent_message(address):
    return (
        f"We've sent a confirmation link to {address}. Open it to start using "
        "this address for recovery. Nothing arrived? Wait a minute, then send "
        "it again."
    )


class SecondaryEmailView(LoginRequiredMixin, FormView):
    """Add or replace the secondary email. The form checks the current
    password and the uniqueness rules; the security module does the rest."""

    form_class = SecondaryEmailForm
    template_name = "accounts/secondary_email.html"
    success_url = reverse_lazy("accounts:security")

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}

    def form_valid(self, form):
        address = form.cleaned_data["email"]
        security.request_secondary_email(self.request.user, address, self.request)
        messages.success(self.request, _confirmation_sent_message(address))
        return super().form_valid(form)


class RemoveSecondaryEmailView(LoginRequiredMixin, View):
    """A POST-only button on the hub: drop the secondary, pending or
    verified."""

    http_method_names = ["post"]

    def post(self, request):
        if security.remove_secondary_email(request.user):
            messages.success(request, "Your secondary email was removed.")
        return redirect("accounts:security")


class ResendSecondaryConfirmationView(LoginRequiredMixin, View):
    """A POST-only button on the hub: mail a fresh confirmation link while
    the secondary is pending. The cooldown skips a second email inside a
    minute without changing the message."""

    http_method_names = ["post"]

    def post(self, request):
        user = request.user
        if user.has_pending_secondary_email:
            security.send_secondary_confirmation(user, request)
            messages.success(request, _confirmation_sent_message(user.secondary_email))
        return redirect("accounts:security")


class ConfirmSecondaryEmailView(TemplateView):
    """The emailed confirmation link. Works signed out, on any device.

    A GET only shows the address and a Confirm button, so email scanners
    that follow links confirm nothing; the POST does the confirming.
    """

    template_name = "accounts/secondary_email_confirm.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            _user, context["address"] = security.check_confirmation_token(
                kwargs["token"]
            )
        except security.ConfirmationError as error:
            context["error"] = str(error)
        return context

    def post(self, request, token):
        try:
            user = security.confirm_secondary_email(token)
        except security.ConfirmationError as error:
            context = {"error": str(error)}
        else:
            context = {"confirmed": True, "address": user.secondary_email}
        return self.render_to_response(context)


# --- Forgotten password -------------------------------------------------------


class ResetPasswordView(PasswordResetView):
    """Step 1: ask for an address. The form owns matching, the cooldown and
    where the link goes; every outcome lands on the same done page."""

    form_class = ResetPasswordForm
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/email/password_reset.txt"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class ResetPasswordDoneView(PasswordResetDoneView):
    """Step 2: the same "if an account matches" message for everyone."""

    template_name = "accounts/password_reset_done.html"


class ResetPasswordConfirmView(PasswordResetConfirmView):
    """Step 3: the emailed link. Django's token expires after
    ``PASSWORD_RESET_TIMEOUT`` and dies once the password changes, which
    also makes it single-use. Sends the "password reset" notice; the
    customer signs in themselves afterwards."""

    form_class = SetNewPasswordForm
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form):
        response = super().form_valid(form)
        security.send_security_notice(form.user, security.Notice.PASSWORD_RESET)
        return response


class ResetPasswordCompleteView(PasswordResetCompleteView):
    """Step 4: done — off to sign in."""

    template_name = "accounts/password_reset_complete.html"
