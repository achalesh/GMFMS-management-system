from django.urls import path

from . import views

app_name = "registrations"
urlpatterns = [
    path("", views.start, name="start"),
    path("step/<int:step>/", views.step, name="step"),
    path("confirmation/", views.confirmation, name="confirmation"),
    path("photo/<uuid:pk>/", views.preview_photo, name="photo"),
    path("discard/", views.discard, name="discard"),
]
