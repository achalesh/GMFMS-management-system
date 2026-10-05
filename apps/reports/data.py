from collections import Counter
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.accounts.policies import scope_queryset, scopes_for
from apps.facilitators.models import FacilitatorAppointment
from apps.facilitators.selectors import locations_for, registry_for
from apps.registrations.review_selectors import applications_for
from apps.verification.projection import authorization_status

PENDING = {"SUBMITTED", "UNDER_REVIEW", "CORRECTION_REQUIRED"}
LIMIT = 10000


def export_allowed(user):
    return bool(user.is_active and (user.is_superuser or scopes_for(user, "reports.export")))


def snapshot(user, filters, export=False):
    capability = "reports.export" if export else "dashboard.view"
    places = locations_for(user, capability).filter(
        active=True,
        block__active=True,
        block__district__active=True,
        block__district__state__active=True,
    )
    for key, field in [
        ("district", "block__district_id"),
        ("block", "block_id"),
        ("panchayat", "pk"),
    ]:
        if filters.get(key):
            places = places.filter(**{field: filters[key].pk})
    places = list(places.order_by("block__district__name_en", "block__name_en", "name_en"))
    ids = [p.pk for p in places]
    fs = (
        registry_for(user)
        .filter(current_appointment__panchayat_id__in=ids)
        .select_related("current_appointment__panchayat__block__district__state")
    )
    apps = (
        applications_for(user)
        .filter(panchayat_id__in=ids)
        .select_related("panchayat__block__district")
    )
    if fs.count() > LIMIT or apps.count() > LIMIT:
        raise ValidationError("More than 10,000 records. Narrow the location filters.")
    fs = list(fs)
    apps = list(apps)
    for f in fs:
        f.report_status = authorization_status(f)
    return places, fs, apps


def summarize(places, fs, apps):
    today = timezone.localdate()
    active = [f for f in fs if f.report_status == "ACTIVE"]
    covered = {
        f.current_appointment.panchayat_id
        for f in active
        if f.current_appointment.role == "PRIMARY"
    }
    statuses = Counter(f.report_status for f in fs)
    return dict(
        panchayats=len(places),
        blocks=len({p.block_id for p in places}),
        applications=len(apps),
        under_review=sum(a.status == "UNDER_REVIEW" for a in apps),
        pending=sum(a.status in PENDING for a in apps),
        approved=len(fs),
        active=len(active),
        covered=len(covered),
        vacant=len(places) - len(covered),
        suspended=statuses["SUSPENDED"],
        expired=statuses["EXPIRED"],
        expiring=sum(
            min(f.valid_until, f.current_appointment.effective_to or f.valid_until)
            <= today + timedelta(days=30)
            for f in active
        ),
        coverage=round(100 * len(covered) / len(places), 1) if places else 0,
    )


def progress(places, fs, apps, level):
    # Group once in memory after joined, permission-scoped queries; no per-row DB queries.
    groups = {}
    for p in places:
        obj = p.block.district if level == "district" else p.block if level == "block" else p
        groups.setdefault(obj.pk, {"object": obj, "places": [], "fs": [], "apps": []})[
            "places"
        ].append(p)
    lookup = {p.pk: key for key, g in groups.items() for p in g["places"]}
    for f in fs:
        groups[lookup[f.current_appointment.panchayat_id]]["fs"].append(f)
    for a in apps:
        groups[lookup[a.panchayat_id]]["apps"].append(a)
    return [
        dict(object=g["object"], **summarize(g["places"], g["fs"], g["apps"]))
        for g in groups.values()
    ]


def date_matches(value, filters):
    return (
        value is not None
        and (not filters.get("start") or value >= filters["start"])
        and (not filters.get("end") or value <= filters["end"])
    )


