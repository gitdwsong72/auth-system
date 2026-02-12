# PRD: [화면명]

## 문서 정보
| 항목 | 내용 |
|------|------|
| 작성자 | |
| 작성일 | |
| 버전 | 1.0 |
| 상태 | Draft / Review / Approved |
| 공통 PRD | [공통 사항](./common.md) 참조 |

---

## 1. 화면 개요

### 1.1 목적
> 이 화면의 주요 목적과 사용자에게 제공하는 가치를 설명합니다.

### 1.2 대상 사용자
> 이 화면을 사용하는 주요 사용자 그룹

-

### 1.3 진입 경로
> 사용자가 이 화면에 도달하는 경로

```
메인 메뉴 > 카테고리 > [화면명]
URL: /domain/page
```

---

## 2. 화면 구성

### 2.1 레이아웃
> 화면의 전체 레이아웃을 ASCII 또는 다이어그램으로 표현

```
┌─────────────────────────────────────────┐
│  Header (검색/필터 영역)                  │
├─────────────────────────────────────────┤
│                                         │
│  Main Content (그리드/리스트)             │
│                                         │
├─────────────────────────────────────────┤
│  Footer (페이지네이션/액션 버튼)           │
└─────────────────────────────────────────┘
```

### 2.2 컴포넌트 목록

| 컴포넌트 | 타입 | 설명 |
|----------|------|------|
| SearchBar | 공통 | 검색 입력 |
| FilterPanel | 전용 | 필터 패널 |
| DataGrid | 공통 | 데이터 그리드 |
| Pagination | 공통 | 페이지네이션 |

---

## 3. 기능 상세

### 3.1 검색/필터

#### 검색 조건
| 필드명 | 타입 | 필수 | 설명 |
|--------|------|------|------|
| keyword | text | N | 키워드 검색 |
| dateRange | date-range | N | 기간 선택 |
| status | select | N | 상태 필터 |

#### 동작
- 검색 버튼 클릭 또는 Enter 시 조회
- 필터 변경 시 즉시 조회 (디바운스 300ms)
- 초기화 버튼으로 모든 조건 리셋

### 3.2 그리드

#### 컬럼 정의
| 컬럼명 | 필드 | 너비 | 정렬 | 설명 |
|--------|------|------|------|------|
| No | rowNum | 60px | center | 행 번호 |
| 이름 | name | flex | left | 클릭 시 상세 이동 |
| 상태 | status | 100px | center | 배지 렌더러 |
| 등록일 | createdAt | 120px | center | YYYY-MM-DD |
| 작업 | actions | 100px | center | 수정/삭제 버튼 |

#### 그리드 기능
- [ ] 정렬: name, createdAt
- [ ] 필터: 컬럼 헤더 필터
- [ ] 선택: 다중 선택 (체크박스)
- [ ] 페이징: 서버사이드 (20/50/100건)

### 3.3 CRUD 기능

#### 생성 (Create)
- 트리거: [등록] 버튼 클릭
- 동작: 모달 또는 별도 페이지 이동
- 필수 입력: field1, field2

#### 조회 (Read)
- 행 클릭 시 상세 페이지 이동
- URL: `/domain/{id}`

#### 수정 (Update)
- 트리거: 행 더블클릭 또는 [수정] 버튼
- 동작: 인라인 편집 또는 모달

#### 삭제 (Delete)
- 트리거: [삭제] 버튼
- 확인: 삭제 확인 다이얼로그
- 다중 삭제: 체크박스 선택 후 일괄 삭제

---

## 4. API 연동

### 4.1 목록 조회
```
GET /api/v1/domain
Query: page, pageSize, sort, keyword, status, startDate, endDate
```

### 4.2 상세 조회
```
GET /api/v1/domain/{id}
```

### 4.3 생성
```
POST /api/v1/domain
Body: { name, ... }
```

### 4.4 수정
```
PUT /api/v1/domain/{id}
Body: { name, ... }
```

### 4.5 삭제
```
DELETE /api/v1/domain/{id}
```

### 4.6 일괄 삭제
```
DELETE /api/v1/domain/batch
Body: { ids: [1, 2, 3] }
```

---

## 5. 상태 관리

### 5.1 Zustand Store
```typescript
interface DomainState {
  // Data
  items: Item[];
  selectedItem: Item | null;
  total: number;

  // UI State
  loading: boolean;
  error: string | null;

  // Filters
  filters: FilterParams;

  // Actions
  fetchItems: () => Promise<void>;
  setFilters: (filters: Partial<FilterParams>) => void;
  selectItem: (item: Item) => void;
}
```

---

## 6. 에러 처리

| 에러 코드 | 메시지 | 처리 방법 |
|-----------|--------|----------|
| 404 | 데이터를 찾을 수 없습니다 | 목록으로 리다이렉트 |
| 403 | 권한이 없습니다 | 토스트 메시지 |
| 500 | 서버 오류가 발생했습니다 | 재시도 안내 |

---

## 7. 테스트 시나리오

### 7.1 기능 테스트
- [ ] 목록 조회 정상 동작
- [ ] 검색/필터 동작 확인
- [ ] 페이징 동작 확인
- [ ] CRUD 각 기능 정상 동작
- [ ] 에러 상황 처리 확인

### 7.2 비기능 테스트
- [ ] 대용량 데이터 (1000건+) 렌더링 성능
- [ ] 동시 요청 처리
- [ ] 네트워크 지연 시 UX

---

## 8. 변경 이력

| 버전 | 일자 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | | | 최초 작성 |
