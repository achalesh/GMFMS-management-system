from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters

from apps.organization.models import SystemSetting

from .correction_forms import CorrectionForm
from .correction_services import apply_correction, digest_token, valid_ticket
from .models import CorrectionRequest
from .security import consume_budget, post_budget


def unavailable(request):
    response = render(request, "corrections/unavailable.html", status=404)
    response["Referrer-Policy"] = "same-origin"
    return response


def session_ticket(request, pk):
    digest = request.session.get("correction_grants", {}).get(str(pk))
    ticket = (
        CorrectionRequest.objects.select_related("application__panchayat__block__district")
        .filter(pk=pk)
        .first()
    )
    return (ticket, digest) if valid_ticket(ticket, digest) else (None, None)


@never_cache
@post_budget
@sensitive_post_parameters()
def access(request, pk):
    if request.method == "POST":
        if not consume_budget(request, "correction-access", 30):
            return HttpResponse("Too many attempts. Please try again in an hour.", status=429)
        token = request.POST.get("token", "")
        if not 32 <= len(token) <= 100:
            return unavailable(request)
        ticket = CorrectionRequest.objects.select_related("application").filter(pk=pk).first()
        digest = digest_token(token)
        if not valid_ticket(ticket, digest):
            return unavailable(request)
        request.session.cycle_key()
        grants = request.session.get("correction_grants", {})
        # Limit retained grants on a shared session.
        grants = {str(pk): digest}
        request.session["correction_grants"] = grants
        return redirect("corrections:edit", pk=pk)
    response = render(request, "corrections/access.html")
    response["Referrer-Policy"] = "same-origin"
    return response


@never_cache
@post_budget
@sensitive_post_parameters()
def edit(request, pk):
    ticket, digest = session_ticket(request, pk)
    if not ticket:
        return unavailable(request)
    policy = SystemSetting.objects.get(pk=1)
    try:
        form = CorrectionForm(
            request.POST if request.method == "POST" else None,
            files=request.FILES if request.method == "POST" else None,
            application=ticket.application,
            ticket=ticket,
            policy=policy,
        )
    except ValidationError:
        return unavailable(request)
    if getattr(request, "registration_upload_rejected", False):
        form.add_error(None, "Upload limit exceeded. Choose smaller files.")
    if request.method == "POST" and form.is_valid():
        if not consume_budget(request, "correction-submit", 20):
            return HttpResponse("Too many attempts. Please try again in an hour.", status=429)
        for upload in request.FILES.values():
            upload.seek(0)
        try:
            application = apply_correction(
                ticket_id=pk, digest=digest, data=request.POST, files=request.FILES
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            request.session.pop("correction_grants", None)
            request.session["correction_receipt"] = {"number": application.application_number}
            return redirect("corrections:complete")
    response = render(
        request,
        "corrections/edit.html",
        {
            "ticket": ticket,
            "application": ticket.application,
            "form": form,
            "max_upload_mb": policy.max_upload_mb,
            "has_photo": "photo" in ticket.allowed_fields,
            "consent_version": policy.consent_version,
        },
    )
    response["Referrer-Policy"] = "same-origin"
    return response


@never_cache
def complete(request):
    receipt = request.session.get("correction_receipt")
    if not receipt:
        return unavailable(request)
    return render(request, "corrections/complete.html", {"receipt": receipt})
