import unicodedata
from datetime import date
from difflib import SequenceMatcher

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.services import record_event
from apps.organization.models import SystemSetting

from .catalog import CONSENT
from .forms import EquipmentForm, LocationForm, PersonalForm, ProfessionalForm
from .models import (
    Application,
    ApplicationSequence,
    DocumentType,
    DuplicateWarning,
    RegistrationDraft,
    RegistrationUpload,
)

STEP_FORMS = {1: LocationForm, 2: PersonalForm, 3: ProfessionalForm, 4: EquipmentForm}


def json_values(cleaned):
    result = {}
    for key, value in cleaned.items():
        if key == "revision":
            continue
        if hasattr(value, "pk"):
            value = value.pk
        elif hasattr(value, "values_list"):
            value = list(value.values_list("pk", flat=True))
        elif isinstance(value, date):
            value = value.isoformat()
        result[key] = value
    return result


def ensure_editable(draft, revision):
    if draft.expires_at <= timezone.now():
        raise ValidationError("This draft has expired. Start a new application.")
    if hasattr(draft, "application"):
        raise ValidationError("This application has already been submitted.")
    if draft.revision != revision:
        raise ValidationError("This draft changed in another tab. Reload before continuing.")


def save_step(*, draft_id, step, revision, cleaned):
    saved_files = []
    try:
        with transaction.atomic():
            draft = RegistrationDraft.objects.select_for_update().get(pk=draft_id)
            ensure_editable(draft, revision)
            if step > draft.completed_step + 1:
                raise ValidationError("Complete the previous steps first.")
            if step == 5:
                for key, remove in cleaned.items():
                    if not key.startswith("remove_doc_") or not remove:
                        continue
                    slot = key.removeprefix("remove_")
                    if DocumentType.objects.filter(
                        code=slot.removeprefix("doc_"), active=True, required=True
                    ).exists():
                        raise ValidationError("A required document cannot be removed.")
                    old = draft.uploads.filter(slot=slot).first()
                    if old:
                        storage, old_name = old.file.storage, old.file.name
                        old.delete()
                        transaction.on_commit(lambda s=storage, n=old_name: s.delete(n))
                for slot, value in cleaned.items():
                    if not isinstance(value, dict) or "content" not in value:
                        continue
                    old = draft.uploads.filter(slot=slot).first()
                    if old:
                        storage, old_name = old.file.storage, old.file.name
                        old.delete()
                        transaction.on_commit(lambda s=storage, n=old_name: s.delete(n))
                    upload = RegistrationUpload(
                        draft=draft,
                        slot=slot,
                        content_type=value["content_type"],
                        byte_size=value["byte_size"],
                        sha256=value["sha256"],
                    )
                    upload.file.save(value["content"].name, value["content"], save=False)
                    saved_files.append((upload.file.storage, upload.file.name))
                    upload.save()
            else:
                # Reject stale or forged fields even when this service is called directly.
                form = STEP_FORMS[step]({**json_values(cleaned), "revision": revision})
                if not form.is_valid():
                    raise ValidationError("This step is no longer valid. Check your selections.")
                draft.data = {**draft.data, str(step): json_values(form.cleaned_data)}
            draft.completed_step = max(draft.completed_step, step)
            draft.revision += 1
            draft.save()
            return draft
    except Exception:
        for storage, name in saved_files:
            storage.delete(name)
        raise


def validated_data(draft):
    result = {}
    for number, form_class in STEP_FORMS.items():
        form = form_class({**draft.data.get(str(number), {}), "revision": draft.revision})
        if not form.is_valid():
            raise ValidationError(
                f"Step {number} needs attention. A selection may no longer be available."
            )
        result[number] = form.cleaned_data
    slots = set(draft.uploads.values_list("slot", flat=True))
    if "photo" not in slots:
        raise ValidationError("A profile photograph is required.")
    for kind in DocumentType.objects.filter(active=True, required=True):
        if "doc_" + kind.code not in slots:
            raise ValidationError(f"Upload the required document: {kind.name}.")
    if any(not item.file.storage.exists(item.file.name) for item in draft.uploads.all()):
        raise ValidationError("An uploaded file is unavailable. Upload it again before submitting.")
    return result


