from ipaddress import ip_address, ip_network

from django.conf import settings


def client_ip(request):
    peer = request.META.get("REMOTE_ADDR")
    try:
        address = ip_address(peer)
        trusted = any(
            address in ip_network(cidr) for cidr in getattr(settings, "TRUSTED_PROXY_CIDRS", [])
        )
        if trusted and request.META.get("HTTP_X_REAL_IP"):
            return str(ip_address(request.META["HTTP_X_REAL_IP"]))
    except ValueError:
        pass
    return peer
