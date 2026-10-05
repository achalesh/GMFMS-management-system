from datetime import datetime, timezone

from django.db.models import F
from django.shortcuts import render
from django.utils.crypto import salted_hmac

from .models import RequestBudget
from .security import client_ip


def consume_reset_budget(request, *, limit=5, window_seconds=900):
    now = datetime.now(timezone.utc)
    bucket = int(now.timestamp()) // window_seconds
    identity = client_ip(request) or "unknown"
    key = salted_hmac(
        "password-reset-throttle", f"{identity}:{bucket}", algorithm="sha256"
    ).hexdigest()
    RequestBudget.objects.get_or_create(
        key=key,
        defaults={
            "expires_at": datetime.fromtimestamp((bucket + 1) * window_seconds, timezone.utc)
        },
    )
    return RequestBudget.objects.filter(pk=key, hits__lt=limit).update(hits=F("hits") + 1) == 1


class PasswordResetThrottleMixin:
    def post(self, request, *args, **kwargs):
        if not consume_reset_budget(request):
            response = render(request, "errors/429.html", status=429)
            response["Retry-After"] = "900"
            return response
        return super().post(request, *args, **kwargs)
