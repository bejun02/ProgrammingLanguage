"""
================================================================================
config.py - 시뮬레이션 설정 및 유틸리티 모듈
================================================================================
이 파일은 시뮬레이션의 전역 설정과 핵심 유틸리티 함수들을 정의합니다.

주요 기능:
1. GlobalVariable 인스턴스 생성 (전역 상태 관리)
2. 시간 관련 헬퍼 함수 (load_time_for, unload_time_for, process_time_for)
3. 공장 초기화 함수 (build_factory)
4. 이벤트 스케줄링 함수 (schedule, run)
5. 로깅 및 기록 함수 (log, record_machine_run, record_amr_run)

사용 흐름:
    1. main.py에서 FactoryConfig 생성
    2. sim_core.simulate()에서 build_factory() 호출
    3. 시뮬레이션 중 schedule()로 이벤트 예약
    4. run()으로 모든 이벤트 실행
================================================================================
"""

from typing import Optional, Callable, Tuple
import heapq, random
from data_structures import AMR, Machine, Job, Stocker, FactoryConfig, Warehouse, GlobalVariable

# ================================================================================
# 전역 변수 인스턴스 생성
# ================================================================================
# 시뮬레이션 전체에서 공유되는 상태를 관리하는 싱글톤 인스턴스
# 다른 모듈에서 from config import global_variable로 import하여 사용
global_variable = GlobalVariable()


# ================================================================================
# 시뮬레이션 초기화 함수
# ================================================================================
def reset_sim():
    """
    시나리오 재실행을 위한 전역 상태 완전 초기화
    
    여러 시나리오를 연속 실행할 때, 이전 실행의 상태를 깨끗이 제거합니다.
    - 모든 Machine, AMR, Job 초기화
    - 이벤트 큐(pq) 초기화
    - 생산 통계 초기화
    """
    global_variable.reset()


# ================================================================================
# AMR 적재/하역 시간 함수
# ================================================================================
def load_time_for(stage: str) -> float:
    """
    특정 스테이지에서 AMR 적재(load) 시간 반환
    
    Args:
        stage (str): 공정 스테이지 ("A"~"E", "WH", "STK")
    
    Returns:
        float: 적재 시간 (기본 10초)
    
    Note:
        - 과제 조건상 모든 스테이지에서 10초 고정
        - stage별 다른 시간이 필요하면 cfg.amr_load_time_by_stage로 설정 가능
    """
    cfg = global_variable.CURRENT_CFG
    if cfg is None:
        return global_variable.DEFAULT_AMR_LOAD  # 10초
    
    base = getattr(cfg, "amr_load_time", global_variable.DEFAULT_AMR_LOAD)
    stage_map = getattr(cfg, "amr_load_time_by_stage", None)
    
    # 스테이지별 커스텀 시간이 있으면 사용
    if stage_map and stage in stage_map:
        return stage_map[stage]
    return base


def unload_time_for(stage_or_stk: str) -> float:
    """
    특정 스테이지에서 AMR 하역(unload) 시간 반환
    
    Args:
        stage_or_stk (str): 공정 스테이지 또는 Stocker ID
    
    Returns:
        float: 하역 시간 (기본 10초)
    
    Note:
        - 과제 조건상 모든 위치에서 10초 고정
        - 위치별 다른 시간이 필요하면 cfg.amr_unload_time_by_stage로 설정 가능
    """
    cfg = global_variable.CURRENT_CFG
    if cfg is None:
        return global_variable.DEFAULT_AMR_UNLOAD  # 10초
    
    base = getattr(cfg, "amr_unload_time", global_variable.DEFAULT_AMR_UNLOAD)
    stage_map = getattr(cfg, "amr_unload_time_by_stage", None)
    
    # 스테이지별 커스텀 시간이 있으면 사용
    if stage_map and stage_or_stk in stage_map:
        return stage_map[stage_or_stk]
    return base


