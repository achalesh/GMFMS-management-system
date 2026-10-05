from django.urls import path

from . import views

app_name = "facilitators"
urlpatterns = [
    path("", views.index, name="index"),
    path("coverage/", views.coverage, name="coverage"),
    path("coverage/districts/<int:district_id>/", views.coverage, name="district"),
    path("coverage/blocks/<int:block_id>/", views.coverage, name="block"),
    path("panchayats/<int:pk>/", views.panchayat, name="panchayat"),
    path("<uuid:pk>/portrait/", views.portrait, name="portrait"),
    path("<uuid:pk>/", views.detail, name="detail"),
    path("<uuid:pk>/actions/<str:action>/", views.action, name="action"),
]
