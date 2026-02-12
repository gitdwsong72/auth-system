#!/usr/bin/env python3
"""
Backpressure 동작 확인 테스트

Usage:
    python test_backpressure.py
"""

import asyncio
import httpx
import time
from collections import Counter


async def make_request(client: httpx.AsyncClient, index: int) -> dict:
    """단일 요청"""
    try:
        start = time.time()
        response = await client.get(
            "http://localhost:8000/api/v1/health",
            timeout=10.0
        )
        duration = time.time() - start

        return {
            "index": index,
            "status": response.status_code,
            "duration": duration,
            "wait_time": response.headers.get("X-Queue-Wait-Time"),
        }
    except Exception as e:
        return {
            "index": index,
            "status": "error",
            "error": str(e),
        }


async def test_backpressure(concurrent_requests: int):
    """
    Backpressure 테스트

    Args:
        concurrent_requests: 동시 요청 수
    """
    print(f"\n🧪 테스트: {concurrent_requests}개 동시 요청")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        # 동시 요청 발송
        tasks = [
            make_request(client, i)
            for i in range(concurrent_requests)
        ]

        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

    # 결과 분석
    status_counts = Counter(r["status"] for r in results)
    durations = [r["duration"] for r in results if isinstance(r["status"], int)]
    waited = [r for r in results if r.get("wait_time")]

    # 출력
    print(f"\n📊 결과:")
    print(f"  총 소요 시간: {total_time:.2f}초")
    print(f"\n  응답 상태:")
    for status, count in sorted(status_counts.items()):
        print(f"    {status}: {count}개")

    if durations:
        print(f"\n  응답 시간:")
        print(f"    평균: {sum(durations)/len(durations):.3f}초")
        print(f"    최소: {min(durations):.3f}초")
        print(f"    최대: {max(durations):.3f}초")

    if waited:
        print(f"\n  대기열 통과: {len(waited)}개 요청")
        wait_times = [float(r["wait_time"]) for r in waited]
        print(f"    평균 대기: {sum(wait_times)/len(wait_times):.3f}초")
        print(f"    최대 대기: {max(wait_times):.3f}초")

    # 판정
    success_rate = status_counts.get(200, 0) / concurrent_requests * 100
    print(f"\n✅ 성공률: {success_rate:.1f}%")

    if concurrent_requests <= 80:
        if success_rate == 100 and not waited:
            print("   ✅ PASS: 즉시 처리됨 (대기 없음)")
        else:
            print("   ⚠️  UNEXPECTED: 임계치 이하인데 대기 발생")

    elif concurrent_requests <= 580:
        if success_rate >= 95:
            print("   ✅ PASS: 대부분 대기 후 처리됨")
        else:
            print("   ⚠️  FAIL: 성공률 낮음")

    else:
        if status_counts.get(503, 0) > 0:
            print("   ✅ PASS: 과부하 거부 동작 확인")
        else:
            print("   ⚠️  UNEXPECTED: 과부하인데 거부 안 됨")


async def main():
    """메인 테스트"""
    print("=" * 60)
    print("🚀 Backpressure 동작 확인 테스트")
    print("=" * 60)
    print("\n⚙️  현재 설정:")
    print("   MAX_CONCURRENT: 80")
    print("   QUEUE_CAPACITY: 500")
    print("   WAIT_TIMEOUT: 5.0초")

    # Test 1: 정상 부하 (임계치 이하)
    await test_backpressure(50)

    # Test 2: 임계치 근처
    await test_backpressure(80)

    # Test 3: 대기열 사용 (초과하지만 수용 가능)
    await test_backpressure(150)

    # Test 4: 과부하 (거부 예상)
    # await test_backpressure(600)  # 주석 해제하여 테스트

    print("\n" + "=" * 60)
    print("✅ 테스트 완료")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
