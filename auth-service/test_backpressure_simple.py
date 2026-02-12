#!/usr/bin/env python3
"""
간단한 Backpressure 동작 확인

Rate Limiting을 우회하여 Backpressure만 테스트
"""

import asyncio
import time

import httpx


async def make_slow_request(client: httpx.AsyncClient, index: int) -> dict:
    """느린 요청 (서버에서 처리 시간 소요)"""
    try:
        start = time.time()
        # /docs는 Rate Limiting 없음
        response = await client.get("http://localhost:8000/docs", timeout=30.0)
        duration = time.time() - start

        wait_time = response.headers.get("X-Queue-Wait-Time")

        return {
            "index": index,
            "status": response.status_code,
            "duration": duration,
            "wait_time": float(wait_time) if wait_time else 0,
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
            "error": str(e)[:50],
        }


async def test_concurrent_load(num_requests: int):
    """동시 부하 테스트"""
    print(f"\n{'='*60}")
    print(f"🧪 테스트: {num_requests}개 동시 요청")
    print(f"{'='*60}")

    async with httpx.AsyncClient() as client:
        # 동시 요청 발송
        start_time = time.time()
        tasks = [make_slow_request(client, i) for i in range(num_requests)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

    # 결과 분석
    success = [r for r in results if r.get("status") == 200]
    errors_503 = [r for r in results if r.get("status") == 503]
    waited = [r for r in results if r.get("wait_time", 0) > 0]

    print("\n📊 결과:")
    print(f"  총 소요 시간: {total_time:.2f}초")
    print("\n  응답 분포:")
    print(f"    ✅ 성공 (200): {len(success)}개")
    print(f"    ❌ 과부하 거부 (503): {len(errors_503)}개")
    print(f"    ⏳ 대기열 통과: {len(waited)}개")

    if success:
        durations = [r["duration"] for r in success]
        print("\n  응답 시간 (성공 요청):")
        print(f"    평균: {sum(durations)/len(durations):.3f}초")
        print(f"    최소: {min(durations):.3f}초")
        print(f"    최대: {max(durations):.3f}초")

    if waited:
        wait_times = [r["wait_time"] for r in waited]
        print("\n  대기 시간:")
        print(f"    평균: {sum(wait_times)/len(wait_times):.3f}초")
        print(f"    최대: {max(wait_times):.3f}초")

    # 판정
    success_rate = len(success) / num_requests * 100
    rejection_rate = len(errors_503) / num_requests * 100

    print("\n📈 통계:")
    print(f"  성공률: {success_rate:.1f}%")
    print(f"  거부율: {rejection_rate:.1f}%")

    # 예상 동작 판정
    if num_requests <= 80:
        if rejection_rate == 0:
            print("\n  ✅ PASS: 임계치 이하, 모두 처리됨")
        else:
            print("\n  ⚠️  UNEXPECTED: 임계치 이하인데 거부 발생")

    elif num_requests <= 580:
        if success_rate >= 90:
            print("\n  ✅ PASS: 대부분 대기 후 처리됨")
        else:
            print("\n  ⚠️  일부 거부됨 (대기열 포화 가능)")

    elif rejection_rate > 0:
        print("\n  ✅ PASS: 과부하 보호 동작 확인")
    else:
        print("\n  ⚠️  UNEXPECTED: 과부하인데 거부 없음")


async def main():
    print("=" * 60)
    print("🚀 Backpressure 간단 동작 테스트")
    print("=" * 60)
    print("\n⚙️  현재 설정:")
    print("   MAX_CONCURRENT: 80")
    print("   QUEUE_CAPACITY: 500")
    print("   WAIT_TIMEOUT: 5.0초")
    print("\n📝 테스트 엔드포인트: /docs (Rate Limiting 없음)")

    # Test 1: 임계치 이하 (즉시 처리 예상)
    await test_concurrent_load(50)

    # Test 2: 임계치 근처
    await test_concurrent_load(80)

    # Test 3: 대기열 사용 (초과하지만 수용 가능)
    await test_concurrent_load(150)

    print(f"\n{'='*60}")
    print("✅ 테스트 완료")
    print("=" * 60)
    print("\n💡 참고:")
    print("  - /docs 엔드포인트는 HTML 반환이라 처리가 빠름")
    print("  - 실제 API는 DB 쿼리로 더 느릴 수 있음")
    print("  - Backpressure는 동시 처리 한계를 보호하는 역할")


if __name__ == "__main__":
    asyncio.run(main())
