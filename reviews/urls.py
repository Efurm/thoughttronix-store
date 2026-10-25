from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path(
        "reviews/product/<int:pk>/",
        views.CreateReviewView.as_view(),
        name="create",
    ),
    path("reviews/<int:pk>/", views.ReviewCardView.as_view(), name="detail"),
    path("reviews/<int:pk>/edit/", views.EditReviewView.as_view(), name="edit"),
]
