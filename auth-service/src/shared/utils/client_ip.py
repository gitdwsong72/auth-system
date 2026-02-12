"""Client IP extraction with trusted proxy validation.

This module provides secure client IP extraction that prevents X-Forwarded-For
header spoofing by only trusting headers from verified proxy servers.
"""

import ipaddress

from fastapi import Request

# Trusted proxies (RFC1918 private ranges + localhost)
# Only trust X-Forwarded-For from these IPs
TRUSTED_PROXIES = [
    "10.0.0.0/8",  # Private network (Class A)
    "172.16.0.0/12",  # Private network (Class B)
    "192.168.0.0/16",  # Private network (Class C)
    "127.0.0.0/8",  # Localhost
    "::1/128",  # IPv6 localhost
    "fd00::/8",  # IPv6 private network
]


def is_trusted_proxy(ip: str) -> bool:
    """Check if IP is a trusted proxy.

    Only trusted proxies are allowed to provide X-Forwarded-For headers.
    This prevents attackers from spoofing their IP address by sending
    fake X-Forwarded-For headers.

    Args:
        ip: IP address to check

    Returns:
        True if IP is in trusted proxy networks, False otherwise

    Example:
        >>> is_trusted_proxy("127.0.0.1")
        True
        >>> is_trusted_proxy("192.168.1.1")
        True
        >>> is_trusted_proxy("1.2.3.4")  # Public IP
        False
    """
    try:
        ip_addr = ipaddress.ip_address(ip)
        for trusted_network in TRUSTED_PROXIES:
            if ip_addr in ipaddress.ip_network(trusted_network):
                return True
        return False
    except ValueError:
        # Invalid IP address
        return False


def get_client_ip(request: Request) -> str:
    """Extract client IP address with trusted proxy validation.

    Security model:
    1. Get directly connected IP (proxy IP)
    2. If proxy is trusted (RFC1918/localhost), check forwarding headers
    3. Otherwise, use direct connection IP to prevent spoofing

    This prevents attackers from bypassing rate limits or audit logs
    by sending fake X-Forwarded-For headers.

    Args:
        request: FastAPI Request object

    Returns:
        Client IP address (validated)

    Example:
        >>> # Behind trusted proxy (e.g., localhost:8080 → app)
        >>> request.client.host = "127.0.0.1"
        >>> request.headers["X-Forwarded-For"] = "203.0.113.42"
        >>> get_client_ip(request)
        "203.0.113.42"  # Trusted, uses forwarded IP

        >>> # Direct connection from internet
        >>> request.client.host = "203.0.113.42"
        >>> request.headers["X-Forwarded-For"] = "127.0.0.1"  # Fake!
        >>> get_client_ip(request)
        "203.0.113.42"  # Not trusted, ignores fake header
    """
    # Get directly connected client IP (proxy IP)
    proxy_ip = request.client.host if request.client else None

    # Only trust forwarding headers from verified proxies
    if proxy_ip and is_trusted_proxy(proxy_ip):
        # X-Forwarded-For header (most common, used by load balancers)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # First IP is the original client (X-Forwarded-For: client, proxy1, proxy2)
            return forwarded_for.split(",")[0].strip()

        # X-Real-IP header (used by Nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

    # Not from trusted proxy - use direct connection IP
    if proxy_ip:
        return proxy_ip

    return "unknown"


def get_client_info(request: Request) -> tuple[str, str | None]:
    """Extract client IP and User-Agent from request.

    Convenience function combining IP extraction and User-Agent retrieval.
    Useful for logging, analytics, and security monitoring.

    Args:
        request: FastAPI Request object

    Returns:
        Tuple of (ip_address, user_agent)

    Example:
        >>> ip, user_agent = get_client_info(request)
        >>> print(f"Request from {ip} using {user_agent}")
    """
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    return ip_address, user_agent
