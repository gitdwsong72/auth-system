"""Client IP extraction with trusted proxy validation tests."""

from unittest.mock import MagicMock

from src.shared.utils.client_ip import (
    get_client_info,
    get_client_ip,
    is_trusted_proxy,
)


class TestIsTrustedProxy:
    """Trusted proxy detection tests."""

    def test_localhost_ipv4_is_trusted(self):
        """127.0.0.1 (localhost) is trusted."""
        assert is_trusted_proxy("127.0.0.1") is True

    def test_localhost_ipv6_is_trusted(self):
        """::1 (IPv6 localhost) is trusted."""
        assert is_trusted_proxy("::1") is True

    def test_private_class_a_is_trusted(self):
        """10.0.0.0/8 network is trusted."""
        assert is_trusted_proxy("10.0.0.1") is True
        assert is_trusted_proxy("10.255.255.255") is True

    def test_private_class_b_is_trusted(self):
        """172.16.0.0/12 network is trusted."""
        assert is_trusted_proxy("172.16.0.1") is True
        assert is_trusted_proxy("172.31.255.255") is True

    def test_private_class_c_is_trusted(self):
        """192.168.0.0/16 network is trusted."""
        assert is_trusted_proxy("192.168.0.1") is True
        assert is_trusted_proxy("192.168.255.255") is True

    def test_public_ip_is_not_trusted(self):
        """Public IPs are not trusted."""
        assert is_trusted_proxy("8.8.8.8") is False  # Google DNS
        assert is_trusted_proxy("1.1.1.1") is False  # Cloudflare DNS
        assert is_trusted_proxy("203.0.113.42") is False  # TEST-NET-3

    def test_invalid_ip_is_not_trusted(self):
        """Invalid IP addresses are not trusted."""
        assert is_trusted_proxy("not-an-ip") is False
        assert is_trusted_proxy("999.999.999.999") is False
        assert is_trusted_proxy("") is False


class TestGetClientIP:
    """Client IP extraction tests with spoofing prevention."""

    def test_direct_connection_without_headers(self):
        """Direct connection without proxy headers uses client.host."""
        # Arrange
        request = MagicMock()
        request.client.host = "203.0.113.42"
        request.headers = {}

        # Act
        ip = get_client_ip(request)

        # Assert
        assert ip == "203.0.113.42"

    def test_trusted_proxy_uses_x_forwarded_for(self):
        """Trusted proxy (localhost) can provide X-Forwarded-For."""
        # Arrange
        request = MagicMock()
        request.client.host = "127.0.0.1"  # Trusted proxy
        request.headers = {"X-Forwarded-For": "203.0.113.42"}

        # Act
        ip = get_client_ip(request)

        # Assert
        assert ip == "203.0.113.42"  # Uses forwarded IP

    def test_untrusted_proxy_ignores_x_forwarded_for(self):
        """Untrusted proxy (public IP) cannot fake X-Forwarded-For."""
        # Arrange
        request = MagicMock()
        request.client.host = "203.0.113.1"  # Public IP (not trusted)
        request.headers = {"X-Forwarded-For": "127.0.0.1"}  # Fake!

        # Act
        ip = get_client_ip(request)

        # Assert
        assert ip == "203.0.113.1"  # Ignores fake header, uses direct IP

    def test_x_forwarded_for_with_multiple_ips(self):
        """X-Forwarded-For with multiple IPs uses first (original client)."""
        # Arrange
        request = MagicMock()
        request.client.host = "127.0.0.1"  # Trusted
        request.headers = {"X-Forwarded-For": "203.0.113.42, 192.168.1.1, 10.0.0.1"}

        # Act
        ip = get_client_ip(request)

        # Assert
        assert ip == "203.0.113.42"  # First IP (original client)

    def test_x_forwarded_for_with_spaces(self):
        """X-Forwarded-For with spaces is trimmed."""
        # Arrange
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {"X-Forwarded-For": "  203.0.113.42  "}

        # Act
        ip = get_client_ip(request)

        # Assert
        assert ip == "203.0.113.42"  # Trimmed

    def test_trusted_proxy_uses_x_real_ip(self):
        """Trusted proxy can provide X-Real-IP (Nginx)."""
        # Arrange
        request = MagicMock()
        request.client.host = "192.168.1.1"  # Trusted (private network)
        request.headers = {"X-Real-IP": "203.0.113.42"}

        # Act
        ip = get_client_ip(request)

        # Assert
        assert ip == "203.0.113.42"

    def test_x_forwarded_for_takes_precedence_over_x_real_ip(self):
        """X-Forwarded-For is checked before X-Real-IP."""
        # Arrange
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {
            "X-Forwarded-For": "203.0.113.42",
            "X-Real-IP": "203.0.113.99",
        }

        # Act
        ip = get_client_ip(request)

        # Assert
        assert ip == "203.0.113.42"  # X-Forwarded-For wins

    def test_no_client_returns_unknown(self):
        """Missing client returns 'unknown'."""
        # Arrange
        request = MagicMock()
        request.client = None
        request.headers = {}

        # Act
        ip = get_client_ip(request)

        # Assert
        assert ip == "unknown"

    def test_private_network_class_a_is_trusted(self):
        """10.x.x.x proxies are trusted."""
        # Arrange
        request = MagicMock()
        request.client.host = "10.0.0.1"
        request.headers = {"X-Forwarded-For": "203.0.113.42"}

        # Act
        ip = get_client_ip(request)

        # Assert
        assert ip == "203.0.113.42"

    def test_private_network_class_b_is_trusted(self):
        """172.16-31.x.x proxies are trusted."""
        # Arrange
        request = MagicMock()
        request.client.host = "172.20.0.1"
        request.headers = {"X-Forwarded-For": "203.0.113.42"}

        # Act
        ip = get_client_ip(request)

        # Assert
        assert ip == "203.0.113.42"

    def test_private_network_class_c_is_trusted(self):
        """192.168.x.x proxies are trusted."""
        # Arrange
        request = MagicMock()
        request.client.host = "192.168.100.1"
        request.headers = {"X-Forwarded-For": "203.0.113.42"}

        # Act
        ip = get_client_ip(request)

        # Assert
        assert ip == "203.0.113.42"


