# 🚀 Auth System 즉시 배포 가이드 (현재 프로젝트용)

> **현재 프로젝트 상태**: ✅ JWT 키 준비됨, ✅ 환경 변수 설정됨, ✅ 개선 작업 완료

---

## 📋 현재 프로젝트 현황

### ✅ 준비 완료 사항
- **JWT 키**: `keys/private.pem`, `keys/public.pem` 존재
- **환경 변수**: `.env` 파일 설정됨
- **마이그레이션**: `scripts/migrations/001_add_performance_indexes.sql` 준비됨
- **보안 개선**: 모든 Phase 1-3 작업 완료 (14/14)
- **테스트**: 55개 테스트 (통합 21개 + 단위 34개)

### ⚠️ 배포 전 확인 필요
- [ ] 프로덕션 데이터베이스 (RDS 또는 자체 PostgreSQL)
- [ ] 프로덕션 Redis (ElastiCache 또는 자체 Redis with TLS)
- [ ] 도메인 및 SSL 인증서
- [ ] CORS 허용 도메인 설정

---

## 🎯 1단계: 로컬에서 즉시 실행 (1분)

현재 프로젝트를 로컬에서 바로 실행해봅니다.

```bash
# 1. 프로젝트 디렉토리로 이동
cd /Users/sktl/WF/WF01/auth-system

# 2. Docker Compose로 전체 스택 실행
docker-compose up -d

# 3. 서비스 상태 확인 (30초 대기)
sleep 30
docker-compose ps

# 4. 헬스 체크
curl http://localhost:8000/api/v1/health

# 5. 로그 확인
docker-compose logs -f auth-service
```

### 접속 URL
- **Auth API**: http://localhost:8000
- **Auth Admin**: http://localhost:5173
- **API Gateway**: http://localhost:8080
- **PostgreSQL**: localhost:5432 (devuser/devpassword)
- **Redis**: localhost:6379

### 테스트 시나리오
```bash
# 회원가입
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!",
    "username": "testuser"
  }'

# 로그인
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!"
  }'

# 토큰으로 사용자 정보 조회
TOKEN="받은_액세스_토큰"
curl http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🎯 2단계: 프로덕션 환경 변수 준비 (5분)

### 2.1 프로덕션 .env 파일 생성

```bash
# 프로덕션용 환경 변수 파일 생성
cat > .env.production << 'EOF'
# ===========================================
# 프로덕션 환경 설정
# ===========================================
ENV=production

# ===========================================
# 데이터베이스 (RDS 또는 자체 호스팅)
# ===========================================
# 예시: RDS PostgreSQL
DB_PRIMARY_DB_URL=postgresql://admin:YOUR_DB_PASSWORD@auth-db.xxxxx.ap-northeast-2.rds.amazonaws.com:5432/authdb

# 또는 자체 호스팅
# DB_PRIMARY_DB_URL=postgresql://postgres:password@your-db-server:5432/authdb

# ===========================================
# Redis (ElastiCache 또는 자체 호스팅, TLS 필수!)
# ===========================================
# ElastiCache with TLS
REDIS_URL=rediss://:YOUR_REDIS_AUTH_TOKEN@auth-redis.xxxxx.cache.amazonaws.com:6379/0

# 또는 자체 Redis with TLS
# REDIS_URL=rediss://:password@your-redis-server:6380/0

# 개발 환경에서만 TLS 없이 가능
# REDIS_URL=redis://localhost:6379/0

# ===========================================
# JWT 설정 (RS256 권장)
# ===========================================
JWT_ALGORITHM=RS256
JWT_PRIVATE_KEY_PATH=keys/private.pem
JWT_PUBLIC_KEY_PATH=keys/public.pem
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# HS256 사용 시 (권장하지 않음)
# JWT_ALGORITHM=HS256
# JWT_SECRET_KEY=$(openssl rand -base64 64)

