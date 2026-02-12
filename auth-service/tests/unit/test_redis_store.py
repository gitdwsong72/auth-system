"""Redis Store 단위 테스트."""

from unittest.mock import patch

import pytest

from src.shared.security.redis_store import RedisTokenStore


@pytest.mark.asyncio
class TestRedisStoreInitialization:
    """Redis Store 초기화 테스트."""

    async def test_initialize_redis_connection(self, fake_redis, mock_jwt_settings):
        """Redis 연결 초기화."""
        # Arrange
        with patch("src.shared.security.redis_store.security_settings", mock_jwt_settings):
            store = RedisTokenStore()
            store._client = fake_redis

            # Act & Assert
            assert store._client is not None

    async def test_client_property_raises_when_not_initialized(self):
        """초기화하지 않고 client 접근 시 RuntimeError."""
        # Arrange
        store = RedisTokenStore()

        # Act & Assert
        with pytest.raises(RuntimeError) as exc_info:
            _ = store.client
        assert "초기화되지 않았습니다" in str(exc_info.value)

    async def test_close_redis_connection(self, fake_redis):
        """Redis 연결 종료."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis

        # Act
        await store.close()

        # Assert - no exception raised


@pytest.mark.asyncio
class TestRedisStoreBlacklist:
    """토큰 블랙리스트 테스트."""

    async def test_blacklist_token_success(self, fake_redis):
        """토큰 블랙리스트 추가."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        jti = "test-jti-12345"
        ttl_seconds = 3600

        # Act
        await store.blacklist_token(jti, ttl_seconds)

        # Assert
        is_blacklisted = await store.is_blacklisted(jti)
        assert is_blacklisted is True

    async def test_is_blacklisted_false_for_new_token(self, fake_redis):
        """블랙리스트에 없는 토큰은 False."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        jti = "non-existent-jti"

        # Act
        result = await store.is_blacklisted(jti)

        # Assert
        assert result is False

    async def test_blacklist_token_with_ttl_expiration(self, fake_redis):
        """블랙리스트 토큰 TTL 확인."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        jti = "expiring-jti"
        ttl_seconds = 10

        # Act
        await store.blacklist_token(jti, ttl_seconds)

        # Assert
        ttl = await fake_redis.ttl(f"blacklist:{jti}")
        assert 0 < ttl <= ttl_seconds

    async def test_blacklist_multiple_tokens(self, fake_redis):
        """여러 토큰을 블랙리스트에 추가."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        jtis = ["jti-1", "jti-2", "jti-3"]

        # Act
        for jti in jtis:
            await store.blacklist_token(jti, 3600)

        # Assert
        for jti in jtis:
            assert await store.is_blacklisted(jti) is True


@pytest.mark.asyncio
class TestRedisStoreRateLimit:
    """Rate Limiting 테스트."""

    async def test_check_rate_limit_first_request(self, fake_redis):
        """첫 요청은 항상 허용."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        key = "user:1:login"
        max_requests = 5
        window_seconds = 60

        # Act
        result = await store.check_rate_limit(key, max_requests, window_seconds)

        # Assert
        assert result is True

    async def test_check_rate_limit_within_limit(self, fake_redis):
        """제한 내 요청은 허용."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        key = "user:1:api"
        max_requests = 5
        window_seconds = 60

        # Act
        results = []
        for _ in range(5):
            results.append(await store.check_rate_limit(key, max_requests, window_seconds))

        # Assert
        assert all(results)

    async def test_check_rate_limit_exceeds_limit(self, fake_redis):
        """제한 초과 요청은 차단."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        key = "user:1:api"
        max_requests = 3
        window_seconds = 60

        # Act
        results = []
        for _ in range(5):
            results.append(await store.check_rate_limit(key, max_requests, window_seconds))

        # Assert
        assert results[:3] == [True, True, True]
        assert results[3:] == [False, False]

    async def test_get_rate_limit_remaining_full(self, fake_redis):
        """요청하지 않은 경우 전체 횟수 반환."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        key = "user:1:api"
        max_requests = 10

        # Act
        remaining = await store.get_rate_limit_remaining(key, max_requests)

        # Assert
        assert remaining == max_requests

    async def test_get_rate_limit_remaining_after_requests(self, fake_redis):
        """요청 후 남은 횟수 확인."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        key = "user:1:api"
        max_requests = 10
        window_seconds = 60

        # Act
        await store.check_rate_limit(key, max_requests, window_seconds)
        await store.check_rate_limit(key, max_requests, window_seconds)
        await store.check_rate_limit(key, max_requests, window_seconds)
        remaining = await store.get_rate_limit_remaining(key, max_requests)

        # Assert
        assert remaining == 7

    async def test_get_rate_limit_remaining_zero_when_exceeded(self, fake_redis):
        """제한 초과 시 0 반환."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        key = "user:1:api"
        max_requests = 2
        window_seconds = 60

        # Act
        for _ in range(5):
            await store.check_rate_limit(key, max_requests, window_seconds)
        remaining = await store.get_rate_limit_remaining(key, max_requests)

        # Assert
        assert remaining == 0


@pytest.mark.asyncio
class TestRedisStoreFailedLogin:
    """로그인 실패 관리 테스트."""

    async def test_increment_failed_login_first_attempt(self, fake_redis, mock_jwt_settings):
        """첫 로그인 실패."""
        # Arrange
        with patch("src.shared.security.redis_store.security_settings", mock_jwt_settings):
            store = RedisTokenStore()
            store._client = fake_redis
            email = "test@example.com"

            # Act
            count = await store.increment_failed_login(email)

            # Assert
            assert count == 1

    async def test_increment_failed_login_multiple_attempts(self, fake_redis, mock_jwt_settings):
        """여러 번 로그인 실패."""
        # Arrange
        with patch("src.shared.security.redis_store.security_settings", mock_jwt_settings):
            store = RedisTokenStore()
            store._client = fake_redis
            email = "test@example.com"

            # Act
            counts = []
            for _ in range(5):
                counts.append(await store.increment_failed_login(email))

            # Assert
            assert counts == [1, 2, 3, 4, 5]

    async def test_get_failed_login_count_zero_for_new_user(self, fake_redis):
        """새 사용자는 실패 횟수 0."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        email = "new@example.com"

        # Act
        count = await store.get_failed_login_count(email)

        # Assert
        assert count == 0

    async def test_get_failed_login_count_after_failures(self, fake_redis, mock_jwt_settings):
        """실패 후 횟수 조회."""
        # Arrange
        with patch("src.shared.security.redis_store.security_settings", mock_jwt_settings):
            store = RedisTokenStore()
            store._client = fake_redis
            email = "test@example.com"

            # Act
            await store.increment_failed_login(email)
            await store.increment_failed_login(email)
            count = await store.get_failed_login_count(email)

            # Assert
            assert count == 2

    async def test_reset_failed_login(self, fake_redis, mock_jwt_settings):
        """로그인 실패 횟수 초기화."""
        # Arrange
        with patch("src.shared.security.redis_store.security_settings", mock_jwt_settings):
            store = RedisTokenStore()
            store._client = fake_redis
            email = "test@example.com"

            # Act
            await store.increment_failed_login(email)
            await store.increment_failed_login(email)
            await store.reset_failed_login(email)
            count = await store.get_failed_login_count(email)

            # Assert
            assert count == 0

    async def test_is_account_locked_false_below_threshold(self, fake_redis, mock_jwt_settings):
        """임계값 미만은 계정 잠기지 않음."""
        # Arrange
        with patch("src.shared.security.redis_store.security_settings", mock_jwt_settings):
            store = RedisTokenStore()
            store._client = fake_redis
            email = "test@example.com"

            # Act
            await store.increment_failed_login(email)
            await store.increment_failed_login(email)
            is_locked, remaining = await store.is_account_locked(email)

            # Assert
            assert is_locked is False
            assert remaining == 0

    async def test_is_account_locked_true_at_threshold(self, fake_redis, mock_jwt_settings):
        """임계값 도달 시 계정 잠금."""
        # Arrange
        with patch("src.shared.security.redis_store.security_settings", mock_jwt_settings):
            store = RedisTokenStore()
            store._client = fake_redis
            email = "test@example.com"
            max_attempts = mock_jwt_settings.password_max_failed_attempts

            # Act
            for _ in range(max_attempts):
                await store.increment_failed_login(email)
            is_locked, remaining = await store.is_account_locked(email)

            # Assert
            assert is_locked is True
            assert remaining > 0

    async def test_increment_failed_login_sets_ttl(self, fake_redis, mock_jwt_settings):
        """첫 실패 시 TTL 설정."""
        # Arrange
        with patch("src.shared.security.redis_store.security_settings", mock_jwt_settings):
            store = RedisTokenStore()
            store._client = fake_redis
            email = "test@example.com"

            # Act
            await store.increment_failed_login(email)

            # Assert
            ttl = await fake_redis.ttl(f"failed_login:{email}")
            expected_ttl = mock_jwt_settings.password_lockout_minutes * 60
            assert 0 < ttl <= expected_ttl


