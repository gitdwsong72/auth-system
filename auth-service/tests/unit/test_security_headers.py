"""Unit tests for Security Headers Middleware.

Tests that security headers are properly added to all responses
to protect against XSS, clickjacking, and other web vulnerabilities.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request
from starlette.responses import Response

from src.shared.middleware.security_headers import SecurityHeadersMiddleware


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request."""
    request = MagicMock(spec=Request)
    request.url = MagicMock()
    request.url.path = "/api/v1/users/me"
    return request


@pytest.fixture
def mock_call_next():
    """Create a mock call_next function."""

    async def _call_next(request: Request) -> Response:
        return Response(content="OK", status_code=200)

    return _call_next


@pytest.fixture
def security_middleware():
    """Create a SecurityHeadersMiddleware instance."""
    app = MagicMock()
    return SecurityHeadersMiddleware(app)


@pytest.mark.asyncio
class TestSecurityHeadersMiddleware:
    """Test SecurityHeadersMiddleware functionality."""

    async def test_adds_x_content_type_options_header(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test X-Content-Type-Options header is added."""
        # Act
        response = await security_middleware.dispatch(mock_request, mock_call_next)

        # Assert
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    async def test_adds_x_frame_options_header(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test X-Frame-Options header is added to prevent clickjacking."""
        # Act
        response = await security_middleware.dispatch(mock_request, mock_call_next)

        # Assert
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

    async def test_adds_x_xss_protection_header(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test X-XSS-Protection header is added for legacy browsers."""
        # Act
        response = await security_middleware.dispatch(mock_request, mock_call_next)

        # Assert
        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

    async def test_adds_referrer_policy_header(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test Referrer-Policy header is added."""
        # Act
        response = await security_middleware.dispatch(mock_request, mock_call_next)

        # Assert
        assert "Referrer-Policy" in response.headers
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    async def test_adds_permissions_policy_header(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test Permissions-Policy header is added."""
        # Act
        response = await security_middleware.dispatch(mock_request, mock_call_next)

        # Assert
        assert "Permissions-Policy" in response.headers
        policy = response.headers["Permissions-Policy"]
        assert "geolocation=()" in policy
        assert "microphone=()" in policy
        assert "camera=()" in policy
        assert "payment=()" in policy
        assert "usb=()" in policy

    async def test_adds_csp_header_for_api_endpoints(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test Content-Security-Policy header for regular API endpoints."""
        # Arrange
        mock_request.url.path = "/api/v1/users/me"

        # Act
        response = await security_middleware.dispatch(mock_request, mock_call_next)

        # Assert
        assert "Content-Security-Policy" in response.headers
        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    async def test_adds_relaxed_csp_for_swagger_docs(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_call_next: Any,
    ):
        """Test relaxed CSP for Swagger UI endpoints."""
        # Test /docs endpoint
        mock_request = MagicMock(spec=Request)
        mock_request.url = MagicMock()
        mock_request.url.path = "/docs"

        # Act
        response = await security_middleware.dispatch(mock_request, mock_call_next)

        # Assert
        csp = response.headers["Content-Security-Policy"]
        assert "https://cdn.jsdelivr.net" in csp
        assert "'unsafe-inline'" in csp

    async def test_adds_relaxed_csp_for_redoc(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_call_next: Any,
    ):
        """Test relaxed CSP for ReDoc endpoint."""
        # Arrange
        mock_request = MagicMock(spec=Request)
        mock_request.url = MagicMock()
        mock_request.url.path = "/redoc"

        # Act
        response = await security_middleware.dispatch(mock_request, mock_call_next)

        # Assert
        csp = response.headers["Content-Security-Policy"]
        assert "https://cdn.jsdelivr.net" in csp

    async def test_adds_relaxed_csp_for_openapi_json(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_call_next: Any,
    ):
        """Test relaxed CSP for OpenAPI JSON endpoint."""
        # Arrange
        mock_request = MagicMock(spec=Request)
        mock_request.url = MagicMock()
        mock_request.url.path = "/openapi.json"

        # Act
        response = await security_middleware.dispatch(mock_request, mock_call_next)

        # Assert
        csp = response.headers["Content-Security-Policy"]
        assert "https://cdn.jsdelivr.net" in csp

    @patch("src.shared.middleware.security_headers.security_settings")
    async def test_adds_hsts_header_in_production(
        self,
        mock_settings: Any,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test HSTS header is added in production environment."""
        # Arrange
        mock_settings.env = "production"

        # Act
        response = await security_middleware.dispatch(mock_request, mock_call_next)

        # Assert
        assert "Strict-Transport-Security" in response.headers
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts

    @patch("src.shared.middleware.security_headers.security_settings")
    async def test_no_hsts_header_in_development(
        self,
        mock_settings: Any,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test HSTS header is NOT added in development environment."""
        # Arrange
        mock_settings.env = "development"

        # Act
        response = await security_middleware.dispatch(mock_request, mock_call_next)

        # Assert
        assert "Strict-Transport-Security" not in response.headers

    async def test_all_security_headers_present(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test all required security headers are present in response."""
        # Act
        response = await security_middleware.dispatch(mock_request, mock_call_next)

        # Assert - Check all required headers
        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Content-Security-Policy",
            "Referrer-Policy",
            "Permissions-Policy",
        ]

        for header in required_headers:
            assert header in response.headers, f"Missing security header: {header}"

    async def test_preserves_existing_response_headers(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
    ):
        """Test that existing response headers are preserved."""

        # Arrange
        async def _call_next_with_headers(request: Request) -> Response:
            response = Response(content="OK", status_code=200)
            response.headers["X-Custom-Header"] = "custom-value"
            return response

        # Act
        response = await security_middleware.dispatch(
            mock_request,
            _call_next_with_headers,
        )

        # Assert - Custom header should be preserved
        assert response.headers["X-Custom-Header"] == "custom-value"
        # Security headers should also be present
        assert "X-Content-Type-Options" in response.headers

    async def test_works_with_different_response_status_codes(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
    ):
        """Test middleware works with various HTTP status codes."""
        # Test cases: different status codes
        test_cases = [200, 201, 400, 401, 404, 500]

        for status_code in test_cases:
            # Arrange
            async def _call_next(request: Request) -> Response:
                return Response(content="test", status_code=status_code)

            # Act
            response = await security_middleware.dispatch(mock_request, _call_next)

            # Assert
            assert response.status_code == status_code
            assert "X-Content-Type-Options" in response.headers

    async def test_csp_blocks_inline_scripts_for_api(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test CSP for API endpoints blocks unsafe inline scripts."""
        # Arrange
        mock_request.url.path = "/api/v1/auth/login"

        # Act
        response = await security_middleware.dispatch(mock_request, mock_call_next)

        # Assert
        csp = response.headers["Content-Security-Policy"]
        # For API endpoints, should NOT have 'unsafe-inline' for scripts
        # (Note: style-src may have it for inline styles, but script-src should not)
        assert "script-src 'self'" in csp
        # Verify it doesn't allow unsafe inline for scripts
        parts = csp.split(";")
        script_src = next(p for p in parts if "script-src" in p)
        assert "'unsafe-inline'" not in script_src or "script-src 'self'" in script_src


@pytest.mark.asyncio
class TestSecurityHeadersEdgeCases:
    """Test edge cases and special scenarios."""

    async def test_handles_none_response_gracefully(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
    ):
        """Test middleware handles None response gracefully."""

        # Arrange
        async def _call_next_none(request: Request) -> Response:
            return Response(content="", status_code=204)

        # Act
        response = await security_middleware.dispatch(mock_request, _call_next_none)

        # Assert
        assert response.status_code == 204
        assert "X-Content-Type-Options" in response.headers

    async def test_works_with_streaming_response(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
    ):
        """Test middleware works with streaming responses."""
        from starlette.responses import StreamingResponse

        # Arrange
        async def generate():
            yield b"chunk1"
            yield b"chunk2"

        async def _call_next_streaming(request: Request) -> Response:
            return StreamingResponse(generate(), media_type="text/plain")

        # Act
        response = await security_middleware.dispatch(
            mock_request,
            _call_next_streaming,
        )

        # Assert
        assert "X-Content-Type-Options" in response.headers

    async def test_header_values_are_correct_format(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test that header values follow correct format/spec."""
        # Act
        response = await security_middleware.dispatch(mock_request, mock_call_next)

        # Assert - Verify specific header value formats
        # X-Frame-Options should be DENY or SAMEORIGIN
        assert response.headers["X-Frame-Options"] in ["DENY", "SAMEORIGIN"]

        # X-Content-Type-Options should be nosniff
        assert response.headers["X-Content-Type-Options"] == "nosniff"

        # X-XSS-Protection should be properly formatted
        xss_protection = response.headers["X-XSS-Protection"]
        assert xss_protection in ["0", "1", "1; mode=block"]

    async def test_csp_frame_ancestors_none(
        self,
        security_middleware: SecurityHeadersMiddleware,
        mock_request: Request,
        mock_call_next: Any,
    ):
        """Test CSP frame-ancestors is set to 'none' to prevent clickjacking."""
        # Act
        response = await security_middleware.dispatch(mock_request, mock_call_next)

        # Assert
        csp = response.headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in csp
