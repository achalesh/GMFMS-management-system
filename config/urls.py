from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.accounts.api import CurrentUserView
from apps.audit.views import index as audit_index
from apps.dashboard.views import health, ready
from apps.locations.api import BlockList, DistrictList, PanchayatList
from apps.verification.views import api as verification_api
from config import admin as admin_config  # noqa: F401

urlpatterns = [
    path("reports/", include("apps.reports.urls")),
    path("cards/", include("apps.idcards.urls")),
    path("verify/", include("apps.verification.urls")),
    path("verification/", include("apps.verification.staff_urls")),
    path("api/v1/verify/<str:token>/", verification_api, name="public-verification-api"),
    path("facilitators/", include("apps.facilitators.urls")),
    path("applications/", include("apps.registrations.review_urls")),
    path("correct/", include("apps.registrations.correction_urls")),
    path("register/media-facilitator/", include("apps.registrations.urls")),
    path("", include("apps.dashboard.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("settings/", include("apps.organization.urls")),
    path("audit/", audit_index, name="audit"),
    # Use the same throttled login for emergency admin.
    path("admin/login/", lambda request: redirect("accounts:login")),
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("locations/", include("apps.locations.urls")),
    path("api/v1/districts/", DistrictList.as_view(), name="api-districts"),
    path("api/v1/blocks/", BlockList.as_view(), name="api-blocks"),
    path("api/v1/panchayats/", PanchayatList.as_view(), name="api-panchayats"),
    path("health/", health, name="health"),
    path("internal/ready/", ready, name="ready"),
    path("api/v1/auth/me/", CurrentUserView.as_view(), name="api-me"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"),
]
handler400 = "apps.dashboard.views.error_400"
handler403 = "apps.dashboard.views.error_403"
handler404 = "apps.dashboard.views.error_404"
handler500 = "apps.dashboard.views.error_500"
