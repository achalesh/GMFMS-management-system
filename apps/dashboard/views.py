from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from apps.accounts.policies import require_capability, scopes_for
from apps.facilitators.selectors import locations_for
from apps.locations.models import Block, District
from apps.reports.data import progress, snapshot, summarize


@never_cache
@require_capability("dashboard.view")
def home(request, district_id=None, block_id=None):
    filters = {}
    allowed = locations_for(request.user, "dashboard.view")
    title = "Network overview"
    if district_id:
        obj = get_object_or_404(
            District.objects.filter(blocks__panchayats__in=allowed).distinct(), pk=district_id
        )
        filters["district"] = obj
        title = obj.name_en
    if block_id:
        obj = get_object_or_404(
            Block.objects.filter(panchayats__in=allowed).distinct(), pk=block_id
        )
        filters["block"] = obj
        title = obj.name_en
    try:
        places, fs, apps = snapshot(request.user, filters)
    except ValidationError as e:
        return render(request, "reports/limit.html", {"error": e.messages}, status=400)
    contact_ids = (
        set(locations_for(request.user, "contacts.view").values_list("pk", flat=True))
        if block_id
        else set()
    )
    members = (
        [
            {
                "id": f.pk,
                "place": f.current_appointment.panchayat.name_en,
                "name": f.full_name,
                "number": f.facilitator_number,
                "status": f.report_status,
                "mobile": f.application.mobile
                if f.current_appointment.panchayat_id in contact_ids
                else "Restricted",
                "registered": f.application.submitted_at,
            }
            for f in fs
        ]
        if block_id
        else []
    )
    level = "panchayat" if block_id else "block" if district_id else "district"
    metrics = summarize(places, fs, apps)
    labels = [
        ("panchayats", "Panchayats"),
        ("blocks", "Blocks"),
        ("approved", "Approved facilitators"),
        ("active", "Active facilitators"),
        ("vacant", "Vacant panchayats"),
        ("suspended", "Suspended"),
        ("expired", "Expired"),
        ("expiring", "Expiring in 30 days"),
    ]
    application_access = bool(
        request.user.is_superuser or scopes_for(request.user, "applications.view")
    )
    if application_access:
        labels += [
            ("applications", "Applications received"),
            ("under_review", "Under review"),
            ("pending", "Pending decisions"),
        ]
    return render(
        request,
        "dashboard/home.html",
        {
            "members": members,
            "title": title,
            "metrics": metrics,
            "cards": [(label, metrics[key]) for key, label in labels],
            "progress": progress(places, fs, apps, level),
            "level": level,
            "application_access": application_access,
            "report_query": urlencode({k: v.pk for k, v in filters.items()}),
        },
    )


@login_required
def profile(request):
    return render(
        request,
        "accounts/profile.html",
        {
            "assignments": request.user.role_assignments.filter(active=True)
            .select_related("role")
            .prefetch_related("jurisdictions"),
        },
    )


def health(request):
    # Liveness only. No database, environment or configuration disclosure.
    return JsonResponse({"status": "ok"})


def error_400(request, exception):
    return render(request, "errors/400.html", status=400)


def error_403(request, exception):
    return render(request, "errors/403.html", status=403)


def error_404(request, exception):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    # Static page: must still work during a database outage.
    from django.http import HttpResponse
    from django.template.loader import render_to_string

    return HttpResponse(render_to_string("errors/500.html"), status=500)


@never_cache
def ready(request):
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ready"})