# ================================================================================
# 공정 흐름 관련 함수
# ================================================================================
def next_stage_for(job: Job, current_stage: str) -> Optional[str]:
    """
    현재 공정 완료 후 다음 스테이지 결정
    
    Args:
        job (Job): 현재 제품
        current_stage (str): 현재 완료된 스테이지 ("A"~"E")
    
    Returns:
        Optional[str]: 다음 스테이지 ("A"~"E") 또는 None (완료 시)
    
    로직:
        1. job.pending_stage가 이미 설정되어 있으면 그대로 반환
        2. 현재 스테이지가 E가 아니면 다음 스테이지(B,C,D,E)로
        3. E 완료 시:
           - cycle_idx < max_cycles-1 이면 A로 돌아감 (2사이클 반복)
           - 그렇지 않으면 None (Stocker로 이동)
    
    공정 흐름 예시:
        ProdA 1사이클: A → B → C → D → E
        ProdA 2사이클: A → B → C → D → E → Stocker
    """
    # 이미 다음 스테이지가 결정되어 있으면 그대로 반환 (중복 계산 방지)
    if getattr(job, "pending_stage", None):
        return job.pending_stage
    
    try:
        i = global_variable.ROUTE.index(current_stage)  # 현재 스테이지 인덱스
    except ValueError:
        return None
    
    # 아직 E가 아니면 다음 공정으로
    if i + 1 < len(global_variable.ROUTE):
        job.pending_stage = global_variable.ROUTE[i + 1]
        return job.pending_stage
    
    # E 완료 → 사이클 반복 여부 확인
    if job.cycle_idx + 1 < job.max_cycles:
        job.cycle_idx += 1           # 사이클 증가 (0 → 1)
        job.pending_stage = global_variable.ROUTE[0]  # A로 돌아감
        return job.pending_stage
    else:
        return None  # 2사이클 완료 → Stocker로


def process_time_for(stage: str, job: Job, m: Optional[Machine] = None) -> float:
    """
    주어진 제품의 사이클과 스테이지에 맞는 공정시간 반환
    
    Args:
        stage (str): 공정 스테이지 ("A"~"E")
        job (Job): 현재 제품 (product, cycle_idx 정보 포함)
        m (Optional[Machine]): 설비 (현재 미사용, 추후 확장용)
    
    Returns:
        float: 공정 시간 (초 단위)
    
    공정시간 테이블 (분):
    ┌──────────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
    │          │ A1 │ B1 │ C1 │ D1 │ E1 │ A2 │ B2 │ C2 │ D2 │ E2 │
    ├──────────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
    │ ProdA    │ 15 │ 15 │ 15 │ 15 │ 15 │ 15 │ 15 │ 15 │ 15 │ 15 │
    │ ProdB    │  5 │ 40 │ 25 │ 25 │ 15 │ 10 │ 20 │ 10 │ 10 │ 15 │
    └──────────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘
    
    Note:
        - ProdA: 모든 공정에서 15분(900초) 균일
        - ProdB: 공정별로 상이 (병목 공정: B1=40분)
    """
    cfg = global_variable.CURRENT_CFG
    try:
        if cfg and getattr(cfg, "process_times_by_product_cycle", None):
            per_cycle = cfg.process_times_by_product_cycle.get(job.product, {})
            
            # 정확한 사이클/스테이지 매칭 시도
            if job.cycle_idx in per_cycle and stage in per_cycle[job.cycle_idx]:
                return per_cycle[job.cycle_idx][stage]
            
            # 정확한 매칭 실패 시, 가장 가까운 하위 사이클 값 사용
            if per_cycle:
                cand = [(k, d[stage]) for k, d in per_cycle.items()
                        if k <= job.cycle_idx and stage in d]
                if cand:
                    cand.sort(key=lambda x: x[0], reverse=True)
                    return cand[0][1]
    except:
        print("ERROR: process_time_for 계산 중 오류 발생")


