#!/usr/bin/env python3
"""Solid Cache 설정 검증 스크립트.

이 스크립트는 Solid Cache가 올바르게 설정되었는지 검증합니다:
1. 테이블 생성 확인
2. 인덱스 생성 확인
3. Cleanup 함수 확인
4. 기본 CRUD 작업 테스트
5. 성능 벤치마크 (선택사항)

Usage:
    python scripts/verify_solid_cache.py
    python scripts/verify_solid_cache.py --benchmark  # 성능 테스트 포함
"""

import asyncio
import sys
import time
from pathlib import Path

import asyncpg

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.shared.database.solid_cache import SolidCache


async def verify_table_exists(conn: asyncpg.Connection) -> bool:
    """solid_cache_entries 테이블이 존재하는지 확인한다."""
    query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'solid_cache_entries'
        )
    """
    exists = await conn.fetchval(query)
    return exists


async def verify_indexes(conn: asyncpg.Connection) -> dict:
    """인덱스가 올바르게 생성되었는지 확인한다."""
    query = """
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'solid_cache_entries'
        AND schemaname = 'public'
    """
    rows = await conn.fetch(query)
    indexes = [row["indexname"] for row in rows]

    return {
        "idx_solid_cache_expires": "idx_solid_cache_expires" in indexes,
        "idx_solid_cache_key_pattern": "idx_solid_cache_key_pattern" in indexes,
        "primary_key": "solid_cache_entries_pkey" in indexes,
    }


async def verify_cleanup_function(conn: asyncpg.Connection) -> bool:
    """cleanup_expired_cache() 함수가 존재하는지 확인한다."""
    query = """
        SELECT EXISTS (
            SELECT FROM pg_proc
            WHERE proname = 'cleanup_expired_cache'
        )
    """
    exists = await conn.fetchval(query)
    return exists


async def test_basic_operations(pool: asyncpg.Pool) -> dict:
    """기본 CRUD 작업을 테스트한다."""
    cache = SolidCache(pool)
    results = {}

    try:
        # 1. SET
        await cache.set("test_key", "test_value", ttl_seconds=60)
        results["set"] = "✅ PASS"
    except Exception as e:
        results["set"] = f"❌ FAIL: {e}"

    try:
        # 2. GET
        value = await cache.get("test_key")
        if value == "test_value":
            results["get"] = "✅ PASS"
        else:
            results["get"] = f"❌ FAIL: Expected 'test_value', got '{value}'"
    except Exception as e:
        results["get"] = f"❌ FAIL: {e}"

    try:
        # 3. SET JSON
        data = {"user_id": 123, "name": "Test User"}
        await cache.set_json("test_json", data, ttl_seconds=60)
        results["set_json"] = "✅ PASS"
    except Exception as e:
        results["set_json"] = f"❌ FAIL: {e}"

    try:
        # 4. GET JSON
        cached_data = await cache.get_json("test_json")
        if cached_data == data:
            results["get_json"] = "✅ PASS"
        else:
            results["get_json"] = "❌ FAIL: Data mismatch"
    except Exception as e:
        results["get_json"] = f"❌ FAIL: {e}"

    try:
        # 5. EXISTS
        exists = await cache.exists("test_key")
        if exists:
            results["exists"] = "✅ PASS"
        else:
            results["exists"] = "❌ FAIL: Key should exist"
    except Exception as e:
        results["exists"] = f"❌ FAIL: {e}"

    try:
        # 6. TTL
        ttl = await cache.ttl("test_key")
        if 0 < ttl <= 60:
            results["ttl"] = f"✅ PASS (TTL: {ttl}s)"
        else:
            results["ttl"] = f"❌ FAIL: Invalid TTL {ttl}"
    except Exception as e:
        results["ttl"] = f"❌ FAIL: {e}"

    try:
        # 7. DELETE
        await cache.delete("test_key")
        exists = await cache.exists("test_key")
        if not exists:
            results["delete"] = "✅ PASS"
        else:
            results["delete"] = "❌ FAIL: Key should not exist after delete"
    except Exception as e:
        results["delete"] = f"❌ FAIL: {e}"

    try:
        # 8. DELETE PATTERN
        await cache.set("pattern:1", "value1", ttl_seconds=60)
        await cache.set("pattern:2", "value2", ttl_seconds=60)
        await cache.set("other:1", "value3", ttl_seconds=60)

        deleted = await cache.delete_pattern("pattern:%")
        if deleted >= 2:
            results["delete_pattern"] = f"✅ PASS (Deleted {deleted} keys)"
        else:
            results["delete_pattern"] = f"❌ FAIL: Expected 2+, deleted {deleted}"
    except Exception as e:
        results["delete_pattern"] = f"❌ FAIL: {e}"

    try:
        # 9. GET STATS
        stats = await cache.get_stats()
        if "total_entries" in stats and "expired_entries" in stats:
            results["get_stats"] = f"✅ PASS (Entries: {stats['total_entries']})"
        else:
            results["get_stats"] = "❌ FAIL: Invalid stats format"
    except Exception as e:
        results["get_stats"] = f"❌ FAIL: {e}"

    try:
        # 10. CLEANUP
        deleted = await cache.cleanup_expired()
        results["cleanup_expired"] = f"✅ PASS (Cleaned up {deleted} entries)"
    except Exception as e:
        results["cleanup_expired"] = f"❌ FAIL: {e}"

    # Cleanup test data
    try:
        await cache.delete("test_json")
        await cache.delete("other:1")
    except Exception:
        pass

    return results


async def benchmark_operations(pool: asyncpg.Pool, iterations: int = 100) -> dict:
    """성능 벤치마크를 실행한다."""
    cache = SolidCache(pool)
    results = {}

    # 1. SET 성능
    start = time.perf_counter()
    for i in range(iterations):
        await cache.set(f"bench_key_{i}", f"value_{i}", ttl_seconds=300)
    elapsed = time.perf_counter() - start
    results["set_avg_ms"] = (elapsed / iterations) * 1000

    # 2. GET 성능
    start = time.perf_counter()
    for i in range(iterations):
        await cache.get(f"bench_key_{i}")
    elapsed = time.perf_counter() - start
    results["get_avg_ms"] = (elapsed / iterations) * 1000

    # 3. JSON SET 성능
    test_data = {"user_id": 123, "name": "Test", "roles": ["admin", "user"]}
    start = time.perf_counter()
    for i in range(iterations):
        await cache.set_json(f"bench_json_{i}", test_data, ttl_seconds=300)
    elapsed = time.perf_counter() - start
    results["set_json_avg_ms"] = (elapsed / iterations) * 1000

    # 4. JSON GET 성능
    start = time.perf_counter()
    for i in range(iterations):
        await cache.get_json(f"bench_json_{i}")
    elapsed = time.perf_counter() - start
    results["get_json_avg_ms"] = (elapsed / iterations) * 1000

    # Cleanup benchmark data
    await cache.delete_pattern("bench_key_%")
    await cache.delete_pattern("bench_json_%")

    return results


async def main(run_benchmark: bool = False):
    """메인 검증 함수."""
    # Database URL (환경변수에서 읽기)
    import os

    db_url = os.getenv(
        "DB_PRIMARY_DB_URL",
        "postgresql://auth_user:auth_pass@localhost:5433/auth_db?sslmode=disable",
    )

    print("=" * 80)
    print("Solid Cache 검증 시작")
    print("=" * 80)
    print(f"Database: {db_url.split('@')[1] if '@' in db_url else 'unknown'}\n")

    try:
        # Connection Pool 생성
        pool = await asyncpg.create_pool(
            db_url,
            min_size=2,
            max_size=5,
        )

        async with pool.acquire() as conn:
            # 1. 테이블 존재 확인
            print("📋 Step 1: 테이블 존재 확인")
            table_exists = await verify_table_exists(conn)
            if table_exists:
                print("   ✅ solid_cache_entries 테이블이 존재합니다\n")
            else:
                print("   ❌ solid_cache_entries 테이블이 존재하지 않습니다")
                print(
                    "   💡 마이그레이션을 실행하세요: scripts/migrations/005_add_solid_cache.sql\n"
                )
                return

            # 2. 인덱스 확인
            print("📋 Step 2: 인덱스 확인")
            indexes = await verify_indexes(conn)
            for idx_name, exists in indexes.items():
                status = "✅" if exists else "❌"
                print(f"   {status} {idx_name}")
            print()

            # 3. Cleanup 함수 확인
            print("📋 Step 3: Cleanup 함수 확인")
            cleanup_exists = await verify_cleanup_function(conn)
            if cleanup_exists:
                print("   ✅ cleanup_expired_cache() 함수가 존재합니다\n")
            else:
                print("   ❌ cleanup_expired_cache() 함수가 존재하지 않습니다\n")

        # 4. 기본 CRUD 테스트
        print("📋 Step 4: 기본 CRUD 작업 테스트")
        crud_results = await test_basic_operations(pool)
        for operation, result in crud_results.items():
            print(f"   {operation.upper()}: {result}")
        print()

        # 5. 성능 벤치마크 (옵션)
        if run_benchmark:
            print("📋 Step 5: 성능 벤치마크 (100 iterations)")
            benchmark_results = await benchmark_operations(pool, iterations=100)
            for operation, avg_ms in benchmark_results.items():
                print(f"   {operation}: {avg_ms:.2f}ms")
            print()

        # 최종 통계
        cache = SolidCache(pool)
        stats = await cache.get_stats()
        print("📊 Solid Cache 통계:")
        print(f"   총 엔트리: {stats['total_entries']}")
        print(f"   만료된 엔트리: {stats['expired_entries']}")
        print(f"   스토리지 크기: {stats['total_size_bytes'] / 1024:.2f} KB")
        print()

        # 결론
        all_passed = all("✅" in str(r) for r in crud_results.values())
        if all_passed and table_exists and all(indexes.values()) and cleanup_exists:
            print("=" * 80)
            print("🎉 모든 검증 통과! Solid Cache가 정상적으로 설정되었습니다.")
            print("=" * 80)
        else:
            print("=" * 80)
            print("⚠️  일부 검증 실패. 위 결과를 확인하세요.")
            print("=" * 80)

        await pool.close()

    except asyncpg.InvalidCatalogNameError:
        print(f"❌ 데이터베이스에 연결할 수 없습니다: {db_url}")
        print("💡 DB_PRIMARY_DB_URL 환경변수를 확인하세요.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Solid Cache 검증 스크립트")
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="성능 벤치마크 실행 (시간이 오래 걸릴 수 있음)",
    )
    args = parser.parse_args()

    asyncio.run(main(run_benchmark=args.benchmark))
