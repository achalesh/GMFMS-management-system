import hashlib
import secrets
import unicodedata

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organization.models import SystemSetting

from .application_data import validate_application
from .catalog import CONSENT
from .correction_forms import CorrectionForm
from .duplicates import refresh_warnings
from .models import Application, CorrectionRequest, RegistrationUpload
from .review_services import history


def valid_ticket(ticket, digest):
    return bool(
        ticket
        and digest
        and secrets.compare_digest(ticket.token_hash, digest)
        and ticket.used_at is None
        and ticket.revoked_at is None
        and ticket.expires_at > timezone.now()
        and ticket.application.status == "CORRECTION_REQUIRED"
    )


def digest_token(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def serialized(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def apply_correction(*, ticket_id, digest, data, files):
    saved_files = []
    try:
        with transaction.atomic():
            policy = SystemSetting.objects.select_for_update().get(pk=1)
            reference = CorrectionRequest.objects.get(pk=ticket_id)
            app = Application.objects.select_for_update().get(pk=reference.application_id)
            ticket = CorrectionRequest.objects.select_for_update().get(pk=ticket_id)
            ticket.application = app
            if not valid_ticket(ticket, digest):
                raise ValidationError(
                    "This correction link has expired, was replaced or has already been used."
                )
            form = CorrectionForm(
                data=data, files=files, application=app, ticket=ticket, policy=policy
            )
            if not form.is_valid():
                raise ValidationError(
                    "Please check the requested fields and consent before resubmitting."
                )
            if form.cleaned_data["revision"] != app.revision:
                raise ValidationError(
                    "This application changed. Reload before submitting corrections."
                )
            changes = {}
            for key in ticket.allowed_fields:
                value = form.cleaned_data.get(key)
                if key == "photo" or key.startswith("doc_"):
                    if not value:
                        continue
                    old = app.uploads.filter(slot=key).first()
                    old_hash = old.sha256 if old else None
                    if old:
                        storage, old_name = old.file.storage, old.file.name
                        old.delete()
                        transaction.on_commit(lambda s=storage, n=old_name: s.delete(n))
                    upload = RegistrationUpload(
                        application=app,
                        slot=key,
                        content_type=value["content_type"],
                        byte_size=value["byte_size"],
                        sha256=value["sha256"],
                    )
                    upload.file.save(value["content"].name, value["content"], save=False)
                    saved_files.append((upload.file.storage, upload.file.name))
                    upload.save()
                    changes[key] = {"old": old_hash, "new": upload.sha256}
                elif key in {"skills", "languages", "equipment"}:
                    old = list(getattr(app, key).values_list("pk", flat=True))
                    new = list(form.validated[key].values_list("pk", flat=True))
                    old_names = [str(item) for item in getattr(app, key).all()]
                    new_names = [str(item) for item in form.validated[key]]
                    getattr(app, key).set(new)
                    if sorted(old) != sorted(new):
                        changes[key] = {
                            "old": old_names,
                            "new": new_names,
                            "old_ids": old,
                            "new_ids": new,
                        }
                elif key in {
                    "facebook",
                    "instagram",
                    "youtube",
                    "twitter",
                    "linkedin",
                    "other_profile",
                }:
                    old = app.social_profiles.get(key, "")
                    new = form.validated[key]
                    app.social_profiles = {**app.social_profiles, key: new}
                    if old != new:
                        changes[key] = {"old": old, "new": new}
                else:
                    old = getattr(app, key)
                    new = form.validated[key]
                    setattr(app, key, new)
                    if old != new:
                        changes[key] = {"old": serialized(old), "new": serialized(new)}
            if not changes:
                raise ValidationError("Make at least one requested correction before resubmitting.")
            old_consent = {
                "version": app.consent_version,
                "timestamp": app.consented_at.isoformat(),
                "text": app.consent_text,
            }
            app.normalized_name = " ".join(
                unicodedata.normalize("NFKC", app.full_name).casefold().split()
            )[:180]
            app.consent_version = policy.consent_version
            app.consent_text = CONSENT
            app.consented_at = timezone.now()
            changes["consent"] = {
                "old": old_consent,
                "new": {
                    "version": app.consent_version,
                    "timestamp": app.consented_at.isoformat(),
                    "text": app.consent_text,
                },
            }
            validate_application(app)
            old_status = app.status
            app.status = "SUBMITTED"
            app.reviewed_by = None
            app.revision += 1
            app.full_clean()
            app.save()
            ticket.used_at = timezone.now()
            ticket.save(update_fields=["used_at", "updated_at"])
            refresh_warnings(app)
            history(
                app,
                None,
                "correction_resubmitted",
                old_status,
                "Applicant resubmitted requested corrections.",
                changes,
            )
            return app
    except Exception:
        for storage, name in saved_files:
            storage.delete(name)
        raise
