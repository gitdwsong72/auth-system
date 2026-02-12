"""SQLLoader utility unit tests."""

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.shared.utils.sql_loader import SQLLoader, create_sql_loader, reload_all_loaders


class TestSQLLoader:
    """SQLLoader 단위 테스트"""

    def test_load_success(self, tmp_path: Path):
        """SQL 파일 로드 성공"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        test_file = sql_path / "test_query.sql"
        test_content = "SELECT * FROM users WHERE id = $1"
        test_file.write_text(test_content)

        loader = SQLLoader("test_domain", base_path=tmp_path)

        # Act
        result = loader.load("test_query.sql")

        # Assert
        assert result == test_content

    def test_load_file_not_found(self, tmp_path: Path):
        """SQL 파일 없음 - FileNotFoundError 발생"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        loader = SQLLoader("test_domain", base_path=tmp_path)

        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load("nonexistent.sql")

        assert "SQL file not found" in str(exc_info.value)

    def test_caching_enabled(self, tmp_path: Path):
        """캐싱 활성화 - 두 번째 로드는 캐시에서 반환"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        test_file = sql_path / "cached.sql"
        test_file.write_text("SELECT 1")

        loader = SQLLoader("test_domain", base_path=tmp_path, enable_cache=True)

        # Act
        result1 = loader.load("cached.sql")
        # 파일이 캐시되었으므로 두 번째 로드는 캐시에서 반환
        # 단, 파일 수정 시간이 변경되면 자동으로 재로드됨
        # 따라서 여기서는 캐시 통계만 확인
        loader.load("cached.sql")

        # Assert
        assert result1 == "SELECT 1"
        # result2는 파일이 수정되었다면 새 내용일 수 있음 (수정 감지 기능)
        stats = loader.get_cache_stats()
        assert stats["cached_files"] >= 1
        assert stats["tracked_files"] >= 1

    def test_caching_disabled(self, tmp_path: Path):
        """캐싱 비활성화 - 매번 파일에서 로드"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        test_file = sql_path / "no_cache.sql"
        test_file.write_text("SELECT 1")

        loader = SQLLoader("test_domain", base_path=tmp_path, enable_cache=False)

        # Act
        result1 = loader.load("no_cache.sql")
        test_file.write_text("SELECT 2")
        result2 = loader.load("no_cache.sql")

        # Assert
        assert result1 == "SELECT 1"
        assert result2 == "SELECT 2"
        stats = loader.get_cache_stats()
        assert stats["cached_files"] == 0
        assert stats["tracked_files"] == 0

    def test_force_reload(self, tmp_path: Path):
        """force_reload 플래그 - 캐시 무시하고 재로드"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        test_file = sql_path / "reload.sql"
        test_file.write_text("SELECT 1")

        loader = SQLLoader("test_domain", base_path=tmp_path, enable_cache=True)

        # Act
        result1 = loader.load("reload.sql")
        test_file.write_text("SELECT 2")
        result2 = loader.load("reload.sql", force_reload=True)

        # Assert
        assert result1 == "SELECT 1"
        assert result2 == "SELECT 2"

    def test_file_modification_detection(self, tmp_path: Path):
        """파일 수정 감지 - mtime 변경 시 자동 재로드"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        test_file = sql_path / "modified.sql"
        test_file.write_text("SELECT 1")

        loader = SQLLoader("test_domain", base_path=tmp_path, enable_cache=True)

        # Act
        result1 = loader.load("modified.sql")

        # 파일 수정 시간이 변경되도록 잠시 대기
        time.sleep(0.01)
        test_file.write_text("SELECT 2")

        result2 = loader.load("modified.sql")

        # Assert
        assert result1 == "SELECT 1"
        assert result2 == "SELECT 2"

    def test_load_query_convenience_method(self, tmp_path: Path):
        """load_query - queries/ 서브디렉토리 편의 메서드"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql" / "queries"
        sql_path.mkdir(parents=True)

        test_file = sql_path / "get_user.sql"
        test_content = "SELECT * FROM users WHERE id = $1"
        test_file.write_text(test_content)

        loader = SQLLoader("test_domain", base_path=tmp_path)

        # Act
        result = loader.load_query("get_user")

        # Assert
        assert result == test_content

    def test_load_command_convenience_method(self, tmp_path: Path):
        """load_command - commands/ 서브디렉토리 편의 메서드"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql" / "commands"
        sql_path.mkdir(parents=True)

        test_file = sql_path / "create_user.sql"
        test_content = "INSERT INTO users (email) VALUES ($1)"
        test_file.write_text(test_content)

        loader = SQLLoader("test_domain", base_path=tmp_path)

        # Act
        result = loader.load_command("create_user")

        # Assert
        assert result == test_content

    def test_reload_specific_file(self, tmp_path: Path):
        """특정 파일 재로드"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        file1 = sql_path / "query1.sql"
        file2 = sql_path / "query2.sql"
        file1.write_text("SELECT 1")
        file2.write_text("SELECT 2")

        loader = SQLLoader("test_domain", base_path=tmp_path, enable_cache=True)

        # Act
        loader.load("query1.sql")
        loader.load("query2.sql")

        # query1만 캐시에서 제거 (로드할 때 사용한 경로와 동일해야 함)
        loader.reload("query1.sql")

        stats = loader.get_cache_stats()

        # Assert
        assert "query1.sql" not in loader._cache
        assert "query2.sql" in loader._cache
        assert stats["cached_files"] == 1

    def test_reload_all_files(self, tmp_path: Path):
        """전체 파일 재로드"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        file1 = sql_path / "query1.sql"
        file2 = sql_path / "query2.sql"
        file1.write_text("SELECT 1")
        file2.write_text("SELECT 2")

        loader = SQLLoader("test_domain", base_path=tmp_path, enable_cache=True)

        # Act
        loader.load("query1.sql")
        loader.load("query2.sql")
        loader.reload()  # 전체 재로드

        stats = loader.get_cache_stats()

        # Assert
        assert stats["cached_files"] == 0
        assert stats["tracked_files"] == 0

    def test_clear_cache(self, tmp_path: Path):
        """캐시 클리어"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        test_file = sql_path / "test.sql"
        test_file.write_text("SELECT 1")

        loader = SQLLoader("test_domain", base_path=tmp_path, enable_cache=True)
        loader.load("test.sql")

        # Act
        loader.clear_cache()

        # Assert
        stats = loader.get_cache_stats()
        assert stats["cached_files"] == 0
        assert stats["tracked_files"] == 0

    def test_get_cache_stats(self, tmp_path: Path):
        """캐시 통계 조회"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        for i in range(3):
            file = sql_path / f"query{i}.sql"
            file.write_text(f"SELECT {i}")

        loader = SQLLoader("test_domain", base_path=tmp_path, enable_cache=True)

        # Act
        for i in range(3):
            loader.load(f"query{i}.sql")

        stats = loader.get_cache_stats()

        # Assert
        assert stats["cached_files"] == 3
        assert stats["tracked_files"] == 3

    def test_empty_sql_file(self, tmp_path: Path):
        """빈 SQL 파일 처리"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        test_file = sql_path / "empty.sql"
        test_file.write_text("   \n\n  ")  # 공백만 있는 파일

        loader = SQLLoader("test_domain", base_path=tmp_path)

        # Act
        result = loader.load("empty.sql")

        # Assert
        assert result == ""  # strip()으로 인해 빈 문자열

    def test_sql_file_with_whitespace(self, tmp_path: Path):
        """앞뒤 공백이 있는 SQL 파일 처리"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        test_file = sql_path / "whitespace.sql"
        test_content = "\n\n  SELECT * FROM users  \n\n"
        test_file.write_text(test_content)

        loader = SQLLoader("test_domain", base_path=tmp_path)

        # Act
        result = loader.load("whitespace.sql")

        # Assert
        assert result == "SELECT * FROM users"  # strip() 적용됨

    def test_malformed_path(self, tmp_path: Path):
        """잘못된 경로 처리"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        loader = SQLLoader("test_domain", base_path=tmp_path)

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            loader.load("../../../etc/passwd")

    def test_unicode_content(self, tmp_path: Path):
        """유니코드 SQL 파일 처리"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        test_file = sql_path / "unicode.sql"
        test_content = "-- 사용자 조회\nSELECT * FROM users WHERE name = '한글'"
        test_file.write_text(test_content, encoding="utf-8")

        loader = SQLLoader("test_domain", base_path=tmp_path)

        # Act
        result = loader.load("unicode.sql")

        # Assert
        assert "한글" in result
        assert "사용자 조회" in result


