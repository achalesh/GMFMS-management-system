import hashlib
import json
from urllib.parse import urlsplit

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.audit.services import record_event
from apps.facilitators.models import Facilitator
from apps.facilitators.selectors import permitted
from apps.organization.models import OrganizationSetting, SystemSetting
from apps.verification.projection import authorization_status
from apps.verification.services import verification_url

from .models import IdentityCard
from .rendering import render_cards


def source(f):
    a = f.current_appointment
    if not a:
        raise ValidationError("An approved current appointment is required.")
    org = OrganizationSetting.objects.get(pk=1)
    upload = f.application.uploads.filter(slot="photo", content_type="image/jpeg").first()
    if not upload:
        raise ValidationError("A validated portrait is required before generating a card.")
    payload = {
        "name": f.full_name,
        "number": f.facilitator_number,
        "panchayat": a.panchayat.name_en,
        "district": a.panchayat.block.district.name_en,
        "block": a.panchayat.block.name_en,
        "role": a.get_role_display(),
        "valid_until": min(f.valid_until, a.effective_to or f.valid_until).isoformat(),
        "brand": org.short_name,
        "organization": org.name,
        "network": org.network_name,
        "organization_phone": org.phone,
        "signatory": org.signatory_name,
        "origin": urlsplit(verification_url(f)).netloc,
        "appointment": str(a.pk),
        "portrait_sha256": upload.sha256,
        "template": "1",
        "verification_url": verification_url(f),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return payload, digest, upload


def card_state(card):
    if card.status != "ISSUED":
        return card.status
    f = card.facilitator
    if timezone.localdate() > card.valid_until:
        return "EXPIRED"
    if f.application.status != "APPROVED" or authorization_status(f) != "ACTIVE":
        return "INACTIVE"
    try:
        _, digest, _ = source(f)
    except ValidationError:
        return "OUTDATED"
    return "CURRENT" if digest == card.source_digest else "OUTDATED"


def authorize(actor, f):
    if not f.current_appointment or not permitted(
        actor, f.current_appointment.panchayat, "cards.issue"
    ):
        raise PermissionDenied


@transaction.atomic
def issue_card(*, actor, facilitator_id, revision, reason):
    saved = []
    try:
        SystemSetting.objects.select_for_update().get(pk=1)
        f = Facilitator.objects.select_for_update().get(pk=facilitator_id)
        authorize(actor, f)
        if f.revision != revision:
            raise ValidationError("The facilitator changed. Reload before generating a card.")
        reason = reason.strip()
        if not reason or len(reason) > 2000:
            raise ValidationError("Provide a reason of 1 to 2,000 characters.")
        if f.application.status != "APPROVED" or authorization_status(f) != "ACTIVE":
            raise ValidationError(
                "Cards can only be generated for a currently active, approved appointment."
            )
        snapshot, digest, upload = source(f)
        try:
            with upload.file.open("rb") as stream:
                portrait = stream.read()
        except OSError as exc:
            raise ValidationError("The portrait file is unavailable.") from exc
        if hashlib.sha256(portrait).hexdigest() != upload.sha256:
            raise ValidationError("Portrait integrity check failed.")
        version = (f.cards.aggregate(value=Max("version"))["value"] or 0) + 1
        number = f"{f.facilitator_number}-V{version:03d}"
        qr_url = snapshot.pop("verification_url")
        snapshot.update(
            version=version, card_number=number, issue_date=timezone.localdate().isoformat()
        )
        card = IdentityCard(
            facilitator=f,
            appointment=f.current_appointment,
            card_number=number,
            version=version,
            valid_until=min(f.valid_until, f.current_appointment.effective_to or f.valid_until),
            generated_by=actor,
            source_digest=digest,
            snapshot=snapshot,
        )
        content = render_cards(snapshot, portrait, qr_url + "?card=" + card.public_token)
        for field, data in content.items():
            file = getattr(card, field)
            file.save(
                field + (".png" if field in {"front", "back"} else ".pdf"),
                ContentFile(data),
                save=False,
            )
            saved.append((file.storage, file.name))
        card.pdf_sha256 = hashlib.sha256(content["pdf"]).hexdigest()
        card.print_sha256 = hashlib.sha256(content["print_pdf"]).hexdigest()
        f.cards.filter(status="ISSUED").update(
            status="SUPERSEDED",
            revoked_at=timezone.now(),
            revoked_by=actor,
            revocation_reason="Superseded by " + number,
        )
        card.save()
        f.revision += 1
        f.save(update_fields=["revision", "updated_at"])
        if hasattr(f, "initial_card"):
            f.initial_card.status = "ISSUED"
            f.initial_card.save(update_fields=["status", "updated_at"])
        record_event(
            actor=actor,
            action="card.generated",
            entity=card,
            new_values={"card_number": number, "version": version, "pdf_sha256": card.pdf_sha256},
            reason=reason,
        )
        return card
    except Exception:
        for storage, name in saved:
            storage.delete(name)
        raise


@transaction.atomic
def revoke_card(*, actor, card_id, reason, revision):
    SystemSetting.objects.select_for_update().get(pk=1)
    card = IdentityCard.objects.select_for_update().get(pk=card_id)
    f = Facilitator.objects.select_for_update().get(pk=card.facilitator_id)
    authorize(actor, f)
    if not permitted(actor, f.current_appointment.panchayat, "facilitators.change"):
        raise PermissionDenied
    if f.revision != revision:
        raise ValidationError("The facilitator changed. Reload before revocation.")
    if card.status != "ISSUED":
        raise ValidationError("Only an issued card can be revoked.")
    reason = reason.strip()
    if not reason or len(reason) > 2000:
        raise ValidationError("A revocation reason of 1 to 2,000 characters is required.")
    card.status = "REVOKED"
    card.revoked_at = timezone.now()
    card.revoked_by = actor
    card.revocation_reason = reason
    card.save()
    f.revision += 1
    f.save(update_fields=["revision", "updated_at"])
    record_event(
        actor=actor,
        action="card.revoked",
        entity=card,
        old_values={"status": "ISSUED"},
        new_values={"status": "REVOKED"},
        reason=reason,
    )
    return card


@transaction.atomic
def download_card(*, actor, card_id, revision, reason, format):
    SystemSetting.objects.select_for_update().get(pk=1)
    card = IdentityCard.objects.select_for_update().get(pk=card_id)
    f = Facilitator.objects.select_for_update().get(pk=card.facilitator_id)
    authorize(actor, f)
    card.facilitator = f
    if f.revision != revision:
        raise ValidationError("The facilitator changed. Reload before downloading.")
    if card_state(card) != "CURRENT":
        raise ValidationError(
            "This card is no longer current and cannot be downloaded or reprinted."
        )
    reason = reason.strip()
    if not reason or len(reason) > 2000:
        raise ValidationError("Provide a download/reprint reason.")
    if format not in {"pdf", "print_pdf"}:
        raise ValidationError("Choose a valid print format.")
    file = getattr(card, format)
    try:
        with file.open("rb") as stream:
            content = stream.read()
    except OSError as exc:
        raise ValidationError("Stored card file is unavailable. Generate a new version.") from exc
    expected = card.pdf_sha256 if format == "pdf" else card.print_sha256
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValidationError("Stored card integrity check failed.")
    record_event(
        actor=actor,
        action="card.reprinted",
        entity=card,
        new_values={"version": card.version, "format": format},
        reason=reason,
    )
    return card, content
