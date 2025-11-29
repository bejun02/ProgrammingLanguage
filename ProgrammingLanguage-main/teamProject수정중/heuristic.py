"""
================================================================================
heuristic.py - 설비 디스패칭 & AMR 라우팅 휴리스틱 모듈
================================================================================

이 파일은 고급 스케줄링 휴리스틱을 구현합니다.

주요 기능:
1. 설비 디스패칭 (Machine Routing): Score 기반 최적 설비 선택
2. AMR 디스패칭: Score 기반 최적 AMR 선택

설비 Score 공식:
    Score(m) = LocalWait(m) + α*DownstreamWork_norm(m) + β*Dist(m) + Δ(t,p) + BN(t)

AMR Score 공식:
    Score_AMR(k) = FinishAMR(k) - η*w(t)

파라미터:
    - α (alpha): DownstreamWork 가중치 (기본: 0.5)
    - β (beta): 거리 가중치 (기본: 1.0)
    - γ (gamma): 비율 보정 강도 (기본: 10)
    - δ (delta): 병목 보정 강도 (기본: 20)
    - η (eta): AMR 병목 우선 강도 (기본: 10)

병목 공정: C, E (설비 배분 분석 기반)
================================================================================
"""

from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass, field
import math

# pathfinding 연동을 위한 거리 함수 (외부에서 주입 가능)
# sim_core에서 set_distance_func()로 pathfinding_dist를 연결
_distance_func: Optional[Callable[[Tuple[float, float], Tuple[float, float]], float]] = None

def set_distance_func(func: Callable[[Tuple[float, float], Tuple[float, float]], float]):
    """외부에서 거리 계산 함수 주입 (pathfinding 연동용)"""
    global _distance_func
    _distance_func = func

def get_move_distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """
    두 점 사이 이동 거리 계산
    
    pathfinding이 연동되어 있으면 다익스트라 경로 거리 사용,
    아니면 유클리드 직선 거리 사용
    """
    if _distance_func is not None:
        return _distance_func(a, b)
    return math.hypot(a[0] - b[0], a[1] - b[1])

# ================================================================================
# 휴리스틱 파라미터 클래스
# ================================================================================
@dataclass
class HeuristicParams:
    """휴리스틱 파라미터 설정
    
    Note:
        시뮬레이션이 초(second) 단위로 동작하므로,
        LocalWait이 수천~수만 초 범위임을 고려하여 파라미터 설정.
        γ, δ, η는 분 단위 감각의 60배로 스케일링됨.
        
    최적화 (2024-11-27):
        - delta: 1200 → 1314 (권장값, 병목분석 기반)
        - D1=2분 기준 병목: C, E (각 최대 2160쌍)
    """
    alpha: float = 0.5        # DownstreamWork 가중치
    beta: float = 1.0         # 이동시간 가중치 (거리→시간으로 변경됨)
    gamma: float = 600.0      # 비율 보정 강도 (10 * 60)
    delta: float = 1314.0     # 병목 보정 강도 (권장값) - C, E 우선
    eta: float = 600.0        # AMR 병목 우선 강도 (10 * 60)
    downstream_scale: float = 1000.0  # DownstreamWork 정규화 스케일


# ================================================================================
# 공정 데이터 (README 기준)
# ================================================================================
# 공정 순서
ROUTE = ["A", "B", "C", "D", "E"]

# 가공 시간 (초)
PROCESS_TIMES = {
    "ProdA": {
        0: {"A": 15*60, "B": 15*60, "C": 15*60, "D": 15*60, "E": 15*60},  # 1사이클
        1: {"A": 15*60, "B": 15*60, "C": 15*60, "D": 15*60, "E": 15*60},  # 2사이클
    },
    "ProdB": {
        0: {"A": 5*60, "B": 40*60, "C": 25*60, "D": 2*60, "E": 5*60},     # 1사이클
        1: {"A": 10*60, "B": 10*60, "C": 5*60, "D": 10*60, "E": 15*60},   # 2사이클
    },
}

