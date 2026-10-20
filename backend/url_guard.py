"""
Outbound URL validation (anti-SSRF).

Company administrators can configure webhook URLs that the server will POST to.
In a multi-tenant SaaS this is an SSRF vector: an admin could point the
webhook at internal services (e.g. cloud metadata endpoints, the database, or
the API itself). This module validates scheme and destination before any
outbound request is made.
"""
import ipaddress
import logging
import socket
from urllib.parse import urlparse

from config import settings

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = ("http", "https")


class UnsafeOutboundURL(ValueError):
    """Raised when a URL is not allowed as an outbound target."""


def _host_is_private(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        # Unresolvable hosts are rejected too (fail-closed)
        return True
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return True
    return False


def validate_outbound_url(url: str, context: str = "webhook") -> str:
    """
    Validate that `url` is safe to call from the server.

    Rules:
      - Must be http(s)
      - Host must not resolve to private/loopback/link-local/reserved addresses
        (unless settings.DEBUG allows it, for local development)
      - No credentials embedded in the URL

    Returns the (unchanged) URL if safe; raises UnsafeOutboundURL otherwise.
    """
    if not url or not str(url).strip():
        raise UnsafeOutboundURL("URL vacía")

    url = str(url).strip()
    try:
        parsed = urlparse(url)
    except ValueError as e:
        raise UnsafeOutboundURL(f"URL malformada: {e}")

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeOutboundURL(
            f"Esquema no permitido '{parsed.scheme}'. Use http o https."
        )

    host = parsed.hostname
    if not host:
        raise UnsafeOutboundURL("La URL no incluye un host válido")

    if parsed.username or parsed.password:
        raise UnsafeOutboundURL("No se permiten credenciales embebidas en la URL")

    if settings.DEBUG:
        # Local development: allow anything that resolves
        return url

    if _host_is_private(host):
        logger.warning("[url_guard] URL %s rechazada (host privado/interno) [%s]", host, context)
        raise UnsafeOutboundURL(
            "No se permiten webhooks hacia redes internas o privadas. Configure una URL pública (https recomendado)."
        )
    return url


__all__ = ["validate_outbound_url", "UnsafeOutboundURL"]
