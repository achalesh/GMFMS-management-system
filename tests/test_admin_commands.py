from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.policies import can
from apps.audit.models import AuditLog

from .factories import user_with_role


class AdminAndCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            "root", "root@example.org", "Long-test-password-791!"
        )
        cls.viewer = user_with_role("viewer")

    def test_grant_and_revoke_commands(self):
        from apps.locations.models import District, State

        District.objects.create(
            district_code="TVM", name_en="Thiruvananthapuram", state=State.objects.get(code="KL")
        )
        output = StringIO()
        call_command(
            "grant_role",
            "viewer",
            "REVIEWER",
            actor="root",
            scope="DISTRICT",
            district="TVM",
            stdout=output,
        )
        self.assertTrue(can(self.viewer, "applications.review", district_code="TVM"))
        call_command(
            "revoke_role", "viewer", "REVIEWER", actor="root", reason="Ended", stdout=output
        )
        self.assertFalse(can(self.viewer, "applications.review", district_code="TVM"))

    def test_unauthorized_command_actor_denied(self):
        with self.assertRaises(CommandError):
            call_command(
                "grant_role",
                "viewer",
                "SUPER_ADMIN",
                actor="viewer",
                scope="STATE",
                stdout=StringIO(),
            )

    def test_initial_admin_cannot_be_created_twice(self):
        with self.assertRaises(CommandError):
            call_command("create_initial_admin", stdout=StringIO())

    def test_emergency_admin_updates_are_audited(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            f"/admin/accounts/user/{self.viewer.pk}/change/",
            {
                "username": self.viewer.username,
                "email": self.viewer.email,
                "first_name": "Updated",
                "last_name": "",
                "is_active": "on",
                "is_staff": "on",
                "date_joined_0": "2026-09-28",
                "date_joined_1": "12:00:00",
                "preferred_language": "en",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.viewer.refresh_from_db()
        self.assertTrue(self.viewer.is_staff)
        event = AuditLog.objects.get(action="account.updated")
        self.assertEqual(event.old_values["is_staff"], False)
        self.assertEqual(event.new_values["is_staff"], True)

    def test_admin_cannot_delete_accounts(self):
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.post(
                f"/admin/accounts/user/{self.viewer.pk}/delete/", {"post": "yes"}
            ).status_code,
            403,
        )
        self.assertTrue(User.objects.filter(pk=self.viewer.pk).exists())

    def test_emergency_admin_can_create_staff_account(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/admin/accounts/user/add/").status_code, 200)
        response = self.client.post(
            "/admin/accounts/user/add/",
            {
                "username": "new-staff",
                "email": "NewStaff@Example.org",
                "password1": "New-staff-password-912!",
                "password2": "New-staff-password-912!",
            },
        )
        self.assertEqual(response.status_code, 302)
        account = User.objects.get(username="new-staff")
        self.assertEqual(account.email, "newstaff@example.org")
        self.assertFalse(can(account, "dashboard.view"))
        self.assertTrue(
            AuditLog.objects.filter(action="account.created", entity_id=str(account.pk)).exists()
        )

    def test_case_variant_duplicate_email_is_form_error(self):
        from apps.accounts.admin import CustomUserCreationForm

        form = CustomUserCreationForm(
            data={
                "username": "duplicate",
                "email": "VIEWER@EXAMPLE.ORG",
                "password1": "New-staff-password-912!",
                "password2": "New-staff-password-912!",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