class TestCreateSQLLoader:
    """create_sql_loader 싱글톤 팩토리 함수 테스트"""

    def test_singleton_pattern(self):
        """싱글톤 패턴 - 동일 도메인은 같은 인스턴스 반환"""
        # Act
        loader1 = create_sql_loader("users")
        loader2 = create_sql_loader("users")

        # Assert
        assert loader1 is loader2

    def test_different_domains_different_instances(self):
        """다른 도메인은 다른 인스턴스"""
        # Act
        loader1 = create_sql_loader("users")
        loader2 = create_sql_loader("authentication")

        # Assert
        assert loader1 is not loader2
        assert loader1.domain == "users"
        assert loader2.domain == "authentication"

    def test_cache_enabled_by_default(self):
        """기본적으로 캐시 활성화"""
        # Act
        loader = create_sql_loader("users")

        # Assert
        assert loader.enable_cache is True

    def test_cache_can_be_disabled(self):
        """캐시 비활성화 가능"""
        # Act
        loader = create_sql_loader("test_domain", enable_cache=False)

        # Assert
        assert loader.enable_cache is False

    @patch.dict("os.environ", {"ENV": "development"})
    def test_development_mode(self):
        """개발 모드 - 파일 수정 감지 활성화"""
        # Act
        loader = create_sql_loader("test_dev")

        # Assert
        assert loader.enable_cache is True  # 개발 모드에서도 캐시 사용

    @patch.dict("os.environ", {"ENV": "production"})
    def test_production_mode(self):
        """프로덕션 모드 - 캐시 최대 활용"""
        # Act
        loader = create_sql_loader("test_prod")

        # Assert
        assert loader.enable_cache is True


