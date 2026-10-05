from django.urls import path

from . import views

app_name = "organization"
urlpatterns = [
    path("organization/", views.organization, name="settings"),
    path("system/", views.system, name="system"),
]
