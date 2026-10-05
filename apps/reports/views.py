from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.accounts.policies import require_capability
from apps.audit.services import record_event
from apps.registrations.security import staff_budget

from .data import export_allowed, report_data
from .exporting import export_bytes
from .forms import ExportForm, ReportFilter


@never_cache
@require_capability("dashboard.view")
@require_http_methods(["GET", "POST"])
@staff_budget("report-export", 30)
def index(request):
    exporting = request.method == "POST"
    if exporting and not export_allowed(request.user):
        raise PermissionDenied
    form = ReportFilter(
        request.GET,
        user=request.user,
        capability="reports.export" if exporting else "dashboard.view",
    )
    download = ExportForm(request.POST if exporting else None)
    headers = []
    rows = []
    code = 200
    if form.is_valid():
        try:
            headers, rows = report_data(request.user, form.cleaned_data, export=exporting)
            if exporting and download.is_valid():
                title = dict(form.fields["report"].choices)[
                    form.cleaned_data.get("report") or "coverage"
                ]
                selection = {k: str(v) for k, v in form.cleaned_data.items() if v}
                description = (
                    "As of "
                    + timezone.localtime().strftime("%Y-%m-%d %H:%M %Z")
                    + " | "
                    + "; ".join(k + ": " + v for k, v in selection.items())
                    + " | "
                    + str(len(rows))
                    + " rows. Current authorization; permitted jurisdiction only. Pending counts require application access."
                )
                fmt = download.cleaned_data["format"]
                payload, content_type = export_bytes(fmt, title, headers, rows, description)
                record_event(
                    actor=request.user,
                    action="reports.exported",
                    entity=request.user,
                    new_values={
                        "report": form.cleaned_data.get("report") or "coverage",
                        "format": fmt,
                        "rows": len(rows),
                        "filters": selection,
                    },
                    reason=download.cleaned_data["reason"],
                )
                response = HttpResponse(payload, content_type=content_type)
                response["Content-Disposition"] = (
                    f'attachment; filename="gramaswaraj-{form.cleaned_data.get("report") or "coverage"}-{timezone.localdate()}.{fmt}"'
                )
                response["X-Content-Type-Options"] = "nosniff"
                return response
        except ValidationError as e:
            form.add_error(None, e)
    if form.errors or (exporting and download.errors):
        code = 400
    page = Paginator(rows, 50).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "reports/index.html",
        {
            "form": form,
            "download": download,
            "headers": headers,
            "page": page,
            "query": query.urlencode(),
            "can_export": export_allowed(request.user),
        },
        status=code,
    )