# 1차/2차 비율 목표 (ProdA + ProdB 합산, D1=2분 반영)
# A: (15+5):(15+10) = 20:25 → 1차비율 = 20/45 = 44%
# B: (15+40):(15+10) = 55:25 → 1차비율 = 55/80 = 69%
# C: (15+25):(15+5) = 40:20 → 1차비율 = 40/60 = 67%
# D: (15+2):(15+10) = 17:25 → 1차비율 = 17/42 = 40% (D1=2분)
# E: (15+5):(15+15) = 20:30 → 1차비율 = 20/50 = 40%
TARGET_RATIO_1ST = {
    "A": 20 / 45,   # 44%
    "B": 55 / 80,   # 69%
    "C": 40 / 60,   # 67%
    "D": 17 / 42,   # 40%
    "E": 20 / 50,   # 40%
}

# 병목 공정 (설비 배분 분석 기반: C, E가 병목)
BOTTLENECK_STAGES = {"C", "E"}

# AMR 병목 방향 가중치 (D1=2분 기준, D는 병목 아님)
AMR_BOTTLENECK_WEIGHT = {
    "A": 0,
    "B": 0,
    "C": 2,  # 병목 (최대 2160쌍)
    "D": 0,  # 비병목 (최대 2571쌍) - D1=2분으로 여유 있음
    "E": 2,  # 병목 (최대 2160쌍)
}


# ================================================================================
# 휴리스틱 상태 추적 클래스
# ================================================================================
@dataclass
class HeuristicState:
    """휴리스틱 상태 추적
    
    Note:
        cum1, cum2는 "처리시간 누적"으로 관리 (횟수 아님).
        TARGET_RATIO_1ST가 시간 기준 비율이므로, 동일한 단위로 비교해야
        Δ(t,p) 보정이 올바르게 동작함.
    """
    # 각 stage별 누적 1차/2차 처리시간 (초 단위)
    cum1: Dict[str, float] = field(default_factory=lambda: {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0, "E": 0.0})
    cum2: Dict[str, float] = field(default_factory=lambda: {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0, "E": 0.0})
    
    # 설비별 avail_time (큐 처리 후 비게 되는 시각)
    avail_time: Dict[str, float] = field(default_factory=dict)
    
    # AMR별 free_time, position
    amr_free_time: Dict[str, float] = field(default_factory=dict)
    amr_position: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    
    def get_ratio1(self, stage: str) -> float:
        """현재 1차 처리시간 비율 계산 (시간 기준)"""
        total = self.cum1[stage] + self.cum2[stage]
        if total == 0:
            return TARGET_RATIO_1ST[stage]  # 초기값은 목표값 사용
        return self.cum1[stage] / total
    
    def update_cycle_count(self, stage: str, cycle_idx: int, process_time: float = 1.0):
        """
        공정 완료 시 처리시간 누적 업데이트
        
        Args:
            stage: 공정 스테이지 (A~E)
            cycle_idx: 사이클 인덱스 (0=1차, 1=2차)
            process_time: 해당 공정의 처리시간 (초)
        """
        if cycle_idx == 0:
            self.cum1[stage] += process_time
        else:
            self.cum2[stage] += process_time


# 전역 상태 인스턴스
heuristic_state = HeuristicState()
heuristic_params = HeuristicParams()


# ================================================================================
# 유틸리티 함수
# ================================================================================
def euclidean_dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """유클리드 거리 계산"""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def get_process_time(product: str, cycle_idx: int, stage: str) -> float:
    """Job의 특정 공정 처리시간 반환 (초)"""
    return PROCESS_TIMES.get(product, {}).get(cycle_idx, {}).get(stage, 0)


def calculate_remaining_time(product: str, cycle_idx: int, current_stage: str, max_cycles: int = 2) -> float:
    """
    Job의 남은 모든 공정 처리시간 합 (R_sys)
    
    Args:
        product: 제품 종류 ("ProdA" or "ProdB")
        cycle_idx: 현재 사이클 (0 or 1)
        current_stage: 현재 공정 ("A"~"E")
        max_cycles: 최대 사이클 수 (기본 2)
    
    Returns:
        남은 총 처리시간 (초)
    """
    remaining = 0.0
    
    # 현재 스테이지 인덱스
    try:
        current_idx = ROUTE.index(current_stage)
    except ValueError:
        current_idx = -1
    
    # 현재 사이클의 남은 공정
    for stage in ROUTE[current_idx + 1:]:
        remaining += get_process_time(product, cycle_idx, stage)
    
    # 다음 사이클 (있으면)
    if cycle_idx + 1 < max_cycles:
        next_cycle = cycle_idx + 1
        for stage in ROUTE:
            remaining += get_process_time(product, next_cycle, stage)
    
    return remaining


