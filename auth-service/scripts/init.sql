-- =============================================================================
-- MSA Auth System - 초기 데이터베이스 마이그레이션
-- Description: 인증/인가 시스템의 전체 스키마 생성 (10개 테이블)
-- =============================================================================

BEGIN;

-- =============================================================================
-- 1. users - 사용자 계정 테이블
-- Description: 시스템의 메인 사용자 계정 정보를 저장합니다.
--              이메일/비밀번호 로그인과 소셜 로그인 사용자를 모두 관리합니다.
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL       PRIMARY KEY,
    email           VARCHAR(255)    NOT NULL,
    username        VARCHAR(100),
    password_hash   VARCHAR(255),                          -- 소셜 전용 사용자는 NULL 허용
    display_name    VARCHAR(200),
    phone           VARCHAR(20),
    avatar_url      TEXT,
    email_verified  BOOLEAN         NOT NULL DEFAULT FALSE,
    phone_verified  BOOLEAN         NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    is_superuser    BOOLEAN         NOT NULL DEFAULT FALSE,
    last_login_at   TIMESTAMPTZ,
    password_changed_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE users IS '사용자 계정 테이블 - 이메일/소셜 로그인 사용자 관리';
COMMENT ON COLUMN users.password_hash IS '비밀번호 해시 (소셜 전용 사용자는 NULL)';
COMMENT ON COLUMN users.deleted_at IS 'soft delete 타임스탬프';

-- 활성 사용자 이메일 유니크 (soft delete 된 사용자 제외)
CREATE UNIQUE INDEX IF NOT EXISTS udx_users_email
    ON users (email)
    WHERE deleted_at IS NULL;

-- 활성 사용자 username 유니크 (soft delete 된 사용자 제외)
CREATE UNIQUE INDEX IF NOT EXISTS udx_users_username
    ON users (username)
    WHERE deleted_at IS NULL;

-- [PERFORMANCE] 이메일 검색 성능 향상 (로그인 등)
CREATE INDEX IF NOT EXISTS idx_users_email_active
    ON users (email)
    WHERE deleted_at IS NULL;

