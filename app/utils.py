"""Utility functions for request extraction, validation, and sanitization."""

import re
from typing import Optional
from starlette.requests import Request

# Strict regex for room identifier: alphanumeric, dash, underscore, 1-16 characters
ROOM_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,16}$")


def get_client_ip(request: Request, trust_proxy_headers: bool = False) -> str:
    """
    Extract the client IP address from the request.
    
    By default (trust_proxy_headers=False), this extracts the IP directly from
    the TCP socket connection (request.client.host) to avoid header spoofing.
    
    If trust_proxy_headers=True is explicitly configured behind a trusted internal
    reverse proxy, it checks standard proxy headers.
    """
    if trust_proxy_headers:
        # Check X-Forwarded-For header (first address is the original client)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # First IP in comma-separated list
            client_ip = forwarded_for.split(",")[0].strip()
            if client_ip:
                return client_ip

        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

    # Direct socket connection
    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def sanitize_room(raw_room: Optional[str]) -> Optional[str]:
    """
    Sanitize and validate an untrusted room parameter.
    
    Returns a cleaned string if valid, or None if empty, invalid, or malformed.
    """
    if not raw_room:
        return None

    cleaned = raw_room.strip()
    if not cleaned:
        return None

    if ROOM_REGEX.match(cleaned):
        return cleaned

    # If the input contains invalid characters or exceeds length limit,
    # reject as unverified/None rather than throwing an exception.
    return None