def get_machine_priority(machine_id: str) -> int:
    """Machine ID를 숫자로 변환 (낮을수록 우선)"""
    # "A-01" → 1, "B-03" → 3
    try:
        return int(machine_id.split("-")[1])
    except (IndexError, ValueError):
        return 999


# ================================================================================
# 설비 디스패칭 휴리스틱
# ================================================================================
def calculate_machine_score(
    job_product: str,
    job_cycle_idx: int,
    current_machine_pos: Tuple[float, float],
    target_machine,
    target_stage: str,
    now: float,
    params: HeuristicParams = None
) -> Tuple[float, float]:
    """
    설비 Score 계산
    
    Args:
        job_product: 제품 종류
        job_cycle_idx: 현재 사이클 (0=1차, 1=2차)
        current_machine_pos: 현재 설비 output_port 위치
        target_machine: 후보 설비 객체 (Machine)
        target_stage: 다음 공정 스테이지
        now: 현재 시뮬레이션 시간
        params: 휴리스틱 파라미터
    
    Returns:
        (score, dist): 설비 점수와 거리
    
    Score 공식:
        Score(m) = LocalWait(m) + α*DownstreamWork_norm(m) + β*Dist(m) + Δ(t,p) + BN(t)
    """
    if params is None:
        params = heuristic_params
    
    # ----- 1. LocalWait(m) -----
    # avail_time[m]: 설비가 비게 되는 시각
    avail_time = heuristic_state.avail_time.get(target_machine.name, now)
    
    # move_time: 현재 설비 → 후보 설비 이동시간 (pathfinding 거리/속도)
    # get_move_distance(): pathfinding 연동 시 다익스트라 경로 거리 사용
    move_dist = get_move_distance(current_machine_pos, target_machine.input_port)
    amr_speed = 1.0  # m/s
    move_time = move_dist / amr_speed
    
    # 처리 시간
    process_time = get_process_time(job_product, job_cycle_idx, target_stage)
    
    # LocalWait = max(avail_time, now + move_time) - now + process_time
    local_wait = max(avail_time, now + move_time) - now + process_time
    
    # ----- 2. DownstreamWork(m) -----
    # 설비 큐에 있는 제품들의 R_sys 합
    downstream_work = 0.0
    if hasattr(target_machine, 'input_buf'):
        for queued_job in target_machine.input_buf:
            r_sys = calculate_remaining_time(
                queued_job.product,
                queued_job.cycle_idx,
                target_stage,
                queued_job.max_cycles
            )
            downstream_work += r_sys
    
    # 정규화
    downstream_work_norm = downstream_work / params.downstream_scale
    
    # ----- 3. Dist(m): 이동시간 기준 (거리 아님) -----
    # 단위 일관성을 위해 move_time(초)을 사용
    dist_score = move_time
    
    # ----- 4. Δ(t,p): 비율 보정 -----
    target1 = TARGET_RATIO_1ST.get(target_stage, 0.5)
    ratio1 = heuristic_state.get_ratio1(target_stage)
    
    if job_cycle_idx == 0:  # 1차
        delta = -params.gamma * (target1 - ratio1)
    else:  # 2차
        delta = params.gamma * (target1 - ratio1)
    
    # ----- 5. BN(t): 병목 보정 -----
    if target_stage in BOTTLENECK_STAGES:
        bn = -params.delta
    else:
        bn = 0
    
    # ----- 최종 Score -----
    score = (
        local_wait +
        params.alpha * downstream_work_norm +
        params.beta * dist_score +
        delta +
        bn
    )
    
    return score, dist_score


