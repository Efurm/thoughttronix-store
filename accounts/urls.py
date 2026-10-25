from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("login/", views.SignInView.as_view(), name="login"),
    path("logout/", views.SignOutView.as_view(), name="logout"),
    path("security/", views.SecurityCenterView.as_view(), name="security"),
    path(
        "security/password/",
        views.ChangePasswordView.as_view(),
        name="password_change",
    ),
    path(
        "security/password/done/",
        views.ChangePasswordDoneView.as_view(),
        name="password_change_done",
    ),
    path(
        "security/secondary-email/",
        views.SecondaryEmailView.as_view(),
        name="secondary_email",
    ),
    path(
        "security/secondary-email/remove/",
        views.RemoveSecondaryEmailView.as_view(),
        name="secondary_email_remove",
    ),
    path(
        "security/secondary-email/resend/",
        views.ResendSecondaryConfirmationView.as_view(),
        name="secondary_email_resend",
    ),
    path(
        "secondary-email/confirm/<str:token>/",
        views.ConfirmSecondaryEmailView.as_view(),
        name="secondary_email_confirm",
    ),
    path(
        "password-reset/",
        views.ResetPasswordView.as_view(),
        name="password_reset",
    ),
    path(
        "password-reset/sent/",
        views.ResetPasswordDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        views.ResetPasswordConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        views.ResetPasswordCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
