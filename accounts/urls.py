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
]
