# 🚀 Auth System 배포 가이드

## 목차
1. [로컬 개발 환경](#1-로컬-개발-환경-docker-compose)
2. [로컬 환경 (수동 설치)](#2-로컬-환경-수동-설치)
3. [AWS 배포](#3-aws-배포)
   - [3.1 ECS + Fargate (권장)](#31-aws-ecs--fargate-권장)
   - [3.2 EC2 (단일 서버)](#32-aws-ec2-단일-서버)
   - [3.3 EKS (Kubernetes)](#33-aws-eks-kubernetes)
4. [기타 클라우드](#4-기타-클라우드)
5. [배포 후 검증](#5-배포-후-검증)
6. [트러블슈팅](#6-트러블슈팅)

---

## 배포 전 체크리스트

### 필수 사전 작업
- [ ] 데이터베이스 마이그레이션 적용됨
- [ ] JWT 키 생성 완료 (RS256) 또는 강력한 Secret 설정 (HS256)
- [ ] 환경 변수 설정 완료
- [ ] 프로덕션용 Redis URL 확보 (TLS 필수)
- [ ] CORS 도메인 설정 확인
- [ ] 보안 그룹/방화벽 규칙 준비

### 마이그레이션 적용
```bash
# 로컬에서 먼저 테스트
psql -h localhost -p 5432 -U postgres -d authdb \
  -f auth-service/scripts/migrations/001_add_performance_indexes.sql

# 프로덕션 DB에 적용 (신중하게!)
psql -h your-prod-db.rds.amazonaws.com -U admin -d authdb \
  -f auth-service/scripts/migrations/001_add_performance_indexes.sql
```

### JWT 키 생성
```bash
# RS256 (권장): RSA 키 쌍 생성
mkdir -p keys
ssh-keygen -t rsa -b 4096 -m PEM -f keys/jwt_key -N ""
openssl rsa -in keys/jwt_key -pubout -outform PEM -out keys/public.pem
mv keys/jwt_key keys/private.pem

# 또는 HS256: 강력한 시크릿 생성
openssl rand -base64 64
```

---

## 1. 로컬 개발 환경 (Docker Compose)

### 1.1 빠른 시작
```bash
# 1. 저장소 클론
cd /Users/sktl/WF/WF01/auth-system

# 2. 환경 변수 설정
cp .env.example .env
nano .env  # 필요한 값 수정

# 3. JWT 키 생성 (아직 없다면)
mkdir -p keys
ssh-keygen -t rsa -b 4096 -m PEM -f keys/jwt_key -N ""
openssl rsa -in keys/jwt_key -pubout -outform PEM -out keys/public.pem
mv keys/jwt_key keys/private.pem

# 4. Docker Compose 실행
docker-compose up -d

# 5. 로그 확인
docker-compose logs -f auth-service

# 6. 헬스 체크
curl http://localhost:8000/api/v1/health
```

### 1.2 서비스별 접속 정보
| 서비스 | URL | 포트 | 비고 |
|--------|-----|------|------|
| Auth Service API | http://localhost:8000 | 8000 | FastAPI |
| Auth Admin | http://localhost:5173 | 5173 | React |
| API Gateway | http://localhost:8080 | 8080 | Kong |
| PostgreSQL | localhost:5432 | 5432 | devuser/devpassword |
| Redis | localhost:6379 | 6379 | - |

### 1.3 개발 모드 특징
- ✅ **Hot Reload**: 소스 코드 변경 시 자동 재시작
- ✅ **SQL 자동 리로드**: SQL 파일 수정 시 자동 반영 (캐시 삭제 불필요!)
- ✅ **볼륨 마운트**: `./auth-service/src` → `/app/src`
- ✅ **디버깅**: 로그 레벨 DEBUG

### 1.4 유용한 명령어
```bash
# 서비스 재시작
docker-compose restart auth-service

# 로그 실시간 확인
docker-compose logs -f auth-service

# 컨테이너 접속
docker-compose exec auth-service bash

# DB 접속
docker-compose exec auth-db psql -U devuser -d authdb

# 전체 종료 및 데이터 삭제
docker-compose down -v
```

---

## 2. 로컬 환경 (수동 설치)

Docker 없이 로컬에서 직접 실행하는 방법입니다.

### 2.1 PostgreSQL 설치 및 설정
```bash
# macOS (Homebrew)
brew install postgresql@16
brew services start postgresql@16

# 데이터베이스 생성
createdb authdb
psql authdb < auth-service/scripts/init.sql

# 마이그레이션 적용
psql authdb < auth-service/scripts/migrations/001_add_performance_indexes.sql
```

### 2.2 Redis 설치 및 실행
```bash
# macOS
brew install redis
brew services start redis

# 또는 수동 실행
redis-server
```

### 2.3 Python 환경 설정
```bash
cd auth-service

# Python 3.11+ 확인
python --version

# uv 설치 (권장)
pip install uv

# 의존성 설치
uv pip install -e .

# 또는 pip 사용
pip install -e .
```

### 2.4 환경 변수 설정
```bash
# auth-service/.env 파일 생성
cat > .env << EOF
ENV=development

# 로컬 데이터베이스
DB_PRIMARY_DB_URL=postgresql://devuser:devpassword@localhost:5432/authdb?sslmode=disable

# 로컬 Redis
REDIS_URL=redis://localhost:6379/0

# JWT 설정
JWT_PRIVATE_KEY_PATH=../keys/private.pem
JWT_PUBLIC_KEY_PATH=../keys/public.pem
JWT_ALGORITHM=RS256

# CORS
CORS_ALLOWED_ORIGINS=["http://localhost:5173","http://localhost:3000"]
EOF
```

### 2.5 서버 실행
```bash
cd auth-service

# 개발 모드 (hot reload)
uvicorn src.main:app --reload --port 8000

# 또는 uv 사용
uv run uvicorn src.main:app --reload --port 8000
```

### 2.6 테스트 실행
```bash
# 전체 테스트
pytest tests/ -v

# 커버리지 포함
pytest tests/ -v --cov=src --cov-report=html

# 특정 테스트만
pytest tests/unit/test_jwt_handler.py -v
```

---

## 3. AWS 배포

### 3.1 AWS ECS + Fargate (권장)

**장점**: 서버리스, Auto Scaling, 관리 간편
**비용**: 중간 (실행 시간 기반)

#### 3.1.1 인프라 준비

**A. VPC 및 네트워크**
```bash
# AWS CLI로 VPC 생성
aws ec2 create-vpc --cidr-block 10.0.0.0/16 --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=auth-system-vpc}]'

# 서브넷 생성 (2개 AZ)
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.1.0/24 --availability-zone ap-northeast-2a
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.2.0/24 --availability-zone ap-northeast-2c
```

**B. RDS (PostgreSQL) 생성**
```bash
# RDS PostgreSQL 인스턴스 생성
aws rds create-db-instance \
  --db-instance-identifier auth-system-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 16.1 \
  --master-username admin \
  --master-user-password "YourStrongPassword123!" \
  --allocated-storage 20 \
  --vpc-security-group-ids sg-xxx \
  --db-subnet-group-name your-subnet-group \
  --backup-retention-period 7 \
  --storage-encrypted

# 엔드포인트 확인
aws rds describe-db-instances --db-instance-identifier auth-system-db \
  --query 'DBInstances[0].Endpoint.Address' --output text
```

**C. ElastiCache (Redis) 생성**
```bash
# Redis 클러스터 생성 (TLS 활성화)
aws elasticache create-replication-group \
  --replication-group-id auth-system-redis \
  --replication-group-description "Auth System Redis" \
  --engine redis \
  --cache-node-type cache.t3.micro \
  --num-cache-clusters 2 \
  --transit-encryption-enabled \
  --auth-token "YourRedisAuthToken123!" \
  --security-group-ids sg-xxx \
  --cache-subnet-group-name your-cache-subnet

# 엔드포인트 확인
aws elasticache describe-replication-groups \
  --replication-group-id auth-system-redis \
  --query 'ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint.Address'
```

#### 3.1.2 Docker 이미지 빌드 및 ECR 푸시

```bash
# ECR 저장소 생성
aws ecr create-repository --repository-name auth-service

# ECR 로그인
aws ecr get-login-password --region ap-northeast-2 | \
  docker login --username AWS --password-stdin 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com

# 이미지 빌드
cd auth-service
docker build -t auth-service:latest .

# 태그 및 푸시
docker tag auth-service:latest 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/auth-service:latest
docker push 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/auth-service:latest
```

#### 3.1.3 ECS 태스크 정의

`ecs-task-definition.json` 파일 생성:
```json
{
  "family": "auth-service-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::123456789012:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "auth-service",
      "image": "123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/auth-service:latest",
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
        }
      ],
      "secrets": [
        {
          "name": "DB_PRIMARY_DB_URL",
          "valueFrom": "arn:aws:secretsmanager:ap-northeast-2:123456789012:secret:auth-db-url"
        },
        {
          "name": "REDIS_URL",
          "valueFrom": "arn:aws:secretsmanager:ap-northeast-2:123456789012:secret:redis-url"
        },
        {
          "name": "JWT_SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:ap-northeast-2:123456789012:secret:jwt-secret"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
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

```bash
# 태스크 정의 등록
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json
```

#### 3.1.4 Secrets Manager에 비밀 값 저장

```bash
# DB URL 저장
aws secretsmanager create-secret \
  --name auth-db-url \
  --secret-string "postgresql://admin:YourPassword@auth-system-db.xxx.ap-northeast-2.rds.amazonaws.com:5432/authdb"

# Redis URL 저장 (TLS 사용)
aws secretsmanager create-secret \
  --name redis-url \
  --secret-string "rediss://:YourRedisAuthToken@auth-system-redis.xxx.cache.amazonaws.com:6379/0"

# JWT Secret 저장
aws secretsmanager create-secret \
  --name jwt-secret \
  --secret-string "$(openssl rand -base64 64)"

# JWT RSA 키 저장 (RS256 사용 시)
aws secretsmanager create-secret \
  --name jwt-private-key \
  --secret-string file://keys/private.pem

aws secretsmanager create-secret \
  --name jwt-public-key \
  --secret-string file://keys/public.pem
```

#### 3.1.5 ECS 서비스 생성

```bash
# Application Load Balancer 생성
aws elbv2 create-load-balancer \
  --name auth-service-alb \
  --subnets subnet-xxx subnet-yyy \
  --security-groups sg-xxx \
  --scheme internet-facing \
  --type application

# 타겟 그룹 생성
aws elbv2 create-target-group \
  --name auth-service-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxx \
  --target-type ip \
  --health-check-path /api/v1/health

# ECS 서비스 생성
aws ecs create-service \
  --cluster auth-system-cluster \
  --service-name auth-service \
  --task-definition auth-service-task \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:ap-northeast-2:123456789012:targetgroup/auth-service-tg/xxx,containerName=auth-service,containerPort=8000
```

#### 3.1.6 Auto Scaling 설정

```bash
# Auto Scaling 정책 등록
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/auth-system-cluster/auth-service \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10

# CPU 기반 스케일링
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/auth-system-cluster/auth-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name cpu-scaling-policy \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file://scaling-policy.json
```

`scaling-policy.json`:
```json
{
  "TargetValue": 70.0,
  "PredefinedMetricSpecification": {
    "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
  },
  "ScaleInCooldown": 300,
  "ScaleOutCooldown": 60
}
```

---

### 3.2 AWS EC2 (단일 서버)

**장점**: 간단, 저렴, 완전한 제어
**단점**: 수동 관리 필요, 단일 장애점

#### 3.2.1 EC2 인스턴스 생성

```bash
# EC2 인스턴스 시작
aws ec2 run-instances \
  --image-id ami-0c9c942bd7bf113a2 \  # Amazon Linux 2023
  --instance-type t3.small \
  --key-name your-keypair \
  --security-group-ids sg-xxx \
  --subnet-id subnet-xxx \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=auth-service}]'

# Elastic IP 할당
aws ec2 allocate-address
aws ec2 associate-address --instance-id i-xxx --public-ip x.x.x.x
```

#### 3.2.2 서버 설정

```bash
# EC2 접속
ssh -i your-keypair.pem ec2-user@x.x.x.x

# Docker 설치
sudo yum update -y
sudo yum install docker -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -a -G docker ec2-user

# Docker Compose 설치
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Git 설치 및 저장소 클론
sudo yum install git -y
git clone https://github.com/your-org/auth-system.git
cd auth-system
```

#### 3.2.3 프로덕션 설정

```bash
# 환경 변수 설정
cat > .env << EOF
ENV=production

# RDS 엔드포인트
DB_PRIMARY_DB_URL=postgresql://admin:password@auth-db.xxx.rds.amazonaws.com:5432/authdb

# ElastiCache 엔드포인트 (TLS)
REDIS_URL=rediss://:authtoken@auth-redis.xxx.cache.amazonaws.com:6379/0

# JWT 설정
JWT_SECRET_KEY=$(openssl rand -base64 64)
JWT_ALGORITHM=HS256

# CORS
CORS_ALLOWED_ORIGINS=["https://yourdomain.com","https://app.yourdomain.com"]

# Allowed Hosts
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
EOF

# 권한 설정
chmod 600 .env
```

#### 3.2.4 Docker Compose 프로덕션 설정

`docker-compose.prod.yml` 생성:
```yaml
version: '3.8'

services:
  auth-service:
    build:
      context: ./auth-service
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
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
      start_period: 40s

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
```

#### 3.2.5 Nginx 리버스 프록시 설정

`nginx/nginx.conf`:
```nginx
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

        location / {
            proxy_pass http://auth_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

#### 3.2.6 SSL 인증서 설정 (Let's Encrypt)

```bash
# Certbot 설치
sudo yum install certbot -y

# SSL 인증서 발급
sudo certbot certonly --standalone -d api.yourdomain.com

# 인증서 복사
sudo mkdir -p nginx/ssl
sudo cp /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/api.yourdomain.com/privkey.pem nginx/ssl/

# 자동 갱신 설정
sudo crontab -e
# 추가: 0 3 * * * certbot renew --quiet && docker-compose restart nginx
```

#### 3.2.7 실행 및 모니터링

```bash
# 서비스 시작
docker-compose -f docker-compose.prod.yml up -d

# 로그 확인
docker-compose -f docker-compose.prod.yml logs -f

# 상태 확인
docker-compose -f docker-compose.prod.yml ps

# 자동 시작 설정
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

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable auth-system
sudo systemctl start auth-system
```

---

### 3.3 AWS EKS (Kubernetes)

**장점**: 최고 수준의 확장성, 멀티 클라우드 호환
**단점**: 복잡성 높음, 비용 높음

#### 3.3.1 Kubernetes 매니페스트

**A. Deployment**

`k8s/auth-service-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
  namespace: auth-system
spec:
  replicas: 3
  selector:
    matchLabels:
      app: auth-service
  template:
    metadata:
      labels:
        app: auth-service
    spec:
      containers:
      - name: auth-service
        image: 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/auth-service:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENV
          value: "production"
        - name: DB_PRIMARY_DB_URL
          valueFrom:
            secretKeyRef:
              name: auth-secrets
              key: db-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: auth-secrets
              key: redis-url
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: auth-secrets
              key: jwt-secret
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: auth-service
  namespace: auth-system
spec:
  type: ClusterIP
  selector:
    app: auth-service
  ports:
  - port: 8000
    targetPort: 8000
```

**B. Ingress (ALB)**

`k8s/auth-service-ingress.yaml`:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: auth-service-ingress
  namespace: auth-system
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:ap-northeast-2:123456789012:certificate/xxx
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}, {"HTTPS": 443}]'
    alb.ingress.kubernetes.io/ssl-redirect: '443'
spec:
  rules:
  - host: api.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: auth-service
            port:
              number: 8000
```

**C. HPA (Horizontal Pod Autoscaler)**

`k8s/auth-service-hpa.yaml`:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: auth-service-hpa
  namespace: auth-system
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: auth-service
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### 3.3.2 Secrets 생성

```bash
# Kubernetes Secret 생성
kubectl create namespace auth-system

kubectl create secret generic auth-secrets \
  --from-literal=db-url="postgresql://admin:password@auth-db.xxx.rds.amazonaws.com:5432/authdb" \
  --from-literal=redis-url="rediss://:token@auth-redis.xxx.cache.amazonaws.com:6379/0" \
  --from-literal=jwt-secret="$(openssl rand -base64 64)" \
  --namespace=auth-system
```

#### 3.3.3 배포

```bash
# 모든 매니페스트 적용
kubectl apply -f k8s/

# 배포 상태 확인
kubectl get pods -n auth-system
kubectl get svc -n auth-system
kubectl get ingress -n auth-system

# 로그 확인
kubectl logs -f deployment/auth-service -n auth-system

# 스케일링 확인
kubectl get hpa -n auth-system
```

---

## 4. 기타 클라우드

### 4.1 Google Cloud Platform (GCP)

**Cloud Run (권장)**
```bash
# Cloud Run에 배포
gcloud run deploy auth-service \
  --image gcr.io/your-project/auth-service \
  --platform managed \
  --region asia-northeast3 \
  --allow-unauthenticated \
  --set-env-vars ENV=production \
  --set-secrets DB_PRIMARY_DB_URL=db-url:latest,REDIS_URL=redis-url:latest
```

**GKE (Kubernetes)**
- AWS EKS와 유사한 방식으로 배포

### 4.2 Microsoft Azure

**Azure Container Instances**
```bash
az container create \
  --resource-group auth-system-rg \
  --name auth-service \
  --image yourregistry.azurecr.io/auth-service:latest \
  --cpu 2 \
  --memory 4 \
  --environment-variables ENV=production \
  --secure-environment-variables DB_PRIMARY_DB_URL=$DB_URL
```

**Azure Kubernetes Service (AKS)**
- AWS EKS와 유사한 방식으로 배포

### 4.3 Heroku (간단한 배포)

```bash
# Heroku CLI 설치 후
heroku login
heroku create auth-service-prod

# Buildpack 설정
heroku buildpacks:set heroku/python

# 환경 변수 설정
heroku config:set ENV=production
heroku config:set DB_PRIMARY_DB_URL="postgresql://..."
heroku config:set REDIS_URL="redis://..."

# 배포
git push heroku main

# 로그 확인
heroku logs --tail
```

---

## 5. 배포 후 검증

### 5.1 헬스 체크
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

### 5.2 보안 헤더 검증
```bash
# 보안 헤더 확인
curl -I https://api.yourdomain.com/api/v1/health

# 확인 사항:
# - Strict-Transport-Security (HSTS)
# - X-Content-Type-Options: nosniff
# - X-Frame-Options: DENY
```

### 5.3 인증 플로우 테스트
```bash
# 1. 회원가입
curl -X POST https://api.yourdomain.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "StrongPass123!",
    "username": "testuser"
  }'

# 2. 로그인
TOKEN=$(curl -X POST https://api.yourdomain.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "StrongPass123!"
  }' | jq -r '.data.access_token')

# 3. 인증된 요청
curl https://api.yourdomain.com/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN"
```

### 5.4 성능 테스트
```bash
# Apache Bench로 부하 테스트
ab -n 1000 -c 10 https://api.yourdomain.com/api/v1/health

# wrk로 부하 테스트
wrk -t4 -c100 -d30s https://api.yourdomain.com/api/v1/health
```

### 5.5 데이터베이스 인덱스 검증
```bash
# 프로덕션 DB 접속 후
psql -h your-prod-db.rds.amazonaws.com -U admin -d authdb

# 인덱스 확인
\d users
\d user_roles
\d login_histories

# 쿼리 성능 확인
EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'test@example.com' AND deleted_at IS NULL;
```

---

## 6. 트러블슈팅

### 6.1 일반적인 문제

#### 문제: 데이터베이스 연결 실패
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**해결**:
```bash
# 1. 보안 그룹 확인
aws ec2 describe-security-groups --group-ids sg-xxx

# 2. RDS 엔드포인트 확인
aws rds describe-db-instances --db-instance-identifier auth-system-db

# 3. 연결 테스트
psql -h your-db-host -U admin -d authdb -c "SELECT 1;"
```

#### 문제: Redis 연결 실패
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**해결**:
```bash
# 1. ElastiCache 엔드포인트 확인
aws elasticache describe-replication-groups --replication-group-id auth-system-redis

# 2. TLS 연결 테스트
redis-cli --tls -h your-redis-host -a your-auth-token ping

# 3. URL 형식 확인 (rediss:// vs redis://)
echo $REDIS_URL
```

#### 문제: JWT 검증 실패
```
401 Unauthorized: Invalid token
```

**해결**:
```bash
# 1. JWT Secret/키 확인
aws secretsmanager get-secret-value --secret-id jwt-secret

# 2. 알고리즘 일치 확인 (HS256 vs RS256)
# .env에서 JWT_ALGORITHM 확인

# 3. 키 파일 권한 확인
ls -la keys/
chmod 600 keys/private.pem
```

#### 문제: CORS 오류
```
Access to XMLHttpRequest has been blocked by CORS policy
```

**해결**:
```bash
# 환경 변수 확인
echo $CORS_ALLOWED_ORIGINS

# 올바른 형식:
# CORS_ALLOWED_ORIGINS=["https://yourdomain.com","https://app.yourdomain.com"]

# 서비스 재시작
docker-compose restart auth-service
# 또는
kubectl rollout restart deployment/auth-service -n auth-system
```

### 6.2 로그 확인

**Docker Compose**:
```bash
docker-compose logs -f auth-service
```

**AWS ECS**:
```bash
aws logs tail /ecs/auth-service --follow
```

**Kubernetes**:
```bash
kubectl logs -f deployment/auth-service -n auth-system
```

### 6.3 모니터링 설정

**CloudWatch (AWS)**:
```bash
# 로그 그룹 생성
aws logs create-log-group --log-group-name /ecs/auth-service

# 대시보드 생성
aws cloudwatch put-dashboard --dashboard-name auth-service \
  --dashboard-body file://cloudwatch-dashboard.json
```

**Prometheus + Grafana (Kubernetes)**:
```bash
# Prometheus 설치
helm install prometheus prometheus-community/prometheus

# Grafana 설치
helm install grafana grafana/grafana

# Auth Service 메트릭 노출 (FastAPI)
# src/main.py에 prometheus_fastapi_instrumentator 추가
```

---

## 7. CI/CD 파이프라인

### 7.1 GitHub Actions

`.github/workflows/deploy.yml`:
```yaml
name: Deploy to AWS ECS

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-northeast-2

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1

      - name: Build and push Docker image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: auth-service
          IMAGE_TAG: ${{ github.sha }}
        run: |
          cd auth-service
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG

      - name: Update ECS service
        run: |
          aws ecs update-service \
            --cluster auth-system-cluster \
            --service auth-service \
            --force-new-deployment
```

### 7.2 GitLab CI/CD

`.gitlab-ci.yml`:
```yaml
stages:
  - build
  - deploy

build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t auth-service:$CI_COMMIT_SHA ./auth-service
    - docker tag auth-service:$CI_COMMIT_SHA $ECR_REGISTRY/auth-service:latest
    - docker push $ECR_REGISTRY/auth-service:latest

deploy:
  stage: deploy
  image: alpine:latest
  before_script:
    - apk add --no-cache aws-cli
  script:
    - aws ecs update-service --cluster auth-system-cluster --service auth-service --force-new-deployment
  only:
    - main
```

---

## 8. 백업 및 복구

### 8.1 데이터베이스 백업

**RDS 자동 백업** (이미 설정됨):
```bash
# 백업 확인
aws rds describe-db-snapshots --db-instance-identifier auth-system-db

# 수동 스냅샷 생성
aws rds create-db-snapshot \
  --db-instance-identifier auth-system-db \
  --db-snapshot-identifier auth-db-manual-backup-$(date +%Y%m%d)
```

**수동 백업**:
```bash
# PostgreSQL 덤프
pg_dump -h your-db-host -U admin -d authdb -F c -f backup-$(date +%Y%m%d).dump

# S3에 업로드
aws s3 cp backup-$(date +%Y%m%d).dump s3://your-backup-bucket/
```

### 8.2 복구

```bash
# RDS 스냅샷에서 복구
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier auth-system-db-restored \
  --db-snapshot-identifier auth-db-backup-20240210

# 또는 수동 덤프에서 복구
pg_restore -h your-db-host -U admin -d authdb backup-20240210.dump
```

---

## 요약

| 배포 방법 | 난이도 | 비용 | 확장성 | 권장 용도 |
|-----------|--------|------|--------|-----------|
| **로컬 Docker** | ⭐ | 무료 | - | 개발/테스트 |
| **EC2 단일 서버** | ⭐⭐ | $ | 낮음 | 소규모 프로젝트 |
| **ECS Fargate** | ⭐⭐⭐ | $$ | 높음 | 중대규모 프로젝트 (권장) |
| **EKS** | ⭐⭐⭐⭐ | $$$ | 매우 높음 | 대규모 엔터프라이즈 |
| **Heroku** | ⭐ | $$ | 중간 | 빠른 프로토타입 |

**권장 선택**:
- **스타트업/MVP**: ECS Fargate
- **엔터프라이즈**: EKS
- **개인 프로젝트**: EC2 단일 서버
- **개발/테스트**: 로컬 Docker Compose

---

## 추가 리소스

- [FastAPI 배포 가이드](https://fastapi.tiangolo.com/deployment/)
- [AWS ECS 베스트 프랙티스](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [PostgreSQL 성능 튜닝](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Redis 보안 가이드](https://redis.io/docs/management/security/)
