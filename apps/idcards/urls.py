from django.urls import path

from . import views

app_name = "idcards"
urlpatterns = [
    path("<uuid:pk>/", views.index, name="index"),
    path("<uuid:pk>/generate/", views.generate, name="generate"),
    path("<uuid:pk>/<uuid:card_id>/", views.detail, name="detail"),
    path("<uuid:pk>/<uuid:card_id>/preview/<str:side>/", views.preview, name="preview"),
    path("<uuid:pk>/<uuid:card_id>/actions/<str:operation>/", views.action, name="action"),
]