# ===========================================
# CORS 설정 (프로덕션 도메인만!)
# ===========================================
CORS_ALLOWED_ORIGINS=["https://yourdomain.com","https://app.yourdomain.com","https://admin.yourdomain.com"]

# ===========================================
# Trusted Host 보안
# ===========================================
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com,*.yourdomain.com

# ===========================================
# OAuth 2.0 (선택사항)
# ===========================================
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
KAKAO_CLIENT_ID=
KAKAO_CLIENT_SECRET=
EOF

# 권한 설정 (중요!)
chmod 600 .env.production
```

### 2.2 실제 값으로 교체하기

```bash
# 강력한 비밀번호 생성
openssl rand -base64 32

# Redis Auth Token 생성
openssl rand -base64 48

# JWT Secret 생성 (HS256 사용 시)
openssl rand -base64 64
```

**⚠️ 보안 주의사항**:
- `.env.production` 파일은 **절대 Git에 커밋하지 마세요**
- 프로덕션 비밀번호는 **최소 32자 이상**
- Redis는 **반드시 TLS 사용** (`rediss://`)

---

## 🎯 3단계: AWS 배포 (권장 방법)

### 방법 A: AWS ECS Fargate (가장 간편, 권장)

#### A-1. 인프라 준비 (AWS Console 또는 CLI)

**1. RDS PostgreSQL 생성**
```bash
# AWS Console에서:
# 1. RDS → 데이터베이스 생성
# 2. PostgreSQL 16 선택
# 3. 인스턴스: db.t3.micro (개발), db.t3.small (프로덕션)
# 4. 스토리지: 20GB SSD
# 5. 자동 백업: 7일
# 6. 퍼블릭 액세스: 아니요 (VPC 내부만)

# CLI로 생성:
aws rds create-db-instance \
  --db-instance-identifier auth-system-db \
  --db-instance-class db.t3.small \
  --engine postgres \
  --engine-version 16.1 \
  --master-username admin \
  --master-user-password "YOUR_STRONG_PASSWORD" \
  --allocated-storage 20 \
  --backup-retention-period 7 \
  --storage-encrypted \
  --region ap-northeast-2

# 엔드포인트 확인
aws rds describe-db-instances \
  --db-instance-identifier auth-system-db \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text
```

**2. ElastiCache Redis 생성**
```bash
# AWS Console에서:
# 1. ElastiCache → Redis 클러스터 생성
# 2. 클러스터 모드: 비활성화
# 3. 노드 타입: cache.t3.micro
# 4. 복제본: 1개 (고가용성)
# 5. 전송 중 암호화: 활성화 (TLS 필수!)
# 6. 인증 토큰: 생성

# CLI로 생성:
aws elasticache create-replication-group \
  --replication-group-id auth-system-redis \
  --replication-group-description "Auth System Redis" \
  --engine redis \
  --cache-node-type cache.t3.micro \
  --num-cache-clusters 2 \
  --transit-encryption-enabled \
  --auth-token "YOUR_REDIS_TOKEN_MIN_16_CHARS" \
  --region ap-northeast-2

# 엔드포인트 확인
aws elasticache describe-replication-groups \
  --replication-group-id auth-system-redis \
  --query 'ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint.Address'
```

**3. 데이터베이스 초기화**
```bash
# RDS 엔드포인트로 접속
export DB_HOST="auth-system-db.xxxxx.ap-northeast-2.rds.amazonaws.com"
export DB_PASSWORD="YOUR_DB_PASSWORD"

# 초기 스키마 적용
psql -h $DB_HOST -U admin -d postgres -c "CREATE DATABASE authdb;"
psql -h $DB_HOST -U admin -d authdb -f auth-service/scripts/init.sql

# 마이그레이션 적용
psql -h $DB_HOST -U admin -d authdb -f auth-service/scripts/migrations/001_add_performance_indexes.sql

# 확인
psql -h $DB_HOST -U admin -d authdb -c "\dt"
psql -h $DB_HOST -U admin -d authdb -c "\di"
```

#### A-2. Docker 이미지 빌드 및 ECR 푸시

