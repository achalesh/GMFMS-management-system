from django.urls import path

from . import views

app_name = "locations"
urlpatterns = [
    path("options/blocks/", views.block_options, name="block-options"),
    path("", views.index, name="index"),
    path("districts/<int:pk>/", views.district_detail, name="district"),
    path("blocks/<int:pk>/", views.block_detail, name="block"),
    path("panchayats/", views.panchayat_list, name="panchayats"),
    path("panchayats/<int:pk>/", views.panchayat_detail, name="panchayat"),
    path("edit/<str:kind>/<int:pk>/", views.edit, name="edit"),
    path("import/", views.import_master, name="import"),
    path("import/template/", views.import_template, name="template"),
]