# ================================================================================
# 공장 초기화 함수
# ================================================================================
def build_factory(cfg: FactoryConfig):
    """
    공장 초기 설정 생성 - 설비, AMR, 창고, Stocker 생성
    
    Args:
        cfg (FactoryConfig): 공장 설정 객체
    
    생성 순서:
        1. 랜덤 시드 설정
        2. 각 스테이지(A~E)의 설비 생성
        3. AMR 생성
        4. 원자재 창고(Warehouse) 생성
        5. 완제품 보관소(Stocker) 생성
    
    검증 사항:
        - 설비 좌표가 machine_positions에 제공되었는지
        - 좌표 개수가 설비 개수와 일치하는지
        - 좌표 형식이 올바른지 (x, y) 튜플
        - 중복 좌표가 없는지
    
    Raises:
        ValueError: 좌표 누락, 부족, 형식 오류, 중복 시 발생
    """
    random.seed(cfg.seed)
    global_variable.MACHINES.clear()
    
    # ===== 스테이지별 설비 생성 =====
    for stage in global_variable.ROUTE:
        n = cfg.machine_counts.get(stage, 0)  # 해당 스테이지 설비 개수
        pt = cfg.process_times.get(stage, 1.0)  # 기본 공정 시간 (실제론 process_time_for 사용)
        
        # --- 좌표 검증 ---
        if not cfg.machine_positions or stage not in cfg.machine_positions:
            raise ValueError(f"[build_factory] '{stage}' 스테이지의 수동 좌표가 누락되었습니다. (필요 개수: {n})")
        
        manual_positions = cfg.machine_positions[stage]
        
        if len(manual_positions) < n:
            raise ValueError(
                f"[build_factory] '{stage}' 스테이지의 수동 좌표가 부족합니다. "
                f"필요: {n}, 제공: {len(manual_positions)}"
            )
        elif len(manual_positions) > n:
            log(f"[build_factory] '{stage}': 좌표 {len(manual_positions)}개 중 앞의 {n}개만 사용합니다.")
            manual_positions = manual_positions[:n]

        # 좌표 형식 검증
        for i, xy in enumerate(manual_positions):
            if not isinstance(xy, tuple) or len(xy) != 2:
                raise ValueError(f"[build_factory] '{stage}' 좌표 #{i+1} 형식 오류: {xy} (예: (x, y))")
        
        # 중복 좌표 검증
        if len(set(manual_positions)) != len(manual_positions):
            raise ValueError(f"[build_factory] '{stage}' 수동 좌표에 중복이 있습니다: {manual_positions}")

        # --- 설비 이름 설정 ---
        manual_names = []
        if cfg.machine_names and stage in cfg.machine_names:
            manual_names = cfg.machine_names[stage]
            if len(manual_names) < n:
                raise ValueError(
                    f"[build_factory] '{stage}' 설비 이름이 부족합니다. 필요: {n}, 제공: {len(manual_names)}"
                )
            elif len(manual_names) > n:
                log(f"[build_factory] '{stage}': 이름 {len(manual_names)}개 중 앞의 {n}개만 사용합니다.")
                manual_names = manual_names[:n]

        # --- 설비 생성 ---
        global_variable.MACHINES[stage] = []
        for idx in range(n):
            mname = manual_names[idx] if manual_names else f"{stage}-{idx+1}"
            xy = manual_positions[idx]
            global_variable.MACHINES[stage].append(Machine(mname, stage, xy, pt))
    
    # ===== AMR 생성 =====
    global_variable.AMRS.clear()
    
    # AMR 초기 위치 설정
    if cfg.amr_positions and len(cfg.amr_positions) >= cfg.amr_count:
        positions = cfg.amr_positions[:cfg.amr_count]
    else:
        # 기본 위치: 창고 근처에 0.1m 간격으로 배치
        positions = [(4.0, i * 0.1) for i in range(cfg.amr_count)]

    for i in range(cfg.amr_count):
        global_variable.AMRS.append(AMR(f"AMR-{i+1:02d}", positions[i], cfg.amr_speed))

    if len(global_variable.AMRS) == 0:
        log("⚠️ AMR가 0대입니다. 이 상태에선 공정 간 이송이 불가합니다.")
    
    # ===== 창고 및 Stocker 생성 =====
    # 원자재 창고: 고정 위치 (4, 10)
    global_variable.WAREHOUSE = Warehouse(name="WH-01", xy=cfg.warehouse_xy)
    
    # 완제품 보관소: 고정 위치 (56, 10)
    global_variable.STOCKERS["STK-01"] = Stocker(name="STK-01", xy=cfg.stocker_xy)