def report_data(user, filters, export=False):
    if export and not export_allowed(user):
        raise PermissionDenied
    places, fs, apps = snapshot(user, filters, export)
    kind = filters.get("report") or "coverage"
    if kind in {"applications", "progress", "skills", "equipment"} and not (
        user.is_superuser or scopes_for(user, "applications.view")
    ):
        raise PermissionDenied
    if kind == "history":
        capability = "reports.export" if export else "facilitators.view"
        qs = (
            scope_queryset(
                user,
                FacilitatorAppointment.objects.select_related(
                    "facilitator__application", "panchayat__block__district"
                ),
                capability,
                district_field="panchayat__block__district__district_code",
                block_field="panchayat__block__block_code",
            )
            .filter(panchayat_id__in=[p.pk for p in places])
            .order_by("-effective_from", "pk")
        )
        if filters.get("role"):
            qs = qs.filter(role=filters["role"])
        if filters.get("status"):
            qs = qs.filter(status=filters["status"])
        date_field = {
            "registration": "facilitator__application__submitted_at__date",
            "approval": "approved_at__date",
            "expiry": "effective_to",
        }[filters.get("date_field") or "registration"]
        if filters.get("start"):
            qs = qs.filter(**{date_field + "__gte": filters["start"]})
        if filters.get("end"):
            qs = qs.filter(**{date_field + "__lte": filters["end"]})
        if qs.count() > LIMIT:
            raise ValidationError("More than 10,000 appointments. Narrow filters.")
        headers = [
            "Facilitator ID",
            "Name",
            "District",
            "Block",
            "Panchayat",
            "Role",
            "Recorded status",
            "Effective from",
            "Effective to",
            "Ended",
        ]
        rows = [
            [
                a.facilitator.facilitator_number,
                a.facilitator.full_name,
                a.panchayat.block.district.name_en,
                a.panchayat.block.name_en,
                a.panchayat.name_en,
                a.role,
                a.status,
                a.effective_from.isoformat(),
                a.effective_to.isoformat() if a.effective_to else "",
                timezone.localtime(a.ended_at).date().isoformat() if a.ended_at else "",
            ]
            for a in qs
        ]
    elif kind in {"coverage", "vacancies"}:
        headers = [
            "District",
            "Block",
            "Panchayat",
            "SEC code",
            "Active",
            "Pending",
            "Covered",
            "Vacant",
        ]
        rows = []
        for g in progress(places, fs, apps, "panchayat"):
            p = g["object"]
            if kind == "vacancies" and not g["vacant"]:
                continue
            rows.append(
                [
                    p.block.district.name_en,
                    p.block.name_en,
                    p.name_en,
                    p.sec_local_body_code,
                    g["active"],
                    g["pending"],
                    g["covered"],
                    g["vacant"],
                ]
            )
    elif kind in {"applications", "progress"}:
        headers = [
            "Application number",
            "Name",
            "District",
            "Block",
            "Panchayat",
            "Status",
            "Registered",
        ]
        rows = []
        for a in apps:
            if filters.get("status") == "PENDING":
                if a.status not in PENDING:
                    continue
            elif filters.get("status") and a.status != filters["status"]:
                continue
            if not date_matches(timezone.localtime(a.submitted_at).date(), filters):
                continue
            p = a.panchayat
            rows.append(
                [
                    a.application_number,
                    a.full_name,
                    p.block.district.name_en,
                    p.block.name_en,
                    p.name_en,
                    a.status,
                    timezone.localtime(a.submitted_at).date().isoformat(),
                ]
            )
        if kind == "progress":
            counts = Counter((r[-1][:7], r[-2]) for r in rows)
            headers = ["Registration month", "Current application status", "Applications"]
            rows = [[month, status, count] for (month, status), count in sorted(counts.items())]
    else:
        headers = [
            "Facilitator ID",
            "Name",
            "District",
            "Block",
            "Panchayat",
            "Role",
            "Status",
            "Registered",
            "Approved",
            "Valid until",
            "Mobile",
        ]
        rows = []
        contact_ids = set(locations_for(user, "contacts.view").values_list("pk", flat=True))
        for f in fs:
            a = f.current_appointment
            p = a.panchayat
            expiry = min(f.valid_until, a.effective_to or f.valid_until)
            if filters.get("status") and f.report_status != filters["status"]:
                continue
            if filters.get("role") and a.role != filters["role"]:
                continue
            if kind == "expiring" and (
                f.report_status != "ACTIVE" or expiry > timezone.localdate() + timedelta(days=30)
            ):
                continue
            dates = {
                "registration": timezone.localtime(f.application.submitted_at).date(),
                "approval": timezone.localtime(f.approved_at).date(),
                "expiry": expiry,
            }
            if not date_matches(dates[filters.get("date_field") or "registration"], filters):
                continue
            contact = p.pk in contact_ids
            rows.append(
                [
                    f.facilitator_number,
                    f.full_name,
                    p.block.district.name_en,
                    p.block.name_en,
                    p.name_en,
                    a.role,
                    f.report_status,
                    dates["registration"].isoformat(),
                    dates["approval"].isoformat(),
                    expiry.isoformat(),
                    f.application.mobile if contact else "Restricted",
                ]
            )
    if kind in {"skills", "equipment"}:
        visible_app_ids = {a.pk for a in apps}
        visible = {f.facilitator_number: f for f in fs if f.application_id in visible_app_ids}
        from django.db.models import prefetch_related_objects

        prefetch_related_objects([f.application for f in visible.values()], kind)
        headers = headers[:7] + [kind.title()]
        rows = [
            row[:7]
            + [
                ", ".join(str(item) for item in getattr(visible[row[0]].application, kind).all())
                or "Not provided"
            ]
            for row in rows
            if row[0] in visible
        ]
    if kind in {"coverage", "vacancies"} and not (
        user.is_superuser or scopes_for(user, "applications.view")
    ):
        for row in rows:
            row[5] = "Restricted"
    return headers, rows