class TestGetClientInfo:
    """Client info (IP + User-Agent) extraction tests."""

    def test_extracts_both_ip_and_user_agent(self):
        """Extracts both IP and User-Agent from request."""
        # Arrange
        request = MagicMock()
        request.client.host = "203.0.113.42"
        request.headers = {"User-Agent": "Mozilla/5.0"}

        # Act
        ip, user_agent = get_client_info(request)

        # Assert
        assert ip == "203.0.113.42"
        assert user_agent == "Mozilla/5.0"

    def test_returns_none_for_missing_user_agent(self):
        """Returns None for missing User-Agent."""
        # Arrange
        request = MagicMock()
        request.client.host = "203.0.113.42"
        request.headers = {}

        # Act
        ip, user_agent = get_client_info(request)

        # Assert
        assert ip == "203.0.113.42"
        assert user_agent is None

    def test_applies_trusted_proxy_validation(self):
        """Applies trusted proxy validation to IP extraction."""
        # Arrange
        request = MagicMock()
        request.client.host = "127.0.0.1"  # Trusted
        request.headers = {
            "X-Forwarded-For": "203.0.113.42",
            "User-Agent": "curl/7.68.0",
        }

        # Act
        ip, user_agent = get_client_info(request)

        # Assert
        assert ip == "203.0.113.42"  # Uses forwarded IP
        assert user_agent == "curl/7.68.0"


class TestSecurityScenarios:
    """Real-world security attack scenarios."""

    def test_attacker_spoofs_localhost(self):
        """Attacker from public IP cannot spoof localhost."""
        # Arrange - Attacker at 203.0.113.99 claims to be localhost
        request = MagicMock()
        request.client.host = "203.0.113.99"
        request.headers = {"X-Forwarded-For": "127.0.0.1"}  # Fake!

        # Act
        ip = get_client_ip(request)

        # Assert
        assert ip == "203.0.113.99"  # Real IP, not spoofed

    def test_attacker_spoofs_admin_ip(self):
        """Attacker cannot spoof admin's IP address."""
        # Arrange - Attacker tries to appear as admin
        request = MagicMock()
        request.client.host = "203.0.113.99"
        request.headers = {"X-Forwarded-For": "192.168.1.100"}  # Admin IP

        # Act
        ip = get_client_ip(request)

        # Assert
        assert ip == "203.0.113.99"  # Attacker's real IP

    def test_legitimate_load_balancer_preserves_client_ip(self):
        """Legitimate load balancer (private network) forwards client IP."""
        # Arrange - Request through AWS ALB (10.x.x.x)
        request = MagicMock()
        request.client.host = "10.0.1.100"  # ALB private IP
        request.headers = {"X-Forwarded-For": "203.0.113.42"}  # Real client

        # Act
        ip = get_client_ip(request)

        # Assert
        assert ip == "203.0.113.42"  # Client IP preserved

    def test_cloudflare_proxy_is_not_trusted_by_default(self):
        """Cloudflare proxy (public IP) is not trusted without configuration."""
        # Arrange - Cloudflare IP (example)
        request = MagicMock()
        request.client.host = "104.16.0.1"  # Cloudflare range
        request.headers = {"X-Forwarded-For": "203.0.113.42"}

        # Act
        ip = get_client_ip(request)

        # Assert
        assert ip == "104.16.0.1"  # Not trusted, uses Cloudflare IP
        # Note: In production, add Cloudflare IPs to TRUSTED_PROXIES if using CF

    def test_rate_limit_bypass_attempt(self):
        """Attacker cannot bypass rate limits by changing X-Forwarded-For."""
        # Arrange - Attacker tries multiple fake IPs to bypass rate limit
        request = MagicMock()
        request.client.host = "203.0.113.99"

        fake_ips = [
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
            "127.0.0.1",
        ]

        # Act & Assert - All attempts return real IP
        for fake_ip in fake_ips:
            request.headers = {"X-Forwarded-For": fake_ip}
            ip = get_client_ip(request)
            assert ip == "203.0.113.99"  # Always real IP

    def test_audit_log_tampering_attempt(self):
        """Attacker cannot hide their IP in audit logs."""
        # Arrange - Attacker tries to fake IP for audit log evasion
        request = MagicMock()
        request.client.host = "203.0.113.99"
        request.headers = {
            "X-Forwarded-For": "192.168.1.1",  # Fake internal IP
            "User-Agent": "Mozilla/5.0",
        }

        # Act
        ip, _ = get_client_info(request)

        # Assert
        assert ip == "203.0.113.99"  # Real IP logged, not fake
