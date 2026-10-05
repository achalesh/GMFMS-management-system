import csv
import io
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase
from openpyxl import Workbook

from apps.accounts.models import UserJurisdiction
from apps.accounts.policies import can
from apps.accounts.services import grant_role
from apps.audit.models import AuditLog
from apps.locations.importing import COLUMNS, import_locations, parse_file
from apps.locations.models import Block, District, GramaPanchayat, LocationImport, State
from apps.locations.services import update_location
from tests.factories import user_with_role


def row(**changes):
    values = dict.fromkeys(COLUMNS, "")
    values.update(
        state_code="KL",
        state_name_en="Kerala",
        district_code="TVM",
        district_name_en="Thiruvananthapuram",
        district_order="1",
        block_code="B01001",
        block_name_en="Test Block",
        sec_local_body_code="G01001",
        panchayat_name_en="Test Panchayat",
        active="true",
    )
    values.update(changes)
    return values


def upload(*rows):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(rows or [row()])
    return SimpleUploadedFile("locations.csv", buffer.getvalue().encode())


def run_import(file=None, **options):
    rows, digest = parse_file(file or upload())
    return import_locations(rows=rows, sha256=digest, source="Test source", system=True, **options)


class ImportTests(TestCase):
    def test_csv_creates_normalized_hierarchy_and_audit(self):
        summary = run_import()
        gp = GramaPanchayat.objects.get()
        self.assertEqual(gp.district.district_code, "TVM")
        self.assertEqual(gp.block.district.state.code, "KL")
        self.assertEqual(
            summary["created"], dict.fromkeys(["state", "district", "block", "gramapanchayat"], 1)
        )
        self.assertEqual(LocationImport.objects.count(), 1)
        self.assertTrue(AuditLog.objects.filter(action="locations.imported").exists())

    def test_idempotent_import(self):
        run_import()
        result = run_import()
        self.assertEqual(sum(result["created"].values()), 0)
        self.assertEqual(GramaPanchayat.objects.count(), 1)

    def test_dry_run_rolls_back_records_history_and_audit(self):
        before = AuditLog.objects.count()
        self.assertEqual(run_import(dry_run=True)["created"]["gramapanchayat"], 1)
        self.assertFalse(State.objects.exists())
        self.assertFalse(LocationImport.objects.exists())
        self.assertEqual(AuditLog.objects.count(), before)

    def test_late_invalid_email_rolls_back_entire_batch(self):
        with self.assertRaises(ValidationError):
            run_import(upload(row(), row(sec_local_body_code="G01002", official_email="invalid")))
        self.assertFalse(State.objects.exists())
        self.assertFalse(LocationImport.objects.exists())

    def test_audit_failure_rolls_back_import(self):
        with patch(
            "apps.locations.importing.record_event", side_effect=RuntimeError("audit unavailable")
        ):
            with self.assertRaises(RuntimeError):
                run_import()
        self.assertFalse(State.objects.exists())
        self.assertFalse(LocationImport.objects.exists())

    def test_updates_require_opt_in_and_record_changes(self):
        run_import()
        changed = row(panchayat_name_en="Updated Panchayat")
        with self.assertRaises(ValidationError):
            run_import(upload(changed))
        result = run_import(upload(changed), update_existing=True)
        self.assertEqual(GramaPanchayat.objects.get().name_en, "Updated Panchayat")
        self.assertEqual(result["updated"]["gramapanchayat"], 1)
        self.assertEqual(result["changes"][0]["old"]["name_en"], "Test Panchayat")

    def test_import_cannot_reparent_existing_panchayat(self):
        run_import()
        with self.assertRaises(ValidationError):
            run_import(
                upload(row(block_code="B01002", block_name_en="Other Block")), update_existing=True
            )
        self.assertEqual(Block.objects.count(), 1)

    def test_import_cannot_reparent_existing_block(self):
        run_import()
        with self.assertRaises(ValidationError):
            run_import(
                upload(row(district_code="KLM", district_name_en="Kollam")), update_existing=True
            )
        self.assertEqual(District.objects.count(), 1)

    def test_duplicate_codes_and_conflicting_parents_rejected(self):
        for values in [
            [row(), row()],
            [row(), row(sec_local_body_code="G01002", block_name_en="Conflicting")],
            [row(active="maybe")],
            [row(district_order="not an integer")],
            [row(state_code="")],
        ]:
            with self.subTest(values=values), self.assertRaises(ValidationError):
                parse_file(upload(*values))

    def test_invalid_headers_encoding_and_format_rejected(self):
        for name, data in [
            ("x.csv", b"state_code,state_code\nKL,KL"),
            ("x.csv", b"unknown\nvalue"),
            ("x.csv", b"\xff"),
            ("x.xlsx", b"not a zip"),
            ("x.xls", b"unsupported"),
            ("x.csv", b""),
        ]:
            with self.subTest(name=name, data=data), self.assertRaises(ValidationError):
                parse_file(SimpleUploadedFile(name, data))

    def test_upload_size_is_bounded(self):
        with patch("apps.locations.importing.MAX_BYTES", 10):
            with self.assertRaises(ValidationError):
                parse_file(upload())

    def test_xlsx_accepts_values_rejects_formulas_and_extra_sheets(self):
        book = Workbook()
        sheet = book.active
        sheet.append(COLUMNS)
        sheet.append(list(row().values()))

        def as_file():
            buffer = io.BytesIO()
            book.save(buffer)
            return SimpleUploadedFile("locations.xlsx", buffer.getvalue())

        self.assertEqual(len(parse_file(as_file())[0]), 1)
        sheet["A2"] = '=CONCAT("K","L")'
        with self.assertRaisesMessage(ValidationError, "Formulas"):
            parse_file(as_file())
        sheet["A2"] = "KL"
        book.create_sheet("Other")
        with self.assertRaisesMessage(ValidationError, "exactly one sheet"):
            parse_file(as_file())

    def test_no_actor_cannot_import_without_explicit_system_context(self):
        rows, digest = parse_file(upload())
        with self.assertRaises(PermissionDenied):
            import_locations(rows=rows, sha256=digest, source="Test")

    def test_source_required(self):
        rows, digest = parse_file(upload())
        for source in ["", "a" * 501]:
            with self.assertRaises(ValidationError):
                import_locations(rows=rows, sha256=digest, source=source, system=True)

    def test_parent_delete_is_protected(self):
        run_import()
        for model in [State, District, Block]:
            with self.assertRaises(ProtectedError):
                model.objects.get().delete()