# ================================================================================
# 로깅 및 기록 함수
# ================================================================================
def log(msg: str):
    """
    시뮬레이션 시간과 함께 메시지 출력
    
    Args:
        msg (str): 출력할 메시지
    
    출력 형식: [t=  123.45s] 메시지 내용
    """
    print(f"[t={global_variable.now:6.2f}s] {msg}")


def record_machine_run(m: Machine, job: Job, s: float, e: float):
    """
    설비 가동 기록 저장 (시각화 및 분석용)
    
    Args:
        m (Machine): 설비 객체
        job (Job): 가공한 제품
        s (float): 가공 시작 시간
        e (float): 가공 종료 시간
    
    저장 형식:
        machine_runs[설비명] = [(시작, 종료, job_id, stage), ...]
        job_runs[job_id] = [(stage, 시작, 종료, 설비명), ...]
    """
    global_variable.machine_runs.setdefault(m.name, []).append((s, e, job.job_id, m.stage))
    global_variable.job_runs.setdefault(job.job_id, []).append((m.stage, s, e, m.name))


def record_amr_run(a: AMR, job: Job, s: float, e: float, 
                   frm: Tuple[float, float], to: Tuple[float, float], loaded: bool):
    """
    AMR 이동 기록 저장 (시각화 및 분석용)
    
    Args:
        a (AMR): AMR 객체
        job (Job): 이송한 제품
        s (float): 이동 시작 시간
        e (float): 이동 종료 시간
        frm (Tuple): 출발 좌표
        to (Tuple): 도착 좌표
        loaded (bool): 제품 적재 여부 (True=적재 이동, False=공차 이동)
    
    저장 형식:
        amr_runs[AMR명] = [(시작, 종료, job_id, 출발, 도착, 적재여부), ...]
    """
    global_variable.amr_runs.setdefault(a.name, []).append((s, e, job.job_id, frm, to, loaded))


# ================================================================================
# 이벤트 스케줄링 함수
# ================================================================================
def schedule(at: float, fn: Callable[[], None]):
    """
    특정 시간에 실행할 이벤트를 스케줄에 등록
    
    Args:
        at (float): 이벤트 실행 시간 (시뮬레이션 시간 기준)
        fn (Callable): 실행할 함수 (인자 없음)
    
    Note:
        - heapq(최소 힙)를 사용하여 시간순 정렬 자동 유지
        - 같은 시간의 이벤트는 _seq(순서 번호)로 FIFO 정렬
        - 이산 사건 시뮬레이션의 핵심 메커니즘
    
    Example:
        schedule(100.0, lambda: print("100초에 실행"))
        schedule(50.0, lambda: on_finish_processing(machine))
    """
    global_variable._seq += 1
    heapq.heappush(global_variable.pq, (at, global_variable._seq, fn))


def run():
    """
    이벤트 루프 실행 - t=0부터 종료 시점까지 모든 이벤트 처리
    
    동작 원리:
        1. 우선순위 큐(pq)에서 가장 이른 이벤트를 꺼냄
        2. 해당 시간으로 now 업데이트
        3. 이벤트 함수 실행
        4. 종료 시간(SIM_END) 초과 시 중단
    
    Note:
        - 이벤트 실행 중 새로운 이벤트가 schedule()될 수 있음
        - 이벤트가 없어지면 (pq가 비면) 자동 종료
    """
    while global_variable.pq:
        at, _, fn = heapq.heappop(global_variable.pq)  # 가장 이른 이벤트 추출
        
        # 종료 시간 초과 체크
        if at > global_variable.SIM_END:
            global_variable.now = global_variable.SIM_END
            break
        
        global_variable.now = at  # 시뮬레이션 시간 업데이트
        fn()  # 이벤트 함수 실행