```bash
# 1. ECR 저장소 생성
aws ecr create-repository \
  --repository-name auth-service \
  --region ap-northeast-2

# 2. ECR 로그인
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.ap-northeast-2.amazonaws.com

# YOUR_ACCOUNT_ID 확인:
aws sts get-caller-identity --query Account --output text

# 3. 이미지 빌드
cd auth-service
docker build -t auth-service:latest .

# 4. 태그 및 푸시
export ECR_REGISTRY="YOUR_ACCOUNT_ID.dkr.ecr.ap-northeast-2.amazonaws.com"
docker tag auth-service:latest $ECR_REGISTRY/auth-service:latest
docker push $ECR_REGISTRY/auth-service:latest

# 5. 확인
aws ecr describe-images --repository-name auth-service --region ap-northeast-2
```

#### A-3. Secrets Manager에 민감 정보 저장

```bash
# 1. DB URL 저장
aws secretsmanager create-secret \
  --name auth-service/db-url \
  --secret-string "postgresql://admin:YOUR_PASSWORD@auth-system-db.xxxxx.rds.amazonaws.com:5432/authdb" \
  --region ap-northeast-2

# 2. Redis URL 저장 (TLS 필수!)
aws secretsmanager create-secret \
  --name auth-service/redis-url \
  --secret-string "rediss://:YOUR_REDIS_TOKEN@auth-system-redis.xxxxx.cache.amazonaws.com:6379/0" \
  --region ap-northeast-2

# 3. JWT Private Key 저장
aws secretsmanager create-secret \
  --name auth-service/jwt-private-key \
  --secret-string file://keys/private.pem \
  --region ap-northeast-2

# 4. JWT Public Key 저장
aws secretsmanager create-secret \
  --name auth-service/jwt-public-key \
  --secret-string file://keys/public.pem \
  --region ap-northeast-2

# 5. ARN 확인
aws secretsmanager list-secrets --region ap-northeast-2 | grep auth-service
```

#### A-4. ECS 클러스터 및 서비스 생성

**ECS 태스크 정의 파일 생성**: `ecs-task-definition.json`
```json
{
  "family": "auth-service-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "auth-service",
      "image": "YOUR_ACCOUNT_ID.dkr.ecr.ap-northeast-2.amazonaws.com/auth-service:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENV",
          "value": "production"
        },
        {
          "name": "JWT_ALGORITHM",
          "value": "RS256"
        },
        {
          "name": "CORS_ALLOWED_ORIGINS",
          "value": "[\"https://yourdomain.com\",\"https://app.yourdomain.com\"]"
        },
        {
          "name": "ALLOWED_HOSTS",
          "value": "yourdomain.com,api.yourdomain.com"
        }
      ],
      "secrets": [
        {
          "name": "DB_PRIMARY_DB_URL",
          "valueFrom": "arn:aws:secretsmanager:ap-northeast-2:YOUR_ACCOUNT_ID:secret:auth-service/db-url"
        },
        {
          "name": "REDIS_URL",
          "valueFrom": "arn:aws:secretsmanager:ap-northeast-2:YOUR_ACCOUNT_ID:secret:auth-service/redis-url"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-create-group": "true",
          "awslogs-group": "/ecs/auth-service",
          "awslogs-region": "ap-northeast-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/api/v1/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

**배포 실행**:
```bash
# 1. ECS 클러스터 생성
aws ecs create-cluster \
  --cluster-name auth-system-cluster \
  --region ap-northeast-2

# 2. 태스크 정의 등록
aws ecs register-task-definition \
  --cli-input-json file://ecs-task-definition.json \
  --region ap-northeast-2

# 3. Application Load Balancer 생성 (AWS Console 권장)
# ALB → 로드 밸런서 생성 → Application Load Balancer
# 리스너: HTTP:80 (HTTPS:443으로 리디렉션), HTTPS:443
# SSL 인증서: ACM에서 발급 또는 업로드

