from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters

from apps.audit.services import record_event
from apps.locations.models import Block, District
from apps.registrations.review_selectors import applications_for

from .forms import RegistryActionForm, RegistryFilter
from .models import FacilitatorAppointment
from .selectors import can_enter, locations_for, permitted, primary_appointments, registry_for
from .services import ACTIONS, registry_action


def access(view):
    @login_required
    @never_cache
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not can_enter(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped


def visible_rows(user, queryset):
    rows = list(queryset)
    contacts = set(
        registry_for(user, "contacts.view")
        .filter(pk__in=[r.pk for r in rows])
        .values_list("pk", flat=True)
    )
    for row in rows:
        row.contact_visible = row.pk in contacts
    return rows


@access
def index(request):
    base = registry_for(request.user)
    form = RegistryFilter(request.GET, user=request.user)
    results = base
    if form.is_valid():
        d = form.cleaned_data
        if d["q"]:
            q = d["q"]
            match = (
                Q(facilitator_number__icontains=q)
                | Q(full_name__icontains=q)
                | Q(name_ml__icontains=q)
                | Q(application__application_number__icontains=q)
                | Q(current_appointment__panchayat__name_en__icontains=q)
                | Q(current_appointment__panchayat__block__name_en__icontains=q)
                | Q(current_appointment__panchayat__block__district__name_en__icontains=q)
            )
            contact_ids = (
                registry_for(request.user, "contacts.view")
                .filter(application__mobile__icontains=q)
                .values("pk")
            )
            results = results.filter(match | Q(pk__in=contact_ids))
        for field, lookup in {
            "status": "display_status",
            "role": "current_appointment__role",
            "district": "current_appointment__panchayat__block__district",
            "block": "current_appointment__panchayat__block",
            "panchayat": "current_appointment__panchayat",
            "approval_from": "approved_at__date__gte",
            "approval_to": "approved_at__date__lte",
            "expiry_before": "valid_until__lte",
            "expiry_after": "valid_until__gte",
            "registered_from": "application__submitted_at__date__gte",
            "registered_to": "application__submitted_at__date__lte",
        }.items():
            if d[field]:
                results = results.filter(**{lookup: d[field]})
    else:
        results = results.none()
    page = Paginator(results.order_by("facilitator_number"), 25).get_page(request.GET.get("page"))
    page.object_list = visible_rows(request.user, page.object_list)
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "facilitators/index.html",
        {
            "form": form,
            "page": page,
            "filter_query": query.urlencode(),
            "total": base.count(),
            "active": base.filter(display_status="ACTIVE").count(),
        },
    )


@access
def detail(request, pk):
    f = get_object_or_404(registry_for(request.user), pk=pk)
    a = f.current_appointment
    if not a:
        raise Http404
    can_change = permitted(request.user, a.panchayat)
    contact_visible = permitted(request.user, a.panchayat, "contacts.view")
    application_visible = applications_for(request.user).filter(pk=f.application_id).exists()
    actions = []
    if can_change and f.status not in {"REVOKED", "REPLACED"}:
        actions = [(key, label) for key, label in ACTIONS.items()]
    record_event(actor=request.user, action="facilitator.viewed", entity=f)
    return render(
        request,
        "facilitators/detail.html",
        {
            "facilitator": f,
            "qr_access": can_change or permitted(request.user, a.panchayat, "cards.issue"),
            "appointment": a,
            "contact_visible": contact_visible,
            "application_visible": application_visible,
            "actions": actions,
            "appointments": f.appointments.select_related("panchayat__block__district").order_by(
                "-created_at", "pk"
            ),
            "history": f.status_history.select_related("changed_by").order_by("-pk")
            if can_change
            else None,
        },
    )


