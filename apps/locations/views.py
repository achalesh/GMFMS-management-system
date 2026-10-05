import csv

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.policies import can, require_capability

from .forms import BlockForm, DistrictForm, ImportForm, PanchayatForm, StateForm
from .importing import COLUMNS, import_locations, parse_file
from .models import Block, District, GramaPanchayat, LocationImport, State
from .selectors import staff_locations
from .services import update_location


@require_capability("locations.view")
def index(request):
    districts = staff_locations(request.user, District)
    blocks = staff_locations(request.user, Block)
    panchayats = staff_locations(request.user, GramaPanchayat)
    rows = districts.annotate(
        block_count=Count("blocks", filter=Q(blocks__in=blocks), distinct=True),
        panchayat_count=Count(
            "blocks__panchayats", filter=Q(blocks__panchayats__in=panchayats), distinct=True
        ),
    )
    return render(
        request,
        "locations/index.html",
        {
            "districts": rows,
            "district_count": districts.count(),
            "block_count": blocks.count(),
            "panchayat_count": panchayats.count(),
            "can_manage": can(request.user, "locations.manage"),
            "latest_import": LocationImport.objects.first()
            if can(request.user, "locations.manage")
            else None,
            "state": State.objects.filter(code="KL").first(),
        },
    )


@require_capability("locations.view")
def district_detail(request, pk):
    district = get_object_or_404(staff_locations(request.user, District), pk=pk)
    blocks = (
        staff_locations(request.user, Block)
        .filter(district=district)
        .annotate(panchayat_count=Count("panchayats"))
    )
    return render(
        request,
        "locations/district.html",
        {
            "district": district,
            "blocks": blocks,
            "can_manage": can(request.user, "locations.manage"),
        },
    )


@require_capability("locations.view")
def block_detail(request, pk):
    block = get_object_or_404(
        staff_locations(request.user, Block).select_related("district"), pk=pk
    )
    panchayats = staff_locations(request.user, GramaPanchayat).filter(block=block)
    return render(
        request,
        "locations/block.html",
        {
            "location_block": block,
            "panchayats": panchayats,
            "can_manage": can(request.user, "locations.manage"),
        },
    )


@require_capability("locations.view")
def panchayat_detail(request, pk):
    panchayat = get_object_or_404(
        staff_locations(request.user, GramaPanchayat).select_related("block__district__state"),
        pk=pk,
    )
    return render(
        request,
        "locations/panchayat.html",
        {"panchayat": panchayat, "can_manage": can(request.user, "locations.manage")},
    )


@require_capability("locations.view")
def panchayat_list(request):
    queryset = staff_locations(request.user, GramaPanchayat).select_related("block__district")
    district = request.GET.get("district", "")
    block = request.GET.get("block", "")
    query = request.GET.get("q", "").strip()[:150]
    status = request.GET.get("status", "")
    if district:
        queryset = (
            queryset.filter(block__district_id=int(district))
            if district.isascii() and district.isdigit() and len(district) <= 10
            else queryset.none()
        )
    if block:
        queryset = (
            queryset.filter(block_id=int(block))
            if block.isascii() and block.isdigit() and len(block) <= 10
            else queryset.none()
        )
    if query:
        queryset = queryset.filter(
            Q(name_en__icontains=query)
            | Q(name_ml__icontains=query)
            | Q(sec_local_body_code__icontains=query)
            | Q(lsg_code__icontains=query)
        )
    if status in {"active", "inactive"}:
        queryset = queryset.filter(active=status == "active")
    districts = staff_locations(request.user, District)
    blocks = staff_locations(request.user, Block).none()
    if district.isascii() and district.isdigit() and len(district) <= 10:
        blocks = staff_locations(request.user, Block).filter(district_id=int(district))
    filters = request.GET.copy()
    filters.pop("page", None)
    return render(
        request,
        "locations/panchayats.html",
        {
            "page": Paginator(queryset, 25).get_page(request.GET.get("page")),
            "districts": districts,
            "blocks": blocks,
            "selected_district": district,
            "selected_block": block,
            "query": query,
            "status_filter": status,
            "filter_query": filters.urlencode(),
        },
    )


@require_capability("locations.manage")
def edit(request, kind, pk):
    contracts = {
        "state": (State, StateForm),
        "district": (District, DistrictForm),
        "block": (Block, BlockForm),
        "panchayat": (GramaPanchayat, PanchayatForm),
    }
    if kind not in contracts:
        from django.http import Http404

        raise Http404
    model, form_class = contracts[kind]
    instance = get_object_or_404(model, pk=pk)
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        try:
            update_location(
                actor=request.user,
                model=model,
                pk=pk,
                values={key: form.cleaned_data[key] for key in form_class.Meta.fields},
                expected_revision=form.cleaned_data["expected_revision"],
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(
                request, "Location updated. The change has been recorded in the audit trail."
            )
            return redirect("locations:index")
    return render(
        request, "locations/edit.html", {"form": form, "location": instance, "kind": kind}
    )


@require_capability("locations.manage")
def import_master(request):
    form = ImportForm(request.POST or None, request.FILES or None)
    summary = None
    if request.method == "POST" and form.is_valid():
        try:
            rows, digest = parse_file(form.cleaned_data["file"])
            summary = import_locations(
                rows=rows,
                sha256=digest,
                source=form.cleaned_data["source"],
                actor=request.user,
                dry_run=form.cleaned_data["dry_run"],
                update_existing=form.cleaned_data["update_existing"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        except IntegrityError:
            form.add_error(
                None,
                "A code conflicts with another record or concurrent import. No changes were saved. Review the file and retry.",
            )
        else:
            messages.success(
                request,
                "Validation passed; no changes saved."
                if form.cleaned_data["dry_run"]
                else "Location master imported successfully.",
            )
    return render(
        request,
        "locations/import.html",
        {
            "form": form,
            "summary": summary,
            "batches": LocationImport.objects.select_related("imported_by")[:10],
        },
    )


@require_capability("locations.manage")
def import_template(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="location-import-template.csv"'
    csv.writer(response).writerow(COLUMNS)
    return response


@require_capability("locations.view")
def block_options(request):
    from django.http import JsonResponse

    value = request.GET.get("district", "")
    if not value.isascii() or not value.isdigit() or len(value) > 10:
        return JsonResponse({"error": "A valid district ID is required."}, status=400)
    blocks = staff_locations(request.user, Block).filter(district_id=int(value))
    return JsonResponse({"results": list(blocks.values("id", "name_en")[:200])})