def select_best_machine(
    job,
    current_machine,
    target_stage: str,
    candidate_machines: list,
    now: float,
    params: HeuristicParams = None
):
    """
    최적 설비 선택 (Score 최소화)
    
    Args:
        job: Job 객체
        current_machine: 현재 설비 객체
        target_stage: 다음 공정 스테이지
        candidate_machines: 후보 설비 리스트 (입력 슬롯 여유 있는 설비들)
        now: 현재 시뮬레이션 시간
        params: 휴리스틱 파라미터
    
    Returns:
        선택된 설비 객체 (또는 None)
    
    선택 규칙:
        1. Score가 최소인 설비
        2. Score 동점 시: Dist가 짧은 설비
        3. Dist도 동점 시: machine_id가 작은 설비
    """
    if not candidate_machines:
        return None
    
    if params is None:
        params = heuristic_params
    
    # 현재 설비 위치
    current_pos = current_machine.output_port
    
    # 각 후보 설비에 대해 Score 계산
    scored_machines = []
    for m in candidate_machines:
        score, dist_val = calculate_machine_score(
            job_product=job.product,
            job_cycle_idx=job.cycle_idx,
            current_machine_pos=current_pos,
            target_machine=m,
            target_stage=target_stage,
            now=now,
            params=params
        )
        priority = get_machine_priority(m.name)
        scored_machines.append((score, dist_val, priority, m))
    
    # 정렬: (score, dist, priority) 오름차순
    scored_machines.sort(key=lambda x: (x[0], x[1], x[2]))
    
    # 최적 설비 반환
    return scored_machines[0][3]


# ================================================================================
# AMR 디스패칭 휴리스틱
# ================================================================================
def calculate_amr_score(
    amr,
    pick_xy: Tuple[float, float],
    drop_xy: Tuple[float, float],
    target_stage: str,
    now: float,
    params: HeuristicParams = None
) -> Tuple[float, float]:
    """
    AMR Score 계산
    
    Args:
        amr: AMR 객체
        pick_xy: 픽업 위치
        drop_xy: 드롭 위치
        target_stage: 목적지 공정 스테이지
        now: 현재 시뮬레이션 시간
        params: 휴리스틱 파라미터
    
    Returns:
        (score, move_time_to_pick): AMR 점수와 픽업지까지 이동시간
    
    Score 공식:
        Score_AMR(k) = FinishAMR(k) - η*w(t)
    """
    if params is None:
        params = heuristic_params
    
    # AMR 가용 시점
    free_time = amr.free_time if hasattr(amr, 'free_time') else now
    
    # AMR 현재/미래 위치
    if hasattr(amr, 'planned_xy') and amr.planned_xy is not None and free_time > now:
        amr_pos = amr.planned_xy
    else:
        amr_pos = amr.xy
    
    # 이동 시간 계산 (pathfinding 연동)
    # get_move_distance(): 다익스트라 경로 거리 사용 (설비 우회)
    amr_speed = amr.speed if hasattr(amr, 'speed') else 1.0
    t_to_pick = get_move_distance(amr_pos, pick_xy) / max(amr_speed, 1e-9)
    t_pick_to_drop = get_move_distance(pick_xy, drop_xy) / max(amr_speed, 1e-9)
    
    # FinishAMR 계산
    depart_at = max(free_time, now + t_to_pick)
    finish_amr = depart_at + t_pick_to_drop
    
    # 병목 방향 가중치
    w_t = AMR_BOTTLENECK_WEIGHT.get(target_stage, 0)
    
    # Score
    score = finish_amr - params.eta * w_t
    
    return score, t_to_pick


