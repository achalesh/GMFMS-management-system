from django.core.exceptions import ValidationError

from .forms import EquipmentForm, LocationForm, PersonalForm, ProfessionalForm
from .models import DocumentType

FORM_CLASSES = [LocationForm, PersonalForm, ProfessionalForm, EquipmentForm]


def application_data(application):
    data = {
        "revision": application.revision,
        "district": application.panchayat.block.district_id,
        "block": application.panchayat.block_id,
        "panchayat": application.panchayat_id,
    }
    for form_class in [PersonalForm, ProfessionalForm]:
        for key in form_class.base_fields:
            if key in {"revision", "skills", "languages"}:
                continue
            value = getattr(application, key)
            data[key] = value.isoformat() if hasattr(value, "isoformat") else value
    data.update(
        skills=list(application.skills.values_list("pk", flat=True)),
        languages=list(application.languages.values_list("pk", flat=True)),
        equipment=list(application.equipment.values_list("pk", flat=True)),
        other_equipment=application.other_equipment,
    )
    data.update(
        {
            key: application.social_profiles.get(key, "")
            for key in ["facebook", "instagram", "youtube", "twitter", "linkedin", "other_profile"]
        }
    )
    return data


def validate_application(application):
    data = application_data(application)
    validated = {}
    for form_class in FORM_CLASSES:
        form = form_class(data)
        if not form.is_valid():
            errors = "; ".join(f"{key}: {', '.join(value)}" for key, value in form.errors.items())
            raise ValidationError("Application details need correction. " + errors)
        validated.update(form.cleaned_data)
    slots = set(application.uploads.values_list("slot", flat=True))
    if "photo" not in slots:
        raise ValidationError("A profile photograph is required before approval.")
    for kind in DocumentType.objects.filter(active=True, required=True):
        if "doc_" + kind.code not in slots:
            raise ValidationError(f"A required document is missing: {kind.name}.")
    for upload in application.uploads.all():
        if not upload.file.storage.exists(upload.file.name):
            raise ValidationError(
                "An application file is unavailable. Request a replacement before approval."
            )
    if (
        not application.consent_version
        or not application.consented_at
        or not application.consent_text.get("accuracy")
        or not application.consent_text.get("processing")
    ):
        raise ValidationError("Recorded consent is incomplete.")
    return validated
