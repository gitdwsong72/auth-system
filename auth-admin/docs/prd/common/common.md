# PRD: 공통 사항

## 문서 정보
| 항목 | 내용 |
|------|------|
| 작성자 | |
| 작성일 | |
| 버전 | 1.0 |
| 상태 | Draft / Review / Approved |

---

## 1. 프로젝트 개요

### 1.1 배경
> 이 프로젝트를 시작하게 된 배경과 필요성을 설명합니다.

### 1.2 목표
> 프로젝트의 주요 목표와 기대 효과를 명시합니다.

- 목표 1:
- 목표 2:

### 1.3 범위
> 이 PRD에서 다루는 범위와 다루지 않는 범위를 명확히 합니다.

**포함 범위:**
-

**제외 범위:**
-

---

## 2. 용어 정의

| 용어 | 정의 |
|------|------|
| | |

---

## 3. 기술 스택

### Frontend
- React 18+
- TypeScript 5+
- AG-Grid (Enterprise)
- Recharts
- Zustand

### Backend
- FastAPI
- PostgreSQL
- Python 3.11+

---

## 4. 공통 컴포넌트

### 4.1 DataGrid (AG-Grid)
> 공통 그리드 컴포넌트 사용 가이드

```typescript
import { DataGrid } from '@shared/components/DataGrid';

<DataGrid
  columnDefs={columnDefs}
  rowData={data}
  onRowClick={handleRowClick}
/>
```

### 4.2 Charts (Recharts)
> 공통 차트 컴포넌트 사용 가이드

```typescript
import { LineChart, BarChart } from '@shared/components/Charts';

<LineChart data={chartData} xKey="date" yKeys={['value']} />
```

---

## 5. API 규약

### 5.1 Base URL
```
Development: http://localhost:8000/api/v1
Production: https://api.example.com/api/v1
```

### 5.2 Response Format
```json
{
  "success": true,
  "data": {},
  "message": "Success",
  "error": null
}
```

### 5.3 Error Response
```json
{
  "success": false,
  "data": null,
  "message": "Error message",
  "error": {
    "code": "ERROR_CODE",
    "details": {}
  }
}
```

### 5.4 Pagination
```json
{
  "items": [],
  "total": 100,
  "page": 1,
  "pageSize": 20,
  "totalPages": 5
}
```

---

## 6. 코딩 컨벤션

### 6.1 파일 명명
- 컴포넌트: PascalCase (예: `UserList.tsx`)
- 훅: camelCase with `use` prefix (예: `useUser.ts`)
- 유틸리티: camelCase (예: `formatDate.ts`)
- 타입: PascalCase with suffix (예: `UserTypes.ts`)

### 6.2 폴더 구조
```
src/domains/{domain}/
├── components/     # 도메인 전용 컴포넌트
├── hooks/          # 도메인 전용 훅
├── stores/         # Zustand 스토어
├── pages/          # 페이지 컴포넌트
├── api/            # API 호출 함수
└── types/          # 타입 정의
```

---

## 7. 변경 이력

| 버전 | 일자 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | | | 최초 작성 |
