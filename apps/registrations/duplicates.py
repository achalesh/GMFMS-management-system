from difflib import SequenceMatcher

from django.db.models import Q

from .models import Application, DuplicateWarning


def find_duplicates(application):
    exact = Q(mobile=application.mobile) | Q(panchayat_id=application.panchayat_id)
    if application.email:
        exact |= Q(email__iexact=application.email)
    if application.normalized_name:
        exact |= Q(normalized_name__startswith=application.normalized_name[:4])
    matches = []
    for other in (
        Application.objects.exclude(pk=application.pk)
        .filter(exact)
        .select_related("panchayat__block__district")
        .iterator()
    ):
        reasons = []
        if application.mobile == other.mobile:
            reasons.append("same_mobile")
        if application.email and application.email.lower() == other.email.lower():
            reasons.append("same_email")
        if application.panchayat_id == other.panchayat_id:
            reasons.append("same_panchayat")
        if (
            application.normalized_name
            and SequenceMatcher(None, application.normalized_name, other.normalized_name).ratio()
            >= 0.85
        ):
            reasons.append("similar_name")
        if reasons:
            matches.append((other, reasons))
    return matches


def refresh_warnings(application):
    matches = find_duplicates(application)
    application.duplicate_warnings.all().delete()
    DuplicateWarning.objects.bulk_create(
        [
            DuplicateWarning(application=application, other_application=other, reasons=reasons)
            for other, reasons in matches
        ]
    )
    return matches
