from datetime import datetime, timezone
from functools import wraps

from django.db.models import F
from django.http import HttpResponse
from django.utils.crypto import salted_hmac

from apps.accounts.models import RequestBudget
from apps.accounts.security import client_ip


def consume_budget(request, category, limit, window=3600, *, identity=None):
    now = datetime.now(timezone.utc)
    bucket = int(now.timestamp()) // window
    principal = identity if identity is not None else client_ip(request) or "unknown"
    key = salted_hmac(
        "registration-budget",
        f"{category}:{principal}:{bucket}",
        algorithm="sha256",
    ).hexdigest()
    RequestBudget.objects.get_or_create(
        key=key,
        defaults={"expires_at": datetime.fromtimestamp((bucket + 1) * window, timezone.utc)},
    )
    return RequestBudget.objects.filter(pk=key, hits__lt=limit).update(hits=F("hits") + 1) == 1


def post_budget(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method == "POST" and not consume_budget(request, "steps", 120):
            response = HttpResponse(
                "Too many registration requests. Please try again later.", status=429
            )
            response["Retry-After"] = "3600"
            return response
        return view(request, *args, **kwargs)

    return wrapped


def staff_budget(category, limit):
    """Account-scoped expensive-operation budget: changing IP must not bypass it."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method == "POST" and request.user.is_authenticated:
                if not consume_budget(
                    request, category, limit, identity="user:" + str(request.user.pk)
                ):
                    response = HttpResponse(
                        "Too many requests. Please try again in an hour.", status=429
                    )
                    response["Retry-After"] = "3600"
                    return response
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
