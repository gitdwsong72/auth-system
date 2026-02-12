# PRD: [API 엔드포인트명]

## 문서 정보
| 항목 | 내용 |
|------|------|
| 작성자 | |
| 작성일 | |
| 버전 | 1.0 |
| 상태 | Draft / Review / Approved |
| 공통 PRD | [공통 사항](./common.md) 참조 |

---

## 1. 엔드포인트 개요

### 1.1 목적
> 이 API 엔드포인트의 주요 목적과 제공하는 기능을 설명합니다.

### 1.2 관련 도메인
> 이 엔드포인트가 속하는 비즈니스 도메인

- 도메인: `src/domains/{domain}/`
- 관련 화면 PRD: (있는 경우 링크)

### 1.3 Base Path
```
/api/v1/{domain}
```

---

## 2. 데이터 모델

### 2.1 테이블 스키마

```sql
CREATE TABLE {table_name} (
    id BIGSERIAL PRIMARY KEY,
    -- 컬럼 정의
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 2.2 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|--------|------|----------|--------|------|
| id | BIGSERIAL | N | auto | PK |
| | | | | |
| created_at | TIMESTAMPTZ | N | NOW() | 생성일시 |
| updated_at | TIMESTAMPTZ | N | NOW() | 수정일시 |

### 2.3 인덱스

| 인덱스명 | 컬럼 | 타입 | 용도 |
|----------|------|------|------|
| | | BTREE / GIN / ... | |

### 2.4 테이블 관계

```
{table_name} ──┬── 1:N ──> {related_table}
               └── N:1 ──> {parent_table}
```

---

## 3. API 상세

### 3.1 목록 조회

```
GET /api/v1/{domain}
```

**Query Parameters:**

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| page | int | N | 1 | 페이지 번호 |
| page_size | int | N | 20 | 페이지 크기 |
| sort | string | N | -created_at | 정렬 (- prefix: DESC) |
| keyword | string | N | | 검색 키워드 |

**Response (200):**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 1
      }
    ],
    "total": 100,
    "page": 1,
    "pageSize": 20,
    "totalPages": 5
  }
}
```

### 3.2 상세 조회

```
GET /api/v1/{domain}/{id}
```

**Path Parameters:**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| id | int | 리소스 ID |

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": 1
  }
}
```

### 3.3 생성

```
POST /api/v1/{domain}
```

**Request Body:**
```json
{
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| | | | |

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": 1
  },
  "message": "Created successfully"
}
```

### 3.4 수정

```
PUT /api/v1/{domain}/{id}
```

**Request Body:**
```json
{
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| | | | |

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": 1
  },
  "message": "Updated successfully"
}
```

### 3.5 삭제

```
DELETE /api/v1/{domain}/{id}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Deleted successfully"
}
```

### 3.6 일괄 삭제 (필요시)

```
DELETE /api/v1/{domain}/batch
```

**Request Body:**
```json
{
  "ids": [1, 2, 3]
}
```

---

## 4. 비즈니스 규칙

### 4.1 유효성 검증

| 필드 | 규칙 | 에러 메시지 |
|------|------|------------|
| | | |

### 4.2 권한

| 엔드포인트 | 필요 권한 | 설명 |
|------------|----------|------|
| GET /api/v1/{domain} | READ | 목록 조회 |
| POST /api/v1/{domain} | WRITE | 생성 |
| PUT /api/v1/{domain}/{id} | WRITE | 수정 |
| DELETE /api/v1/{domain}/{id} | DELETE | 삭제 |

### 4.3 상태 전환 (해당시)

```
[초기상태] ──(액션1)──> [상태2] ──(액션2)──> [최종상태]
```

| 현재 상태 | 액션 | 다음 상태 | 조건 |
|-----------|------|-----------|------|
| | | | |

---

## 5. 에러 케이스

| HTTP Status | 에러 코드 | 상황 | 응답 메시지 |
|-------------|-----------|------|------------|
| 400 | VALIDATION_ERROR | 유효성 검증 실패 | 필드별 에러 메시지 |
| 404 | NOT_FOUND | 리소스 없음 | 데이터를 찾을 수 없습니다 |
| 403 | FORBIDDEN | 권한 없음 | 권한이 없습니다 |
| 409 | CONFLICT | 중복/충돌 | 이미 존재하는 데이터입니다 |
| 500 | INTERNAL_ERROR | 서버 오류 | 서버 오류가 발생했습니다 |

---

## 6. 구현 가이드

### 6.1 파일 구조

```
src/domains/{domain}/
├── router.py        # API 엔드포인트 정의
├── service.py       # 비즈니스 로직
├── repository.py    # 데이터 접근 레이어
├── schemas.py       # Pydantic 요청/응답 스키마
└── sql/
    ├── queries/     # SELECT 쿼리
    │   ├── select_list.sql
    │   └── select_detail.sql
    └── commands/    # INSERT/UPDATE/DELETE 쿼리
        ├── insert.sql
        ├── update.sql
        └── delete.sql
```

### 6.2 레이어 패턴
```
Router (요청 수신) → Service (비즈니스 로직) → Repository (SQL 실행)
```

---

## 7. 테스트 시나리오

### 7.1 단위 테스트 (Service)
- [ ] 정상 생성 테스트
- [ ] 유효성 검증 실패 테스트
- [ ] 존재하지 않는 리소스 조회 테스트

### 7.2 통합 테스트 (API)
- [ ] GET 목록 조회 - 페이지네이션 동작
- [ ] GET 목록 조회 - 검색/필터 동작
- [ ] GET 상세 조회 - 정상
- [ ] GET 상세 조회 - 404
- [ ] POST 생성 - 정상
- [ ] POST 생성 - 유효성 검증 실패 (400)
- [ ] PUT 수정 - 정상
- [ ] PUT 수정 - 404
- [ ] DELETE 삭제 - 정상
- [ ] DELETE 삭제 - 404

### 7.3 비기능 테스트
- [ ] 대용량 데이터 조회 성능 (10만건+)
- [ ] 동시 요청 처리
- [ ] SQL 인젝션 방어

---

## 8. 변경 이력

| 버전 | 일자 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | | | 최초 작성 |