def select_best_amr(
    amrs: list,
    pick_xy: Tuple[float, float],
    drop_xy: Tuple[float, float],
    target_stage: str,
    now: float,
    params: HeuristicParams = None
):
    """
    최적 AMR 선택 (Score 최소화)
    
    Args:
        amrs: AMR 객체 리스트
        pick_xy: 픽업 위치
        drop_xy: 드롭 위치
        target_stage: 목적지 공정 스테이지
        now: 현재 시뮬레이션 시간
        params: 휴리스틱 파라미터
    
    Returns:
        선택된 AMR 객체 (또는 None)
    
    선택 규칙:
        1. Score가 최소인 AMR
        2. Score 동점 시: move_time(pos[k], S)가 짧은 AMR
        3. 그래도 동점 시: AMR id가 작은 것
    """
    if not amrs:
        return None
    
    if params is None:
        params = heuristic_params
    
    # 각 AMR에 대해 Score 계산
    scored_amrs = []
    for amr in amrs:
        score, t_to_pick = calculate_amr_score(
            amr=amr,
            pick_xy=pick_xy,
            drop_xy=drop_xy,
            target_stage=target_stage,
            now=now,
            params=params
        )
        amr_id = int(amr.name.split("-")[1]) if "-" in amr.name else 999
        scored_amrs.append((score, t_to_pick, amr_id, amr))
    
    # 정렬: (score, t_to_pick, amr_id) 오름차순
    scored_amrs.sort(key=lambda x: (x[0], x[1], x[2]))
    
    # 최적 AMR 반환
    return scored_amrs[0][3]


# ================================================================================
# 상태 업데이트 함수
# ================================================================================
def update_avail_time(machine, finish_time: float):
    """설비의 avail_time 업데이트"""
    heuristic_state.avail_time[machine.name] = finish_time


def update_cycle_count(stage: str, cycle_idx: int, process_time: float = 1.0):
    """
    공정 완료 시 처리시간 누적 업데이트
    
    Args:
        stage: 공정 스테이지 (A~E)
        cycle_idx: 사이클 인덱스 (0=1차, 1=2차)
        process_time: 해당 공정의 처리시간 (초). 기본값 1.0은 하위 호환용.
    """
    heuristic_state.update_cycle_count(stage, cycle_idx, process_time)


def reset_heuristic_state():
    """휴리스틱 상태 초기화"""
    global heuristic_state
    heuristic_state = HeuristicState()


# ================================================================================
# 디버깅/로깅 함수
# ================================================================================
def print_heuristic_status():
    """현재 휴리스틱 상태 출력 (디버깅용)"""
    print("\n=== Heuristic Status ===")
    print(f"Parameters: α={heuristic_params.alpha}, β={heuristic_params.beta}, "
          f"γ={heuristic_params.gamma}, δ={heuristic_params.delta}, η={heuristic_params.eta}")
    print(f"Distance func connected: {_distance_func is not None}")
    
    print("\nCycle Processing Times (1st / 2nd) [seconds]:")
    for stage in ROUTE:
        c1 = heuristic_state.cum1[stage]
        c2 = heuristic_state.cum2[stage]
        ratio = heuristic_state.get_ratio1(stage)
        target = TARGET_RATIO_1ST[stage]
        print(f"  {stage}: {c1:.0f}s / {c2:.0f}s (ratio1={ratio:.2%}, target={target:.2%})")
    
    print("\nAvail Times:")
    for name, time in sorted(heuristic_state.avail_time.items()):
        print(f"  {name}: {time:.2f}s")
    
    print("=" * 30)


# ================================================================================
# 테스트 함수
# ================================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("Heuristic Module Test")
    print("=" * 70)
    
    # 파라미터 출력
    print(f"\nDefault Parameters:")
    print(f"  α (alpha): {heuristic_params.alpha}")
    print(f"  β (beta): {heuristic_params.beta}")
    print(f"  γ (gamma): {heuristic_params.gamma}")
    print(f"  δ (delta): {heuristic_params.delta}")
    print(f"  η (eta): {heuristic_params.eta}")
    
    # 목표 비율 출력
    print(f"\nTarget Ratio (1st cycle):")
    for stage, ratio in TARGET_RATIO_1ST.items():
        print(f"  {stage}: {ratio:.2%}")
    
    # 병목 공정 출력
    print(f"\nBottleneck Stages: {BOTTLENECK_STAGES}")
    
    # R_sys 계산 테스트
    print(f"\nRemaining Time Test (R_sys):")
    for product in ["ProdA", "ProdB"]:
        for cycle in [0, 1]:
            r_sys = calculate_remaining_time(product, cycle, "A", max_cycles=2)
            print(f"  {product}, cycle={cycle}, stage=A → R_sys={r_sys/60:.1f}분")
    
    print("\n" + "=" * 70)
    print("✅ Heuristic module loaded successfully!")
    print("=" * 70)