# 4. 타겟 그룹 생성
aws elbv2 create-target-group \
  --name auth-service-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxxxx \
  --target-type ip \
  --health-check-path /api/v1/health \
  --health-check-interval-seconds 30 \
  --region ap-northeast-2

# 5. ECS 서비스 생성
aws ecs create-service \
  --cluster auth-system-cluster \
  --service-name auth-service \
  --task-definition auth-service-task \
  --desired-count 2 \
  --launch-type FARGATE \
  --platform-version LATEST \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxx,subnet-yyyyy],securityGroups=[sg-xxxxx],assignPublicIp=ENABLED}" \
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:ap-northeast-2:YOUR_ACCOUNT_ID:targetgroup/auth-service-tg/xxxxx,containerName=auth-service,containerPort=8000 \
  --region ap-northeast-2

# 6. Auto Scaling 설정
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/auth-system-cluster/auth-service \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10 \
  --region ap-northeast-2

# 7. 배포 확인
aws ecs describe-services \
  --cluster auth-system-cluster \
  --services auth-service \
  --region ap-northeast-2

# 8. 로그 확인
aws logs tail /ecs/auth-service --follow --region ap-northeast-2
```

---

### 방법 B: EC2 단일 서버 (간단, 저렴)

#### B-1. EC2 인스턴스 생성 및 설정

```bash
# 1. EC2 인스턴스 시작 (t3.small, 2GB RAM 권장)
aws ec2 run-instances \
  --image-id ami-0c9c942bd7bf113a2 \
  --instance-type t3.small \
  --key-name your-keypair \
  --security-group-ids sg-xxxxx \
  --subnet-id subnet-xxxxx \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=auth-service-prod}]' \
  --region ap-northeast-2

# 2. Elastic IP 할당 (고정 IP)
aws ec2 allocate-address --region ap-northeast-2
aws ec2 associate-address \
  --instance-id i-xxxxx \
  --allocation-id eipalloc-xxxxx \
  --region ap-northeast-2

# 3. EC2 접속
ssh -i your-keypair.pem ec2-user@YOUR_ELASTIC_IP
```

#### B-2. 서버에 Docker 설치

```bash
# EC2 서버 내부에서 실행:

# 1. 시스템 업데이트
sudo yum update -y

# 2. Docker 설치
sudo yum install docker -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -a -G docker ec2-user

# 3. Docker Compose 설치
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 4. 재로그인 (그룹 변경 적용)
exit
ssh -i your-keypair.pem ec2-user@YOUR_ELASTIC_IP

# 5. Docker 확인
docker --version
docker-compose --version
```

#### B-3. 프로젝트 배포

```bash
# 1. Git 설치 및 프로젝트 클론
sudo yum install git -y
git clone https://github.com/your-org/auth-system.git
cd auth-system

# 2. 프로덕션 환경 변수 설정
cat > .env.production << 'EOF'
ENV=production

# RDS 엔드포인트 (위에서 생성한 것)
DB_PRIMARY_DB_URL=postgresql://admin:YOUR_PASSWORD@auth-system-db.xxxxx.rds.amazonaws.com:5432/authdb

# ElastiCache Redis (TLS)
REDIS_URL=rediss://:YOUR_TOKEN@auth-system-redis.xxxxx.cache.amazonaws.com:6379/0

# JWT 설정
JWT_ALGORITHM=RS256
JWT_PRIVATE_KEY_PATH=keys/private.pem
JWT_PUBLIC_KEY_PATH=keys/public.pem

# CORS
CORS_ALLOWED_ORIGINS=["https://yourdomain.com"]

# Allowed Hosts
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
EOF

chmod 600 .env.production

# 3. JWT 키 복사 (로컬에서 서버로)
# 로컬 터미널에서:
# scp -i your-keypair.pem -r keys/ ec2-user@YOUR_ELASTIC_IP:~/auth-system/

# 4. Docker Compose 프로덕션 파일 생성
cat > docker-compose.prod.yml << 'EOF'
version: '3.8'

