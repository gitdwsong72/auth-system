"""
Load Testing Scenarios for Auth System

This module defines comprehensive load testing scenarios using Locust to measure
the performance and capacity limits of the authentication system.

Tested Endpoints:
- POST /api/v1/users/register - User registration
- POST /api/v1/auth/login - User authentication
- POST /api/v1/auth/refresh - Token refresh
- GET /api/v1/users/me - User profile retrieval
- POST /api/v1/auth/logout - User logout
- GET /api/v1/auth/sessions - Session listing
- DELETE /api/v1/auth/sessions - Revoke all sessions

Run Examples:
    # Basic load test (10 users, spawn 1/sec)
    locust -f tests/load/locustfile.py --host=http://localhost:8000 --users 10 --spawn-rate 1

    # Stress test (100 users, spawn 10/sec, 5 min)
    locust -f tests/load/locustfile.py --host=http://localhost:8000 --users 100 --spawn-rate 10 --run-time 5m

    # Headless mode with report
    locust -f tests/load/locustfile.py --host=http://localhost:8000 --users 50 --spawn-rate 5 --run-time 3m --headless --html reports/load_test.html
"""

import random
import string

from locust import HttpUser, between, task


def generate_random_email() -> str:
    """Generate random email for test users."""
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"loadtest_{random_str}@example.com"


def generate_random_username() -> str:
    """Generate random username for test users."""
    return "user_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


def generate_password() -> str:
    """Generate valid password meeting requirements."""
    return "LoadTest123!"


