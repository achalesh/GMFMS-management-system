import logging
import re
from functools import wraps

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import get_template
from django.utils.cache import patch_cache_control
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from apps.audit.services import record_event
from apps.facilitators.models import Facilitator
from apps.facilitators.selectors import permitted, registry_for
from apps.registrations.security import consume_budget

from .projection import public_profile
from .services import qr_png, rotate_token, verification_url

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,64}$")


def public_error(request, status):
    message = {
        404: "Verification unavailable",
        429: "Too many verification requests. Please try again later.",
        503: "Verification temporarily unavailable. Please try again later.",
    }[status]
    if request.path.startswith("/api/"):
        return JsonResponse({"error": message}, status=status)
    return HttpResponse(
        get_template("verification/unavailable.html").render(
            {
                "message": message,
                "organization": {
                    "short_name": "Gramaswaraj",
                    "name": "Identity verification",
                    "network_name": "",
                },
            }
        ),
        status=status,
    )


def public_access(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        category = (
            "verification-portrait"
            if request.path.endswith("/portrait/")
            else "verification-lookup"
        )
        limit = 240 if category == "verification-portrait" else 120
        try:
            if not consume_budget(request, category, limit):
                response = public_error(request, 429)
                response["Retry-After"] = "3600"
            else:
                response = view(request, *args, **kwargs)
        except Exception:
            # Never expose Django debug pages, private model locals or request tokens publicly.
            logging.getLogger("gmfms.security").error(
                "Public verification processing failed; no identity was verified."
            )
            response = public_error(request, 503)
            response["Retry-After"] = "60"
        patch_cache_control(response, private=True, no_store=True, no_cache=True, max_age=0)
        response["Referrer-Policy"] = "no-referrer"
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = (
            "default-src 'none'; img-src 'self'; style-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        )
        return response

    return wrapped


def lookup(token):
    if not TOKEN_PATTERN.fullmatch(token):
        return None
    return (
        Facilitator.objects.select_related(
            "current_appointment__panchayat__block__district__state", "application"
        )
        .filter(verification_token=token, application__status="APPROVED")
        .first()
    )


@public_access
@require_safe
def verify(request, token):
    f = lookup(token)
    if not f:
        return public_error(request, 404)
    data = project(request, f)
    if data is None:
        return public_error(request, 404)
    # No request/context processors or model objects enter the public template context.
    return HttpResponse(
        get_template("verification/profile.html").render(
            {"profile": data, "organization": data["organization"]}
        )
    )


@public_access
@require_safe
def api(request, token):
    f = lookup(token)
    if not f:
        return public_error(request, 404)
    data = project(request, f)
    return JsonResponse(data) if data is not None else public_error(request, 404)


@public_access
@require_safe
def portrait(request, token):
    f = lookup(token)
    if not f:
        return public_error(request, 404)
    upload = f.application.uploads.filter(slot="photo", content_type="image/jpeg").first()
    if not upload:
        return public_error(request, 404)
    try:
        response = FileResponse(upload.file.open("rb"), content_type="image/jpeg")
    except (OSError, ValueError):
        return public_error(request, 404)
    response["Content-Disposition"] = 'inline; filename="portrait.jpg"'
    return response


def staff_record(user, pk):
    f = get_object_or_404(registry_for(user), pk=pk)
    if not f.current_appointment or not (
        permitted(user, f.current_appointment.panchayat, "cards.issue")
        or permitted(user, f.current_appointment.panchayat, "facilitators.change")
    ):
        raise PermissionDenied
    return f


@login_required
@never_cache
@require_safe
def staff(request, pk):
    f = staff_record(request.user, pk)
    try:
        url = verification_url(f)
    except ValidationError as exc:
        url = None
        messages.error(request, exc.messages[0])
    return render(
        request,
        "verification/staff.html",
        {
            "facilitator": f,
            "verification_url": url,
            "can_rotate": permitted(request.user, f.current_appointment.panchayat),
        },
    )


@login_required
@never_cache
@require_safe
def download_qr(request, pk):
    f = staff_record(request.user, pk)
    try:
        url = verification_url(f)
    except ValidationError:
        return HttpResponse(
            "Configure the public application origin before generating QR codes.", status=400
        )
    content = qr_png(url)
    record_event(
        actor=request.user,
        action="verification.qr_generated",
        entity=f,
        new_values={"revision": f.revision},
    )
    response = HttpResponse(content, content_type="image/png")
    response["Content-Disposition"] = (
        "attachment" if request.GET.get("download") == "1" else "inline"
    ) + '; filename="verification-qr.png"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


class RotationForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    reason = forms.CharField(
        max_length=2000, widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"})
    )
    confirmed = forms.BooleanField(
        label="I understand that existing QR codes and verification links will stop working"
    )


@login_required
@never_cache
def rotate(request, pk):
    f = get_object_or_404(registry_for(request.user, "facilitators.change"), pk=pk)
    form = RotationForm(request.POST or None, initial={"revision": f.revision})
    if request.method == "POST" and form.is_valid():
        try:
            rotate_token(actor=request.user, facilitator_id=f.pk, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(
                request,
                "Verification token replaced. Download the new QR code; previous links are no longer valid.",
            )
            return redirect("verification_staff:detail", pk=f.pk)
    return render(request, "verification/rotate.html", {"facilitator": f, "form": form})


def project(request, facilitator):
    profile = public_profile(facilitator)
    if "card" in request.GET:
        from apps.idcards.public import with_card

        return with_card(profile, facilitator, request.GET["card"])
    return profile
