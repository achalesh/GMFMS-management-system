from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.utils import timezone

from apps.facilitators.models import Facilitator, FacilitatorStatusHistory
from apps.facilitators.selectors import primary_appointments, registry_for
from apps.facilitators.services import expire_identities, registry_action
from apps.organization.models import SystemSetting
from tests import test_review as review_fixtures
from tests.factories import assign


class RegistryTests(TestCase):
    setUp = review_fixtures.ReviewTests.setUp
    make_app = review_fixtures.ReviewTests.make_app
    act = review_fixtures.ReviewTests.act
    begin = review_fixtures.ReviewTests.begin

    def approve(self, app=None):
        app = app or self.app
        self.begin(app)
        self.act(
            "approve",
            app=app,
            verification_complete=True,
            acknowledge_duplicates=True,
            reason="Verified test record.",
        )
        return Facilitator.objects.get(application=app)

    def change(self, f, action, **kwargs):
        f.refresh_from_db()
        return registry_action(
            actor=kwargs.pop("actor", self.admin),
            facilitator_id=f.pk,
            action=action,
            revision=kwargs.pop("revision", f.revision),
            reason=kwargs.pop("reason", "Authorized test change."),
            **kwargs,
        )

    def incoming(self, gp=None):
        app = self.make_app(gp=gp, name="Incoming Applicant", mobile="9876543211")
        self.begin(app)
        app.refresh_from_db()
        return app

    def test_approval_sets_current_appointment_and_history(self):
        f = self.approve()
        self.assertEqual(f.current_appointment.facilitator, f)
        self.assertEqual(f.status_history.get().action, "approved")
        self.assertEqual(primary_appointments().count(), 1)

    def test_suspend_reactivate_preserves_identity_and_token(self):
        f = self.approve()
        token, number, appointment = (
            f.verification_token,
            f.facilitator_number,
            f.current_appointment_id,
        )
        self.change(f, "suspend")
        self.assertFalse(primary_appointments().exists())
        f = self.change(f, "reactivate")
        self.assertEqual(
            (f.verification_token, f.facilitator_number, f.current_appointment_id),
            (token, number, appointment),
        )
        self.assertEqual(f.status_history.count(), 3)

    def test_reason_revision_and_role_required(self):
        f = self.approve()
        for kwargs in [{"reason": " "}, {"revision": 0}]:
            with self.assertRaises(ValidationError):
                self.change(f, "suspend", **kwargs)
        for actor in [self.viewer, self.reviewer, self.coordinator]:
            with self.assertRaises(PermissionDenied):
                self.change(f, "suspend", actor=actor)
        self.assertEqual(f.status_history.count(), 1)

    def test_revoke_is_terminal_and_preserves_identity(self):
        f = self.change(self.approve(), "revoke")
        self.assertIsNotNone(f.current_appointment.ended_at)
        for action in ["reactivate", "renew", "replace", "transfer"]:
            with self.assertRaises(ValidationError):
                self.change(f, action)
        self.assertEqual(Facilitator.objects.count(), 1)

    def test_resignation_then_reactivation_creates_new_appointment(self):
        f = self.approve()
        old = f.current_appointment
        self.change(f, "resign")
        f = self.change(f, "reactivate")
        old.refresh_from_db()
        self.assertIsNotNone(old.ended_at)
        self.assertNotEqual(f.current_appointment_id, old.pk)
        self.assertEqual(f.appointments.count(), 2)

    def test_transfer_retains_number_and_moves_scope(self):
        f = self.approve()
        old = f.current_appointment
        f = self.change(f, "transfer", panchayat_id=self.other_gp.pk)
        self.assertTrue(f.facilitator_number.startswith("GS-MF-TVM-"))
        self.assertFalse(registry_for(self.regional).filter(pk=f.pk).exists())
        old.refresh_from_db()
        self.assertIsNotNone(old.ended_at)
        self.assertEqual(f.current_appointment.panchayat, self.other_gp)
        self.assertFalse(primary_appointments().filter(panchayat=self.gp).exists())

    def test_transfer_requires_both_scopes_despite_broader_view_role(self):
        f = self.approve()
        assign(self.regional, "VIEWER", "STATE")
        with self.assertRaises(PermissionDenied):
            self.change(f, "transfer", actor=self.regional, panchayat_id=self.other_gp.pk)
        self.assertEqual(f.appointments.count(), 1)

    def test_transfer_rejects_inactive_and_same_location(self):
        f = self.approve()
        with self.assertRaises(ValidationError):
            self.change(f, "transfer", panchayat_id=self.gp.pk)
        self.other_gp.active = False
        self.other_gp.save()
        with self.assertRaises(ValidationError):
            self.change(f, "transfer", panchayat_id=self.other_gp.pk)

    def test_role_change_preserves_old_appointment_and_vacates_primary(self):
        f = self.approve()
        f = self.change(f, "role", role="ASSISTANT")
        self.assertEqual(f.current_appointment.role, "ASSISTANT")
        self.assertEqual(f.appointments.count(), 2)
        self.assertFalse(primary_appointments().exists())
        with self.assertRaises(ValidationError):
            self.change(f, "role", role="WRONG")

    def test_reactivation_and_role_cannot_create_second_primary(self):
        f = self.approve()
        self.change(f, "suspend")
        self.approve(self.make_app(name="Second"))
        with self.assertRaises(ValidationError):
            self.change(f, "reactivate")
        f.refresh_from_db()
        self.assertEqual(f.status, "SUSPENDED")

    def test_transfer_conflict_rolls_back(self):
        f = self.approve()
        self.approve(self.make_app(gp=self.other_gp))
        with self.assertRaises(ValidationError):
            self.change(f, "transfer", panchayat_id=self.other_gp.pk)
        self.assertEqual(f.appointments.count(), 1)

    def test_policy_override_allows_multiple_primaries(self):
        f = self.approve()
        self.change(f, "suspend")
        self.approve(self.make_app(name="Second"))
        policy = SystemSetting.objects.get(pk=1)
        policy.one_primary_per_panchayat = False
        policy.save()
        self.change(f, "reactivate")
        self.assertEqual(primary_appointments().count(), 2)

    def test_expiry_is_effective_before_command_and_logged_once(self):
        f = self.approve()
        f.valid_until = timezone.localdate() - timedelta(days=1)
        f.save()
        self.assertEqual(f.effective_status, "EXPIRED")
        self.assertFalse(primary_appointments().exists())
        self.assertEqual(registry_for(self.admin).get(pk=f.pk).display_status, "EXPIRED")
        self.assertEqual(expire_identities(), 1)
        self.assertEqual(expire_identities(), 0)
        self.assertEqual(f.status_history.filter(action="expired").count(), 1)

    def test_renew_expired_active_and_suspended_behavior(self):
        f = self.approve()
        f.valid_until = timezone.localdate() - timedelta(days=1)
        f.save()
        expiry = timezone.localdate() + timedelta(days=365)
        f = self.change(f, "renew", valid_until=expiry)
        self.assertEqual(f.effective_status, "ACTIVE")
        self.assertEqual(f.current_appointment.effective_to, expiry)
        self.change(f, "suspend")
        f = self.change(f, "renew", valid_until=expiry + timedelta(days=1))
        self.assertEqual(f.status, "SUSPENDED")

    def test_renewal_cannot_overlap_replacement_approval(self):
        f = self.approve()
        f.valid_until = timezone.localdate() - timedelta(days=1)
        f.save()
        self.approve(self.make_app(name="Second"))
        with self.assertRaises(ValidationError):
            self.change(f, "renew", valid_until=timezone.localdate() + timedelta(days=400))

    def test_invalid_renewal_and_expired_reactivation(self):
        f = self.approve()
        with self.assertRaises(ValidationError):
            self.change(f, "renew", valid_until=f.valid_until)
        self.change(f, "suspend")
        f.valid_until = timezone.localdate() - timedelta(days=1)
        f.save()
        with self.assertRaises(ValidationError):
            self.change(f, "reactivate")

    def test_replacement_atomically_approves_new_identity_and_closes_old(self):
        f = self.approve()
        token = f.verification_token
        incoming = self.incoming()
        f = self.change(
            f,
            "replace",
            replacement_id=incoming.pk,
            application_revision=incoming.revision,
            verification_complete=True,
            acknowledge_duplicates=True,
        )
        incoming.refresh_from_db()
        self.assertEqual(f.status, "REPLACED")
        self.assertEqual(f.verification_token, token)
        self.assertIsNotNone(f.current_appointment.ended_at)
        self.assertEqual(incoming.status, "APPROVED")
        self.assertNotEqual(incoming.facilitator.facilitator_number, f.facilitator_number)
        self.assertEqual(primary_appointments().count(), 1)

    def test_replacement_validation_and_audit_failure_roll_back_both(self):
        f = self.approve()
        incoming = self.incoming()
        with self.assertRaises(ValidationError):
            self.change(
                f,
                "replace",
                replacement_id=incoming.pk,
                application_revision=incoming.revision,
                verification_complete=False,
            )
        with patch(
            "apps.facilitators.services.record_event", side_effect=RuntimeError("audit unavailable")
        ):
            with self.assertRaises(RuntimeError):
                self.change(
                    f,
                    "replace",
                    replacement_id=incoming.pk,
                    application_revision=incoming.revision,
                    verification_complete=True,
                    acknowledge_duplicates=True,
                )
        f.refresh_from_db()
        incoming.refresh_from_db()
        self.assertEqual(f.status, "ACTIVE")
        self.assertIsNone(f.current_appointment.ended_at)
        self.assertEqual(incoming.status, "UNDER_REVIEW")
        self.assertEqual(Facilitator.objects.count(), 1)

    def test_replacement_wrong_location_or_stale_revision(self):
        f = self.approve()
        incoming = self.incoming(self.other_gp)
        with self.assertRaises(ValidationError):
            self.change(
                f, "replace", replacement_id=incoming.pk, application_revision=incoming.revision
            )
        incoming = self.incoming()
        with self.assertRaises(ValidationError):
            self.change(
                f,
                "replace",
                replacement_id=incoming.pk,
                application_revision=0,
                verification_complete=True,
                acknowledge_duplicates=True,
            )

    def test_history_is_append_only_and_action_failure_rolls_back(self):
        f = self.approve()
        event = f.status_history.get()
        with self.assertRaises(ValidationError):
            event.delete()
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            FacilitatorStatusHistory.objects.filter(pk=event.pk).update(reason="changed")
        with patch("apps.facilitators.services.record_event", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.change(f, "suspend")
        f.refresh_from_db()
        self.assertEqual(f.status, "ACTIVE")
        self.assertEqual(f.status_history.count(), 1)

    def test_viewer_privacy_and_contact_search_scope(self):
        f = self.approve()
        self.client.force_login(self.viewer)
        response = self.client.get(f"/facilitators/{f.pk}/")
        self.assertEqual(response.status_code, 200)
        for secret in [
            f.verification_token,
            self.app.mobile,
            self.app.address,
            "Verified test record.",
        ]:
            self.assertNotContains(response, secret)
        response = self.client.get("/facilitators/", {"q": self.app.mobile})
        self.assertEqual(response.context["page"].paginator.count, 0)
        self.assertEqual(self.client.get(f"/facilitators/{f.pk}/actions/suspend/").status_code, 404)

    def test_broader_view_does_not_widen_contacts_or_actions(self):
        f = self.approve(self.make_app(gp=self.other_gp, name="Other Person"))
        assign(self.regional, "VIEWER", "STATE")
        self.client.force_login(self.regional)
        response = self.client.get(f"/facilitators/{f.pk}/")
        self.assertContains(response, "Other Person")
        self.assertNotContains(response, self.app.mobile)
        self.assertEqual(self.client.get(f"/facilitators/{f.pk}/actions/suspend/").status_code, 404)

    def test_lists_detail_and_coverage_are_scoped(self):
        self.approve()
        other = self.approve(self.make_app(gp=self.other_gp))
        self.client.force_login(self.regional)
        self.assertEqual(self.client.get("/facilitators/").context["total"], 1)
        self.assertEqual(self.client.get(f"/facilitators/{other.pk}/").status_code, 404)
        self.assertEqual(
            self.client.get(f"/facilitators/panchayats/{self.other_gp.pk}/").status_code, 404
        )
        response = self.client.get("/facilitators/coverage/")
        self.assertEqual(response.context["total"], 1)
        self.assertEqual(response.context["vacant"], 0)

    def test_vacancies_distinct_even_with_multiple_primary_policy(self):
        self.approve()
        policy = SystemSetting.objects.get(pk=1)
        policy.one_primary_per_panchayat = False
        policy.save()
        self.approve(self.make_app(name="Additional primary"))
        self.client.force_login(self.admin)
        response = self.client.get("/facilitators/coverage/")
        self.assertEqual(response.context["total"], 2)
        self.assertEqual(response.context["occupied"], 1)
        self.assertEqual(response.context["vacant"], 1)

    def test_profile_preserves_history_after_transfer_without_private_leak(self):
        f = self.approve()
        self.change(f, "transfer", panchayat_id=self.other_gp.pk)
        self.client.force_login(self.regional)
        response = self.client.get(f"/facilitators/panchayats/{self.gp.pk}/")
        self.assertContains(response, f.facilitator_number)
        self.assertNotContains(response, f"/facilitators/{f.pk}/")
        self.assertNotContains(response, f.verification_token)

    def test_get_is_readonly_csrf_required_and_anonymous_denied(self):
        f = self.approve()
        self.assertEqual(self.client.get("/facilitators/").status_code, 302)
        self.client.force_login(self.admin)
        response = self.client.get(f"/facilitators/{f.pk}/actions/suspend/")
        self.assertEqual(response.status_code, 200)
        f.refresh_from_db()
        self.assertEqual(f.status, "ACTIVE")
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(
            client.post(
                f"/facilitators/{f.pk}/actions/suspend/", {"revision": f.revision, "reason": "Test"}
            ).status_code,
            403,
        )

    def test_filters_and_all_registry_pages_render(self):
        f = self.approve()
        self.client.force_login(self.admin)
        paths = [
            "/facilitators/",
            f"/facilitators/{f.pk}/",
            "/facilitators/coverage/",
            f"/facilitators/coverage/districts/{self.district.pk}/",
            f"/facilitators/coverage/blocks/{self.block.pk}/",
            f"/facilitators/panchayats/{self.gp.pk}/",
        ]
        for path in paths:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn("no-store", response["Cache-Control"])
        response = self.client.get("/facilitators/", {"district": "bad"})
        self.assertEqual(response.context["page"].paginator.count, 0)
        response = self.client.get(
            "/facilitators/", {"q": f.facilitator_number, "status": "ACTIVE", "role": "PRIMARY"}
        )
        self.assertEqual(response.context["page"].paginator.count, 1)

    def test_replacement_form_detects_changed_incoming_application(self):
        f = self.approve()
        incoming = self.incoming()
        self.client.force_login(self.admin)
        incoming.revision += 1
        incoming.save()
        response = self.client.post(
            f"/facilitators/{f.pk}/actions/replace/",
            {
                "revision": f.revision,
                "reason": "Verified replacement",
                "replacement": f"{incoming.pk}:{incoming.revision - 1}",
                "verification_complete": "on",
                "acknowledge_duplicates": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        f.refresh_from_db()
        self.assertEqual(f.status, "ACTIVE")

    def test_portrait_is_scoped_private_and_token_never_exposed(self):
        f = self.approve()
        other = self.approve(self.make_app(gp=self.other_gp))
        self.client.force_login(self.regional)
        response = self.client.get(f"/facilitators/{f.pk}/portrait/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertIn("no-store", response["Cache-Control"])
        response.close()
        self.assertEqual(self.client.get(f"/facilitators/{other.pk}/portrait/").status_code, 404)

    def test_revocation_after_resignation_preserves_original_end(self):
        f = self.change(self.approve(), "resign", reason="Resigned from appointment.")
        ended = f.current_appointment.ended_at
        f = self.change(f, "revoke", reason="Authorization revoked.")
        self.assertEqual(f.current_appointment.ended_at, ended)
        self.assertEqual(f.current_appointment.end_reason, "Resigned from appointment.")

    def test_primary_promotion_checks_conflict(self):
        f = self.change(self.approve(), "role", role="ASSISTANT")
        self.approve(self.make_app(name="New primary"))
        with self.assertRaises(ValidationError):
            self.change(f, "role", role="PRIMARY")
        f.refresh_from_db()
        self.assertEqual(f.current_appointment.role, "ASSISTANT")

    def test_appointment_notes_are_audited_and_private(self):
        f = self.change(
            self.approve(),
            "details",
            appointment_reference="KGPA/2026/001",
            notes="Private appointment investigation",
        )
        self.assertEqual(f.current_appointment.appointment_reference, "KGPA/2026/001")
        self.assertEqual(
            f.status_history.get(action="details").changes["new"]["notes"],
            "Private appointment investigation",
        )
        self.client.force_login(self.viewer)
        response = self.client.get(f"/facilitators/{f.pk}/")
        self.assertNotContains(response, "Private appointment investigation")
        self.assertNotContains(response, "KGPA/2026/001")

    def test_assistant_approval_does_not_conflict_with_primary(self):
        self.approve()
        incoming = self.incoming()
        self.act(
            "approve",
            app=incoming,
            appointment_role="ASSISTANT",
            verification_complete=True,
            acknowledge_duplicates=True,
            reason="Approved supporting appointment.",
        )
        incoming.refresh_from_db()
        self.assertEqual(incoming.facilitator.current_appointment.role, "ASSISTANT")
        self.assertEqual(primary_appointments().count(), 1)

    def test_invalid_approval_role_rejected(self):
        incoming = self.incoming()
        with self.assertRaises(ValidationError):
            self.act(
                "approve", app=incoming, appointment_role="INVALID", verification_complete=True
            )
        self.assertFalse(Facilitator.objects.exists())
