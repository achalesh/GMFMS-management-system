import io
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import NameObject, TextStringObject

from apps.audit.models import AuditLog
from apps.locations.models import Block, District, GramaPanchayat, State
from apps.registrations.forms import (
    ConsentForm,
    EquipmentForm,
    LocationForm,
    PersonalForm,
    UploadForm,
)
from apps.registrations.models import (
    Application,
    ApplicationSequence,
    DocumentType,
    DuplicateWarning,
    Equipment,
    Language,
    RegistrationDraft,
    RegistrationUpload,
    Skill,
)
from apps.registrations.services import STEP_FORMS, save_step, submit_application
from apps.registrations.uploads import validate_upload

BASE = "/register/media-facilitator/"


def photo(name="portrait.png", size=(300, 400)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (45, 130, 100)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def pdf(active=False):
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=400)
    if active:
        writer._root_object[NameObject("/OpenAction")] = TextStringObject("unsafe")
    buffer = io.BytesIO()
    writer.write(buffer)
    return SimpleUploadedFile("reference.pdf", buffer.getvalue(), content_type="application/pdf")


class RegistrationTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.directory.name)
        self.override.enable()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.override.disable)
        state = State.objects.create(code="KL", name_en="Kerala")
        self.district = District.objects.create(
            state=state, district_code="TVM", name_en="Thiruvananthapuram"
        )
        self.block = Block.objects.create(
            district=self.district, block_code="B01001", name_en="Block"
        )
        self.gp = GramaPanchayat.objects.create(
            block=self.block, sec_local_body_code="G01001", name_en="Panchayat"
        )
        self.values = {
            1: {"district": self.district.pk, "block": self.block.pk, "panchayat": self.gp.pk},
            2: {
                "full_name": "Test Applicant",
                "mobile": "+91 98765 43210",
                "address": "Test address",
                "pin_code": "695001",
            },
            3: {
                "years_experience": 0,
                "languages": [Language.objects.get(code="malayalam").pk],
                "skills": [Skill.objects.get(code="photography").pk],
            },
            4: {
                "equipment": [Equipment.objects.get(code="smartphone").pk],
                "facebook": "https://example.org/profile",
            },
        }

    def draft(self):
        draft = RegistrationDraft.objects.create()
        for number, form_class in STEP_FORMS.items():
            form = form_class({**self.values[number], "revision": draft.revision})
            self.assertTrue(form.is_valid(), form.errors)
            draft = save_step(
                draft_id=draft.pk, step=number, revision=draft.revision, cleaned=form.cleaned_data
            )
        draft = save_step(
            draft_id=draft.pk,
            step=5,
            revision=draft.revision,
            cleaned={"photo": validate_upload(photo(), max_bytes=5 * 1024 * 1024, photo=True)},
        )
        return draft

    def consent(self):
        return {"accuracy": True, "processing": True, "consent_version": "1.0"}

    def submit(self, draft=None, **options):
        draft = draft or self.draft()
        return submit_application(
            draft_id=draft.pk,
            revision=draft.revision,
            consent=options.get("consent", self.consent()),
        )

    def session_draft(self, draft):
        session = self.client.session
        session["registration_draft"] = str(draft.pk)
        session["registration_started"] = 0
        session.save()

    def test_public_start_and_choice_seed(self):
        self.assertEqual(self.client.get(BASE).status_code, 200)
        self.assertEqual(Skill.objects.count(), 12)
        self.assertEqual(Equipment.objects.count(), 12)
        self.assertEqual(Language.objects.count(), 5)
        self.assertEqual(DocumentType.objects.count(), 4)
        call_command("seed_registration_choices", stdout=io.StringIO())
        self.assertEqual(Skill.objects.count(), 12)

    def test_submission_persists_private_data_consent_and_number(self):
        app = self.submit()
        self.assertRegex(app.application_number, r"^GMF-APP-\d{4}-000001$")
        self.assertEqual(app.status, "SUBMITTED")
        self.assertEqual(app.mobile, "9876543210")
        self.assertEqual(app.whatsapp, app.mobile)
        self.assertEqual(app.skills.count(), 1)
        self.assertEqual(app.equipment.count(), 1)
        self.assertEqual(app.languages.count(), 1)
        self.assertEqual(app.uploads.count(), 1)
        self.assertFalse(app.public_mobile_consent)
        self.assertTrue(app.consent_text["processing"])
        self.assertEqual(app.draft.data, {})
        self.assertTrue(AuditLog.objects.filter(action="application.submitted").exists())

    def test_retry_is_idempotent_and_number_sequence_unique(self):
        draft = self.draft()
        app = self.submit(draft)
        again = self.submit(draft)
        self.assertEqual(app.pk, again.pk)
        other = self.submit()
        self.assertNotEqual(app.application_number, other.application_number)
        self.assertEqual(ApplicationSequence.objects.get().value, 2)

    def test_duplicate_warnings_do_not_reject(self):
        first = self.submit()
        second = self.submit()
        warning = DuplicateWarning.objects.get(application=second, other_application=first)
        self.assertIn("same_mobile", warning.reasons)
        self.assertIn("same_panchayat", warning.reasons)
        self.assertIn("similar_name", warning.reasons)
        self.assertEqual(second.status, "SUBMITTED")

    def test_submission_audit_failure_rolls_back_all_database_changes(self):
        draft = self.draft()
        with patch(
            "apps.registrations.services.record_event",
            side_effect=RuntimeError("audit unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                self.submit(draft)
        self.assertEqual(Application.objects.count(), 0)
        self.assertFalse(ApplicationSequence.objects.exists())
        self.assertEqual(draft.uploads.count(), 1)
        self.assertTrue(Path(draft.uploads.get().file.path).exists())

    def test_missing_consent_or_changed_policy_rejected(self):
        draft = self.draft()
        for consent in [
            {"accuracy": True, "processing": False, "consent_version": "1.0"},
            {"accuracy": True, "processing": True, "consent_version": "old"},
        ]:
            with self.assertRaises(ValidationError):
                self.submit(draft, consent=consent)
        self.assertFalse(Application.objects.exists())

    def test_consent_options_independent(self):
        app = self.submit(consent={**self.consent(), "public_email": True})
        self.assertTrue(app.public_email_consent)
        self.assertFalse(app.public_mobile_consent)
        self.assertFalse(app.public_social_consent)

    def test_changed_location_or_choice_prevents_submission(self):
        draft = self.draft()
        self.block.active = False
        self.block.save()
        with self.assertRaises(ValidationError):
            self.submit(draft)
        self.block.active = True
        self.block.save()
        Language.objects.filter(code="malayalam").update(active=False)
        with self.assertRaises(ValidationError):
            self.submit(draft)

    def test_required_document_checked_again_at_submission(self):
        draft = self.draft()
        DocumentType.objects.filter(code="recommendation").update(required=True)
        with self.assertRaisesMessage(ValidationError, "required document"):
            self.submit(draft)

    def test_missing_stored_photo_prevents_submission(self):
        draft = self.draft()
        draft.uploads.get().file.delete(save=False)
        with self.assertRaisesMessage(ValidationError, "unavailable"):
            self.submit(draft)

    def test_skip_steps_and_stale_revision_rejected(self):
        draft = RegistrationDraft.objects.create()
        with self.assertRaises(ValidationError):
            save_step(draft_id=draft.pk, step=3, revision=1, cleaned={})
        form = LocationForm({**self.values[1], "revision": 1})
        self.assertTrue(form.is_valid())
        save_step(draft_id=draft.pk, step=1, revision=1, cleaned=form.cleaned_data)
        with self.assertRaises(ValidationError):
            save_step(draft_id=draft.pk, step=1, revision=1, cleaned=form.cleaned_data)

    def test_expired_draft_rejected(self):
        draft = self.draft()
        RegistrationDraft.objects.filter(pk=draft.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        with self.assertRaises(ValidationError):
            self.submit(draft)
        self.session_draft(draft)
        self.assertRedirects(self.client.get(BASE + "step/2/"), BASE)

    def test_wrong_location_parent_rejected(self):
        other = Block.objects.create(district=self.district, block_code="B01002", name_en="Other")
        form = LocationForm({**self.values[1], "revision": 1, "block": other.pk})
        self.assertFalse(form.is_valid())

    def test_mobile_pin_date_and_partial_emergency_validation(self):
        for invalid in [
            {"mobile": "1234567890"},
            {"pin_code": "000000"},
            {"date_of_birth": "2999-01-01"},
            {"emergency_name": "Person"},
            {"whatsapp": "bad"},
        ]:
            form = PersonalForm({**self.values[2], "revision": 1, **invalid})
            self.assertFalse(form.is_valid(), invalid)

    def test_unsafe_social_scheme_rejected(self):
        form = EquipmentForm({"revision": 1, "facebook": "javascript:alert(1)"})
        self.assertFalse(form.is_valid())

    def test_photo_crop_sanitizes_and_randomizes_name(self):
        value = validate_upload(photo(), max_bytes=5 * 1024 * 1024, photo=True, crop=(20, 80, 2))
        self.assertNotIn("portrait", value["content"].name)
        with Image.open(value["content"]) as image:
            self.assertAlmostEqual(image.width / image.height, 0.75, places=2)
            self.assertEqual(image.format, "JPEG")
            self.assertFalse(image.getexif())

    def test_invalid_file_formats_and_spoofed_images(self):
        for file in [
            SimpleUploadedFile("run.exe", b"MZbad"),
            SimpleUploadedFile("fake.jpg", b"not image", content_type="image/jpeg"),
            SimpleUploadedFile("fake.pdf", b"not pdf", content_type="application/pdf"),
            photo("wrong.jpg"),
            photo(size=(20, 20)),
        ]:
            with self.subTest(name=file.name), self.assertRaises(ValidationError):
                validate_upload(file, max_bytes=100000, photo=file.name != "fake.pdf")

    def test_size_limit_and_invalid_crop(self):
        with self.assertRaises(ValidationError):
            validate_upload(photo(), max_bytes=10, photo=True)
        with self.assertRaises(ValidationError):
            validate_upload(photo(), max_bytes=100000, photo=True, crop=(200, 50, 1))

    def test_pdf_validation(self):
        self.assertEqual(
            validate_upload(pdf(), max_bytes=100000)["content_type"], "application/pdf"
        )
        with self.assertRaises(ValidationError):
            validate_upload(pdf(active=True), max_bytes=100000)
        with self.assertRaises(ValidationError):
            validate_upload(pdf(), max_bytes=100000, photo=True)

    def test_pdf_embedded_action_is_rejected(self):
        from pypdf.generic import ArrayObject, DictionaryObject

        writer = PdfWriter()
        page = writer.add_blank_page(width=300, height=400)
        page[NameObject("/Annots")] = ArrayObject(
            [
                DictionaryObject(
                    {
                        NameObject("/Subtype"): NameObject("/Link"),
                        NameObject("/A"): DictionaryObject(
                            {
                                NameObject("/S"): NameObject("/Launch"),
                                NameObject("/F"): TextStringObject("program.exe"),
                            }
                        ),
                    }
                )
            ]
        )
        buffer = io.BytesIO()
        writer.write(buffer)
        with self.assertRaises(ValidationError):
            validate_upload(
                SimpleUploadedFile("action.pdf", buffer.getvalue(), content_type="application/pdf"),
                max_bytes=100000,
            )

    def test_upload_form_requires_photo_and_configured_document(self):
        draft = RegistrationDraft.objects.create()
        DocumentType.objects.filter(code="identity").update(required=True)
        form = UploadForm(data={"revision": 1}, files={}, draft=draft, max_bytes=100000)
        self.assertFalse(form.is_valid())
        self.assertIn("photo", form.errors)
        self.assertIn("doc_identity", form.errors)

    def test_failed_upload_save_removes_file(self):
        draft = RegistrationDraft.objects.create(completed_step=4)
        with patch.object(RegistrationUpload, "save", side_effect=RuntimeError("database failed")):
            with self.assertRaises(RuntimeError):
                save_step(
                    draft_id=draft.pk,
                    step=5,
                    revision=1,
                    cleaned={"photo": validate_upload(photo(), max_bytes=100000, photo=True)},
                )
        self.assertEqual([p for p in Path(self.directory.name).rglob("*") if p.is_file()], [])

    def test_own_photo_preview_and_cross_session_denial(self):
        draft = self.draft()
        self.session_draft(draft)
        upload = draft.uploads.get()
        response = self.client.get(BASE + f"photo/{upload.pk}/")
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertEqual(Client().get(BASE + f"photo/{upload.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/private-media/" + upload.file.name).status_code, 404)
        self.assertEqual(self.client.get(BASE + f"document/{upload.pk}/").status_code, 404)

    def test_confirmation_private_and_contains_no_sensitive_details(self):
        draft = self.draft()
        self.session_draft(draft)
        app = self.submit(draft)
        response = self.client.get(BASE + "confirmation/")
        self.assertContains(response, app.application_number)
        for value in [app.mobile, app.address, app.full_name]:
            self.assertNotContains(response, value)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertRedirects(Client().get(BASE + "confirmation/"), BASE)

    def test_csrf_required(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post(BASE, {}).status_code, 403)

    def test_honeypot_rejected(self):
        self.assertEqual(self.client.post(BASE, {"website": "bot.example"}).status_code, 400)
        self.assertFalse(
            ConsentForm({"revision": 1, **self.consent(), "website": "bot"}).is_valid()
        )

    def test_new_draft_rate_limit(self):
        for index in range(10):
            self.assertEqual(Client().post(BASE, {}).status_code, 302, index)
        self.assertEqual(Client().post(BASE, {}).status_code, 429)

    def test_prune_removes_only_expired_drafts_and_preserves_application_files(self):
        draft = self.draft()
        old_file = draft.uploads.get().file.path
        RegistrationDraft.objects.filter(pk=draft.pk).update(
            expires_at=timezone.now() - timedelta(days=1)
        )
        app = self.submit()
        saved_file = app.uploads.get().file.path
        RegistrationDraft.objects.filter(pk=app.draft_id).update(
            expires_at=timezone.now() - timedelta(days=1)
        )
        with self.captureOnCommitCallbacks(execute=True):
            call_command("prune_registration_drafts", stdout=io.StringIO())
        self.assertFalse(Path(old_file).exists())
        self.assertTrue(Path(saved_file).exists())
        app.refresh_from_db()
        self.assertIsNone(app.draft_id)

    def test_full_http_wizard_and_repeated_submit(self):
        self.assertRedirects(self.client.post(BASE, {}), BASE + "step/1/")
        for number in range(1, 5):
            draft = RegistrationDraft.objects.get(pk=self.client.session["registration_draft"])
            response = self.client.post(
                BASE + f"step/{number}/", {**self.values[number], "revision": draft.revision}
            )
            self.assertRedirects(response, BASE + f"step/{number + 1}/")
        draft.refresh_from_db()
        response = self.client.post(
            BASE + "step/5/", {"revision": draft.revision, "photo": photo()}
        )
        self.assertRedirects(response, BASE + "step/6/")
        session = self.client.session
        session["registration_started"] = 0
        session.save()
        draft.refresh_from_db()
        payload = {"revision": draft.revision, **self.consent()}
        self.assertRedirects(self.client.post(BASE + "step/6/", payload), BASE + "confirmation/")
        self.assertRedirects(self.client.post(BASE + "step/6/", payload), BASE + "confirmation/")
        self.assertEqual(Application.objects.count(), 1)

    def test_fast_submission_blocked(self):
        import time

        draft = self.draft()
        self.session_draft(draft)
        session = self.client.session
        session["registration_started"] = time.time()
        session.save()
        response = self.client.post(
            BASE + "step/6/", {"revision": draft.revision, **self.consent()}
        )
        self.assertContains(response, "Please review")
        self.assertFalse(Application.objects.exists())

    def test_document_policy_command_audits_and_enforces_actor(self):
        from django.core.management.base import CommandError

        from tests.factories import user_with_role

        admin = user_with_role("policy-admin", "SUPER_ADMIN")
        call_command(
            "configure_registration_document",
            "identity",
            actor=admin.username,
            required="yes",
            reason="Policy",
            stdout=io.StringIO(),
        )
        self.assertTrue(DocumentType.objects.get(code="identity").required)
        self.assertTrue(
            AuditLog.objects.filter(action="registration.document_policy_changed").exists()
        )
        with self.assertRaises(CommandError):
            call_command(
                "configure_registration_document",
                "identity",
                actor="unknown",
                required="no",
                reason="No permission",
            )

    def test_readonly_admin_exposes_warnings_without_mutation(self):
        from tests.factories import user_with_role

        admin = user_with_role("maintenance", "SUPER_ADMIN")
        admin.is_staff = True
        admin.save()
        app = self.submit()
        self.submit()
        self.client.force_login(admin)
        response = self.client.get("/admin/registrations/application/")
        self.assertContains(response, "Duplicate warnings")
        response = self.client.get(f"/admin/registrations/application/{app.pk}/change/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="_save"')
        self.assertEqual(
            self.client.post(f"/admin/registrations/application/{app.pk}/change/", {}).status_code,
            403,
        )

    def test_similar_name_across_panchayats_is_flagged(self):
        first = self.submit()
        second_gp = GramaPanchayat.objects.create(
            block=self.block, sec_local_body_code="G01002", name_en="Other Panchayat"
        )
        self.values[1]["panchayat"] = second_gp.pk
        self.values[2].update(full_name="Test Applicantt", mobile="9876543211")
        second = self.submit()
        warning = DuplicateWarning.objects.get(application=second, other_application=first)
        self.assertEqual(warning.reasons, ["similar_name"])

    def test_optional_document_removal_deletes_private_file(self):
        draft = self.draft()
        draft = save_step(
            draft_id=draft.pk,
            step=5,
            revision=draft.revision,
            cleaned={"doc_certificate": validate_upload(pdf(), max_bytes=100000)},
        )
        name = draft.uploads.get(slot="doc_certificate").file.path
        with self.captureOnCommitCallbacks(execute=True):
            draft = save_step(
                draft_id=draft.pk,
                step=5,
                revision=draft.revision,
                cleaned={"remove_doc_certificate": True},
            )
        self.assertFalse(Path(name).exists())
        self.assertFalse(draft.uploads.filter(slot="doc_certificate").exists())
        self.assertTrue(draft.uploads.filter(slot="photo").exists())

    def test_replacing_photo_keeps_only_new_file(self):
        draft = self.draft()
        old = draft.uploads.get().file.path
        with self.captureOnCommitCallbacks(execute=True):
            save_step(
                draft_id=draft.pk,
                step=5,
                revision=draft.revision,
                cleaned={"photo": validate_upload(photo(), max_bytes=100000, photo=True)},
            )
        self.assertFalse(Path(old).exists())
        self.assertEqual(draft.uploads.count(), 1)
        self.assertTrue(Path(draft.uploads.get().file.path).exists())

    def test_upload_stream_hard_limit(self):
        from django.core.files.uploadhandler import StopUpload
        from django.test import RequestFactory

        from apps.registrations.upload_handlers import RegistrationUploadLimitHandler

        request = RequestFactory().post(BASE + "step/5/")
        handler = RegistrationUploadLimitHandler(request)
        handler.current = 20 * 1024 * 1024
        with self.assertRaises(StopUpload):
            handler.receive_data_chunk(b"a", 0)
        self.assertTrue(request.registration_upload_rejected)

    def test_required_document_cannot_be_removed(self):
        draft = self.draft()
        DocumentType.objects.filter(code="identity").update(required=True)
        with self.assertRaises(ValidationError):
            save_step(
                draft_id=draft.pk,
                step=5,
                revision=draft.revision,
                cleaned={"remove_doc_identity": True},
            )
