"""Pure HTTPS origin validation and local-only RunningHub credential policy.

One live configuration file: config.json (Git ignored). No network or ComfyUI
dependencies. Never include tokens, signed URLs or response bodies in errors.
"""
from __future__ import annotations

import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.json"
OFFICIAL_ORIGINS = {
    "international": "https://www.runninghub.ai",
    "domestic": "https://www.runninghub.cn",
}
_BAD_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".test", ".invalid", ".example")
_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def load_private_config() -> dict:
    """Load only config.json; fail visibly on invalid or unreadable settings."""
    if not CONFIG_PATH.is_file():
        return {}
    try:
        if CONFIG_PATH.stat().st_size > 65536:
            raise ValueError("RH config.json exceeds the 64 KiB limit.")
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("RH config.json cannot be read as valid JSON.") from None
    if not isinstance(data, dict):
        raise ValueError("RH config.json must contain one JSON object.")
    return data


def canonical_origin(value: str, *, allow_path: bool = False) -> str:
    """Strict HTTPS origin, without userinfo, query, fragments or local endpoints."""
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise ValueError("RH HTTPS endpoint is missing or invalid.")
    value = value.strip()
    if any(ord(ch) < 33 or ord(ch) == 127 for ch in value) or "\\" in value:
        raise ValueError("RH HTTPS endpoint has invalid characters.")
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError("RH HTTPS endpoint is malformed.") from None
    if (parsed.scheme != "https" or not hostname or parsed.username is not None
            or parsed.password is not None or parsed.fragment or parsed.query
            or (not allow_path and parsed.path not in ("", "/"))):
        raise ValueError("RH API requires a clean HTTPS origin without URL credentials.")
    host = hostname.rstrip(".").lower()
    if host != hostname.lower() or host == "localhost" or host.endswith(_BAD_HOST_SUFFIXES):
        raise ValueError("RH endpoint must not target a local or reserved hostname.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        if not address.is_global:
            raise ValueError("RH endpoint cannot target a private or loopback address.")
        host_text = f"[{host}]" if address.version == 6 else host
    else:
        labels = host.split(".")
        if len(labels) < 2 or not all(_HOST_LABEL.fullmatch(label) for label in labels):
            raise ValueError("RH endpoint contains an invalid hostname.")
        host_text = host
    if port is not None and (port < 1 or port > 65535):
        raise ValueError("RH HTTPS endpoint port is invalid.")
    suffix = f":{port}" if port is not None and port != 443 else ""
    return f"https://{host_text}{suffix}"


def _custom_endpoints(config: dict) -> dict:
    entries = config.get("trusted_custom_endpoints", {})
    if not isinstance(entries, dict):
        raise ValueError("trusted_custom_endpoints must be an object keyed by HTTPS origin.")
    return entries


def validate_api_origin(base_url: str, *, private_config: dict | None = None) -> str:
    """Allow RH official hosts or explicitly trusted exact custom origins."""
    origin = canonical_origin(base_url)
    if origin in OFFICIAL_ORIGINS.values():
        return origin
    settings = load_private_config() if private_config is None else private_config
    entries = _custom_endpoints(settings)
    if origin not in entries:
        raise ValueError("Custom API origin has not been authorized in local config.json.")
    return origin


def credential_for_origin(config: dict, origin: str) -> str:
    """No cross-region fallback: keys are associated with one trusted origin."""
    if not isinstance(config, dict):
        raise ValueError("RH private configuration is invalid.")
    for site, official in OFFICIAL_ORIGINS.items():
        if origin == official:
            keys = config.get("api_keys", {})
            if not isinstance(keys, dict):
                raise ValueError("config.json api_keys must be an object.")
            key = keys.get(site, "")
            return key.strip() if isinstance(key, str) else ""
    entries = _custom_endpoints(config)
    item = entries.get(origin, "")
    key = item.get("api_key", "") if isinstance(item, dict) else item
    return key.strip() if isinstance(key, str) else ""


def validate_download_url(value: str) -> str:
    """Download URLs may be RH signed-CDN URLs, but never local network targets."""
    if not isinstance(value, str) or not value or len(value) > 16384:
        raise ValueError("RH returned an invalid media download URL.")
    if any(ord(ch) < 33 or ord(ch) == 127 for ch in value) or "\\" in value:
        raise ValueError("RH media URL contains invalid characters.")
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise ValueError("RH media URL is malformed.") from None
    if parsed.fragment:
        raise ValueError("RH media URL must not contain a fragment.")
    # Validate the host without exposing signed query parameters.
    clean_origin = f"{parsed.scheme}://{parsed.netloc}"
    canonical = canonical_origin(clean_origin)
    if parsed.port not in (None, 443):
        raise ValueError("RH media URL must use the standard HTTPS port.")
    return value
