from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import Role, User, UserJurisdiction, UserRole
from apps.accounts.policies import can, scope_queryset
from apps.accounts.services import grant_role, revoke_role
from apps.audit.models import AuditLog

from .factories import assign, user_with_role


class PermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            "root", "root@example.org", "Some-long-password-748!"
        )
        cls.district = user_with_role("district", "DISTRICT_ADMIN", "DISTRICT", "TVM")
        cls.block = user_with_role("block", "BLOCK_COORDINATOR", "BLOCK", "TVM", "B01")
        cls.viewer = user_with_role("viewer")
        cls.operator = user_with_role("operator", "ID_CARD_OPERATOR", "DISTRICT", "KLM")

    def test_roles_are_seeded(self):
        self.assertEqual(Role.objects.count(), 7)

    def test_user_has_uuid_identifier(self):
        self.assertEqual(self.admin.pk.version, 4)

    def test_district_cannot_cross_boundary(self):
        self.assertTrue(can(self.district, "applications.approve", district_code="TVM"))
        self.assertFalse(can(self.district, "applications.approve", district_code="KLM"))
        self.assertFalse(can(self.district, "applications.approve"))
        self.assertFalse(can(self.district, "system.change", district_code="TVM"))

    def test_block_requires_exact_district_and_block(self):
        self.assertTrue(
            can(self.block, "applications.review", district_code="TVM", block_code="B01")
        )
        self.assertFalse(
            can(self.block, "applications.review", district_code="TVM", block_code="B02")
        )
        self.assertFalse(
            can(self.block, "applications.review", district_code="KLM", block_code="B01")
        )
        self.assertFalse(can(self.block, "applications.review", district_code="TVM"))
        self.assertFalse(
            can(self.block, "applications.approve", district_code="TVM", block_code="B01")
        )

    def test_viewer_cannot_edit_or_read_contacts(self):
        for capability in [
            "applications.approve",
            "facilitators.change",
            "organization.change",
            "contacts.view",
            "cards.issue",
        ]:
            self.assertFalse(can(self.viewer, capability))
        self.assertTrue(can(self.viewer, "facilitators.view"))

    def test_card_operator_cannot_approve(self):
        self.assertTrue(can(self.operator, "cards.issue", district_code="KLM"))
        self.assertFalse(can(self.operator, "applications.approve", district_code="KLM"))

    def test_mixed_role_scopes_cannot_leak_write_access(self):
        assign(self.district, "VIEWER", "STATE")
        self.assertTrue(can(self.district, "facilitators.view", district_code="KLM"))
        self.assertFalse(can(self.district, "applications.approve", district_code="KLM"))
        self.assertTrue(can(self.district, "applications.approve", district_code="TVM"))

    def test_unassigned_inactive_and_anonymous_fail_closed(self):
        account = User.objects.create_user("unassigned", "u@example.org")
        UserRole.objects.create(user=account, role=Role.objects.get(code="STATE_ADMIN"))
        self.assertFalse(can(account, "dashboard.view"))
        self.assertFalse(can(AnonymousUser(), "dashboard.view"))
        self.admin.is_active = False
        self.assertFalse(can(self.admin, "system.change"))

    def test_unknown_capability_fails_closed_even_for_superuser(self):
        self.assertFalse(can(self.admin, "typo.permission"))

    def test_query_scope_filters_rows_and_mixed_roles(self):
        all_scopes = UserJurisdiction.objects.all()
        scoped = scope_queryset(self.district, all_scopes, "applications.approve")
        self.assertTrue(scoped.exists())
        self.assertEqual(set(scoped.values_list("district_code", flat=True)), {"TVM"})
        assign(self.district, "VIEWER", "STATE")
        self.assertEqual(
            set(
                scope_queryset(self.district, all_scopes, "applications.approve").values_list(
                    "district_code", flat=True
                )
            ),
            {"TVM"},
        )
        self.assertFalse(scope_queryset(self.viewer, all_scopes, "applications.approve").exists())
        self.assertEqual(
            set(
                scope_queryset(self.block, all_scopes, "applications.review").values_list(
                    "block_code", flat=True
                )
            ),
            {"B01"},
        )

    def test_invalid_scope_assignment_rolls_back(self):
        account = User.objects.create_user("new", "new@example.org")
        with self.assertRaises(ValidationError):
            grant_role(actor=self.admin, user=account, role_code="DISTRICT_ADMIN", scope="STATE")
        self.assertFalse(account.role_assignments.exists())
        self.assertFalse(AuditLog.objects.filter(action="permissions.granted").exists())

    def test_grant_and_revoke_are_audited(self):
        assignment, created = grant_role(
            actor=self.admin,
            user=self.viewer,
            role_code="REVIEWER",
            scope="DISTRICT",
            district_code="TVM",
        )
        self.assertTrue(created)
        self.assertTrue(can(self.viewer, "applications.review", district_code="TVM"))
        revoke_role(actor=self.admin, assignment=assignment, reason="Assignment ended")
        self.assertFalse(can(self.viewer, "applications.review", district_code="TVM"))
        self.assertEqual(AuditLog.objects.filter(action__startswith="permissions.").count(), 2)

    def test_unauthorized_actor_cannot_grant(self):
        with self.assertRaises(PermissionDenied):
            grant_role(actor=self.viewer, user=self.viewer, role_code="SUPER_ADMIN", scope="STATE")

    def test_malformed_direct_write_fails_closed(self):
        assignment = self.district.role_assignments.get()
        UserJurisdiction.objects.create(assignment=assignment, scope="STATE")
        self.assertFalse(can(self.district, "applications.approve", district_code="KLM"))

    def test_scope_shape_is_database_constrained(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            UserJurisdiction.objects.create(
                assignment=self.district.role_assignments.get(), scope="BLOCK", district_code="TVM"
            )

    def test_viewer_and_district_cannot_open_restricted_urls(self):
        for user in [self.viewer, self.district, self.block, self.operator]:
            self.client.force_login(user)
            for path in [
                "/settings/organization/",
                "/settings/system/",
                "/accounts/users/",
                "/audit/",
            ]:
                with self.subTest(user=user.username, path=path):
                    self.assertEqual(self.client.get(path).status_code, 403)
                    self.assertEqual(self.client.post(path, {}).status_code, 403)

    def test_regular_staff_cannot_access_emergency_admin(self):
        self.viewer.is_staff = True
        self.viewer.save()
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_no_role_account_can_inspect_own_access_but_not_dashboard(self):
        account = User.objects.create_user("pending", "pending@example.org")
        self.client.force_login(account)
        self.assertEqual(self.client.get("/").status_code, 403)
        self.assertEqual(self.client.get("/profile/").status_code, 200)

    def test_superuser_can_use_every_foundation_page(self):
        self.client.force_login(self.admin)
        for path in [
            "/",
            "/profile/",
            "/settings/organization/",
            "/settings/system/",
            "/accounts/users/",
            "/audit/",
            "/admin/",
        ]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
