from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("reviews/product/<int:pk>/", views.ReviewCreateView.as_view(), name="create"),
]
