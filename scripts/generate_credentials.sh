#!/bin/bash

# 강력한 Credential 생성 스크립트
# DB, Redis 등의 비밀번호를 안전하게 생성

set -e

echo "🔐 강력한 Credential 생성 도구"
echo "================================"
echo ""

# 함수: 랜덤 비밀번호 생성
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

# 함수: .env 파일 업데이트
update_env() {
    local key=$1
    local value=$2
    local env_file=".env"

    if grep -q "^${key}=" "$env_file" 2>/dev/null; then
        # 기존 값 업데이트 (macOS 호환)
        sed -i '' "s|^${key}=.*|${key}=${value}|" "$env_file"
    else
        # 새로운 값 추가
        echo "${key}=${value}" >> "$env_file"
    fi
}

echo "📝 생성할 credential:"
echo "  1. JWT Secret Key"
echo "  2. PostgreSQL Password"
echo "  3. Redis Password"
echo ""

# JWT Secret Key 생성
JWT_SECRET=$(generate_password)
echo "✅ JWT Secret Key: ${JWT_SECRET:0:10}... (32자)"

# PostgreSQL Password 생성
DB_PASSWORD=$(generate_password)
echo "✅ PostgreSQL Password: ${DB_PASSWORD:0:10}... (32자)"

# Redis Password 생성
REDIS_PASSWORD=$(generate_password)
echo "✅ Redis Password: ${REDIS_PASSWORD:0:10}... (32자)"

echo ""
echo "💾 .env 파일 업데이트 중..."

# .env 파일이 없으면 생성
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "   .env 파일 생성됨 (.env.example에서 복사)"
fi

# Credential 업데이트
update_env "JWT_SECRET_KEY" "$JWT_SECRET"
update_env "DB_PRIMARY_DB_URL" "postgresql://prod_user:${DB_PASSWORD}@localhost:5433/appdb?sslmode=disable"
update_env "REDIS_URL" "redis://:${REDIS_PASSWORD}@localhost:6380/0"

echo "✅ .env 파일 업데이트 완료"
echo ""

# 백업 파일 생성
BACKUP_FILE=".env.credentials.$(date +%Y%m%d_%H%M%S).backup"
cat > "$BACKUP_FILE" <<EOF
# Generated on $(date)
# KEEP THIS FILE SECURE - DO NOT COMMIT TO GIT

JWT_SECRET_KEY=$JWT_SECRET
DB_PASSWORD=$DB_PASSWORD
REDIS_PASSWORD=$REDIS_PASSWORD

# PostgreSQL Connection String:
postgresql://prod_user:${DB_PASSWORD}@localhost:5433/appdb

# Redis Connection String:
redis://:${REDIS_PASSWORD}@localhost:6380/0
EOF

chmod 600 "$BACKUP_FILE"
echo "📄 백업 파일 생성: $BACKUP_FILE (chmod 600)"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚠️  중요 안내사항"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. 백업 파일을 안전한 곳에 보관하세요"
echo "2. docker-compose.yml도 업데이트 필요:"
echo ""
echo "   PostgreSQL:"
echo "     POSTGRES_PASSWORD: $DB_PASSWORD"
echo ""
echo "   Redis:"
echo "     --requirepass $REDIS_PASSWORD"
echo ""
echo "3. 프로덕션 배포 시:"
echo "   - AWS Secrets Manager 사용 권장"
echo "   - 환경 변수로 주입"
echo "   - .env 파일은 Git에 절대 커밋 금지"
echo ""
echo "4. Docker 재시작 필요:"
echo "   docker-compose down"
echo "   docker-compose up -d"
echo ""
