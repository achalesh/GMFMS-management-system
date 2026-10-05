from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.audit.services import record_event
from apps.organization.models import OrganizationSetting, SystemSetting
from apps.organization.services import update_settings

from .factories import user_with_role


class SettingsAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            "root", "root@example.org", "Long-test-password-829!"
        )
        cls.state = user_with_role("state", "STATE_ADMIN")
        cls.viewer = user_with_role("viewer")

    def test_singletons_seeded_and_private_defaults(self):
        self.assertEqual(OrganizationSetting.objects.count(), 1)
        settings = SystemSetting.objects.get()
        self.assertFalse(settings.allow_public_email)
        self.assertFalse(settings.allow_public_mobile)
        self.assertFalse(settings.allow_public_social_profiles)
        self.assertFalse(settings.public_directory_enabled)
        self.assertTrue(settings.one_primary_per_panchayat)

    def test_settings_update_audited_with_old_new_values(self):
        old = OrganizationSetting.objects.get()
        new = update_settings(
            actor=self.admin,
            model=OrganizationSetting,
            values={"name_ml": "കേരളം", "short_name": "New brand"},
            expected_revision=old.revision,
        )
        self.assertEqual(new.revision, 2)
        event = AuditLog.objects.get(action="organizationsetting.updated")
        self.assertEqual(event.old_values["short_name"], "Gramaswaraj")
        self.assertEqual(event.new_values["name_ml"], "കേരളം")
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/"), "New brand")

    def test_stale_write_rejected(self):
        update_settings(
            actor=self.admin, model=SystemSetting, values={"max_upload_mb": 8}, expected_revision=1
        )
        with self.assertRaises(ValidationError):
            update_settings(
                actor=self.admin,
                model=SystemSetting,
                values={"max_upload_mb": 9},
                expected_revision=1,
            )
        self.assertEqual(SystemSetting.objects.get().max_upload_mb, 8)

    def test_invalid_settings_rejected_and_no_audit(self):
        with self.assertRaises(ValidationError):
            update_settings(
                actor=self.admin,
                model=SystemSetting,
                values={"max_upload_mb": 999},
                expected_revision=1,
            )
        self.assertEqual(SystemSetting.objects.get().max_upload_mb, 5)
        self.assertFalse(AuditLog.objects.exists())

    def test_unknown_settings_fields_rejected(self):
        with self.assertRaises(ValidationError):
            update_settings(
                actor=self.admin,
                model=SystemSetting,
                values={"publish_dob": True},
                expected_revision=1,
            )

    def test_settings_and_audit_are_atomic(self):
        with patch(
            "apps.organization.services.record_event", side_effect=RuntimeError("audit unavailable")
        ):
            with self.assertRaises(RuntimeError):
                update_settings(
                    actor=self.admin,
                    model=SystemSetting,
                    values={"max_upload_mb": 8},
                    expected_revision=1,
                )
        self.assertEqual(SystemSetting.objects.get().max_upload_mb, 5)

    def test_state_admin_can_change_branding_not_security(self):
        update_settings(
            actor=self.state,
            model=OrganizationSetting,
            values={"short_name": "Test"},
            expected_revision=1,
        )
        with self.assertRaises(PermissionDenied):
            update_settings(
                actor=self.state,
                model=SystemSetting,
                values={"max_upload_mb": 8},
                expected_revision=1,
            )

    def test_viewer_cannot_call_mutation_service(self):
        with self.assertRaises(PermissionDenied):
            update_settings(
                actor=self.viewer,
                model=OrganizationSetting,
                values={"short_name": "Attack"},
                expected_revision=1,
            )

    def test_audit_is_append_only(self):
        event = record_event(actor=self.admin, action="test", entity=self.admin)
        for operation in [
            lambda: event.save(),
            lambda: event.delete(),
            lambda: AuditLog.objects.filter(pk=event.pk).update(action="changed"),
            lambda: AuditLog.objects.filter(pk=event.pk).delete(),
            lambda: AuditLog.objects.bulk_update([event], ["action"]),
        ]:
            with self.assertRaises(ValidationError):
                operation()

    def test_settings_form_saves_and_blocks_stale_revision(self):
        self.client.force_login(self.admin)
        payload = {
            "facilitator_id_prefix": "GS-MF",
            "default_validity_days": 365,
            "one_primary_per_panchayat": "on",
            "max_upload_mb": 7,
            "consent_version": "1.0",
            "expected_revision": 1,
        }
        response = self.client.post("/settings/system/", payload)
        self.assertRedirects(response, "/settings/system/")
        self.assertEqual(SystemSetting.objects.get().max_upload_mb, 7)
        self.assertContains(
            self.client.post("/settings/system/", payload), "changed in another session"
        )

    def test_audit_events_are_not_exposed_to_viewer_dashboard(self):
        record_event(actor=self.admin, action="private.administrative.event", entity=self.admin)
        self.client.force_login(self.viewer)
        self.assertNotContains(self.client.get("/"), "private.administrative.event")

    def test_reconstructed_event_cannot_overwrite_existing_id(self):
        from django.db import IntegrityError, transaction

        event = record_event(actor=self.admin, action="original", entity=self.admin)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AuditLog(id=event.pk, action="changed", entity_type="account", entity_id="1").save()
        event.refresh_from_db()
        self.assertEqual(event.action, "original")
