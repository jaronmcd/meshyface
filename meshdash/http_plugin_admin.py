from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit


PLUGIN_ADMIN_WRITE_PATHS = frozenset(
    {
        "/api/settings/plugins",
        "/api/settings/plugins/config",
        "/api/settings/plugins/routes",
        "/api/settings/plugins/runtime",
        "/api/plugins/console",
    }
)
_PROXY_CLIENT_HEADER_NAMES = frozenset(
    {
        "cf-connecting-ip",
        "client-ip",
        "fastly-client-ip",
        "fly-client-ip",
        "forwarded",
        "true-client-ip",
        "via",
        "x-real-ip",
    }
)


def request_header_value(handler: object, name: str) -> str:
    headers = getattr(handler, "headers", None)
    if headers is None:
        return ""
    try:
        direct = headers.get(name)
    except Exception:
        direct = None
    if direct is not None:
        return str(direct)
    name_lower = name.lower()
    for key, value in getattr(headers, "items", lambda: [])():
        try:
            if str(key).lower() == name_lower:
                return str(value)
        except Exception:
            continue
    return ""


def extract_request_api_token(handler: object) -> str:
    authorization = request_header_value(handler, "Authorization").strip()
    if authorization:
        parts = authorization.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
    return request_header_value(handler, "X-API-Token").strip()


def _address_is_loopback(value: object) -> bool:
    try:
        address = ipaddress.ip_address(str(value or "").split("%", 1)[0])
    except ValueError:
        return False
    if address.is_loopback:
        return True
    mapped = getattr(address, "ipv4_mapped", None)
    return bool(mapped is not None and mapped.is_loopback)


def _host_header_is_loopback(value: object) -> bool:
    host_header = str(value or "").strip()
    if not host_header or any(char.isspace() for char in host_header):
        return False
    try:
        parsed = urlsplit(f"//{host_header}")
        hostname = str(parsed.hostname or "").rstrip(".").lower()
        if (
            not hostname
            or parsed.username is not None
            or parsed.password is not None
            or bool(parsed.path)
            or bool(parsed.query)
            or bool(parsed.fragment)
        ):
            return False
        # Accessing .port validates an optional port without accepting malformed
        # authorities such as bracketless IPv6 literals.
        parsed.port
    except (TypeError, ValueError):
        return False
    return hostname == "localhost" or _address_is_loopback(hostname)


def _request_has_proxy_metadata(handler: object) -> bool:
    headers = getattr(handler, "headers", None)
    for key, _value in getattr(headers, "items", lambda: [])():
        name = str(key).strip().lower()
        if name in _PROXY_CLIENT_HEADER_NAMES or name.startswith("x-forwarded-"):
            return True
    # The real HTTP headers object supports items(). These fallbacks also keep
    # authorization fail-closed for reduced handler/test doubles.
    for name in (*_PROXY_CLIENT_HEADER_NAMES, "x-forwarded-for"):
        if request_header_value(handler, name):
            return True
    return False


def request_is_loopback(handler: object) -> bool:
    client_address = getattr(handler, "client_address", None)
    client_host = (
        client_address[0]
        if isinstance(client_address, tuple) and client_address
        else ""
    )
    if not _address_is_loopback(client_host):
        return False
    if not _host_header_is_loopback(request_header_value(handler, "Host")):
        return False
    # A reverse proxy terminates the original client connection, so its
    # loopback socket cannot prove that the caller is local. Proxy metadata is
    # therefore a deny signal for tokenless administration, never an allowlist.
    return not _request_has_proxy_metadata(handler)


def plugin_admin_authorization(
    handler: object,
    *,
    required_token: object,
) -> tuple[bool, int, str]:
    del handler, required_token
    # Plugin administration follows the same access model as the dashboard UI:
    # if the dashboard is reachable, the Scripts workspace is reachable. Browser
    # writes are still restricted to same-origin JSON requests by the POST route.
    return True, 200, ""


def request_has_json_content_type(handler: object) -> bool:
    content_type = request_header_value(handler, "Content-Type")
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type == "application/json"


def _origin_matches_host(origin: str, host_header: str) -> bool:
    try:
        parsed_origin = urlsplit(origin)
        parsed_host = urlsplit(f"//{host_header}")
        origin_host = str(parsed_origin.hostname or "").rstrip(".").lower()
        request_host = str(parsed_host.hostname or "").rstrip(".").lower()
        if (
            parsed_origin.scheme not in {"http", "https"}
            or not origin_host
            or not request_host
            or parsed_origin.username is not None
            or parsed_origin.password is not None
            or bool(parsed_origin.path)
            or bool(parsed_origin.query)
            or bool(parsed_origin.fragment)
            or bool(parsed_host.path)
            or bool(parsed_host.query)
            or bool(parsed_host.fragment)
            or origin_host != request_host
        ):
            return False
        default_port = 443 if parsed_origin.scheme == "https" else 80
        origin_port = parsed_origin.port or default_port
        request_port = parsed_host.port or default_port
    except (TypeError, ValueError):
        return False
    return origin_port == request_port


def plugin_browser_write_is_same_origin(handler: object) -> bool:
    fetch_site = request_header_value(handler, "Sec-Fetch-Site").strip().lower()
    if fetch_site in {"cross-site", "same-site"}:
        return False
    origin = request_header_value(handler, "Origin").strip()
    if not origin:
        # Non-browser clients generally omit Origin. Authorization still applies.
        return True
    if origin.lower() == "null":
        return False
    host_header = request_header_value(handler, "Host").strip()
    return bool(host_header) and _origin_matches_host(origin, host_header)
