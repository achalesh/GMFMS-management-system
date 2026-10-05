from django.core.paginator import Paginator
from django.shortcuts import render

from apps.accounts.policies import require_capability

from .models import AuditLog


@require_capability("audit.view")
def index(request):
    events = AuditLog.objects.select_related("user")
    return render(
        request,
        "audit/index.html",
        {"page": Paginator(events, 25).get_page(request.GET.get("page"))},
    )