@transaction.atomic
def submit_application(*, draft_id, revision, consent):
    # Serialize sequence allocation and duplicate checks, including first use of a year.
    policy = SystemSetting.objects.select_for_update().get(pk=1)
    draft = RegistrationDraft.objects.select_for_update().get(pk=draft_id)
    if hasattr(draft, "application"):
        return draft.application
    ensure_editable(draft, revision)
    if draft.completed_step < 5:
        raise ValidationError("Complete all five information steps before submitting.")
    if not consent.get("accuracy") or not consent.get("processing") or consent.get("website"):
        raise ValidationError("Both required consents must be accepted.")
    if consent.get("consent_version") != policy.consent_version:
        raise ValidationError(
            "The consent policy has changed. Reload this page and review it again."
        )
    details = validated_data(draft)
    year = timezone.localdate().year
    sequence, _ = ApplicationSequence.objects.get_or_create(year=year)
    sequence.value += 1
    sequence.save()
    values = {key: value for key, value in details[2].items() if key != "revision"}
    values.update(
        {
            key: value
            for key, value in details[3].items()
            if key not in {"revision", "skills", "languages"}
        }
    )
    equipment_data = details[4]
    app = Application(
        draft=draft,
        application_number=f"GMF-APP-{year}-{sequence.value:06d}",
        normalized_name=" ".join(
            unicodedata.normalize("NFKC", values["full_name"]).casefold().split()
        )[:180],
        panchayat=details[1]["panchayat"],
        **values,
        other_equipment=equipment_data["other_equipment"],
        social_profiles={
            key: equipment_data[key]
            for key in ["facebook", "instagram", "youtube", "twitter", "linkedin", "other_profile"]
            if equipment_data.get(key)
        },
        consent_version=policy.consent_version,
        consent_text=CONSENT,
        consented_at=timezone.now(),
        public_mobile_consent=bool(consent.get("public_mobile")),
        public_email_consent=bool(consent.get("public_email")),
        public_social_consent=bool(consent.get("public_social")),
    )
    app.full_clean()
    app.save()
    app.skills.set(details[3]["skills"])
    app.languages.set(details[3]["languages"])
    app.equipment.set(equipment_data["equipment"])
    draft.uploads.update(application=app, draft=None)
    exact = Q(mobile=app.mobile)
    if app.email:
        exact |= Q(email__iexact=app.email)
    candidates = Application.objects.exclude(pk=app.pk).filter(
        exact | Q(panchayat=app.panchayat) | Q(normalized_name__startswith=app.normalized_name[:4])
    )
    for other in candidates.iterator():
        reasons = []
        if other.mobile == app.mobile:
            reasons.append("same_mobile")
        if app.email and other.email.lower() == app.email.lower():
            reasons.append("same_email")
        if other.panchayat_id == app.panchayat_id:
            reasons.append("same_panchayat")
        if SequenceMatcher(None, app.normalized_name, other.normalized_name).ratio() >= 0.85:
            reasons.append("similar_name")
        if reasons:
            DuplicateWarning.objects.create(
                application=app, other_application=other, reasons=reasons
            )
    # Draft PII is no longer needed after a durable application has been created.
    draft.data = {}
    draft.save(update_fields=["data", "updated_at"])
    record_event(
        actor=None,
        action="application.submitted",
        entity=app,
        new_values={
            "application_number": app.application_number,
            "status": app.status,
            "panchayat_id": app.panchayat_id,
            "duplicate_warning_count": app.duplicate_warnings.count(),
            "consent_version": app.consent_version,
        },
    )
    return app