class AuthSystemUser(HttpUser):
    """
    Simulated user for authentication system load testing.

    Represents a typical user journey through the auth system with realistic
    waiting times between actions.
    """

    # Wait between 1-3 seconds between tasks (simulates real user think time)
    wait_time = between(1, 3)

    # User session state
    access_token: str | None = None
    refresh_token: str | None = None
    email: str | None = None
    password: str | None = None

    def on_start(self):
        """
        Called when a simulated user starts.
        Registers a new user and logs in to establish session.
        """
        # Generate unique credentials for this user
        self.email = generate_random_email()
        self.password = generate_password()
        username = generate_random_username()

        # Register new user
        register_response = self.client.post(
            "/api/v1/users/register",
            json={
                "email": self.email,
                "password": self.password,
                "username": username,
            },
            name="/api/v1/users/register",
        )

        if register_response.status_code == 201:
            # Login to get tokens
            self._perform_login()

    def _perform_login(self) -> bool:
        """
        Perform login and store tokens.

        Returns:
            bool: True if login successful, False otherwise
        """
        login_response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": self.email,
                "password": self.password,
                "device_info": "Locust Load Test",
            },
            name="/api/v1/auth/login",
        )

        if login_response.status_code == 200:
            data = login_response.json()
            if data.get("success"):
                self.access_token = data["data"]["access_token"]
                self.refresh_token = data["data"]["refresh_token"]
                return True

        return False

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authorization headers with current access token."""
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    @task(10)
    def get_user_profile(self):
        """
        Task: Get current user profile (weight: 10).

        Most common operation - users frequently check their profile/info.
        """
        if not self.access_token:
            return

        self.client.get(
            "/api/v1/users/me",
            headers=self._get_auth_headers(),
            name="/api/v1/users/me",
        )

    @task(5)
    def refresh_access_token(self):
        """
        Task: Refresh access token (weight: 5).

        Regular operation as tokens expire (every 30 min by default).
        """
        if not self.refresh_token:
            return

        response = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": self.refresh_token},
            name="/api/v1/auth/refresh",
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                self.access_token = data["data"]["access_token"]
                self.refresh_token = data["data"]["refresh_token"]

    @task(2)
    def get_sessions(self):
        """
        Task: Get active sessions (weight: 2).

        Less common - users occasionally check their active sessions.
        """
        if not self.access_token:
            return

        self.client.get(
            "/api/v1/auth/sessions",
            headers=self._get_auth_headers(),
            name="/api/v1/auth/sessions",
        )

    @task(1)
    def update_profile(self):
        """
        Task: Update user profile (weight: 1).

        Rare operation - users occasionally update their profile info.
        """
        if not self.access_token:
            return

        self.client.put(
            "/api/v1/users/me",
            headers=self._get_auth_headers(),
            json={
                "username": generate_random_username(),
                "bio": f"Updated bio at {random.randint(1000, 9999)}",
            },
            name="/api/v1/users/me [PUT]",
        )


class LoginHeavyUser(HttpUser):
    """
    User scenario focused on login operations.

    Simulates scenarios like:
    - Mobile app users frequently logging in/out
    - Multiple device access
    - Session management testing
    """

    wait_time = between(2, 5)

    access_token: str | None = None
    refresh_token: str | None = None
    email: str | None = None
    password: str | None = None

    def on_start(self):
        """Register a permanent test user for login testing."""
        self.email = generate_random_email()
        self.password = generate_password()
        username = generate_random_username()

        self.client.post(
            "/api/v1/users/register",
            json={
                "email": self.email,
                "password": self.password,
                "username": username,
            },
        )

    @task(10)
    def login(self):
        """
        Task: User login (weight: 10).

        Primary focus - stress test authentication with bcrypt hashing.
        """
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": self.email,
                "password": self.password,
                "device_info": "Locust Login Test",
            },
            name="/api/v1/auth/login",
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                self.access_token = data["data"]["access_token"]
                self.refresh_token = data["data"]["refresh_token"]

    @task(3)
    def logout(self):
        """
        Task: User logout (weight: 3).

        Test session cleanup and token blacklisting performance.
        """
        if not self.access_token:
            return

        self.client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {self.access_token}"},
            name="/api/v1/auth/logout",
        )

        # Clear tokens after logout
        self.access_token = None
        self.refresh_token = None

    @task(2)
    def get_profile_after_login(self):
        """
        Task: Get profile immediately after login (weight: 2).

        Tests token validation and database query performance.
        """
        if not self.access_token:
            return

        self.client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {self.access_token}"},
            name="/api/v1/users/me",
        )


class RegistrationStressUser(HttpUser):
    """
    User scenario focused on registration load.

    Simulates:
    - Marketing campaigns driving new user signups
    - Bot registration attempts
    - Concurrent user creation stress
    """

    wait_time = between(1, 2)

    @task
    def register_user(self):
        """
        Task: Register new user.

        Each execution creates a new unique user to stress database writes,
        password hashing, and unique constraint validation.
        """
        self.client.post(
            "/api/v1/users/register",
            json={
                "email": generate_random_email(),
                "password": generate_password(),
                "username": generate_random_username(),
            },
            name="/api/v1/users/register",
        )


class TokenRefreshHeavyUser(HttpUser):
    """
    User scenario focused on token refresh operations.

    Simulates:
    - Long-running sessions with frequent token refreshes
    - Mobile apps with aggressive token refresh strategies
    - Redis cache stress testing
    """

    wait_time = between(0.5, 1.5)

    access_token: str | None = None
    refresh_token: str | None = None

    def on_start(self):
        """Register and login to get initial tokens."""
        email = generate_random_email()
        password = generate_password()
        username = generate_random_username()

        # Register
        self.client.post(
            "/api/v1/users/register",
            json={
                "email": email,
                "password": password,
                "username": username,
            },
        )

        # Login
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": password,
            },
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                self.access_token = data["data"]["access_token"]
                self.refresh_token = data["data"]["refresh_token"]

    @task(20)
    def refresh_token(self):
        """
        Task: Refresh access token aggressively (weight: 20).

        Stress tests JWT generation, Redis operations, and database updates.
        """
        if not self.refresh_token:
            return

        response = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": self.refresh_token},
            name="/api/v1/auth/refresh",
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                self.access_token = data["data"]["access_token"]
                self.refresh_token = data["data"]["refresh_token"]

    @task(5)
    def verify_token_works(self):
        """
        Task: Verify refreshed token works (weight: 5).

        Ensures refresh operation produces valid tokens.
        """
        if not self.access_token:
            return

        self.client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {self.access_token}"},
            name="/api/v1/users/me",
        )
