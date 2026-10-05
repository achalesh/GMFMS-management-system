from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin


class BrowserSecurityMiddleware(MiddlewareMixin):
    """Protect custom pages and reject truncated multipart bodies before any view runs."""

    def process_view(self, request, view, args, kwargs):
        if request.method == "POST" and request.content_type == "multipart/form-data":
            # StopUpload otherwise leaves earlier, valid-looking partial files in request.FILES.
            request.POST
            if getattr(request, "registration_upload_rejected", False):
                return HttpResponse("Upload limit exceeded. Choose smaller files.", status=413)

    def process_response(self, request, response):
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("X-Frame-Options", "DENY")
        response.setdefault("Referrer-Policy", "same-origin")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # Django admin and Swagger maintain their own script requirements. Public verification
        # and private file responses already provide stricter policies, preserved by setdefault.
        if not request.path.startswith(("/admin/", "/api/docs/")):
            response.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
            )
        return response


class TrustedProxyMiddleware:
    """Normalize only headers from explicitly trusted direct peers before throttling."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from apps.accounts.security import client_ip

        address = client_ip(request)
        if address:
            request.META["REMOTE_ADDR"] = address
        # Downstream code must not reinterpret a client-supplied proxy chain.
        request.META.pop("HTTP_X_FORWARDED_FOR", None)
        request.META.pop("HTTP_X_REAL_IP", None)
        return self.get_response(request)
