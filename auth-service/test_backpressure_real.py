#!/usr/bin/env python3
"""
실제 API로 Backpressure 테스트

POST /api/v1/auth/register (DB 쓰기 - 느림)
"""

import asyncio
import random
import string
import time

import httpx


def random_email():
    """랜덤 이메일 생성"""
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"test_{random_str}@example.com"


async def register_user(client: httpx.AsyncClient, index: int) -> dict:
    """회원가입 요청 (DB INSERT + bcrypt hashing)"""
    try:
        start = time.time()
        response = await client.post(
            "http://localhost:8000/api/v1/auth/register",
            json={
                "email": random_email(),
                "password": "TestPass123!",
                "username": f"testuser_{index}",
            },
            timeout=30.0,
        )
        duration = time.time() - start

        wait_time = response.headers.get("X-Queue-Wait-Time")
        queue_status = response.headers.get("X-Queue-Status")

        return {
            "index": index,
            "status": response.status_code,
            "duration": duration,
            "wait_time": float(wait_time) if wait_time else 0,
            "queue_status": queue_status,
        }
    except TimeoutError:
        return {
            "index": index,
            "status": "timeout",
            "duration": 30.0,
        }
    except Exception as e:
        return {
            "index": index,
            "status": "error",
            "error": str(e)[:80],
        }


async def test_heavy_load(num_requests: int):
    """무거운 작업 부하 테스트"""
    print(f"\n{'='*60}")
    print(f"🧪 테스트: {num_requests}개 동시 회원가입 (DB + bcrypt)")
    print(f"{'='*60}")

    async with httpx.AsyncClient() as client:
        # 동시 요청 발송
        start_time = time.time()
        tasks = [register_user(client, i) for i in range(num_requests)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

    # 결과 분석
    success = [r for r in results if r.get("status") == 201]  # 회원가입 성공
    errors_503 = [r for r in results if r.get("status") == 503]
    errors_other = [
        r for r in results if isinstance(r.get("status"), int) and r.get("status") not in [201, 503]
    ]
    waited = [r for r in results if r.get("wait_time", 0) > 0]

    print("\n📊 결과:")
    print(f"  총 소요 시간: {total_time:.2f}초")
    print("\n  응답 분포:")
    print(f"    ✅ 성공 (201): {len(success)}개")
    print(f"    ❌ 과부하 거부 (503): {len(errors_503)}개")
    if errors_other:
        print(f"    ⚠️  기타 오류: {len(errors_other)}개")
    print(f"    ⏳ 대기열 통과: {len(waited)}개")

    # 503 상세 분석
    if errors_503:
        queue_statuses = {}
        for r in errors_503:
            status = r.get("queue_status", "unknown")
            queue_statuses[status] = queue_statuses.get(status, 0) + 1
        print("\n  503 거부 사유:")
        for status, count in queue_statuses.items():
            print(f"    {status}: {count}개")

    if success:
        durations = [r["duration"] for r in success]
        print("\n  응답 시간 (성공 요청):")
        print(f"    평균: {sum(durations)/len(durations):.3f}초")
        print(f"    최소: {min(durations):.3f}초")
        print(f"    최대: {max(durations):.3f}초")

    if waited:
        wait_times = [r["wait_time"] for r in waited]
        print("\n  대기 시간 (대기열 통과):")
        print(f"    평균: {sum(wait_times)/len(wait_times):.3f}초")
        print(f"    최소: {min(wait_times):.3f}초")
        print(f"    최대: {max(wait_times):.3f}초")

    # 판정
    success_rate = len(success) / num_requests * 100
    rejection_rate = len(errors_503) / num_requests * 100

    print("\n📈 통계:")
    print(f"  성공률: {success_rate:.1f}%")
    print(f"  거부율: {rejection_rate:.1f}%")
    print(f"  처리량: {len(success) / total_time:.1f} req/s")

    # 예상 동작 판정
    if num_requests <= 80:
        if rejection_rate == 0:
            print("\n  ✅ PASS: 임계치 이하, 모두 처리됨")
        else:
            print("\n  ⚠️  UNEXPECTED: 임계치 이하인데 거부 발생")

    elif num_requests <= 580:
        if success_rate >= 90:
            print("\n  ✅ PASS: 대부분 대기 후 처리됨")
            if len(waited) > 0:
                print("       대기열 시스템 정상 동작!")
        else:
            print("\n  ⚠️  일부 거부됨 (시스템 보호 동작)")

    elif rejection_rate > 0:
        print("\n  ✅ PASS: 과부하 보호 동작 확인")
        print("       시스템이 안정적으로 보호됨")
    else:
        print("\n  ⚠️  UNEXPECTED: 과부하인데 거부 없음")


async def main():
    print("=" * 60)
    print("🚀 Backpressure 실제 API 테스트")
    print("=" * 60)
    print("\n⚙️  현재 설정:")
    print("   MAX_CONCURRENT: 80")
    print("   QUEUE_CAPACITY: 500")
    print("   WAIT_TIMEOUT: 5.0초")
    print("\n📝 테스트 API: POST /api/v1/auth/register")
    print("   - DB INSERT 작업")
    print("   - bcrypt 해싱 (CPU 집약적)")
    print("   - 예상 처리 시간: ~200ms/요청")

    # Test 1: 소량 (임계치 이하)
    await test_heavy_load(30)

    # Test 2: 중간 (임계치 근처)
    await test_heavy_load(80)

    # Test 3: 대량 (대기열 사용)
    await test_heavy_load(150)

    # Test 4: 과부하 (거부 예상) - 주석 해제하여 테스트
    # await test_heavy_load(600)

    print(f"\n{'='*60}")
    print("✅ 테스트 완료")
    print("=" * 60)
    print("\n💡 Backpressure 효과:")
    print("  1. 시스템이 처리 가능한 만큼만 받아들임")
    print("  2. 초과 요청은 대기열에서 순차 처리")
    print("  3. 대기열 초과 시 즉시 거부 (시스템 보호)")
    print("  4. 크래시 없이 안정적으로 동작")


if __name__ == "__main__":
    asyncio.run(main())
