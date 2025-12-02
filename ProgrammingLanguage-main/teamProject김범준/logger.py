"""
================================================================================
logger.py - AMR 작업 로깅 모듈
================================================================================
이 파일은 AMR의 작업 예약 및 완료를 추적하는 로깅 함수들을 제공합니다.

주요 함수:
- _amr_push_task(): AMR 작업 예약 시 tasks 리스트에 추가
- _amr_pop_task(): AMR 작업 완료 시 tasks 리스트에서 제거

AMR 작업 타임라인:
    1. depart_at: AMR이 현재 위치에서 출발
    2. arrive_pick: 픽업 위치 도착
    3. depart_pick: 적재 완료 후 출발 (arrive_pick + 10초)
    4. arrive_drop: 드롭 위치 도착
    5. depart_drop: 하역 완료 후 자유 상태 (arrive_drop + 10초)

용도:
    - AMR의 예정된 작업 가시화
    - 디버깅 및 시뮬레이션 검증
    - AMR 작업 충돌 감지
================================================================================
"""

from typing import Optional
from data_structures import *


def _amr_push_task(amr: AMR, *, job_id: Optional[str], pick_xy, drop_xy,
                   depart_at, arrive_pick, depart_pick, arrive_drop, depart_drop):
    """
    AMR 작업 예약 시 타임라인을 AMR에 기록
    
    Args:
        amr (AMR): 작업을 수행할 AMR
        job_id (Optional[str]): 이송할 제품 ID (예: "ProdA-0001")
        pick_xy: 픽업 위치 좌표
        drop_xy: 드롭 위치 좌표
        depart_at (float): 출발 시간
        arrive_pick (float): 픽업 위치 도착 시간
        depart_pick (float): 픽업 완료 후 출발 시간
        arrive_drop (float): 드롭 위치 도착 시간
        depart_drop (float): 드롭 완료 후 자유 시간
    
    호출 시점:
        - reserve_amr() 함수에서 AMR 예약 직후 호출
    
    타임라인 예시 (픽업까지 10m, 드롭까지 20m):
        depart_at=0 → arrive_pick=10 → depart_pick=20 → arrive_drop=40 → depart_drop=50
                      (10m/1mps)        (+10s 적재)      (20m/1mps)       (+10s 하역)
    """
    amr.tasks.append({
        "job_id": job_id,              # 이송할 제품 ID
        "pick_xy": pick_xy,            # 픽업 위치
        "drop_xy": drop_xy,            # 드롭 위치
        "depart_at": depart_at,        # 출발 시간
        "arrive_pick": arrive_pick,    # 픽업 도착 시간
        "depart_pick": depart_pick,    # 픽업 완료 후 출발 시간
        "arrive_drop": arrive_drop,    # 드롭 도착 시간
        "depart_drop": depart_drop,    # 드롭 완료 시간 (작업 종료)
    })


def _amr_pop_task(amr: AMR, *, job_id: Optional[str], depart_drop: float, tol: float = 1e-9):
    """
    AMR 작업 완료 시 해당 예약을 tasks 리스트에서 제거
    
    Args:
        amr (AMR): 작업을 완료한 AMR
        job_id (Optional[str]): 완료한 제품 ID (우선 매칭 기준)
        depart_drop (float): 드롭 완료 시간 (매칭 기준)
        tol (float): 시간 비교 허용 오차 (부동소수점 오차 대응)
    
    매칭 로직:
        1. job_id + depart_drop 시간 모두 일치하는 작업 우선
        2. job_id 없으면 depart_drop 시간만으로 매칭 (fallback)
    
    호출 시점:
        - sim_core.py의 드롭 완료 이벤트 핸들러에서 호출
    
    Note:
        - 매칭 실패 시 아무 작업도 제거하지 않음 (오류 방지)
        - tol=1e-9로 부동소수점 비교 오차 대응
    """
    idx = -1
    
    # 1차 시도: job_id와 depart_drop 시간 모두 매칭
    if job_id is not None:
        for i, t in enumerate(amr.tasks):
            if t.get("job_id") == job_id and abs(t.get("depart_drop", -1) - depart_drop) < tol:
                idx = i
                break
    
    # 2차 시도 (fallback): depart_drop 시간만으로 매칭
    if idx < 0:
        for i, t in enumerate(amr.tasks):
            if abs(t.get("depart_drop", -1) - depart_drop) < tol:
                idx = i
                break
    
    # 매칭된 작업 제거
    if idx >= 0:
        amr.tasks.pop(idx)
    
        