@pytest.mark.asyncio
class TestRedisStoreGenericCache:
    """범용 캐시 테스트."""

    async def test_cache_set_and_get(self, fake_redis):
        """캐시 저장 및 조회."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        key = "test_key"
        value = "test_value"
        ttl_seconds = 300

        # Act
        await store.cache_set(key, value, ttl_seconds)
        result = await store.cache_get(key)

        # Assert
        assert result == value

    async def test_cache_get_none_for_non_existent_key(self, fake_redis):
        """존재하지 않는 키는 None 반환."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        key = "non_existent"

        # Act
        result = await store.cache_get(key)

        # Assert
        assert result is None

    async def test_cache_delete(self, fake_redis):
        """캐시 삭제."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        key = "test_key"
        value = "test_value"

        # Act
        await store.cache_set(key, value, 300)
        await store.cache_delete(key)
        result = await store.cache_get(key)

        # Assert
        assert result is None

    async def test_cache_set_overwrites_existing(self, fake_redis):
        """기존 키 덮어쓰기."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        key = "test_key"

        # Act
        await store.cache_set(key, "old_value", 300)
        await store.cache_set(key, "new_value", 300)
        result = await store.cache_get(key)

        # Assert
        assert result == "new_value"


@pytest.mark.asyncio
class TestRedisStoreMFACode:
    """MFA 코드 관리 테스트."""

    async def test_store_mfa_code(self, fake_redis):
        """MFA 코드 저장."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        user_id = 1
        code = "123456"

        # Act
        await store.store_mfa_code(user_id, code)

        # Assert
        stored = await fake_redis.get(f"mfa_code:{user_id}")
        assert stored == code

    async def test_verify_mfa_code_success(self, fake_redis):
        """올바른 MFA 코드 검증."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        user_id = 1
        code = "123456"

        # Act
        await store.store_mfa_code(user_id, code)
        result = await store.verify_mfa_code(user_id, code)

        # Assert
        assert result is True

    async def test_verify_mfa_code_wrong_code(self, fake_redis):
        """잘못된 MFA 코드 검증."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        user_id = 1
        correct_code = "123456"
        wrong_code = "654321"

        # Act
        await store.store_mfa_code(user_id, correct_code)
        result = await store.verify_mfa_code(user_id, wrong_code)

        # Assert
        assert result is False

    async def test_verify_mfa_code_deletes_on_success(self, fake_redis):
        """검증 성공 시 코드 삭제."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        user_id = 1
        code = "123456"

        # Act
        await store.store_mfa_code(user_id, code)
        await store.verify_mfa_code(user_id, code)
        stored = await fake_redis.get(f"mfa_code:{user_id}")

        # Assert
        assert stored is None

    async def test_verify_mfa_code_false_for_non_existent(self, fake_redis):
        """존재하지 않는 코드 검증 실패."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        user_id = 999

        # Act
        result = await store.verify_mfa_code(user_id, "123456")

        # Assert
        assert result is False


@pytest.mark.asyncio
class TestRedisStoreActiveTokens:
    """활성 토큰 관리 테스트."""

    async def test_register_active_token(self, fake_redis):
        """활성 토큰 등록."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        user_id = 1
        jti = "token-jti-1"
        ttl_seconds = 3600

        # Act
        await store.register_active_token(user_id, jti, ttl_seconds)

        # Assert
        tokens = await store.get_user_active_tokens(user_id)
        assert jti in tokens

    async def test_register_multiple_active_tokens(self, fake_redis):
        """여러 활성 토큰 등록."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        user_id = 1
        jtis = ["jti-1", "jti-2", "jti-3"]

        # Act
        for jti in jtis:
            await store.register_active_token(user_id, jti, 3600)

        # Assert
        tokens = await store.get_user_active_tokens(user_id)
        assert len(tokens) == 3
        for jti in jtis:
            assert jti in tokens

    async def test_get_user_active_tokens_empty(self, fake_redis):
        """활성 토큰이 없는 경우 빈 리스트."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        user_id = 999

        # Act
        tokens = await store.get_user_active_tokens(user_id)

        # Assert
        assert tokens == []

    async def test_remove_active_token(self, fake_redis):
        """특정 활성 토큰 제거."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        user_id = 1
        jti1 = "jti-1"
        jti2 = "jti-2"

        # Act
        await store.register_active_token(user_id, jti1, 3600)
        await store.register_active_token(user_id, jti2, 3600)
        await store.remove_active_token(user_id, jti1)
        tokens = await store.get_user_active_tokens(user_id)

        # Assert
        assert jti1 not in tokens
        assert jti2 in tokens

    async def test_clear_user_active_tokens(self, fake_redis):
        """모든 활성 토큰 제거."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        user_id = 1

        # Act
        await store.register_active_token(user_id, "jti-1", 3600)
        await store.register_active_token(user_id, "jti-2", 3600)
        await store.clear_user_active_tokens(user_id)
        tokens = await store.get_user_active_tokens(user_id)

        # Assert
        assert tokens == []