services:
  auth-service:
    build:
      context: ./auth-service
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env.production
    volumes:
      - ./keys:/app/keys:ro
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - auth-service
    restart: always
EOF

# 5. Nginx 설정
mkdir -p nginx/ssl
cat > nginx/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream auth_service {
        server auth-service:8000;
    }

    # HTTP → HTTPS 리디렉션
    server {
        listen 80;
        server_name api.yourdomain.com;
        return 301 https://$server_name$request_uri;
    }

    # HTTPS
    server {
        listen 443 ssl http2;
        server_name api.yourdomain.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # 보안 헤더 (이미 FastAPI에서 추가되지만 이중 보호)
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "DENY" always;

        location / {
            proxy_pass http://auth_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # 타임아웃 설정
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # Health check endpoint
        location /api/v1/health {
            proxy_pass http://auth_service;
            access_log off;
        }
    }
}
EOF

# 6. SSL 인증서 발급 (Let's Encrypt)
sudo yum install certbot -y
sudo systemctl stop nginx  # nginx가 실행 중이면 중지

# Standalone 모드로 인증서 발급
sudo certbot certonly --standalone \
  -d api.yourdomain.com \
  --email your-email@example.com \
  --agree-tos \
  --non-interactive

# 인증서 복사
sudo cp /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/api.yourdomain.com/privkey.pem nginx/ssl/
sudo chown ec2-user:ec2-user nginx/ssl/*.pem

# 7. 서비스 시작
docker-compose -f docker-compose.prod.yml up -d

# 8. 로그 확인
docker-compose -f docker-compose.prod.yml logs -f

# 9. 헬스 체크
curl http://YOUR_ELASTIC_IP:8000/api/v1/health
curl https://api.yourdomain.com/api/v1/health
```

#### B-4. 자동 시작 설정

```bash
# Systemd 서비스 등록
sudo cat > /etc/systemd/system/auth-system.service << EOF
[Unit]
Description=Auth System
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/ec2-user/auth-system
ExecStart=/usr/local/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.prod.yml down
User=ec2-user

[Install]
WantedBy=multi-user.target
EOF

# 서비스 활성화
sudo systemctl daemon-reload
sudo systemctl enable auth-system
sudo systemctl start auth-system

# 상태 확인
sudo systemctl status auth-system

# SSL 자동 갱신 설정
sudo crontab -e
# 추가:
0 3 * * * certbot renew --quiet --deploy-hook "systemctl restart auth-system"
```

---

## 🎯 4단계: 배포 후 검증 (필수!)

### 4.1 헬스 체크
```bash
# 기본 헬스 체크
curl https://api.yourdomain.com/api/v1/health

# 예상 응답:
# {
#   "status": "healthy",
#   "version": "1.0.0",
#   "environment": "production"
# }
```

### 4.2 보안 헤더 검증
```bash
curl -I https://api.yourdomain.com/api/v1/health

# 확인 사항:
# ✓ Strict-Transport-Security: max-age=31536000; includeSubDomains
# ✓ X-Content-Type-Options: nosniff
# ✓ X-Frame-Options: DENY
# ✓ X-XSS-Protection: 1; mode=block
```

### 4.3 인증 플로우 테스트
```bash
# 1. 회원가입
curl -X POST https://api.yourdomain.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "prodtest@example.com",
    "password": "SecurePass123!",
    "username": "produser"
  }'

# 2. 로그인
curl -X POST https://api.yourdomain.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "prodtest@example.com",
    "password": "SecurePass123!"
  }'

# 3. 토큰으로 사용자 정보 조회
TOKEN="받은_액세스_토큰"
curl https://api.yourdomain.com/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN"
```

### 4.4 데이터베이스 인덱스 확인
```bash
# RDS 접속
psql -h auth-system-db.xxxxx.rds.amazonaws.com -U admin -d authdb

# 인덱스 확인
\di

# 쿼리 성능 확인
EXPLAIN ANALYZE
SELECT * FROM users
WHERE email = 'prodtest@example.com'
AND deleted_at IS NULL;

# 인덱스가 사용되는지 확인:
# Index Scan using idx_users_email_active
```

### 4.5 모니터링 설정

**CloudWatch 대시보드** (AWS Console):
```bash
# 1. CloudWatch → 대시보드 생성
# 2. 위젯 추가:
#    - ECS CPU/Memory 사용률
#    - ALB Request Count
#    - RDS 연결 수
#    - ElastiCache Hit Rate

# 3. 알람 설정:
aws cloudwatch put-metric-alarm \
  --alarm-name auth-service-high-cpu \
  --alarm-description "Auth Service CPU > 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --alarm-actions arn:aws:sns:ap-northeast-2:YOUR_ACCOUNT_ID:alerts
```

---

## 🔍 트러블슈팅

### 문제 1: "could not connect to server" (DB 연결 실패)

**증상**:
```
sqlalchemy.exc.OperationalError: (psycopg.OperationalError) could not connect to server
```

**해결**:
```bash
# 1. RDS 보안 그룹 확인
aws ec2 describe-security-groups --group-ids sg-xxxxx

# 인바운드 규칙에 다음 추가:
# Type: PostgreSQL
# Port: 5432
# Source: ECS 태스크의 보안 그룹 또는 VPC CIDR

# 2. RDS 엔드포인트 확인
aws rds describe-db-instances \
  --db-instance-identifier auth-system-db \
  --query 'DBInstances[0].Endpoint.Address'

# 3. 연결 테스트
psql -h YOUR_RDS_ENDPOINT -U admin -d authdb -c "SELECT 1;"
```

### 문제 2: "Error connecting to Redis"

**증상**:
```
redis.exceptions.ConnectionError: Error 111 connecting to redis:6379. Connection refused.
```

**해결**:
```bash
# 1. ElastiCache 엔드포인트 확인
aws elasticache describe-replication-groups \
  --replication-group-id auth-system-redis

# 2. TLS 연결 확인 (rediss:// 사용!)
echo $REDIS_URL  # rediss://로 시작해야 함

# 3. Redis CLI로 연결 테스트
redis-cli --tls -h YOUR_REDIS_ENDPOINT -a YOUR_AUTH_TOKEN ping
# 응답: PONG

# 4. 보안 그룹 확인 (6379 포트 허용)
```

### 문제 3: "Token validation failed"

**증상**:
```
401 Unauthorized: Invalid token
```

**해결**:
```bash
# 1. JWT 키 파일 확인
ls -la keys/
# private.pem과 public.pem이 있어야 함

# 2. ECS 태스크 정의에서 키가 마운트되었는지 확인
# Secrets Manager를 사용하는 경우 ARN 확인

# 3. JWT_ALGORITHM 확인
# RS256 사용 시 키 파일 필요
# HS256 사용 시 JWT_SECRET_KEY 필요

# 4. 로그 확인
docker-compose logs auth-service | grep -i jwt
# 또는
aws logs tail /ecs/auth-service --follow | grep -i jwt
```

### 문제 4: CORS 오류

**증상**:
```
Access to XMLHttpRequest has been blocked by CORS policy
```

**해결**:
```bash
# 1. CORS_ALLOWED_ORIGINS 확인
echo $CORS_ALLOWED_ORIGINS

# 2. 올바른 형식 확인 (JSON 배열):
# CORS_ALLOWED_ORIGINS=["https://yourdomain.com","https://app.yourdomain.com"]

# 3. 프로토콜 확인 (http vs https)
# 프로덕션에서는 https만 사용

# 4. 환경 변수 업데이트 후 재시작
docker-compose -f docker-compose.prod.yml restart auth-service
# 또는
aws ecs update-service \
  --cluster auth-system-cluster \
  --service auth-service \
  --force-new-deployment
```

---

## 📊 비용 예상 (AWS 기준, 서울 리전)

### 최소 구성 (소규모 프로젝트)
| 서비스 | 스펙 | 월 예상 비용 |
|--------|------|-------------|
| EC2 (t3.small) | 2vCPU, 2GB RAM | ~$15 |
| RDS (db.t3.micro) | 1vCPU, 1GB RAM, 20GB SSD | ~$20 |
| ElastiCache (cache.t3.micro) | 1vCPU, 0.5GB RAM | ~$12 |
| ELB (Application Load Balancer) | - | ~$20 |
| 데이터 전송 | 1TB 아웃바운드 | ~$10 |
| **총계** | | **~$77/월** |

### 권장 구성 (중규모 프로젝트)
| 서비스 | 스펙 | 월 예상 비용 |
|--------|------|-------------|
| ECS Fargate | 2 tasks, 0.5vCPU, 1GB RAM | ~$25 |
| RDS (db.t3.small) | 2vCPU, 2GB RAM, Multi-AZ | ~$90 |
| ElastiCache | cache.t3.small, 복제본 1개 | ~$50 |
| ALB | - | ~$20 |
| 데이터 전송 | 5TB | ~$50 |
| **총계** | | **~$235/월** |

---

## ✅ 배포 체크리스트

배포 전 마지막 확인:

### 보안
- [ ] JWT Secret/키 강력하게 설정됨
- [ ] Redis TLS 활성화됨 (`rediss://`)
- [ ] RDS 암호화 활성화됨
- [ ] 보안 그룹 최소 권한 원칙 적용
- [ ] Secrets Manager/환경 변수로 비밀 정보 관리
- [ ] CORS 도메인 프로덕션만 허용
- [ ] ALLOWED_HOSTS 설정됨

### 데이터베이스
- [ ] 초기 스키마 적용됨 (`init.sql`)
- [ ] 마이그레이션 적용됨 (`001_add_performance_indexes.sql`)
- [ ] 인덱스 생성 확인됨
- [ ] 자동 백업 활성화됨 (7일 이상)

### 모니터링
- [ ] CloudWatch 로그 설정됨
- [ ] 헬스 체크 엔드포인트 작동 확인
- [ ] 알람 설정 (CPU, Memory, Error Rate)

### 성능
- [ ] Auto Scaling 설정됨 (최소 2개 인스턴스)
- [ ] ALB/ELB 연결됨
- [ ] Redis 캐싱 작동 확인

### SSL/도메인
- [ ] SSL 인증서 발급/업로드됨
- [ ] DNS A 레코드 설정됨 (도메인 → ELB/IP)
- [ ] HTTPS 리디렉션 설정됨

---

## 🎓 다음 단계

배포가 완료되면:

1. **모니터링 설정**
   - CloudWatch 대시보드 구성
   - Slack/이메일 알람 연동
   - 에러 추적 (Sentry 등)

2. **CI/CD 파이프라인**
   - GitHub Actions 또는 GitLab CI
   - 자동 테스트 → 빌드 → 배포

3. **백업 전략**
   - RDS 자동 스냅샷 (7일)
   - 중요 데이터 S3 백업

4. **성능 최적화**
   - Redis 캐시 Hit Rate 모니터링
   - 슬로우 쿼리 분석
   - APM 도구 도입 (New Relic, DataDog 등)

---

## 📞 지원

문제 발생 시:
1. 로그 확인: `docker-compose logs -f` 또는 `aws logs tail`
2. 헬스 체크: `/api/v1/health` 엔드포인트
3. 데이터베이스 연결: `psql` 명령으로 직접 연결 테스트
4. Redis 연결: `redis-cli` 명령으로 테스트

**긴급 롤백**:
```bash
# ECS
aws ecs update-service \
  --cluster auth-system-cluster \
  --service auth-service \
  --task-definition auth-service-task:PREVIOUS_REVISION

# EC2 Docker Compose
docker-compose -f docker-compose.prod.yml down
git checkout PREVIOUS_COMMIT
docker-compose -f docker-compose.prod.yml up -d
```
