from functools import wraps

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters

from apps.audit.services import record_event
from apps.locations.models import Block, District, GramaPanchayat

from .application_data import FORM_CLASSES, application_data
from .duplicates import find_duplicates
from .models import Application, RegistrationUpload
from .review_forms import ActionForm
from .review_selectors import applications_for, can_act, can_enter
from .review_services import ACTIONS, TRANSITIONS, active_primary, review_action


def review_access(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not can_enter(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped


class FilterForm(forms.Form):
    q = forms.CharField(required=False, max_length=150, label="Name, mobile or application number")
    status = forms.ChoiceField(
        required=False,
        choices=[("pending", "Pending review"), ("", "All statuses")]
        + list(Application.Status.choices),
    )
    district = forms.ModelChoiceField(queryset=District.objects.none(), required=False)
    block = forms.ModelChoiceField(queryset=Block.objects.none(), required=False)
    panchayat = forms.ModelChoiceField(
        queryset=GramaPanchayat.objects.none(), required=False, label="Panchayat"
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, base, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["district"].queryset = District.objects.filter(
            pk__in=base.values("panchayat__block__district_id")
        )
        self.fields["block"].queryset = Block.objects.filter(
            pk__in=base.values("panchayat__block_id")
        )
        self.fields["panchayat"].queryset = GramaPanchayat.objects.filter(
            pk__in=base.values("panchayat_id")
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean(self):
        data = super().clean()
        if data.get("date_from") and data.get("date_to") and data["date_from"] > data["date_to"]:
            raise ValidationError("The start date must not be after the end date.")
        return data


@never_cache
@review_access
def index(request):
    base = applications_for(request.user)
    counts = {
        row["status"]: row["total"]
        for row in base.values("status").annotate(total=Count("pk")).order_by()
    }
    parameters = request.GET.copy()
    if "status" not in parameters:
        parameters["status"] = "pending"
    form = FilterForm(parameters, base=base)
    queryset = base
    if form.is_valid():
        data = form.cleaned_data
        if data["status"] == "pending":
            queryset = queryset.filter(status__in=["SUBMITTED", "UNDER_REVIEW"])
        elif data["status"]:
            queryset = queryset.filter(status=data["status"])
        if data["q"]:
            query = data["q"]
            queryset = queryset.filter(
                Q(full_name__icontains=query)
                | Q(name_ml__icontains=query)
                | Q(mobile__icontains=query)
                | Q(application_number__icontains=query)
            )
        for field, lookup in [
            ("district", "panchayat__block__district"),
            ("block", "panchayat__block"),
            ("panchayat", "panchayat"),
        ]:
            if data[field]:
                queryset = queryset.filter(**{lookup: data[field]})
        if data["date_from"]:
            queryset = queryset.filter(submitted_at__date__gte=data["date_from"])
        if data["date_to"]:
            queryset = queryset.filter(submitted_at__date__lte=data["date_to"])
    else:
        queryset = queryset.none()
    queryset = (
        queryset.select_related("panchayat__block__district")
        .annotate(warning_count=Count("duplicate_warnings"))
        .order_by("-submitted_at", "pk")
    )
    parameters.pop("page", None)
    return render(
        request,
        "applications/index.html",
        {
            "form": form,
            "page": Paginator(queryset, 25).get_page(request.GET.get("page")),
            "counts": counts,
            "total": base.count(),
            "filter_query": parameters.urlencode(),
            "status_cards": [
                (label, counts.get(code, 0)) for code, label in Application.Status.choices
            ],
        },
    )


def sections_for(application):
    data = application_data(application)
    sections = []
    for title, form_class in zip(
        ["Panchayat", "Personal details", "Experience & skills", "Equipment & profiles"],
        FORM_CLASSES,
        strict=True,
    ):
        form = form_class(data)
        form.is_valid()
        rows = []
        for key, field in form.fields.items():
            if key == "revision":
                continue
            value = form.cleaned_data.get(key, data.get(key, ""))
            if hasattr(value, "values_list"):
                value = ", ".join(str(item) for item in value)
            rows.append(
                (
                    field.label or key.replace("_", " ").capitalize(),
                    value if value not in ("", None) else "Not provided",
                )
            )
        sections.append({"title": title, "rows": rows})
    return sections


@never_cache
@review_access
def detail(request, pk):
    app = get_object_or_404(
        applications_for(request.user).select_related(
            "panchayat__block__district", "reviewed_by", "decided_by"
        ),
        pk=pk,
    )
    matches = find_duplicates(app)
    visible = set(
        applications_for(request.user)
        .filter(pk__in=[other.pk for other, _ in matches])
        .values_list("pk", flat=True)
    )
    duplicate_rows = [
        {
            "application": other if other.pk in visible else None,
            "reasons": [reason.replace("_", " ").capitalize() for reason in reasons]
            if other.pk in visible
            else ["Restricted match — consult a statewide administrator."],
        }
        for other, reasons in matches[:50]
    ]
    actions = [
        {"code": action, "label": action.replace("_", " ").capitalize()}
        for action, capability in ACTIONS.items()
        if app.status == TRANSITIONS[action][0] and can_act(request.user, app, capability)
    ]
    record_event(actor=request.user, action="application.viewed", entity=app)
    return render(
        request,
        "applications/detail.html",
        {
            "application": app,
            "sections": sections_for(app),
            "duplicates": duplicate_rows,
            "duplicate_count": len(matches),
            "actions": actions,
            "events": [
                {
                    "event": event,
                    "label": event.action.replace("_", " ").capitalize(),
                    "changes": [
                        (key.replace("_", " ").capitalize(), value)
                        for key, value in event.changes.items()
                    ],
                }
                for event in app.review_events.select_related("actor")
            ],
            "uploads": app.uploads.all(),
            "active_primary": active_primary(app.panchayat).exists(),
            "latest_correction": app.correction_requests.order_by("-created_at").first(),
        },
    )


@never_cache
@review_access
@sensitive_post_parameters()
def action(request, pk, action):
    if action not in ACTIONS:
        raise Http404
    app = get_object_or_404(
        applications_for(request.user).select_related("panchayat__block__district"), pk=pk
    )
    if not can_act(request.user, app, ACTIONS[action]):
        raise PermissionDenied
    form = ActionForm(
        request.POST if request.method == "POST" else None,
        action=action,
        initial={"revision": app.revision},
    )
    if request.method == "POST" and form.is_valid():
        try:
            result = review_action(
                actor=request.user, application_id=app.pk, action=action, **form.cleaned_data
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            if result["correction"]:
                url = (
                    settings.PUBLIC_BASE_URL
                    + reverse("corrections:access", args=[result["correction"].pk])
                    + "#"
                    + result["token"]
                )
                response = render(
                    request,
                    "applications/correction_link.html",
                    {
                        "application": result["application"],
                        "ticket": result["correction"],
                        "correction_url": url,
                    },
                )
                response["Referrer-Policy"] = "same-origin"
                return response
            messages.success(request, "Application updated. The decision has been recorded.")
            return redirect("applications:detail", pk=app.pk)
    return render(
        request,
        "applications/action.html",
        {
            "application": app,
            "form": form,
            "action": action,
            "action_label": action.replace("_", " ").capitalize(),
            "duplicate_count": len(find_duplicates(app)) if action == "approve" else 0,
        },
    )


@never_cache
@review_access
def download(request, pk, file_id):
    app = get_object_or_404(
        applications_for(request.user).select_related("panchayat__block__district"), pk=pk
    )
    if not can_act(request.user, app, "applications.review"):
        raise PermissionDenied
    upload = get_object_or_404(RegistrationUpload, pk=file_id, application=app)
    inline = (
        upload.slot == "photo"
        and request.GET.get("preview") == "1"
        and upload.content_type == "image/jpeg"
    )
    try:
        handle = upload.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404 from exc
    try:
        record_event(
            actor=request.user,
            action="application.file_viewed" if inline else "application.file_downloaded",
            entity=app,
            new_values={"upload_id": str(upload.pk), "slot": upload.slot},
        )
    except Exception:
        handle.close()
        raise
    filename = f"{app.application_number}-{upload.slot}." + (
        "pdf" if upload.content_type == "application/pdf" else "jpg"
    )
    response = FileResponse(
        handle, as_attachment=not inline, filename=filename, content_type=upload.content_type
    )
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    response["X-Content-Type-Options"] = "nosniff"
    return response
