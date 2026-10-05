import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.facilitators.models import (
    Facilitator,
    FacilitatorAppointment,
    FacilitatorSequence,
    IdentityCardMetadata,
)
from apps.locations.models import Block, District, GramaPanchayat, State
from apps.organization.models import SystemSetting
from apps.registrations.catalog import CONSENT
from apps.registrations.correction_services import apply_correction, digest_token
from apps.registrations.models import (
    Application,
    CorrectionRequest,
    Language,
    RegistrationUpload,
    ReviewEvent,
)
from apps.registrations.review_services import review_action
from apps.registrations.uploads import validate_upload
from tests.factories import assign, user_with_role
from tests.test_registrations import pdf, photo


class ReviewTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.media.cleanup)
        self.addCleanup(self.override.disable)
        state = State.objects.create(code="KL", name_en="Kerala")
        self.district = District.objects.create(
            state=state, district_code="TVM", name_en="Thiruvananthapuram"
        )
        self.block = Block.objects.create(
            district=self.district, block_code="B01001", name_en="First Block"
        )
        self.sibling = Block.objects.create(
            district=self.district, block_code="B01002", name_en="Second Block"
        )
        other = District.objects.create(state=state, district_code="KLM", name_en="Kollam")
        self.other_block = Block.objects.create(
            district=other, block_code="B02001", name_en="Other District Block"
        )
        self.gp = GramaPanchayat.objects.create(
            block=self.block, sec_local_body_code="G01001", name_en="First Panchayat"
        )
        self.other_gp = GramaPanchayat.objects.create(
            block=self.other_block, sec_local_body_code="G02001", name_en="Other Panchayat"
        )
        self.admin = user_with_role("admin", "SUPER_ADMIN")
        self.regional = user_with_role("district", "DISTRICT_ADMIN", "DISTRICT", "TVM")
        self.coordinator = user_with_role("block", "BLOCK_COORDINATOR", "BLOCK", "TVM", "B01001")
        self.reviewer = user_with_role("reviewer", "REVIEWER", "DISTRICT", "TVM")
        self.viewer = user_with_role("viewer", "VIEWER")
        self.app = self.make_app()

    def make_app(self, gp=None, name="Test Applicant", mobile="9876543210"):
        app = Application.objects.create(
            application_number="GMF-APP-TEST-" + uuid.uuid4().hex[:8],
            panchayat=gp or self.gp,
            full_name=name,
            normalized_name=name.lower(),
            mobile=mobile,
            whatsapp=mobile,
            address="Private home address",
            pin_code="695001",
            consent_version="1.0",
            consent_text=CONSENT,
            consented_at=timezone.now(),
        )
        app.languages.add(Language.objects.get(code="malayalam"))
        data = validate_upload(photo(), max_bytes=100000, photo=True)
        RegistrationUpload.objects.create(
            application=app,
            slot="photo",
            file=data["content"],
            content_type=data["content_type"],
            byte_size=data["byte_size"],
            sha256=data["sha256"],
        )
        return app

    def act(self, action, app=None, actor=None, **kwargs):
        app = app or self.app
        app.refresh_from_db()
        return review_action(
            actor=actor or self.admin,
            application_id=app.pk,
            action=action,
            revision=app.revision,
            **kwargs,
        )

    def begin(self, app=None):
        return self.act("start_review", app=app)

    def correction(self, fields=None):
        self.begin()
        return self.act(
            "request_correction",
            reason="Please correct these details.",
            allowed_fields=fields or ["full_name"],
        )

    def correct(self, result, **values):
        app = result["application"]
        app.refresh_from_db()
        return apply_correction(
            ticket_id=result["correction"].pk,
            digest=digest_token(result["token"]),
            data={
                "revision": app.revision,
                "accuracy": True,
                "processing": True,
                "consent_version": "1.0",
                **values,
            },
            files={},
        )

    def url(self, app=None):
        return f"/applications/{(app or self.app).pk}/"

    def test_review_to_approval_creates_all_identity_records(self):
        self.begin()
        self.act("approve", verification_complete=True)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "APPROVED")
        facilitator = self.app.facilitator
        self.assertEqual(facilitator.facilitator_number, "GS-MF-TVM-0001")
        self.assertEqual(facilitator.approved_by, self.admin)
        self.assertGreaterEqual(len(facilitator.verification_token), 40)
        self.assertEqual(facilitator.appointments.get().role, "PRIMARY")
        self.assertEqual(facilitator.initial_card.status, "PENDING")
        self.assertEqual(self.app.decided_by, self.admin)
        self.assertEqual(self.app.review_events.count(), 2)
        self.assertTrue(AuditLog.objects.filter(action="application.approve").exists())

    def test_approval_requires_under_review_and_verification(self):
        with self.assertRaises(ValidationError):
            self.act("approve", verification_complete=True)
        self.begin()
        with self.assertRaises(ValidationError):
            self.act("approve")
        self.assertFalse(Facilitator.objects.exists())

    def test_repeat_approval_does_not_create_duplicate_identity(self):
        self.begin()
        self.act("approve", verification_complete=True)
        with self.assertRaises(ValidationError):
            self.act("approve", verification_complete=True)
        self.assertEqual(Facilitator.objects.count(), 1)
        self.assertEqual(FacilitatorSequence.objects.get().value, 1)

    def test_stale_action_rejected(self):
        self.begin()
        with self.assertRaisesMessage(ValidationError, "another session"):
            review_action(
                actor=self.admin,
                application_id=self.app.pk,
                action="reject",
                revision=1,
                reason="Stale",
            )
        self.assertEqual(ReviewEvent.objects.count(), 1)

    def test_invalid_transition_and_unknown_action(self):
        with self.assertRaises(ValidationError):
            self.act("request_correction", reason="Check", allowed_fields=["full_name"])
        with self.assertRaises(ValidationError):
            self.act("arbitrary")
        self.assertFalse(ReviewEvent.objects.exists())

    def test_rejection_requires_reason_and_creates_no_identity(self):
        self.begin()
        with self.assertRaises(ValidationError):
            self.act("reject", reason="   ")
        self.act("reject", reason="Recommendation could not be verified.")
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "REJECTED")
        self.assertFalse(Facilitator.objects.exists())
        self.assertEqual(
            self.app.review_events.get(action="reject").reason,
            "Recommendation could not be verified.",
        )

    def test_role_boundaries_review_and_approval(self):
        for actor in [self.coordinator, self.reviewer]:
            with self.assertRaises(PermissionDenied):
                self.act("reject", actor=actor, reason="Unauthorized")
            with self.assertRaises(PermissionDenied):
                self.act("approve", actor=actor, verification_complete=True)
        self.act("start_review", actor=self.coordinator)
        self.act("approve", actor=self.regional, verification_complete=True)
        self.assertEqual(Facilitator.objects.count(), 1)

    def test_direct_service_cross_district_denied(self):
        app = self.make_app(gp=self.other_gp)
        for action in ["start_review", "request_correction", "approve", "reject"]:
            with self.assertRaises(PermissionDenied):
                self.act(
                    action,
                    app=app,
                    actor=self.regional,
                    reason="Not allowed",
                    verification_complete=True,
                )

    def test_mixed_view_scope_does_not_expand_write_scope(self):
        assign(self.regional, "REVIEWER", "STATE")
        app = self.make_app(gp=self.other_gp, mobile="9876543211", name="Other Applicant")
        self.begin(app)
        with self.assertRaises(PermissionDenied):
            self.act(
                "approve",
                app=app,
                actor=self.regional,
                verification_complete=True,
                acknowledge_duplicates=True,
                reason="Not allowed",
            )

    def test_active_primary_conflict_blocks_second_approval(self):
        self.begin()
        self.act("approve", verification_complete=True)
        second = self.make_app(mobile="9876543211", name="Second Person")
        self.begin(second)
        with self.assertRaisesMessage(ValidationError, "active primary"):
            self.act(
                "approve",
                app=second,
                verification_complete=True,
                acknowledge_duplicates=True,
                reason="Reviewed",
            )
        second.refresh_from_db()
        self.assertEqual(second.status, "UNDER_REVIEW")
        self.assertEqual(FacilitatorSequence.objects.get().value, 1)

    def test_policy_can_allow_multiple_primary_appointments(self):
        self.begin()
        self.act("approve", verification_complete=True)
        SystemSetting.objects.filter(pk=1).update(one_primary_per_panchayat=False)
        second = self.make_app(mobile="9876543211", name="Second Person")
        self.begin(second)
        self.act(
            "approve",
            app=second,
            verification_complete=True,
            acknowledge_duplicates=True,
            reason="Multiple positions authorized.",
        )
        self.assertEqual(FacilitatorAppointment.objects.count(), 2)
        self.assertEqual(FacilitatorSequence.objects.get().value, 2)

    def test_duplicate_warning_requires_acknowledgment_and_reason(self):
        self.make_app(name="Similar Applicant")
        self.begin()
        for options in [{"acknowledge_duplicates": True}, {"reason": "Reviewed"}]:
            with self.assertRaises(ValidationError):
                self.act("approve", verification_complete=True, **options)
        self.act(
            "approve",
            verification_complete=True,
            acknowledge_duplicates=True,
            reason="Separate applicants; verified supporting details.",
        )
        self.assertEqual(Facilitator.objects.count(), 1)

    def test_approval_checks_new_duplicates_after_review_started(self):
        self.begin()
        self.make_app(name="New Candidate")
        with self.assertRaisesMessage(ValidationError, "duplicate"):
            self.act("approve", verification_complete=True)

    def test_approval_revalidates_location_and_file_existence(self):
        self.begin()
        self.gp.active = False
        self.gp.save()
        with self.assertRaises(ValidationError):
            self.act("approve", verification_complete=True)
        self.gp.active = True
        self.gp.save()
        self.app.uploads.get().file.delete(save=False)
        with self.assertRaisesMessage(ValidationError, "unavailable"):
            self.act("approve", verification_complete=True)

    def test_approval_audit_failure_rolls_back_identity_sequence_and_status(self):
        self.begin()
        with patch(
            "apps.registrations.review_services.record_event",
            side_effect=RuntimeError("Audit failed"),
        ):
            with self.assertRaises(RuntimeError):
                self.act("approve", verification_complete=True)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "UNDER_REVIEW")
        for model in [
            Facilitator,
            FacilitatorAppointment,
            IdentityCardMetadata,
            FacilitatorSequence,
        ]:
            self.assertFalse(model.objects.exists(), model)
        self.assertEqual(self.app.review_events.count(), 1)

    def test_card_metadata_failure_rolls_back_entire_approval(self):
        self.begin()
        with patch.object(
            IdentityCardMetadata.objects, "create", side_effect=RuntimeError("Storage failed")
        ):
            with self.assertRaises(RuntimeError):
                self.act("approve", verification_complete=True)
        self.assertFalse(Facilitator.objects.exists())
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "UNDER_REVIEW")

    def test_correction_only_selected_fields_and_history(self):
        result = self.correction()
        app = self.correct(
            result,
            full_name="Corrected Applicant",
            mobile="9999999999",
            panchayat=self.other_gp.pk,
            status="APPROVED",
        )
        self.assertEqual(app.full_name, "Corrected Applicant")
        self.assertEqual(app.mobile, "9876543210")
        self.assertEqual(app.panchayat, self.gp)
        self.assertEqual(app.status, "SUBMITTED")
        changes = app.review_events.get(action="correction_resubmitted").changes
        self.assertEqual(
            changes["full_name"], {"old": "Test Applicant", "new": "Corrected Applicant"}
        )
        self.assertIn("consent", changes)
        result["correction"].refresh_from_db()
        self.assertIsNotNone(result["correction"].used_at)

    def test_correction_forbidden_fields_rejected_at_issue(self):
        self.begin()
        for field in [
            "status",
            "panchayat",
            "district",
            "application_number",
            "reviewed_by",
            "revision",
        ]:
            with self.assertRaises(ValidationError):
                self.act("request_correction", reason="Forged", allowed_fields=[field])

    def test_expired_revoked_and_used_tokens_cannot_modify(self):
        result = self.correction()
        ticket = result["correction"]
        CorrectionRequest.objects.filter(pk=ticket.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        with self.assertRaises(ValidationError):
            self.correct(result, full_name="Changed")
        renewed = self.act("renew_correction", reason="Original link expired.")
        with self.assertRaises(ValidationError):
            self.correct(result, full_name="Changed")
        self.correct(renewed, full_name="Updated")
        with self.assertRaises(ValidationError):
            self.correct(renewed, full_name="Updated again")

    def test_wrong_token_rejected(self):
        result = self.correction()
        with self.assertRaises(ValidationError):
            apply_correction(ticket_id=result["correction"].pk, digest="0" * 64, data={}, files={})

    def test_cancel_correction_revokes_access(self):
        result = self.correction()
        self.act("cancel_correction", reason="Applicant confirmed existing details.")
        with self.assertRaises(ValidationError):
            self.correct(result, full_name="Changed")
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "UNDER_REVIEW")

    def test_unchanged_correction_not_accepted(self):
        result = self.correction()
        with self.assertRaisesMessage(ValidationError, "at least one"):
            self.correct(result, full_name=self.app.full_name)

    def test_correction_requires_consent_and_current_version(self):
        result = self.correction()
        with self.assertRaises(ValidationError):
            self.correct(result, full_name="Changed", processing=False)
        SystemSetting.objects.filter(pk=1).update(consent_version="2.0")
        with self.assertRaises(ValidationError):
            self.correct(result, full_name="Changed")

    def test_correction_audit_failure_rolls_back_and_leaves_token_usable(self):
        result = self.correction()
        with patch(
            "apps.registrations.review_services.record_event",
            side_effect=RuntimeError("Audit failed"),
        ):
            with self.assertRaises(RuntimeError):
                self.correct(result, full_name="Changed")
        self.app.refresh_from_db()
        self.assertEqual(self.app.full_name, "Test Applicant")
        self.assertEqual(self.app.status, "CORRECTION_REQUIRED")
        result["correction"].refresh_from_db()
        self.assertIsNone(result["correction"].used_at)

    def test_corrected_document_replaces_file_and_records_hash(self):
        result = self.correction(["doc_certificate"])
        payload = {
            "revision": result["application"].revision,
            "accuracy": True,
            "processing": True,
            "consent_version": "1.0",
        }
        app = apply_correction(
            ticket_id=result["correction"].pk,
            digest=digest_token(result["token"]),
            data=payload,
            files={"doc_certificate": pdf()},
        )
        self.assertEqual(app.uploads.count(), 2)
        self.assertIn(
            "doc_certificate", app.review_events.get(action="correction_resubmitted").changes
        )

    def test_failed_correction_file_write_removes_new_file(self):
        result = self.correction(["doc_certificate"])
        before = {p for p in Path(self.media.name).rglob("*") if p.is_file()}
        with patch(
            "apps.registrations.review_services.record_event",
            side_effect=RuntimeError("Audit failed"),
        ):
            with self.assertRaises(RuntimeError):
                apply_correction(
                    ticket_id=result["correction"].pk,
                    digest=digest_token(result["token"]),
                    data={
                        "revision": result["application"].revision,
                        "accuracy": True,
                        "processing": True,
                        "consent_version": "1.0",
                    },
                    files={"doc_certificate": pdf()},
                )
        self.assertEqual(before, {p for p in Path(self.media.name).rglob("*") if p.is_file()})

    def test_review_history_is_append_only(self):
        self.begin()
        event = self.app.review_events.get()
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            self.app.review_events.update(reason="Tampered")
        with self.assertRaises(ValidationError):
            event.delete()

    def test_dashboard_counts_search_and_filters_are_scoped(self):
        self.make_app(gp=self.other_gp, name="Hidden Person", mobile="9876543211")
        self.client.force_login(self.regional)
        response = self.client.get("/applications/")
        self.assertEqual(response.context["total"], 1)
        self.assertContains(response, "Test Applicant")
        self.assertNotContains(response, "Hidden Person")
        response = self.client.get("/applications/", {"q": "9876543210", "status": ""})
        self.assertEqual(response.context["page"].paginator.count, 1)
        response = self.client.get("/applications/", {"district": self.other_gp.block.district_id})
        self.assertEqual(response.context["page"].paginator.count, 0)

    def test_viewer_and_anonymous_cannot_access_applications(self):
        self.assertEqual(self.client.get("/applications/").status_code, 302)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get("/applications/").status_code, 403)
        self.assertEqual(self.client.get(self.url()).status_code, 403)

    def test_cross_boundary_detail_action_and_download_denied(self):
        app = self.make_app(gp=self.other_gp, name="Hidden Name")
        self.client.force_login(self.regional)
        for path in [
            self.url(app),
            self.url(app) + "action/start_review/",
            self.url(app) + f"files/{app.uploads.get().pk}/",
        ]:
            self.assertEqual(self.client.get(path).status_code, 404, path)
        self.assertEqual(
            self.client.post(self.url(app) + "action/start_review/", {"revision": 1}).status_code,
            404,
        )

    def test_block_scope_cannot_read_sibling_block(self):
        gp = GramaPanchayat.objects.create(
            block=self.sibling, sec_local_body_code="G01002", name_en="Sibling"
        )
        app = self.make_app(gp=gp)
        self.client.force_login(self.coordinator)
        self.assertEqual(self.client.get(self.url(app)).status_code, 404)

    def test_duplicate_outside_scope_is_redacted(self):
        app = self.make_app(gp=self.other_gp, name="Hidden Applicant")
        self.client.force_login(self.regional)
        response = self.client.get(self.url())
        self.assertContains(response, "Match outside your access")
        self.assertNotContains(response, "Hidden Applicant")
        self.assertNotContains(response, app.application_number)

    def test_staff_download_audited_attachment_private(self):
        data = validate_upload(pdf(), max_bytes=100000)
        document = RegistrationUpload.objects.create(
            application=self.app,
            slot="doc_certificate",
            file=data["content"],
            content_type=data["content_type"],
            byte_size=data["byte_size"],
            sha256=data["sha256"],
        )
        self.client.force_login(self.reviewer)
        response = self.client.get(self.url() + f"files/{document.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        response.close()
        self.assertTrue(AuditLog.objects.filter(action="application.file_downloaded").exists())

    def test_file_cannot_be_accessed_through_wrong_application(self):
        app = self.make_app()
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(self.url() + f"files/{app.uploads.get().pk}/").status_code, 404
        )

    def test_actions_require_csrf_and_get_does_not_mutate(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        path = self.url() + "action/start_review/"
        self.assertEqual(client.get(path).status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "SUBMITTED")
        self.assertEqual(client.post(path, {"revision": 1}).status_code, 403)

    def test_correction_http_exchange_only_allowed_fields_and_one_use(self):
        result = self.correction(["full_name"])
        ticket = result["correction"]
        base = f"/correct/{ticket.pk}/"
        self.assertEqual(self.client.get(base + "edit/").status_code, 404)
        self.assertRedirects(self.client.post(base, {"token": result["token"]}), base + "edit/")
        response = self.client.get(base + "edit/")
        self.assertContains(response, "Correct your application")
        self.assertNotContains(response, 'name="mobile"')
        self.assertNotContains(response, "Private home address")
        response = self.client.post(
            base + "edit/",
            {
                "revision": result["application"].revision,
                "full_name": "Updated Applicant",
                "accuracy": True,
                "processing": True,
                "consent_version": "1.0",
            },
        )
        self.assertRedirects(response, "/correct/complete/")
        self.assertEqual(self.client.get(base + "edit/").status_code, 404)
        self.assertEqual(self.client.post(base, {"token": result["token"]}).status_code, 404)

    def test_correction_csrf_required_and_token_not_stored_raw(self):
        result = self.correction()
        ticket = result["correction"]
        self.assertNotEqual(ticket.token_hash, result["token"])
        self.assertEqual(len(ticket.token_hash), 64)
        self.assertEqual(
            Client(enforce_csrf_checks=True)
            .post(f"/correct/{ticket.pk}/", {"token": result["token"]})
            .status_code,
            403,
        )

    def test_correction_link_response_contains_fragment_not_query_token(self):
        self.begin()
        self.client.force_login(self.admin)
        self.app.refresh_from_db()
        response = self.client.post(
            self.url() + "action/request_correction/",
            {
                "revision": self.app.revision,
                "reason": "Correct spelling",
                "allowed_fields": ["full_name"],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("#", response.context["correction_url"])
        self.assertNotIn("?token", response.context["correction_url"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["Referrer-Policy"], "same-origin")

    def test_changed_consent_and_draft_pruning_do_not_break_review(self):
        self.assertIsNone(self.app.draft_id)
        result = self.correction()
        app = self.correct(result, full_name="Reviewed Applicant")
        self.begin(app)
        self.act("approve", app=app, verification_complete=True)
        self.assertTrue(Facilitator.objects.filter(application=app).exists())

    def test_reviewer_cannot_view_approval_form(self):
        self.begin()
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.get(self.url() + "action/approve/").status_code, 403)

    def test_filter_invalid_dates_and_status_fail_safely(self):
        self.client.force_login(self.admin)
        for values in [
            {"status": "UNKNOWN"},
            {"date_from": "bad"},
            {"date_from": "2026-12-01", "date_to": "2026-01-01"},
        ]:
            response = self.client.get("/applications/", values)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["page"].paginator.count, 0)

    def test_correction_link_issue_audit_failure_rolls_back_ticket(self):
        self.begin()
        with patch(
            "apps.registrations.review_services.record_event",
            side_effect=RuntimeError("Audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.act(
                    "request_correction", reason="Correct details", allowed_fields=["full_name"]
                )
        self.assertFalse(CorrectionRequest.objects.exists())
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "UNDER_REVIEW")