@access
@sensitive_post_parameters()
def action(request, pk, action):
    if action not in ACTIONS:
        raise Http404
    f = get_object_or_404(registry_for(request.user, "facilitators.change"), pk=pk)
    form = RegistryActionForm(request.POST or None, action=action, facilitator=f, user=request.user)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data.copy()
        if "panchayat" in data:
            data["panchayat_id"] = data.pop("panchayat").pk
        if "replacement" in data:
            data["replacement_id"] = data.pop("replacement").pk
        try:
            registry_action(actor=request.user, facilitator_id=f.pk, action=action, **data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(
                request,
                "Registry updated. The decision and appointment history have been recorded.",
            )
            return redirect("facilitators:detail", pk=f.pk)
    return render(
        request,
        "facilitators/action.html",
        {"facilitator": f, "form": form, "action": action, "label": ACTIONS[action]},
    )


@access
def coverage(request, district_id=None, block_id=None):
    places = locations_for(request.user).filter(
        active=True,
        block__active=True,
        block__district__active=True,
        block__district__state__active=True,
    )
    title = "Panchayat coverage"
    district = None
    region_blocks = None
    if district_id:
        district = get_object_or_404(
            District.objects.filter(pk__in=places.values("block__district_id")), pk=district_id
        )
        places = places.filter(block__district=district)
        title = district.name_en
        region_blocks = Block.objects.filter(pk__in=places.values("block_id"))
    if block_id:
        region = get_object_or_404(
            Block.objects.filter(pk__in=places.values("block_id")), pk=block_id
        )
        places = places.filter(block=region)
        district = region.district
        title = region.name_en + " Block"
    places = places.annotate(
        covered=Exists(primary_appointments().filter(panchayat_id=OuterRef("pk")))
    )
    total, occupied = places.count(), places.filter(covered=True).count()
    if request.GET.get("vacant") == "1":
        places = places.filter(covered=False)
    if request.GET.get("q"):
        places = places.filter(name_en__icontains=request.GET["q"][:150])
    page = Paginator(
        places.order_by("block__district__display_order", "block__name_en", "name_en", "pk"), 30
    ).get_page(request.GET.get("page"))
    rows = list(page.object_list)
    assignments = (
        primary_appointments()
        .filter(panchayat_id__in=[p.pk for p in rows])
        .select_related("facilitator__application")
    )
    contact_ids = set(registry_for(request.user, "contacts.view").values_list("pk", flat=True))
    by_place = {}
    for item in assignments:
        item.contact_visible = item.facilitator_id in contact_ids
        by_place.setdefault(item.panchayat_id, []).append(item)
    for place in rows:
        place.primary_assignments = by_place.get(place.pk, [])
    page.object_list = rows
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "facilitators/coverage.html",
        {
            "title": title,
            "district": district,
            "blocks": region_blocks,
            "districts": District.objects.filter(
                pk__in=locations_for(request.user).values("block__district_id")
            )
            if not district
            else None,
            "page": page,
            "total": total,
            "occupied": occupied,
            "vacant": total - occupied,
            "filter_query": query.urlencode(),
        },
    )


@access
def panchayat(request, pk):
    place = get_object_or_404(locations_for(request.user), pk=pk)
    history = list(
        FacilitatorAppointment.objects.filter(panchayat=place)
        .select_related("facilitator")
        .order_by("-created_at", "pk")
    )
    viewable = set(
        registry_for(request.user)
        .filter(pk__in=[a.facilitator_id for a in history])
        .values_list("pk", flat=True)
    )
    for a in history:
        a.facilitator_visible = a.facilitator_id in viewable
    current = visible_rows(
        request.user,
        registry_for(request.user).filter(
            current_appointment__panchayat=place, current_appointment__ended_at__isnull=True
        ),
    )
    return render(
        request,
        "facilitators/panchayat.html",
        {
            "place": place,
            "current": current,
            "appointments": history,
            "covered": primary_appointments().filter(panchayat=place).exists(),
            "applications": applications_for(request.user)
            .filter(panchayat=place)
            .order_by("-submitted_at")[:50],
        },
    )


@access
def portrait(request, pk):
    f = get_object_or_404(registry_for(request.user), pk=pk)
    upload = get_object_or_404(f.application.uploads, slot="photo")
    try:
        response = FileResponse(upload.file.open("rb"), content_type="image/jpeg")
    except (FileNotFoundError, OSError):
        raise Http404 from None
    response["Content-Disposition"] = 'inline; filename="portrait.jpg"'
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox; default-src 'none'"
    record_event(actor=request.user, action="facilitator.portrait_viewed", entity=f)
    return response
