from ipaddress import ip_network
from pathlib import Path

from django.conf import settings
from django.core.checks import Error, register


@register(deploy=True)
def storage_and_browser_checks(app_configs, **kwargs):
    errors = []
    media = Path(settings.MEDIA_ROOT).resolve()
    public_roots = [Path(settings.STATIC_ROOT).resolve()] + [
        Path(p).resolve() for p in settings.STATICFILES_DIRS
    ]
    if any(
        media == root or media.is_relative_to(root) or root.is_relative_to(media)
        for root in public_roots
    ):
        errors.append(
            Error("Private media and public static roots must not overlap.", id="gmfms.E001")
        )
    if not settings.SESSION_COOKIE_HTTPONLY:
        errors.append(Error("Session cookies must be HttpOnly.", id="gmfms.E002"))
    if settings.CORS_ALLOW_ALL_ORIGINS:
        errors.append(Error("Wildcard CORS is not permitted.", id="gmfms.E003"))
    if any(not origin.startswith("https://") for origin in settings.CSRF_TRUSTED_ORIGINS):
        errors.append(Error("Production CSRF trusted origins must use HTTPS.", id="gmfms.E004"))
    try:
        if any(ip_network(cidr).prefixlen == 0 for cidr in settings.TRUSTED_PROXY_CIDRS):
            raise ValueError("Wildcard proxy network")
    except ValueError:
        errors.append(
            Error(
                "Trusted proxy CIDRs must be valid, explicit networks; /0 is forbidden.",
                id="gmfms.E005",
            )
        )
    return errors
