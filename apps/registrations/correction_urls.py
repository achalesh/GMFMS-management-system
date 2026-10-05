from django.urls import path

from . import correction_views as views

app_name = "corrections"
urlpatterns = [
    path("complete/", views.complete, name="complete"),
    path("<uuid:pk>/", views.access, name="access"),
    path("<uuid:pk>/edit/", views.edit, name="edit"),
]