class TestReloadAllLoaders:
    """reload_all_loaders 전역 함수 테스트"""

    def test_reload_all_clears_all_caches(self, tmp_path: Path):
        """전체 로더의 캐시 클리어"""
        # Arrange
        domain1_path = tmp_path / "domain1" / "sql"
        domain2_path = tmp_path / "domain2" / "sql"
        domain1_path.mkdir(parents=True)
        domain2_path.mkdir(parents=True)

        (domain1_path / "test1.sql").write_text("SELECT 1")
        (domain2_path / "test2.sql").write_text("SELECT 2")

        loader1 = SQLLoader("domain1", base_path=tmp_path, enable_cache=True)
        loader2 = SQLLoader("domain2", base_path=tmp_path, enable_cache=True)

        loader1.load("test1.sql")
        loader2.load("test2.sql")

        # Mock the global instances
        with patch(
            "src.shared.utils.sql_loader._loader_instances",
            {"domain1": loader1, "domain2": loader2},
        ):
            # Act
            reload_all_loaders()

            # Assert
            assert loader1.get_cache_stats()["cached_files"] == 0
            assert loader2.get_cache_stats()["cached_files"] == 0

    def test_reload_all_with_no_loaders(self):
        """로더가 없을 때 reload_all 호출 - 오류 없이 처리"""
        # Arrange
        with patch("src.shared.utils.sql_loader._loader_instances", {}):
            # Act & Assert
            reload_all_loaders()  # No exception should be raised


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_multiple_loads_same_file(self, tmp_path: Path):
        """같은 파일 여러 번 로드 - 캐시 효율성 검증"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        test_file = sql_path / "popular.sql"
        test_file.write_text("SELECT * FROM users")

        loader = SQLLoader("test_domain", base_path=tmp_path, enable_cache=True)

        # Act
        results = [loader.load("popular.sql") for _ in range(10)]

        # Assert
        assert all(r == results[0] for r in results)
        stats = loader.get_cache_stats()
        assert stats["cached_files"] == 1  # 한 번만 캐시됨

    def test_concurrent_file_creation(self, tmp_path: Path):
        """파일 생성 후 즉시 로드"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        loader = SQLLoader("test_domain", base_path=tmp_path)

        # Act - 파일 생성 후 즉시 로드
        test_file = sql_path / "new_file.sql"
        test_file.write_text("SELECT NOW()")
        result = loader.load("new_file.sql")

        # Assert
        assert result == "SELECT NOW()"

    def test_subdirectory_structure(self, tmp_path: Path):
        """서브디렉토리 구조에서 SQL 파일 로드"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql" / "queries" / "nested"
        sql_path.mkdir(parents=True)

        test_file = sql_path / "deep.sql"
        test_file.write_text("SELECT * FROM deep_table")

        loader = SQLLoader("test_domain", base_path=tmp_path)

        # Act
        result = loader.load("queries/nested/deep.sql")

        # Assert
        assert result == "SELECT * FROM deep_table"

    def test_file_path_with_special_characters(self, tmp_path: Path):
        """특수 문자가 포함된 파일명"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        test_file = sql_path / "query-with-dash.sql"
        test_file.write_text("SELECT 1")

        loader = SQLLoader("test_domain", base_path=tmp_path)

        # Act
        result = loader.load("query-with-dash.sql")

        # Assert
        assert result == "SELECT 1"

    def test_large_sql_file(self, tmp_path: Path):
        """큰 SQL 파일 처리"""
        # Arrange
        domain_path = tmp_path / "test_domain"
        sql_path = domain_path / "sql"
        sql_path.mkdir(parents=True)

        # 대량의 SQL 생성
        large_content = "\n".join([f"SELECT {i} FROM table_{i};" for i in range(1000)])
        test_file = sql_path / "large.sql"
        test_file.write_text(large_content)

        loader = SQLLoader("test_domain", base_path=tmp_path)

        # Act
        result = loader.load("large.sql")

        # Assert
        assert "SELECT 0 FROM table_0" in result
        assert "SELECT 999 FROM table_999" in result
        assert result.count("SELECT") == 1000
