import time

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from apps.organization.models import SystemSetting

from .catalog import CONSENT
from .forms import ConsentForm, UploadForm
from .models import Application, DocumentType, RegistrationDraft, RegistrationUpload
from .security import consume_budget, post_budget
from .services import STEP_FORMS, save_step, submit_application

TITLES = [
    "Panchayat",
    "Personal details",
    "Experience & skills",
    "Equipment & profiles",
    "Photo & documents",
    "Review & consent",
]


def owned_draft(request):
    key = request.session.get("registration_draft")
    if not key:
        return None
    return RegistrationDraft.objects.filter(pk=key, expires_at__gt=timezone.now()).first()


@never_cache
@post_budget
@sensitive_post_parameters()
def start(request):
    draft = owned_draft(request)
    if request.method == "POST":
        if draft and not hasattr(draft, "application"):
            return redirect("registrations:step", step=min(draft.completed_step + 1, 6))
        if request.POST.get("website"):
            return HttpResponse("Unable to start application.", status=400)
        if not consume_budget(request, "starts", 10):
            return HttpResponse("Too many new applications. Try again in an hour.", status=429)
        draft = RegistrationDraft.objects.create()
        request.session["registration_draft"] = str(draft.pk)
        request.session["registration_started"] = time.time()
        return redirect("registrations:step", step=1)
    return render(
        request,
        "registrations/start.html",
        {"draft": draft, "has_submission": draft and hasattr(draft, "application")},
    )


def review_sections(draft):
    sections = []
    for number, form_class in STEP_FORMS.items():
        form = form_class({**draft.data.get(str(number), {}), "revision": draft.revision})
        form.is_valid()
        fields = []
        for key, field in form.fields.items():
            if key == "revision":
                continue
            value = form.cleaned_data.get(key, "")
            if hasattr(value, "all"):
                value = ", ".join(str(item) for item in value)
            if value is None or value == "":
                value = "Not provided"
            fields.append((field.label or key.replace("_", " ").capitalize(), value))
        sections.append({"number": number, "title": TITLES[number - 1], "fields": fields})
    return sections


@never_cache
@post_budget
@sensitive_post_parameters()
def step(request, step):
    if step not in range(1, 7):
        raise Http404
    draft = owned_draft(request)
    if not draft:
        messages.info(
            request,
            "Start a new application. Previous drafts expire after 24 hours or when your browser session is lost.",
        )
        return redirect("registrations:start")
    if hasattr(draft, "application"):
        return redirect("registrations:confirmation")
    if step > draft.completed_step + 1:
        return redirect("registrations:step", step=draft.completed_step + 1)
    policy = SystemSetting.objects.get(pk=1)
    initial = {
        **draft.data.get(str(step), {}),
        "revision": draft.revision,
        "consent_version": policy.consent_version,
    }
    args = {"data": request.POST if request.method == "POST" else None, "initial": initial}
    if step <= 4:
        form = STEP_FORMS[step](**args)
    elif step == 5:
        form = UploadForm(
            **args,
            files=request.FILES if request.method == "POST" else None,
            draft=draft,
            max_bytes=policy.max_upload_mb * 1024 * 1024,
        )
    else:
        form = ConsentForm(**args)
    if getattr(request, "registration_upload_rejected", False):
        form.add_error(
            None,
            "Upload limit exceeded. Use at most 9 files, each up to 20 MB, with a combined maximum of 100 MB.",
        )
    if request.method == "POST" and form.is_valid():
        try:
            if step == 6:
                if time.time() - request.session.get("registration_started", time.time()) < 5:
                    raise ValidationError("Please review your information before submitting.")
                if not consume_budget(request, "submissions", 5):
                    return HttpResponse(
                        "Submission limit reached. Please try again in an hour.", status=429
                    )
                submit_application(
                    draft_id=draft.pk,
                    revision=form.cleaned_data["revision"],
                    consent=form.cleaned_data,
                )
                return redirect("registrations:confirmation")
            save_step(
                draft_id=draft.pk,
                step=step,
                revision=form.cleaned_data["revision"],
                cleaned=form.cleaned_data,
            )
            return redirect("registrations:step", step=step + 1)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(
        request,
        "registrations/step.html",
        {
            "form": form,
            "draft": draft,
            "step": step,
            "title": TITLES[step - 1],
            "steps": TITLES,
            "previous": step - 1,
            "max_upload_mb": policy.max_upload_mb,
            "consent_version": policy.consent_version,
            "sections": review_sections(draft) if step == 6 else [],
            "uploads": draft.uploads.all(),
            "document_types": DocumentType.objects.filter(active=True),
            "consent": CONSENT,
        },
    )


@never_cache
def confirmation(request):
    draft = owned_draft(request)
    if not draft or not hasattr(draft, "application"):
        return redirect("registrations:start")
    return render(request, "registrations/confirmation.html", {"application": draft.application})


@never_cache
def preview_photo(request, pk):
    draft = owned_draft(request)
    if not draft:
        raise Http404
    upload = get_object_or_404(RegistrationUpload, pk=pk, draft=draft, slot="photo")
    try:
        response = FileResponse(upload.file.open("rb"), content_type="image/jpeg")
    except FileNotFoundError as exc:
        raise Http404 from exc
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response


@require_POST
@never_cache
@post_budget
def discard(request):
    draft = owned_draft(request)
    if draft:
        with transaction.atomic():
            draft = RegistrationDraft.objects.select_for_update().get(pk=draft.pk)
            if not Application.objects.filter(draft=draft).exists():
                for upload in draft.uploads.all():
                    transaction.on_commit(
                        lambda s=upload.file.storage, n=upload.file.name: s.delete(n)
                    )
                draft.delete()
        request.session.pop("registration_draft", None)
        request.session.pop("registration_started", None)
    return redirect("registrations:start")
