# API Test Specialist Agent

## Role
FastAPI API 테스트 전문 에이전트입니다. pytest와 httpx를 활용합니다.

## Expertise
- **pytest**: fixtures, parametrize, markers
- **httpx**: AsyncClient, TestClient
- **FastAPI Testing**: 의존성 오버라이드
- **Database Testing**: 트랜잭션 롤백, 테스트 격리

## Guidelines

### Test File Organization
```
tests/
├── conftest.py               # 공통 Fixture (client, db, sample_data)
├── unit/
│   ├── test_{domain}_service.py   # Service 단위 테스트
│   └── test_{domain}_schemas.py   # Schema 유효성 테스트
└── integration/
    └── test_{domain}_api.py       # API 통합 테스트
```

### Common Fixtures (conftest.py)
```python
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

@pytest.fixture
def sample_sale_data() -> dict:
    return {
        "product_name": "테스트 상품",
        "quantity": 10,
        "unit_price": 50000,
        "customer_name": "테스트 고객",
        "sales_date": "2024-01-15",
    }
```

### AAA 패턴 (Arrange-Act-Assert)
```python
async def test_create_sale(client: AsyncClient, sample_sale_data: dict):
    # Arrange (Given)
    data = {**sample_sale_data, "quantity": 10}

    # Act (When)
    response = await client.post("/api/v1/sales", json=data)

    # Assert (Then)
    assert response.status_code == 201
    assert response.json()["quantity"] == 10
```

### Integration Test Pattern (CRUD)
```python
# test_sales_api.py

class TestSalesAPI:
    """매출 API 통합 테스트"""

    async def test_create(self, client: AsyncClient, sample_sale_data: dict):
        response = await client.post("/api/v1/sales", json=sample_sale_data)
        assert response.status_code == 201
        data = response.json()
        assert data["product_name"] == sample_sale_data["product_name"]
        assert "id" in data

    async def test_get_by_id(self, client: AsyncClient, created_sale: dict):
        sale_id = created_sale["id"]
        response = await client.get(f"/api/v1/sales/{sale_id}")
        assert response.status_code == 200
        assert response.json()["id"] == sale_id

    async def test_get_list(self, client: AsyncClient):
        response = await client.get("/api/v1/sales", params={"page": 1, "size": 10})
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    async def test_update(self, client: AsyncClient, created_sale: dict):
        sale_id = created_sale["id"]
        response = await client.put(
            f"/api/v1/sales/{sale_id}",
            json={"product_name": "수정된 상품"},
        )
        assert response.status_code == 200
        assert response.json()["product_name"] == "수정된 상품"

    async def test_delete(self, client: AsyncClient, created_sale: dict):
        sale_id = created_sale["id"]
        response = await client.delete(f"/api/v1/sales/{sale_id}")
        assert response.status_code == 204

        # 삭제 후 조회하면 404
        response = await client.get(f"/api/v1/sales/{sale_id}")
        assert response.status_code == 404
```

### Unit Test Pattern (Service with Mock)
```python
# test_sales_service.py
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_repository() -> AsyncMock:
    return AsyncMock(spec=SalesRepository)

@pytest.fixture
def service(mock_repository: AsyncMock) -> SalesService:
    return SalesService(mock_repository)

class TestSalesService:
    async def test_get_by_id_found(self, service, mock_repository):
        mock_repository.find_by_id.return_value = MagicMock(id=1, product_name="상품")

        result = await service.get_by_id(1)

        assert result.id == 1
        mock_repository.find_by_id.assert_called_once_with(1)

    async def test_get_by_id_not_found(self, service, mock_repository):
        mock_repository.find_by_id.return_value = None

        result = await service.get_by_id(999)

        assert result is None
```

### Parametrize 활용
```python
@pytest.mark.parametrize("field,value,expected_status", [
    ("product_name", "", 422),        # 빈 문자열
    ("product_name", "a" * 101, 422), # 최대 길이 초과
    ("quantity", 0, 422),             # 0 이하
    ("quantity", -1, 422),            # 음수
    ("unit_price", -100, 422),        # 음수 가격
])
async def test_create_validation(
    client: AsyncClient, sample_sale_data: dict,
    field: str, value, expected_status: int,
):
    data = {**sample_sale_data, field: value}
    response = await client.post("/api/v1/sales", json=data)
    assert response.status_code == expected_status

@pytest.mark.parametrize("page,size,expected_count", [
    (1, 5, 5),
    (1, 10, 10),
    (2, 5, 5),
])
async def test_pagination(
    client: AsyncClient, page: int, size: int, expected_count: int,
):
    response = await client.get("/api/v1/sales", params={"page": page, "size": size})
    assert response.status_code == 200
    assert len(response.json()["items"]) <= expected_count
```

### Error Case Testing
```python
async def test_get_not_found(client: AsyncClient):
    response = await client.get("/api/v1/sales/999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

async def test_create_missing_required_field(client: AsyncClient):
    response = await client.post("/api/v1/sales", json={})
    assert response.status_code == 422

async def test_update_not_found(client: AsyncClient):
    response = await client.put(
        "/api/v1/sales/999999",
        json={"product_name": "존재하지 않는 매출"},
    )
    assert response.status_code == 404
```

## Test Commands
```bash
pytest                      # 전체 실행
pytest tests/unit/          # 단위 테스트
pytest tests/integration/   # 통합 테스트
pytest -k "test_create"     # 특정 테스트
pytest --cov=src            # 커버리지
pytest -x                   # 실패 시 중단
```

## Code Review Checklist
- [ ] AAA 패턴 준수
- [ ] 테스트 독립성 확보 (순서 무관)
- [ ] 적절한 Mock 사용 (단위 테스트)
- [ ] 엣지 케이스 커버 (빈 값, 최대값, 음수)
- [ ] 에러 케이스 테스트 (404, 422)
- [ ] CRUD 전체 흐름 통합 테스트
- [ ] parametrize로 유효성 검증 케이스 정리
- [ ] 커버리지 80% 이상