-- =============================================================================
-- 2. roles - 역할 테이블
-- Description: RBAC(Role-Based Access Control) 역할을 정의합니다.
--              시스템 역할(is_system=true)은 삭제할 수 없습니다.
-- =============================================================================
CREATE TABLE IF NOT EXISTS roles (
    id              BIGSERIAL       PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL UNIQUE,
    display_name    VARCHAR(200),
    description     TEXT,
    is_system       BOOLEAN         NOT NULL DEFAULT FALSE,  -- 시스템 역할은 삭제 불가
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE roles IS '역할 테이블 - RBAC 역할 정의 (시스템 역할은 삭제 불가)';
COMMENT ON COLUMN roles.is_system IS 'true이면 시스템 역할로 삭제 불가';

-- =============================================================================
-- 3. permissions - 권한 테이블
-- Description: 세분화된 권한을 정의합니다.
--              resource(대상) + action(행위) 조합으로 권한을 표현합니다.
--              예: resource='users', action='read' → 사용자 조회 권한
-- =============================================================================
CREATE TABLE IF NOT EXISTS permissions (
    id              BIGSERIAL       PRIMARY KEY,
    resource        VARCHAR(100)    NOT NULL,                -- 대상 리소스 (예: users, roles)
    action          VARCHAR(50)     NOT NULL,                -- 행위 (예: read, write, delete)
    description     TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_permissions_resource_action UNIQUE (resource, action)
);

COMMENT ON TABLE permissions IS '권한 테이블 - resource + action 조합의 세분화된 권한';
COMMENT ON COLUMN permissions.resource IS '대상 리소스 (예: users, roles, api_keys)';
COMMENT ON COLUMN permissions.action IS '행위 (예: read, write, delete, admin)';

-- =============================================================================
-- 4. user_roles - 사용자-역할 매핑 테이블
-- Description: 사용자에게 역할을 부여하는 junction 테이블입니다.
--              만료일(expires_at) 설정으로 임시 역할 부여가 가능합니다.
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_roles (
    id              BIGSERIAL       PRIMARY KEY,
    user_id         BIGINT          NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    role_id         BIGINT          NOT NULL REFERENCES roles (id) ON DELETE CASCADE,
    granted_by      BIGINT          REFERENCES users (id) ON DELETE SET NULL,
    granted_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,                             -- NULL이면 만료 없음

    CONSTRAINT uq_user_roles_user_role UNIQUE (user_id, role_id)
);

COMMENT ON TABLE user_roles IS '사용자-역할 매핑 테이블 - 역할 부여 및 만료 관리';
COMMENT ON COLUMN user_roles.granted_by IS '역할을 부여한 관리자 ID';
COMMENT ON COLUMN user_roles.expires_at IS '역할 만료일 (NULL이면 무기한)';

CREATE INDEX IF NOT EXISTS idx_user_roles_user_id
    ON user_roles (user_id);

-- [PERFORMANCE] 유효한 역할만 필터링 (만료되지 않은 역할)
-- NOTE: NOW()는 VOLATILE이라 partial index에 사용 불가
-- 대신 user_id + expires_at 복합 인덱스 사용
CREATE INDEX IF NOT EXISTS idx_user_roles_user_expires
    ON user_roles (user_id, expires_at);

-- =============================================================================
-- 5. role_permissions - 역할-권한 매핑 테이블
-- Description: 역할에 권한을 연결하는 junction 테이블입니다.
-- =============================================================================
CREATE TABLE IF NOT EXISTS role_permissions (
    id              BIGSERIAL       PRIMARY KEY,
    role_id         BIGINT          NOT NULL REFERENCES roles (id) ON DELETE CASCADE,
    permission_id   BIGINT          NOT NULL REFERENCES permissions (id) ON DELETE CASCADE,

    CONSTRAINT uq_role_permissions_role_perm UNIQUE (role_id, permission_id)
);

COMMENT ON TABLE role_permissions IS '역할-권한 매핑 테이블 - 역할별 세부 권한 연결';

CREATE INDEX IF NOT EXISTS idx_role_permissions_role_id
    ON role_permissions (role_id);

-- =============================================================================
-- 6. oauth_accounts - 소셜 로그인 계정 테이블
-- Description: OAuth 2.0 소셜 로그인 연동 계정을 관리합니다.
--              하나의 사용자가 여러 소셜 계정을 연결할 수 있습니다.
--              (예: Google, GitHub, Kakao 등)
-- =============================================================================
CREATE TABLE IF NOT EXISTS oauth_accounts (
    id                  BIGSERIAL       PRIMARY KEY,
    user_id             BIGINT          NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    provider            VARCHAR(50)     NOT NULL,            -- 소셜 제공자 (google, github, kakao 등)
    provider_user_id    VARCHAR(255)    NOT NULL,            -- 소셜 제공자 측 사용자 ID
    provider_email      VARCHAR(255),
    provider_username   VARCHAR(255),
    access_token        TEXT,
    refresh_token       TEXT,
    token_expires_at    TIMESTAMPTZ,
    raw_data            JSONB,                               -- 소셜 제공자 원본 프로필 데이터
    linked_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_oauth_provider_user UNIQUE (provider, provider_user_id)
);

COMMENT ON TABLE oauth_accounts IS '소셜 로그인 계정 테이블 - OAuth 2.0 연동 관리';
COMMENT ON COLUMN oauth_accounts.raw_data IS '소셜 제공자로부터 받은 원본 프로필 JSON 데이터';

CREATE INDEX IF NOT EXISTS idx_oauth_accounts_user_id
    ON oauth_accounts (user_id);

CREATE INDEX IF NOT EXISTS idx_oauth_accounts_provider_user
    ON oauth_accounts (provider, provider_user_id);

-- =============================================================================
-- 7. refresh_tokens - JWT 리프레시 토큰 테이블
-- Description: JWT 인증의 리프레시 토큰을 관리합니다.
--              토큰 해시만 저장하여 보안을 강화합니다.
--              디바이스 정보를 JSONB로 저장하여 세션 관리에 활용합니다.
-- =============================================================================
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id              BIGSERIAL       PRIMARY KEY,
    user_id         BIGINT          NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash      VARCHAR(255)    NOT NULL UNIQUE,         -- 토큰의 해시값만 저장
    device_info     JSONB,                                   -- { user_agent, ip_address, device_name }
    expires_at      TIMESTAMPTZ     NOT NULL,
    revoked_at      TIMESTAMPTZ,                             -- NULL이면 유효, 값이 있으면 폐기
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE refresh_tokens IS 'JWT 리프레시 토큰 테이블 - 토큰 해시 기반 관리';
COMMENT ON COLUMN refresh_tokens.token_hash IS '리프레시 토큰의 SHA-256 해시값';
COMMENT ON COLUMN refresh_tokens.device_info IS '디바이스 정보 JSON (user_agent, ip_address 등)';
COMMENT ON COLUMN refresh_tokens.revoked_at IS '토큰 폐기 시각 (NULL이면 유효)';

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id
    ON refresh_tokens (user_id);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash
    ON refresh_tokens (token_hash)
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at
    ON refresh_tokens (expires_at)
    WHERE revoked_at IS NULL;

-- =============================================================================
-- 8. mfa_devices - 다중 인증(MFA) 디바이스 테이블
-- Description: TOTP(앱), SMS 등 다중 인증 수단을 관리합니다.
--              사용자당 여러 MFA 디바이스를 등록할 수 있으며,
--              하나를 기본(is_primary)으로 설정합니다.
-- =============================================================================
CREATE TABLE IF NOT EXISTS mfa_devices (
    id                  BIGSERIAL       PRIMARY KEY,
    user_id             BIGINT          NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    type                VARCHAR(20)     NOT NULL,            -- 'totp' 또는 'sms'
    name                VARCHAR(100),                        -- 디바이스 별칭 (예: 'My Phone')
    secret_encrypted    TEXT,                                -- 암호화된 TOTP 시크릿
    phone               VARCHAR(20),                         -- SMS 인증용 전화번호
    is_primary          BOOLEAN         NOT NULL DEFAULT FALSE,
    is_verified         BOOLEAN         NOT NULL DEFAULT FALSE,
    last_used_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,

    CONSTRAINT chk_mfa_type CHECK (type IN ('totp', 'sms'))
);

COMMENT ON TABLE mfa_devices IS '다중 인증(MFA) 디바이스 테이블 - TOTP/SMS 인증 수단 관리';
COMMENT ON COLUMN mfa_devices.secret_encrypted IS '암호화된 TOTP 시크릿 키';
COMMENT ON COLUMN mfa_devices.is_primary IS '기본 MFA 디바이스 여부';

CREATE INDEX IF NOT EXISTS idx_mfa_devices_user_id
    ON mfa_devices (user_id)
    WHERE deleted_at IS NULL;

-- =============================================================================
-- 9. api_keys - API 키 관리 테이블
-- Description: 외부 시스템 연동을 위한 API 키를 관리합니다.
--              키 해시만 저장하며, prefix로 키를 식별합니다.
--              스코프(scopes)로 접근 범위를 제한합니다.
-- =============================================================================
CREATE TABLE IF NOT EXISTS api_keys (
    id              BIGSERIAL       PRIMARY KEY,
    user_id         BIGINT          NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name            VARCHAR(200)    NOT NULL,                -- API 키 이름 (예: 'Production Key')
    key_prefix      VARCHAR(10)     NOT NULL,                -- 키 식별용 접두사 (예: 'ak_3f8x')
    key_hash        VARCHAR(255)    NOT NULL UNIQUE,         -- API 키의 해시값
    scopes          JSONB           NOT NULL DEFAULT '[]'::JSONB,  -- 허용 스코프 목록
    rate_limit      INTEGER         NOT NULL DEFAULT 1000,   -- 분당 요청 제한
    expires_at      TIMESTAMPTZ,                             -- NULL이면 만료 없음
    last_used_at    TIMESTAMPTZ,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ                              -- NULL이면 유효, 값이 있으면 폐기
);

COMMENT ON TABLE api_keys IS 'API 키 관리 테이블 - 외부 시스템 연동용 키 발급/관리';
COMMENT ON COLUMN api_keys.key_prefix IS '키 식별용 접두사 (원본 키는 발급 시 1회만 표시)';
COMMENT ON COLUMN api_keys.key_hash IS 'API 키의 SHA-256 해시값';
COMMENT ON COLUMN api_keys.scopes IS '허용된 스코프 목록 (JSON 배열)';
COMMENT ON COLUMN api_keys.rate_limit IS '분당 최대 요청 수';

CREATE INDEX IF NOT EXISTS idx_api_keys_user_id
    ON api_keys (user_id);

CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash
    ON api_keys (key_hash)
    WHERE revoked_at IS NULL;

-- =============================================================================
-- 10. login_histories - 로그인 이력 테이블
-- Description: 모든 로그인 시도(성공/실패)를 기록하는 감사 로그입니다.
--              보안 모니터링, 이상 탐지, 사용자 활동 추적에 활용합니다.
--              user_id가 NULL일 수 있습니다 (존재하지 않는 계정으로 시도 시).
-- =============================================================================
CREATE TABLE IF NOT EXISTS login_histories (
    id              BIGSERIAL       PRIMARY KEY,
    user_id         BIGINT          REFERENCES users (id) ON DELETE SET NULL,  -- 실패 시 NULL 가능
    email           VARCHAR(255),                            -- 시도한 이메일 (실패 기록용)
    login_type      VARCHAR(20)     NOT NULL,                -- 'password', 'oauth', 'api_key', 'mfa'
    provider        VARCHAR(50),                             -- OAuth 제공자 (oauth 로그인 시)
    ip_address      INET,                                    -- 접속 IP 주소
    user_agent      TEXT,                                    -- 브라우저/클라이언트 정보
    success         BOOLEAN         NOT NULL,                -- 로그인 성공 여부
    failure_reason  VARCHAR(100),                            -- 실패 사유 (예: 'invalid_password', 'account_locked')
    mfa_used        BOOLEAN         NOT NULL DEFAULT FALSE,  -- MFA 사용 여부
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_login_type CHECK (login_type IN ('password', 'oauth', 'api_key', 'mfa'))
);

COMMENT ON TABLE login_histories IS '로그인 이력 테이블 - 보안 감사 로그 (성공/실패 모두 기록)';
COMMENT ON COLUMN login_histories.user_id IS '로그인 시도 사용자 (존재하지 않는 계정이면 NULL)';
COMMENT ON COLUMN login_histories.failure_reason IS '실패 사유 코드 (예: invalid_password, account_locked, mfa_failed)';

CREATE INDEX IF NOT EXISTS idx_login_histories_user_id
    ON login_histories (user_id);

CREATE INDEX IF NOT EXISTS idx_login_histories_created_at
    ON login_histories (created_at);

-- [PERFORMANCE] 사용자별 로그인 이력 조회 (최신순 정렬)
CREATE INDEX IF NOT EXISTS idx_login_histories_user_created
    ON login_histories (user_id, created_at DESC);

-- =============================================================================
-- updated_at 자동 갱신 트리거 함수
-- Description: UPDATE 시 updated_at 컬럼을 자동으로 현재 시각으로 갱신합니다.
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_updated_at_column() IS 'updated_at 컬럼 자동 갱신 트리거 함수';

-- users 테이블에 트리거 적용
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- roles 테이블에 트리거 적용
CREATE TRIGGER trg_roles_updated_at
    BEFORE UPDATE ON roles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- 기본 역할 데이터 삽입
-- Description: 시스템 초기 역할 3종 (관리자, 일반 사용자, 매니저)
-- =============================================================================
INSERT INTO roles (name, display_name, is_system) VALUES
    ('admin',   '관리자',       TRUE),
    ('user',    '일반 사용자',  TRUE),
    ('manager', '매니저',       TRUE)
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- 기본 권한 데이터 삽입
-- Description: 주요 리소스별 CRUD + admin 권한 정의
--   리소스: users, roles, permissions, api_keys
--   액션: read, write, delete, admin
-- =============================================================================
INSERT INTO permissions (resource, action, description) VALUES
    -- users 리소스 권한
    ('users',       'read',     '사용자 정보 조회'),
    ('users',       'write',    '사용자 정보 수정'),
    ('users',       'delete',   '사용자 삭제'),
    ('users',       'admin',    '사용자 관리 (전체 권한)'),
    -- roles 리소스 권한
    ('roles',       'read',     '역할 정보 조회'),
    ('roles',       'write',    '역할 생성/수정'),
    ('roles',       'delete',   '역할 삭제'),
    ('roles',       'admin',    '역할 관리 (전체 권한)'),
    -- permissions 리소스 권한
    ('permissions', 'read',     '권한 정보 조회'),
    ('permissions', 'write',    '권한 생성/수정'),
    ('permissions', 'delete',   '권한 삭제'),
    ('permissions', 'admin',    '권한 관리 (전체 권한)'),
    -- api_keys 리소스 권한
    ('api_keys',    'read',     'API 키 정보 조회'),
    ('api_keys',    'write',    'API 키 생성/수정'),
    ('api_keys',    'delete',   'API 키 삭제'),
    ('api_keys',    'admin',    'API 키 관리 (전체 권한)')
ON CONFLICT (resource, action) DO NOTHING;

-- =============================================================================
-- 기본 역할-권한 매핑 삽입
-- Description:
--   admin   → 모든 권한 (16개)
--   user    → 기본 read 권한 (users.read, roles.read, permissions.read, api_keys.read)
--   manager → read + write 권한 (8개)
-- =============================================================================

-- admin 역할: 모든 권한 부여
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
    CROSS JOIN permissions p
WHERE r.name = 'admin'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- user 역할: read 권한만 부여
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
    CROSS JOIN permissions p
WHERE r.name = 'user'
    AND p.action = 'read'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- manager 역할: read + write 권한 부여
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
    CROSS JOIN permissions p
WHERE r.name = 'manager'
    AND p.action IN ('read', 'write')
ON CONFLICT (role_id, permission_id) DO NOTHING;

COMMIT;
