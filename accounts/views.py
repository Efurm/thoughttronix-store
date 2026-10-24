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
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from . import security
from .forms import (
    ChangePasswordForm,
    ResetPasswordForm,
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
