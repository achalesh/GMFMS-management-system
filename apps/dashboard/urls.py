from django.urls import path

from . import views

app_name = "dashboard"
urlpatterns = [
    path("dashboard/districts/<int:district_id>/", views.home, name="district"),
    path("dashboard/blocks/<int:block_id>/", views.home, name="block"),
    path("", views.home, name="home"),
    path("profile/", views.profile, name="profile"),
]
