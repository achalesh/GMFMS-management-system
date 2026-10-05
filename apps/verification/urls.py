from django.urls import path

from . import views

app_name = "verification"
urlpatterns = [
    path("<str:token>/", views.verify, name="verify"),
    path("<str:token>/portrait/", views.portrait, name="portrait"),
]
