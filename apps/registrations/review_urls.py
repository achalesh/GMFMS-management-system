from django.urls import path

from . import review_views as views

app_name = "applications"
urlpatterns = [
    path("", views.index, name="index"),
    path("<uuid:pk>/", views.detail, name="detail"),
    path("<uuid:pk>/action/<str:action>/", views.action, name="action"),
    path("<uuid:pk>/files/<uuid:file_id>/", views.download, name="download"),
]
