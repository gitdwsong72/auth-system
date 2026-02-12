#!/bin/bash

# RSA 키 페어 생성 스크립트
# JWT RS256 알고리즘용 4096비트 RSA 키 생성

set -e  # 에러 발생 시 즉시 종료

echo "🔐 Generating RSA key pair for JWT (RS256)..."
echo ""

# 키 디렉토리 생성
KEYS_DIR="$(dirname "$0")/../keys"
mkdir -p "$KEYS_DIR"
cd "$KEYS_DIR"

# 이미 키가 존재하는 경우 백업
if [ -f "private.pem" ] || [ -f "public.pem" ]; then
    echo "⚠️  Existing keys found. Creating backup..."
    BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    [ -f "private.pem" ] && mv private.pem "$BACKUP_DIR/"
    [ -f "public.pem" ] && mv public.pem "$BACKUP_DIR/"
    echo "✅ Backup created: keys/$BACKUP_DIR/"
    echo ""
fi

# 1. Private key 생성 (4096 비트)
echo "1️⃣  Generating private key (4096 bits)..."
openssl genrsa -out private.pem 4096 2>/dev/null

# 2. Public key 추출
echo "2️⃣  Extracting public key..."
openssl rsa -in private.pem -pubout -out public.pem 2>/dev/null

# 3. 권한 설정
echo "3️⃣  Setting file permissions..."
chmod 600 private.pem  # 소유자만 읽기/쓰기
chmod 644 public.pem   # 모두 읽기, 소유자만 쓰기

echo ""
echo "✅ RSA key pair generated successfully!"
echo ""
echo "📁 Generated files:"
echo "   - keys/private.pem (4096 bits, chmod 600)"
echo "   - keys/public.pem  (public key, chmod 644)"
echo ""

# .gitignore 업데이트 (keys/ 디렉토리 제외)
GITIGNORE_FILE="$(dirname "$0")/../.gitignore"
if [ -f "$GITIGNORE_FILE" ]; then
    if ! grep -q "^keys/" "$GITIGNORE_FILE" 2>/dev/null; then
        echo "4️⃣  Updating .gitignore..."
        echo "" >> "$GITIGNORE_FILE"
        echo "# RSA keys for JWT" >> "$GITIGNORE_FILE"
        echo "keys/" >> "$GITIGNORE_FILE"
        echo "*.pem" >> "$GITIGNORE_FILE"
        echo "*.key" >> "$GITIGNORE_FILE"
        echo "✅ .gitignore updated"
    fi
fi

echo ""
echo "⚠️  SECURITY WARNINGS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. 🔒 NEVER commit keys/private.pem to Git"
echo "2. 🔒 Store private.pem securely (use secrets manager in production)"
echo "3. 🔒 Rotate keys periodically (every 6-12 months)"
echo "4. 🔒 For production, consider AWS Secrets Manager or HashiCorp Vault"
echo ""
echo "📝 Next steps:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Update .env file:"
echo "   JWT_PRIVATE_KEY_PATH=keys/private.pem"
echo "   JWT_PUBLIC_KEY_PATH=keys/public.pem"
echo ""
echo "2. For production deployment:"
echo "   - Upload keys to secrets manager"
echo "   - Set ENV=production"
echo "   - Set JWT_PRIVATE_KEY_PATH to secure location"
echo ""
echo "3. Test the keys:"
echo "   uv run uvicorn src.main:app --port 8000"
echo ""
