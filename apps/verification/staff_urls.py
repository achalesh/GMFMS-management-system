from django.urls import path

from . import views

app_name = "verification_staff"
urlpatterns = [
    path("<uuid:pk>/", views.staff, name="detail"),
    path("<uuid:pk>/qr.png", views.download_qr, name="qr"),
    path("<uuid:pk>/rotate/", views.rotate, name="rotate"),
]