class LocationAccessTests(TestCase):
    def setUp(self):
        cache.clear()
        run_import(
            upload(
                row(),
                row(
                    sec_local_body_code="G01002", block_code="B01002", block_name_en="Second Block"
                ),
                row(
                    sec_local_body_code="G02001",
                    block_code="B02001",
                    block_name_en="Kollam Block",
                    district_code="KLM",
                    district_name_en="Kollam",
                    district_order="2",
                ),
            )
        )
        self.gp = GramaPanchayat.objects.get(sec_local_body_code="G01001")
        self.block = self.gp.block
        self.district = self.gp.district
        self.other = GramaPanchayat.objects.get(sec_local_body_code="G02001")
        self.admin = user_with_role("manager", "SUPER_ADMIN")
        self.viewer = user_with_role("viewer")
        self.regional = user_with_role("district", "DISTRICT_ADMIN", "DISTRICT", "TVM")
        self.coordinator = user_with_role("block", "BLOCK_COORDINATOR", "BLOCK", "TVM", "B01001")

    def test_public_dependent_api_uses_database_and_excludes_contacts(self):
        response = self.client.get("/api/v1/districts/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        response = self.client.get("/api/v1/blocks/", {"district": self.district.pk})
        self.assertEqual(response.json()["count"], 2)
        response = self.client.get("/api/v1/panchayats/", {"block": self.block.pk})
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["district"], self.district.pk)
        self.assertNotIn("official_email", response.json()["results"][0])
        self.assertNotIn("office_phone", response.json()["results"][0])

    def test_api_requires_valid_parent_and_rejects_writes(self):
        for value in ["", "-1", "0", "abc", "²", "9" * 100]:
            with self.subTest(value=value):
                self.assertEqual(
                    self.client.get("/api/v1/blocks/", {"district": value}).status_code, 400
                )
        self.assertEqual(self.client.get("/api/v1/panchayats/").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/blocks/?district=999999").json()["count"], 0)
        self.assertEqual(self.client.post("/api/v1/districts/", {}).status_code, 405)

    def test_inactive_ancestor_hides_public_descendants(self):
        for obj in [self.gp, self.block, self.district, self.district.state]:
            obj.active = False
            obj.save()
            self.assertEqual(
                self.client.get("/api/v1/panchayats/", {"block": self.block.pk}).json()["count"], 0
            )
            obj.active = True
            obj.save()

    def test_anonymous_staff_screen_redirects(self):
        self.assertEqual(self.client.get("/locations/").status_code, 302)

    def test_district_staff_cannot_access_other_district(self):
        self.client.force_login(self.regional)
        response = self.client.get("/locations/")
        self.assertEqual(response.context["panchayat_count"], 2)
        for path in [
            f"/locations/districts/{self.other.district_id}/",
            f"/locations/blocks/{self.other.block_id}/",
            f"/locations/panchayats/{self.other.pk}/",
        ]:
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(
            self.client.get(
                "/locations/options/blocks/", {"district": self.other.district_id}
            ).json()["results"],
            [],
        )

    def test_block_detail_renders_location_and_parent_link(self):
        self.client.force_login(self.coordinator)
        response = self.client.get(f"/locations/blocks/{self.block.pk}/")
        self.assertContains(response, self.block.name_en)
        self.assertContains(response, f"/locations/districts/{self.district.pk}/")
        self.assertContains(response, self.gp.name_en)

    def test_block_staff_sees_only_assigned_block(self):
        self.client.force_login(self.coordinator)
        response = self.client.get("/locations/")
        self.assertEqual(response.context["panchayat_count"], 1)
        self.assertEqual(response.context["block_count"], 1)
        sibling = Block.objects.get(block_code="B01002")
        self.assertEqual(self.client.get(f"/locations/blocks/{sibling.pk}/").status_code, 404)
        detail = self.client.get(f"/locations/districts/{self.district.pk}/")
        self.assertEqual(
            list(detail.context["blocks"].values_list("pk", flat=True)), [self.block.pk]
        )

    def test_viewer_cannot_edit_or_import(self):
        self.client.force_login(self.viewer)
        for path in [
            "/locations/import/",
            f"/locations/edit/panchayat/{self.gp.pk}/",
            "/locations/import/template/",
        ]:
            self.assertEqual(self.client.get(path).status_code, 403)

    def test_directory_search_and_invalid_filters(self):
        self.client.force_login(self.regional)
        self.assertEqual(
            self.client.get("/locations/panchayats/", {"q": "G01001"})
            .context["page"]
            .paginator.count,
            1,
        )
        for district in ["²", str(self.other.district_id)]:
            self.assertEqual(
                self.client.get("/locations/panchayats/", {"district": district})
                .context["page"]
                .paginator.count,
                0,
            )

    def test_unresolved_or_inactive_scope_fails_closed(self):
        scope = UserJurisdiction.objects.get(assignment__user=self.coordinator)
        scope.block = None
        scope.save()
        self.assertFalse(can(self.coordinator, "locations.view"))
        call_command("resolve_location_jurisdictions", stdout=io.StringIO())
        self.assertTrue(can(self.coordinator, "locations.view"))
        self.block.active = False
        self.block.save()
        self.assertFalse(can(self.coordinator, "locations.view"))

    def test_grant_rejects_unknown_or_wrong_district_block(self):
        for district, block in [("UNKNOWN", "B01001"), ("TVM", "B02001")]:
            with self.assertRaises(ValidationError):
                grant_role(
                    actor=self.admin,
                    user=self.viewer,
                    role_code="BLOCK_COORDINATOR",
                    scope="BLOCK",
                    district_code=district,
                    block_code=block,
                )

    def test_grant_resolves_existing_legacy_assignment(self):
        scope = UserJurisdiction.objects.get(assignment__user=self.coordinator)
        scope.block = None
        scope.district = None
        scope.save()
        grant_role(
            actor=self.admin,
            user=self.coordinator,
            role_code="BLOCK_COORDINATOR",
            scope="BLOCK",
            district_code="TVM",
            block_code="B01001",
        )
        scope.refresh_from_db()
        self.assertEqual(scope.block_id, self.block.pk)

    def test_edit_requires_reason_revision_and_audits(self):
        changed = update_location(
            actor=self.admin,
            model=GramaPanchayat,
            pk=self.gp.pk,
            values={"name_en": "Reviewed name"},
            expected_revision=1,
            reason="Source correction",
        )
        self.assertEqual(changed.revision, 2)
        self.assertTrue(
            AuditLog.objects.filter(action="location.updated", reason="Source correction").exists()
        )
        for revision, reason, values in [
            (1, "Stale", {"name_en": "Old"}),
            (2, "", {"name_en": "No reason"}),
            (2, "Reparent", {"block_id": self.other.block_id}),
        ]:
            with self.assertRaises(ValidationError):
                update_location(
                    actor=self.admin,
                    model=GramaPanchayat,
                    pk=self.gp.pk,
                    values=values,
                    expected_revision=revision,
                    reason=reason,
                )

    def test_edit_audit_failure_rolls_back(self):
        with patch(
            "apps.locations.services.record_event", side_effect=RuntimeError("audit unavailable")
        ):
            with self.assertRaises(RuntimeError):
                update_location(
                    actor=self.admin,
                    model=GramaPanchayat,
                    pk=self.gp.pk,
                    values={"name_en": "Unsaved"},
                    expected_revision=1,
                    reason="Test",
                )
        self.gp.refresh_from_db()
        self.assertEqual(self.gp.name_en, "Test Panchayat")

    def test_import_and_edit_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        for path in ["/locations/import/", f"/locations/edit/panchayat/{self.gp.pk}/"]:
            self.assertEqual(client.post(path, {}).status_code, 403)

    def test_api_pagination(self):
        GramaPanchayat.objects.bulk_create(
            [
                GramaPanchayat(
                    block=self.block, sec_local_body_code=f"TEST{i}", name_en=f"Test {i:03}"
                )
                for i in range(105)
            ]
        )
        first = self.client.get("/api/v1/panchayats/", {"block": self.block.pk}).json()
        self.assertEqual(first["count"], 106)
        self.assertEqual(len(first["results"]), 100)
        second = self.client.get(first["next"]).json()
        self.assertEqual(len(second["results"]), 6)


class BundledSeedTests(TestCase):
    def test_authoritative_snapshot_counts_hierarchy_and_idempotency(self):
        call_command("seed_kerala_locations", stdout=io.StringIO())
        self.assertEqual(State.objects.count(), 1)
        self.assertEqual(District.objects.count(), 14)
        self.assertEqual(Block.objects.count(), 152)
        self.assertEqual(GramaPanchayat.objects.count(), 941)
        gp_counts = [73, 68, 53, 72, 71, 52, 82, 86, 88, 94, 70, 23, 71, 38]
        block_counts = [11, 11, 8, 12, 11, 8, 14, 16, 13, 15, 12, 4, 11, 6]
        for district, gp_count, block_count in zip(
            District.objects.all(), gp_counts, block_counts, strict=True
        ):
            self.assertEqual(district.blocks.count(), block_count)
            self.assertEqual(
                GramaPanchayat.objects.filter(block__district=district).count(), gp_count
            )
        call_command("seed_kerala_locations", stdout=io.StringIO())
        self.assertEqual(GramaPanchayat.objects.count(), 941)
        self.assertEqual(sum(LocationImport.objects.first().summary["created"].values()), 0)

    def test_csv_exists_and_all_rows_have_unique_sec_codes(self):
        with (Path(settings.BASE_DIR) / "data/kerala/locations.csv").open("rb") as source:
            rows, digest = parse_file(source)
        self.assertEqual(len(rows), 941)
        self.assertEqual(len({entry["sec_local_body_code"] for entry in rows}), 941)
        self.assertEqual(len(digest), 64)