@pytest.mark.asyncio
class TestRedisStorePermissionsCache:
    """권한 캐싱 테스트."""

    async def test_cache_user_permissions(self, fake_redis):
        """사용자 권한 캐싱."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        user_id = 1
        permissions_data = {
            "roles": ["admin"],
            "permissions": ["users:read", "users:write"],
        }

        # Act
        await store.cache_user_permissions(user_id, permissions_data)
        result = await store.get_cached_user_permissions(user_id)

        # Assert
        assert result == permissions_data

    async def test_get_cached_user_permissions_none_for_non_existent(self, fake_redis):
        """캐시되지 않은 권한은 None."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        user_id = 999

        # Act
        result = await store.get_cached_user_permissions(user_id)

        # Assert
        assert result is None

    async def test_invalidate_user_permissions(self, fake_redis):
        """특정 사용자 권한 캐시 무효화."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        user_id = 1
        permissions_data = {"roles": ["user"], "permissions": ["users:read"]}

        # Act
        await store.cache_user_permissions(user_id, permissions_data)
        await store.invalidate_user_permissions(user_id)
        result = await store.get_cached_user_permissions(user_id)

        # Assert
        assert result is None

    async def test_invalidate_role_permissions(self, fake_redis):
        """역할 권한 변경 시 모든 사용자 캐시 무효화."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        user_ids = [1, 2, 3]

        # Act
        for user_id in user_ids:
            await store.cache_user_permissions(
                user_id,
                {"roles": ["admin"], "permissions": []},
            )
        await store.invalidate_role_permissions(user_ids)

        # Assert
        for user_id in user_ids:
            result = await store.get_cached_user_permissions(user_id)
            assert result is None

    async def test_invalidate_role_permissions_empty_list(self, fake_redis):
        """빈 사용자 리스트로 호출 시 에러 없음."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis

        # Act & Assert
        await store.invalidate_role_permissions([])

    async def test_invalidate_all_permissions(self, fake_redis):
        """모든 권한 캐시 무효화."""
        # Arrange
        store = RedisTokenStore()
        store._client = fake_redis
        user_ids = [1, 2, 3, 4, 5]

        # Act
        for user_id in user_ids:
            await store.cache_user_permissions(
                user_id,
                {"roles": ["user"], "permissions": []},
            )
        await store.invalidate_all_permissions()

        # Assert
        for user_id in user_ids:
            result = await store.get_cached_user_permissions(user_id)
            assert result is None


@pytest.mark.asyncio
class TestRedisStoreProfileCache:
    """프로필 캐싱 테스트."""

    pass
