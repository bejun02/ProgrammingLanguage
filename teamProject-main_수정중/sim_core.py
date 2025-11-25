"""
================================================================================
sim_core.py - 시뮬레이션 핵심 로직 모듈
================================================================================
이 파일은 반도체 공장 시뮬레이션의 핵심 로직을 담당합니다.

주요 기능:
1. simulate(): 시뮬레이션 메인 함수
2. AMR 예약 및 이동 (reserve_amr, record_amr_run)
3. 설비 가공 시작/완료 (try_start_processing, on_finish_processing)
4. 공정 간 제품 이동 (move_to_next_stage_from_output)
5. 이전 공정에서 제품 당겨오기 (pull_from_prev_to)

시뮬레이션 흐름:
    1. simulate(cfg) 호출
    2. reset_sim() → 상태 초기화
    3. build_factory(cfg) → 설비/AMR/창고 생성
    4. bootstrap_start() → 초기 제품 투입
    5. run() → 이벤트 루프 실행
    6. 결과 반환 (machine_runs, amr_runs 등)

이산 사건 시뮬레이션 (Discrete Event Simulation):
    - heapq로 이벤트 우선순위 큐 관리
    - schedule(time, callback)으로 이벤트 예약
    - run()에서 시간순으로 이벤트 처리

================================================================================
"""

import math, random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from data_structures import *
from config import *
from config import global_variable
from logger import _amr_push_task, _amr_pop_task
from pathfinding import init_obstacle_map, pathfinding_dist, obstacle_map


# ================================================================================
# 메인 시뮬레이션 함수
# ================================================================================
def simulate(cfg: FactoryConfig):
    """
    시뮬레이션 메인 함수 - 시나리오별 설정으로 실행
    
    Args:
        cfg (FactoryConfig): 공장 설정 객체
    
    실행 순서:
        1. reset_sim(): 이전 시뮬레이션 상태 초기화
        2. 설정 저장 (CURRENT_CFG, SIM_END)
        3. build_factory(): 설비/AMR/창고 생성
        4. FEED_SEQ 설정: 제품 투입 순서 (ProdA, ProdB 교대)
        5. bootstrap_start() 예약: t=0에서 초기 투입 시작
        6. run(): 이벤트 루프 실행
    
    시뮬레이션 종료 조건:
        - SIM_END 시간 도달 (예: 15일 = 1,296,000초)
        - 이벤트 큐가 비어있음 (모든 작업 완료)
    """
    # 1. 이전 시뮬레이션 상태 초기화
    reset_sim()
    
    # 2. 설정 저장
    global_variable.CURRENT_CFG = cfg
    global_variable.SIM_END = float(cfg.sim_time) if cfg.sim_time and cfg.sim_time > 0 else float("inf")
    
    # 3. 공장 구성 요소 생성 (설비, AMR, 창고, Stocker)
    build_factory(cfg)
    
    # 3.5. 장애물 맵 초기화 (과업 1: 다익스트라 경로 탐색용)
    if cfg.machine_positions:
        init_obstacle_map(cfg.machine_positions)
    
    # 4. 랜덤 시드 설정 (재현성 확보)
    random.seed(cfg.seed)
    
    # 5. 제품 투입 순서 설정 (기본: ProdA, ProdB 교대)
    global_variable.FEED_SEQ = list(cfg.feed_sequence) if cfg.feed_sequence else ["ProdA", "ProdB"]
    global_variable.FEED_IDX = 0
    
    # 6. t=0에서 초기 제품 투입 시작
    schedule(0.0, bootstrap_start)
    
    # 7. 이벤트 루프 실행
    run()

# ================================================================================
# 설비 입력/가공 관련 함수
# ================================================================================
def enqueue_to_machine(m: Machine, job: Job):
    """
    설비 입력 버퍼(input_buf)에 제품 적재
    
    Args:
        m (Machine): 대상 설비
        job (Job): 적재할 제품
    
    동작:
        1. 설비가 유휴 상태인지 확인
        2. input_buf에 job 추가
        3. pending_stage 초기화 (중복 계산 방지)
        4. 입력 예약 해제
        5. 유휴 상태면 즉시 가공 시도
    
    호출 시점:
        - AMR이 제품을 설비에 하역 완료했을 때
    """
    # 설비가 유휴 상태인지 확인 (가공 중도, 대기 중도 없음)
    was_idle = (m.processing_job is None) and (m.waiting_done is None)
    
    # 입력 버퍼에 제품 추가
    m.input_buf.append(job)
    job.pending_stage = None  # 다음 스테이지 정보 초기화
    
    # 입력 슬롯 예약 해제
    release_input(m)
    
    # 로그 출력
    if was_idle:
        log(f"{job.job_id}: {m.name} input_buf 적재 → 즉시 가공 시도 (len={len(m.input_buf)})")
    else:
        log(f"{job.job_id}: {m.name} input_buf 대기 (len={len(m.input_buf)})")
    
    # 가공 시작 시도
    try_start_processing(m)



def on_finish_processing(m: Machine):
    """
    설비 공정 완료 이벤트 핸들러
    
    Args:
        m (Machine): 가공 완료된 설비
    
    동작:
        1. processing_job에서 완료된 job 꺼냄
        2. output_buf가 비어있으면:
           - output_buf에 job 이동
           - 다음 공정으로 이동 시도 (move_to_next_stage_from_output)
           - 다음 제품 가공 시작 시도 (try_start_processing)
        3. output_buf가 꽉 차있으면:
           - waiting_done에 임시 대기
           - (output_buf 비워지면 자동으로 이동됨)
    
    설비 내부 상태 흐름:
        [input_buf] → [processing_job] → [output_buf] → [AMR 픽업]
                                             ↓
                                      [waiting_done] (버퍼 꽉참 시)
    """
    job = m.processing_job
    m.processing_job = None
    log(f"{job.job_id}: {m.stage} 완료 @ {m.name}")

    # output_buf가 비어있으면 바로 이동
    if m.output_buf is None:
        m.output_buf = job
        log(f"{m.name} output_buf ← {job.job_id}")
        move_to_next_stage_from_output(m)  # 다음 공정으로 이동 시도
        try_start_processing(m)            # 다음 제품 가공 시작 시도
    else:
        # output_buf가 꽉 찼으면 waiting_done에 대기
        m.waiting_done = job
        log(f"{m.name} output 꽉참 → {job.job_id} waiting_done 대기")

def bootstrap_start():
    """
    시뮬레이션 시작 시 초기 제품 투입 (t=0에서 1회 호출)
    
    동작:
        A공정 설비들 중 입력 슬롯이 비어있는 곳에 원자재를 투입합니다.
        창고(Warehouse)가 비어있으면 새 제품을 생성합니다.
    
    초기화 흐름:
        1. A공정 설비 목록 확인
        2. 입력 슬롯이 비어있는 설비 탐색
        3. 창고에 재고 없으면 새 제품 생성 (generate_one_job)
        4. 창고→A공정 AMR 디스패치 (try_dispatch_from_warehouse_to_A)
        5. 슬롯이 채워질 때까지 반복
    
    Note:
        - while True 루프로 가능한 많은 제품을 초기에 투입
        - A공정 설비 슬롯이 모두 차면 종료
    """
    while True:
        # A공정 설비 목록
        next_machines = global_variable.MACHINES.get("A", [])
        if not next_machines:
            break
        
        # 입력 슬롯이 비어있는 설비 탐색
        slot_ok = [m for m in next_machines if has_free_input(m)]
        if not slot_ok:
            break  # 모든 A설비 슬롯이 꽉 찼음

        # 창고에 재고 없으면 새 제품 생성
        if not global_variable.WAREHOUSE or not global_variable.WAREHOUSE.inventory:
            generate_one_job()

        if not global_variable.WAREHOUSE.inventory:
            break  # 제품 생성 실패
        
        # 창고 → A공정으로 AMR 디스패치
        try_dispatch_from_warehouse_to_A()

# ================================================================================
# AMR 예약 및 이동 함수
# ================================================================================
def reserve_amr(pick_xy: Tuple[float, float], drop_xy: Tuple[float, float],
                request_time: float, load_sec: float, unload_sec: float,
                job_id: Optional[str] = None):
    """
    AMR 예약 - 가장 빨리 작업 완료할 수 있는 AMR 선택
    
    Args:
        pick_xy (Tuple): 픽업 위치 좌표
        drop_xy (Tuple): 드롭 위치 좌표
        request_time (float): 요청 시간 (현재 시뮬레이션 시간)
        load_sec (float): 적재 시간 (기본 10초)
        unload_sec (float): 하역 시간 (기본 10초)
        job_id (Optional[str]): 이송할 제품 ID (로깅용)
    
    Returns:
        dict: AMR 예약 정보
            - depart_at: 출발 시간
            - arrive_pick: 픽업 도착 시간
            - depart_pick: 픽업 완료 후 출발 시간
            - arrive_drop: 드롭 도착 시간
            - depart_drop: 드롭 완료 시간 (작업 종료)
            - amr: 선택된 AMR 객체
            - future_start: AMR의 현재/예정 위치
    
    AMR 선택 기준 (ETA 최소):
        각 AMR의 현재/미래 위치를 고려하여 작업 완료 시간을 예측하고,
        가장 빨리 완료할 수 있는 AMR을 선택합니다.
    
    타임라인 계산:
        depart_at = max(request_time, amr.free_time)  # AMR 가용 시점
        arrive_pick = depart_at + dist(현재위치, 픽업위치) / 속도
        depart_pick = arrive_pick + load_sec
        arrive_drop = depart_pick + dist(픽업위치, 드롭위치) / 속도
        depart_drop = arrive_drop + unload_sec
    
    확장 포인트 (과제 Task 1):
        - 현재: 유클리드 직선 거리 사용
        - 개선: Dijkstra 알고리즘으로 실제 경로 거리 계산
    """
    if not global_variable.AMRS:
        raise RuntimeError("No AMRs available.")

    cands = []  # 후보 AMR 목록 (완료시간, 도착시간, ..., AMR객체, 시작위치)
    
    # 모든 AMR에 대해 ETA 계산
    for a in global_variable.AMRS:
        # AMR이 언제 출발할 수 있는지 (현재 시간 vs AMR 가용 시간)
        depart_at = max(request_time, a.free_time)
        
        # AMR의 현재/미래 위치 결정
        # - free_time > request_time: 아직 작업 중이므로 planned_xy(완료 후 위치) 사용
        # - 그렇지 않으면: 현재 위치(a.xy) 사용
        future_start = a.planned_xy if (a.planned_xy is not None and a.free_time > request_time) else a.xy
        
        # 이동 시간 계산 (유클리드 거리 / 속도)
        # TODO: Dijkstra 알고리즘으로 실제 경로 거리로 교체 (Task 1)
        t_pick = dist(future_start, pick_xy) / max(a.speed, 1e-9)
        t_drop = dist(pick_xy, drop_xy) / max(a.speed, 1e-9)
        
        # 타임라인 계산
        arrive_pick = depart_at + t_pick
        depart_pick = arrive_pick + load_sec         # 적재 완료
        arrive_drop = depart_pick + t_drop
        depart_drop = arrive_drop + unload_sec       # 하역 완료 (작업 종료)
        
        cands.append((depart_drop, arrive_drop, depart_pick, arrive_pick, depart_at, a.name, a, future_start))

    # ETA(depart_drop)가 가장 빠른 AMR 선택
    cands.sort()
    depart_drop, arrive_drop, depart_pick, arrive_pick, depart_at, _, amr, future_start = cands[0]

    # 예약 결과 로깅
    log(
        f"[Reserve-FINAL] pick={pick_xy} drop={drop_xy} "
        f"chosen={amr.name} | depart@{depart_at:.2f} → arrive_pick@{arrive_pick:.2f} "
        f"(load {depart_pick - arrive_pick:.2f}s) → arrive_drop@{arrive_drop:.2f} "
        f"(unload {depart_drop - arrive_drop:.2f}s) → free@{depart_drop:.2f}"
    )
    
    # AMR 상태 업데이트 (예약 반영)
    amr.free_time = depart_drop      # 다음 작업 가능 시점
    amr.planned_xy = drop_xy         # 작업 완료 후 위치

    # 작업 타임라인 기록 (logger.py)
    _amr_push_task(amr,
                   job_id=job_id,
                   pick_xy=pick_xy, drop_xy=drop_xy,
                   depart_at=depart_at,
                   arrive_pick=arrive_pick, depart_pick=depart_pick,
                   arrive_drop=arrive_drop, depart_drop=depart_drop)

    return {
        "depart_at": depart_at,
        "arrive_pick": arrive_pick,
        "depart_pick": depart_pick,
        "arrive_drop": arrive_drop,
        "depart_drop": depart_drop,
        "amr": amr,
        "future_start": future_start,
    }

# ================================================================================
# 설비 가공 시작 함수
# ================================================================================
def try_start_processing(m: Machine):
    """
    설비 가공 시작 시도
    
    Args:
        m (Machine): 가공을 시도할 설비
    
    동작:
        1. input_buf가 비어있고 가공 중인 제품이 없으면:
           - A공정: 이전 공정(E)에서 당겨오기 + 창고에서 새 제품 투입
           - 다른 공정: 이전 공정에서 당겨오기
        2. waiting_done에 제품이 있으면: 대기 (output_buf 비워질 때까지)
        3. input_buf에 제품이 있으면: 가공 시작
    
    가공 시작 로직:
        - input_buf에서 cycle_idx가 가장 큰 제품 선택 (재가공 우선)
        - process_time_for()로 공정 시간 계산
        - schedule()로 완료 이벤트 예약
    
    Pull 방식 vs Push 방식:
        - 현재 구현: Pull 방식 (설비가 이전 공정에서 당겨옴)
        - 장점: 설비 유휴 시간 최소화, 라인 밸런싱 용이
    """
    # 입력 버퍼가 비어있고 가공 중도 없으면 → 이전 공정에서 당겨오기
    if (m.processing_job is None) and (not m.input_buf):
        if m.stage == "A":
            # A공정: E에서 재가공품 당겨오기 (cycle_idx >= 1 우선)
            pull_from_prev_to(m, policy="cyclemax")
            # 재가공품이 없으면 창고에서 새 제품 투입
            if not _exists_priority_job_for_A():
                try_dispatch_from_warehouse_to_A()
        else:
            # B~E공정: 이전 공정에서 ETA 기준으로 당겨오기
            pull_from_prev_to(m, policy="eta")
    
    # waiting_done에 제품이 있으면 대기 (output_buf 비워져야 진행 가능)
    if m.waiting_done is not None:
        return
    
    # 가공 시작: input_buf에서 cycle_idx가 가장 큰 제품 선택
    if m.processing_job is None and m.input_buf:
        # 재가공품(cycle_idx=1)을 우선 처리
        max_idx = max(range(len(m.input_buf)), key=lambda i: m.input_buf[i].cycle_idx)
        job = m.input_buf.pop(max_idx)
        
        # 공정 시간 계산
        s = global_variable.now  # 시작 시간
        pt = process_time_for(m.stage, job, m)  # 공정 시간
        e = s + pt  # 종료 시간
        
        m.processing_job = job

        def start():
            """가공 시작 이벤트 핸들러"""
            log(f"{job.job_id}({job.product}): {m.stage} 시작 @ {m.name} (dur={pt}s, cycle_idx={job.cycle_idx})")
            record_machine_run(m, job, s, e)
            
            # 이전 공정에 빈 슬롯 알림 → 새 제품 당겨오기 트리거
            if m.stage == "A":
                kick_dispatch_from_prev_stage("A")
            else:
                kick_dispatch_from_prev_stage(m.stage)
            
            # 가공 완료 이벤트 예약
            schedule(e, lambda: on_finish_processing(m))
        
        schedule(s, start)

# ================================================================================
# 공정 간 제품 이동 함수
# ================================================================================
def move_to_next_stage_from_output(m: Machine):
    """
    output_buf에 있는 제품을 다음 공정으로 이동
    
    Args:
        m (Machine): 출발 설비 (output_buf에 제품 있음)
    
    동작:
        1. job 상태 확인 (None, reserved, in_transit 체크)
        2. 다음 스테이지 결정 (next_stage_for)
           - A→B, B→C, C→D, D→E
           - E→A (2사이클 반복)
           - E→Stocker (2사이클 완료 시)
        3. 다음 스테이지가 없으면 (nxt=None): Stocker로 출하
        4. 다음 설비 중 입력 슬롯이 비어있는 곳 탐색
        5. AMR 예약 후 이동 스케줄 등록
    
    이벤트 체인 (AMR 이동):
        go_pickup → pickup_start → pickup_end → drop_arrive → drop_end
    """
    job = m.output_buf
    
    # job이 없거나 이미 예약/이송 중이면 스킵
    if job is None or job.reserved or job.in_transit:
        return
    
    # 다음 스테이지 결정
    nxt = next_stage_for(job, m.stage)
    
    # ===== Case 1: 다음 스테이지 없음 → Stocker로 출하 =====
    if nxt is None:
        stk = global_variable.STOCKERS.get("STK-01")
        if not stk:
            m.output_buf = None
            log(f"{job.job_id}: 출하 완료 (Stocker 미구성)")
            # waiting_done 처리
            if m.waiting_done is not None and m.output_buf is None:
                moved = m.waiting_done
                m.waiting_done = None
                m.output_buf = moved
                move_to_next_stage_from_output(m)
            try_start_processing(m)
            return

        # Stocker로 AMR 디스패치
        drop_xy = stk.xy
        load_sec = load_time_for(m.stage)
        unload_sec = unload_time_for("STK")
        res = reserve_amr(m.output_port, drop_xy, request_time=global_variable.now,
                          load_sec=load_sec, unload_sec=unload_sec, job_id=job.job_id)
        job.reserved = True
        amr = res["amr"]
        depart_at, arrive_pick, depart_pick = res["depart_at"], res["arrive_pick"], res["depart_pick"]
        arrive_drop, depart_drop = res["arrive_drop"], res["depart_drop"]
        future_start = res["future_start"]

        # ----- AMR 이동 이벤트 핸들러 정의 -----
        def go_pickup():
            """AMR이 픽업 위치로 이동 (공차)"""
            log(f"{amr.name}: 픽업지({m.name}={m.output_port})로 이동 중")
            record_amr_run(amr, job, depart_at, arrive_pick, future_start, m.output_port, loaded=False)
            amr.xy = m.output_port

        def pickup_start():
            """AMR 적재 시작"""
            log(f"{job.job_id}: {amr.name} 적재 중 ({load_sec:.2f}s) @ {m.name}")

        def pickup_end():
            """AMR 적재 완료 후 출발"""
            if m.output_buf is job:
                m.output_buf = None
                job.in_transit = True
                log(f"{job.job_id}: {amr.name} 적재 완료 & 출발 → {drop_xy}")
                record_amr_run(amr, job, depart_pick, arrive_drop, m.output_port, drop_xy, loaded=True)
            
            # waiting_done 처리 (output_buf 비워졌으면 대기 중이던 제품 이동)
            if m.waiting_done is not None and m.output_buf is None:
                moved = m.waiting_done
                m.waiting_done = None
                m.output_buf = moved
                move_to_next_stage_from_output(m)
            try_start_processing(m)

        def drop_arrive():
            """AMR이 Stocker 도착"""
            amr.xy = drop_xy
            log(f"{job.job_id}: {amr.name} 도착 (하차 대기 시작, {unload_sec:.2f}s) → {drop_xy}")

        def drop_end():
            """AMR 하역 완료 → Stocker에 보관"""
            job.in_transit = False
            job.reserved = False
            log(f"{job.job_id}: {amr.name} 하차 완료 @ Stocker")
            log(f"{job.job_id}: 출하 완료 → Stocker에 보관")
            stk.store(job.job_id)  # Stocker에 완제품 저장

            # waiting_done 처리
            if m.waiting_done is not None and m.output_buf is None:
                moved = m.waiting_done
                m.waiting_done = None
                m.output_buf = moved
                move_to_next_stage_from_output(m)
            try_start_processing(m)
            _amr_pop_task(amr, job_id=job.job_id, depart_drop=res["depart_drop"])

        # 이벤트 스케줄 등록
        schedule(depart_at, go_pickup)
        schedule(arrive_pick, pickup_start)
        schedule(depart_pick, pickup_end)
        schedule(arrive_drop, drop_arrive)
        schedule(depart_drop, drop_end)

        # AMR 대기 기록 (시각화용)
        global_variable.amr_waits.setdefault(amr.name, []).append((arrive_pick, depart_pick, job.job_id, "load", m.output_port))
        global_variable.amr_waits.setdefault(amr.name, []).append((arrive_drop, depart_drop, job.job_id, "unload", drop_xy))
        return
    
    # ===== Case 2: 다음 스테이지가 있음 → 다음 설비로 이동 =====
    next_machines: List[Machine] = global_variable.MACHINES.get(nxt, [])
    if not next_machines:
        log(f"다음 스테이지 '{nxt}' 없음")
        return

    # 입력 슬롯이 비어있는 설비 탐색
    slot_ok = [x for x in next_machines if has_free_input(x)]

    if slot_ok:
        # 라운드로빈으로 설비 선택 (부하 분산)
        rr = global_variable.ROUND_ROBIN_IDX.get(nxt, 0)
        drop_m = slot_ok[rr % len(slot_ok)]
        global_variable.ROUND_ROBIN_IDX[nxt] = rr + 1
        log(f"{nxt}: 입력 슬롯 여유 {drop_m.name} 선택 (라운드로빈, free {len(slot_ok)}대)")
    else:
        # 모든 설비 슬롯이 꽉 참 → 대기
        log(f"{nxt}: 모든 설비 입력 슬롯 꽉참 → {job.job_id} output 대기 유지")
        return
    
    # 입력 슬롯 선점 (경합 방지)
    if not reserve_input(drop_m):
        log(f"{drop_m.name}: 입력 슬롯 선점 실패(경합). 다시 탐색/대기")
        return
    
    # AMR 예약
    drop_xy = drop_m.input_port
    load_sec = load_time_for(m.stage)
    unload_sec = unload_time_for(nxt)
    res = reserve_amr(m.output_port, drop_xy, request_time=global_variable.now,
                      load_sec=load_sec, unload_sec=unload_sec, job_id=job.job_id)

    job.reserved = True
    amr = res["amr"]
    depart_at, arrive_pick, depart_pick = res["depart_at"], res["arrive_pick"], res["depart_pick"]
    arrive_drop, depart_drop = res["arrive_drop"], res["depart_drop"]
    future_start = res["future_start"]

    # ----- AMR 이동 이벤트 핸들러 정의 -----
    def go_pickup():
        """AMR이 픽업 위치로 이동 (공차)"""
        log(f"{amr.name}: 픽업지({m.name}={m.output_port})로 이동 중")
        record_amr_run(amr, job, depart_at, arrive_pick, future_start, m.output_port, loaded=False)
        amr.xy = m.output_port

    def pickup_start():
        """AMR 적재 시작"""
        log(f"{job.job_id}: {amr.name} 적재 중 ({load_sec:.2f}s) @ {m.name}")

    def pickup_end():
        """AMR 적재 완료 후 출발"""
        if m.output_buf is job:
            m.output_buf = None
            job.in_transit = True
            log(f"{job.job_id}: {amr.name} 적재 완료 & 출발 → {drop_xy}")
            record_amr_run(amr, job, depart_pick, arrive_drop, m.output_port, drop_xy, loaded=True)

        # waiting_done 처리
        if m.waiting_done is not None and m.output_buf is None:
            moved = m.waiting_done
            m.waiting_done = None
            m.output_buf = moved
            move_to_next_stage_from_output(m)
        try_start_processing(m)

    def drop_arrive():
        """AMR이 다음 설비 도착"""
        amr.xy = drop_xy
        log(f"{job.job_id}: {amr.name} 도착 (하차 대기 시작, {unload_sec:.2f}s) → {drop_xy}")

    def drop_end():
        """AMR 하역 완료 → 다음 설비 input_buf에 적재"""
        job.in_transit = False
        job.reserved = False
        log(f"{job.job_id}: {amr.name} 하차 완료 @ {drop_m.name}")
        
        enqueue_to_machine(drop_m, job)  # 다음 설비에 제품 적재
        release_input(drop_m)            # 입력 슬롯 예약 해제

        _amr_pop_task(amr, job_id=job.job_id, depart_drop=res["depart_drop"])
    
        # 이전 공정에 빈 슬롯 알림
        kick_dispatch_from_prev_stage(nxt)

    # 이벤트 스케줄 등록
    schedule(depart_at, go_pickup)
    schedule(arrive_pick, pickup_start)
    schedule(depart_pick, pickup_end)
    schedule(arrive_drop, drop_arrive)
    schedule(depart_drop, drop_end)

    # AMR 대기 기록 (시각화용)
    global_variable.amr_waits.setdefault(amr.name, []).append((arrive_pick, depart_pick, job.job_id, "load", m.output_port))
    global_variable.amr_waits.setdefault(amr.name, []).append((arrive_drop, depart_drop, job.job_id, "unload", drop_xy))
    
    
# ================================================================================
# 창고 → A공정 디스패치 함수
# ================================================================================
def try_dispatch_from_warehouse_to_A():
    """
    원자재 창고에서 A공정(산화)으로 AMR 디스패치
    
    동작:
        1. E→A 재가공품이 있으면 스킵 (우선순위 낮음)
        2. A공정 설비 중 입력 슬롯이 비어있는 곳 탐색
        3. 창고에 재고 없으면 새 제품 생성
        4. 라운드로빈으로 설비 선택
        5. AMR 예약 후 이동 스케줄 등록
    
    호출 시점:
        - bootstrap_start(): 시뮬레이션 시작 시
        - try_start_processing(): A설비 빈 슬롯 발생 시
        - kick_dispatch_from_prev_stage(): 이전 공정 완료 시
    
    우선순위:
        - E→A 재가공품이 있으면 해당 제품 우선 (이 함수 스킵)
        - 재가공품 없으면 창고에서 새 제품 투입
    """
    # E→A 재가공품이 있으면 스킵 (재가공품 우선)
    if _exists_priority_job_for_A():
        return

    # A공정 설비 목록
    next_machines = global_variable.MACHINES.get("A", [])
    if not next_machines:
        return
    
    # 입력 슬롯이 비어있는 설비 탐색
    slot_ok = [m for m in next_machines if has_free_input(m)]
    if not slot_ok:
        return  # 모든 A설비 슬롯이 꽉 참

    # 창고에 재고 없으면 새 제품 생성
    if global_variable.WAREHOUSE is None or not global_variable.WAREHOUSE.inventory:
        generate_one_job()
    if not global_variable.WAREHOUSE.inventory:
        return  # 제품 생성 실패

    # 라운드로빈으로 설비 선택
    rr = global_variable.ROUND_ROBIN_IDX.get("A", 0)
    drop_m = slot_ok[rr % len(slot_ok)]
    global_variable.ROUND_ROBIN_IDX["A"] = rr + 1

    # 입력 슬롯 선점
    if not reserve_input(drop_m):
        return

    # 창고에서 제품 출고
    job = global_variable.WAREHOUSE.pop()
    if job is None:
        release_input(drop_m)
        return

    # AMR 예약
    pick_xy = global_variable.WAREHOUSE.xy
    drop_xy = drop_m.input_port
    load_sec = load_time_for("WH")
    unload_sec = unload_time_for("A")

    res = reserve_amr(pick_xy, drop_xy, request_time=global_variable.now,
                      load_sec=load_sec, unload_sec=unload_sec, job_id=job.job_id)
    amr = res["amr"]
    depart_at, arrive_pick, depart_pick = res["depart_at"], res["arrive_pick"], res["depart_pick"]
    arrive_drop, depart_drop = res["arrive_drop"], res["depart_drop"]
    future_start = res["future_start"]

    job.reserved = True

    # ----- AMR 이동 이벤트 핸들러 정의 -----
    def go_pickup():
        """AMR이 창고로 이동 (공차)"""
        log(f"{amr.name}: 픽업지(Warehouse={pick_xy})로 이동 중")
        record_amr_run(amr, job, depart_at, arrive_pick, future_start, pick_xy, loaded=False)
        amr.xy = pick_xy

    def pickup_start():
        """창고에서 적재 시작"""
        log(f"{job.job_id}: {amr.name} 창고 적재 중 ({load_sec:.2f}s)")

    def pickup_end():
        """적재 완료 후 A공정으로 출발"""
        job.in_transit = True
        log(f"{job.job_id}: {amr.name} 적재 완료 & 출발 → {drop_m.name}@{drop_xy}")
        record_amr_run(amr, job, depart_pick, arrive_drop, pick_xy, drop_xy, loaded=True)

    def drop_arrive():
        """A공정 설비 도착"""
        amr.xy = drop_xy
        log(f"{job.job_id}: {amr.name} A 도착 (하차 대기 시작, {unload_sec:.2f}s) → {drop_xy}")

    def drop_end():
        """하역 완료 → A설비 input_buf에 적재"""
        job.in_transit = False
        job.reserved = False
        enqueue_to_machine(drop_m, job)
        release_input(drop_m)
        # 다음 창고→A 디스패치 시도 (연쇄)
        try_dispatch_from_warehouse_to_A()
        _amr_pop_task(amr, job_id=job.job_id, depart_drop=res["depart_drop"])

    # 이벤트 스케줄 등록
    schedule(depart_at, go_pickup)
    schedule(arrive_pick, pickup_start)
    schedule(depart_pick, pickup_end)
    schedule(arrive_drop, drop_arrive)
    schedule(depart_drop, drop_end)

    # AMR 대기 기록 (시각화용)
    global_variable.amr_waits.setdefault(amr.name, []).append((arrive_pick, depart_pick, job.job_id, "load", pick_xy))
    global_variable.amr_waits.setdefault(amr.name, []).append((arrive_drop, depart_drop, job.job_id, "unload", drop_xy))


    
    
# ================================================================================
# 유틸리티 함수
# ================================================================================

# 경로 탐색 모드 설정 (True: 다익스트라, False: 유클리드)
USE_PATHFINDING = True

def dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """
    두 점 사이의 이동 거리 계산
    
    Args:
        a (Tuple): 좌표 1 (x1, y1)
        b (Tuple): 좌표 2 (x2, y2)
    
    Returns:
        float: 이동 거리
    
    모드:
        - USE_PATHFINDING = True: 다익스트라 알고리즘 (설비 우회)
        - USE_PATHFINDING = False: 유클리드 직선 거리 (기존 방식)
    
    과업 1 구현:
        다익스트라 알고리즘으로 설비를 피해 이동하는 실제 경로 거리 계산
    """
    if USE_PATHFINDING and len(obstacle_map.obstacles) > 0:
        return pathfinding_dist(a, b)
    else:
        return math.hypot(a[0] - b[0], a[1] - b[1])


def has_free_input(m: Machine) -> bool:
    """
    설비 입력 슬롯이 비어있는지 확인
    
    Args:
        m (Machine): 확인할 설비
    
    Returns:
        bool: True면 슬롯 사용 가능, False면 꽉 참
    
    조건:
        - input_buf 길이 < input_capacity (용량 미만)
        - input_reserved가 False (예약되지 않음)
    """
    return (len(m.input_buf) < m.input_capacity) and (not m.input_reserved)


def reserve_input(m: Machine) -> bool:
    """
    설비 입력 슬롯 예약 (AMR 도착 전 선점)
    
    Args:
        m (Machine): 예약할 설비
    
    Returns:
        bool: True면 예약 성공, False면 실패 (이미 꽉 참)
    
    용도:
        AMR이 드롭 위치로 이동하는 동안 해당 슬롯이 다른 AMR에 의해
        선점되는 것을 방지합니다.
    """
    if has_free_input(m):
        m.input_reserved = True
        return True
    return False

def release_input(m: Machine):
    """
    설비 입력 슬롯 예약 해제
    
    Args:
        m (Machine): 예약 해제할 설비
    
    호출 시점:
        - 드롭 완료 직후 (enqueue_to_machine)
        - 가공 시작 시점 (try_start_processing)
    """
    m.input_reserved = False


def kick_dispatch_from_prev_stage(stage: str):
    """
    이전 공정에 빈 슬롯 발생 알림 → 제품 당겨오기 트리거
    
    Args:
        stage (str): 현재 스테이지 (빈 슬롯이 생긴 곳)
    
    동작:
        PREV_OF 맵을 참조하여 이전 공정의 설비들에게
        output_buf 처리 기회를 제공합니다.
    
    예시:
        kick_dispatch_from_prev_stage("B") 호출 시
        → PREV_OF["B"] = ["A"]
        → 모든 A설비의 move_to_next_stage_from_output() 호출
    """
    prevs = PREV_OF.get(stage, [])
    for prev in prevs:
        if prev == "WH":
            try_dispatch_from_warehouse_to_A()  # 창고 → A
        else:
            for m_prev in global_variable.MACHINES.get(prev, []):
                move_to_next_stage_from_output(m_prev)


# ================================================================================
# ETA 예측 및 상류 소스 선택 함수
# ================================================================================
def _predict_eta_for_pick(amrs, start_xy, pick_xy, drop_xy, load_sec, unload_sec, now):
    """
    AMR 예약 없이 ETA(도착 예정 시간)만 예측
    
    Args:
        amrs: AMR 목록
        start_xy: (미사용, 호환성용)
        pick_xy: 픽업 위치
        drop_xy: 드롭 위치
        load_sec: 적재 시간
        unload_sec: 하역 시간
        now: 현재 시뮬레이션 시간
    
    Returns:
        float: 가장 빠른 AMR의 작업 완료 예상 시간
    
    용도:
        select_upstream_source()에서 여러 소스 중 ETA가 가장 빠른 것을 
        선택할 때 사용합니다. 실제 예약은 하지 않습니다.
    """
    best = float("inf")
    for a in amrs:
        depart_at = max(now, a.free_time)
        future_start = a.planned_xy if (a.planned_xy is not None and a.free_time > now) else a.xy
        t_pick = dist(future_start, pick_xy) / max(a.speed, 1e-9)
        t_drop = dist(pick_xy, drop_xy) / max(a.speed, 1e-9)
        eta = depart_at + t_pick + load_sec + t_drop + unload_sec
        if eta < best:
            best = eta
    return best


def select_upstream_source(prev_machines: List[Machine],
                           drop_xy: Tuple[float, float],
                           policy: str = "eta") -> Optional[Tuple[Machine, Job]]:
    """
    이전 공정 설비들 중 제품을 당겨올 소스 선택
    
    Args:
        prev_machines (List[Machine]): 이전 공정 설비 목록
        drop_xy (Tuple): 드롭 위치 (다음 설비 입력 포트)
        policy (str): 선택 정책
    
    Returns:
        Optional[Tuple[Machine, Job]]: (소스 설비, 제품) 또는 None
    
    선택 정책 (policy):
        - 'eta': AMR ETA + load/unload 합이 최소 (기본값, 추천)
        - 'nearby': drop_xy와 거리가 가장 가까운 설비
        - 'oldest': 가장 오래된 job_id(작은 번호) 우선
        - 'cyclemax': cycle_idx가 큰 작업 우선 (재가공 우선)
        - 'wipbal': WIP가 큰 설비에서 먼저 빼줌 (라인 밸런싱)
    
    후보 조건:
        - output_buf에 job이 있음
        - reserved가 False (아직 예약되지 않음)
        - in_transit이 False (이송 중이 아님)
    
    확장 포인트:
        새로운 정책을 추가하여 최적화 성능 향상 가능
    """
    cands = []
    for m in prev_machines:
        job = m.output_buf
        # 유효한 후보인지 확인
        if job is None or job.reserved or job.in_transit:
            continue
        pick_xy = m.output_port
        
        # 정책별 점수 계산
        if policy == "nearby":
            # 거리가 가까운 설비 우선
            score = dist(pick_xy, drop_xy)
        elif policy == "oldest":
            # job_id 번호가 작은(오래된) 제품 우선
            try:
                num = int(job.job_id.split("-")[-1])
            except:
                num = 10**9
            score = num
        elif policy == "cyclemax":
            # cycle_idx가 큰(재가공) 제품 우선 (음수로 정렬)
            score = -job.cycle_idx
        elif policy == "wipbal":
            # WIP(재공품)가 많은 설비에서 먼저 빼줌 (라인 밸런싱)
            wip = len(m.input_buf) + (1 if m.processing_job else 0) + (1 if m.waiting_done else 0)
            score = -wip  # WIP 많은 곳 우선 (음수)
        else:  # 기본값: eta
            # AMR ETA가 가장 빠른 소스 선택
            load_sec = load_time_for(m.stage)
            unload_sec = unload_time_for(next_stage_for(job, m.stage) or "STK")
            score = _predict_eta_for_pick(global_variable.AMRS,
                                          start_xy=None,
                                          pick_xy=pick_xy, drop_xy=drop_xy,
                                          load_sec=load_sec, unload_sec=unload_sec,
                                          now=global_variable.now)
        cands.append((score, m, job))

    if not cands:
        return None

    # 점수 기준 정렬 (동점 시 job_id, 설비명으로 정렬)
    cands.sort(key=lambda x: (x[0], getattr(x[2], "job_id", ""), x[1].name))
    _, src_m, job = cands[0]
    return src_m, job

# ================================================================================
# Pull 방식 제품 이동 함수
# ================================================================================
def pull_from_prev_to(m_next: Machine, policy: str = "eta"):
    """
    다음 설비(m_next)의 입력 슬롯이 열렸을 때, 이전 설비에서 제품을 당겨오는 함수
    
    Args:
        m_next (Machine): 제품을 받을 설비 (Pull 요청 주체)
        policy (str): 소스 선택 정책 (eta, nearby, oldest, cyclemax, wipbal)
    
    동작:
        1. m_next의 입력 슬롯 예약
        2. 이전 공정 설비들 중 적합한 소스 선택 (select_upstream_source)
        3. AMR 예약 후 이동 스케줄 등록
        4. 이동 완료 후 다시 pull_from_prev_to 호출 (연쇄)
    
    Pull 방식의 장점:
        - 설비가 능동적으로 제품을 당겨옴
        - 유휴 시간 최소화
        - 라인 밸런싱 용이
    
    PREV_OF 참조:
        - A: E(재가공) 또는 WH(신규)
        - B: A
        - C: B
        - D: C
        - E: D
    """
    nxt = m_next.stage
    prev_stages = PREV_OF.get(nxt, [])
    prev_machines = []
    
    # 이전 공정 설비 목록 수집 (WH 제외)
    for p in prev_stages:
        if p == "WH":
            continue
        prev_machines.extend(global_variable.MACHINES.get(p, []))

    # 입력 슬롯 예약
    if not reserve_input(m_next):
        return

    # 소스 선택
    drop_xy = m_next.input_port
    pick = select_upstream_source(prev_machines, drop_xy, policy=policy)
    if pick is None:
        release_input(m_next)  # 예약 해제
        return

    src_m, job = pick
    
    # AMR 예약
    load_sec = load_time_for(src_m.stage)
    unload_sec = unload_time_for(nxt)
    res = reserve_amr(src_m.output_port, drop_xy,
                      request_time=global_variable.now,
                      load_sec=load_sec, unload_sec=unload_sec,
                      job_id=job.job_id)
    amr = res["amr"]
    depart_at, arrive_pick, depart_pick = res["depart_at"], res["arrive_pick"], res["depart_pick"]
    arrive_drop, depart_drop = res["arrive_drop"], res["depart_drop"]
    future_start = res["future_start"]
    job.reserved = True

    # ----- AMR 이동 이벤트 핸들러 정의 -----
    def go_pickup():
        """AMR이 소스 설비로 이동 (공차)"""
        log(f"{amr.name}: 픽업지({src_m.name}={src_m.output_port})로 이동 중")
        record_amr_run(amr, job, depart_at, arrive_pick, future_start, src_m.output_port, loaded=False)
        amr.xy = src_m.output_port

    def pickup_start():
        """소스 설비에서 적재 시작"""
        log(f"{job.job_id}: {amr.name} 적재 중 ({load_sec:.2f}s) @ {src_m.name}")

    def pickup_end():
        """적재 완료 후 출발"""
        if src_m.output_buf is job:
            src_m.output_buf = None
            job.in_transit = True
            log(f"{job.job_id}: {amr.name} 적재 완료 & 출발 → {m_next.name}@{drop_xy}")
            record_amr_run(amr, job, depart_pick, arrive_drop, src_m.output_port, drop_xy, loaded=True)

        # 소스 설비의 waiting_done 처리
        if src_m.waiting_done is not None and src_m.output_buf is None:
            moved = src_m.waiting_done
            src_m.waiting_done = None
            src_m.output_buf = moved
            move_to_next_stage_from_output(src_m)
        try_start_processing(src_m)

    def drop_arrive():
        """목적지 설비 도착"""
        amr.xy = drop_xy
        log(f"{job.job_id}: {amr.name} 도착 (하차 대기 시작, {unload_sec:.2f}s) → {drop_xy}")

    def drop_end():
        """하역 완료 → 목적지 설비 input_buf에 적재"""
        job.in_transit = False
        job.reserved = False
        enqueue_to_machine(m_next, job)
        release_input(m_next)
        _amr_pop_task(amr, job_id=job.job_id, depart_drop=res["depart_drop"])
        # 연쇄 Pull: 다시 이전 공정에서 당겨오기 시도
        pull_from_prev_to(m_next, policy=policy)

    # 이벤트 스케줄 등록
    schedule(depart_at, go_pickup)
    schedule(arrive_pick, pickup_start)
    schedule(depart_pick, pickup_end)
    schedule(arrive_drop, drop_arrive)
    schedule(depart_drop, drop_end)

    # AMR 대기 기록 (시각화용)
    global_variable.amr_waits.setdefault(amr.name, []).append((arrive_pick, depart_pick, job.job_id, "load", src_m.output_port))
    global_variable.amr_waits.setdefault(amr.name, []).append((arrive_drop, depart_drop, job.job_id, "unload", drop_xy))
    
# ================================================================================
# 제품 생성 및 우선순위 함수
# ================================================================================
def generate_one_job():
    """
    새 제품(Job) 1개 생성하여 창고(Warehouse)에 입고
    
    동작:
        1. FEED_SEQ에서 다음 제품 종류 결정 (ProdA/ProdB 교대)
        2. Job 객체 생성 (고유 ID 부여)
        3. Warehouse에 입고
    
    제품 ID 형식:
        - ProdA-0001, ProdA-0002, ...
        - ProdB-0001, ProdB-0002, ...
    
    호출 시점:
        - 창고 재고가 비었을 때 (try_dispatch_from_warehouse_to_A)
        - 초기 투입 시 (bootstrap_start)
    
    통계 업데이트:
        - FEED_COUNT: 총 출고 수
        - FEED_COUNT_A: ProdA 출고 수
        - FEED_COUNT_B: ProdB 출고 수
    """
    # 다음 제품 종류 결정 (교대)
    if not global_variable.FEED_SEQ:
        prod = "ProdA"
    else:
        idx = global_variable.FEED_IDX % len(global_variable.FEED_SEQ)
        prod = global_variable.FEED_SEQ[idx]
        global_variable.FEED_IDX += 1

    # 통계 업데이트
    global_variable.FEED_COUNT += 1
    
    # Job 객체 생성
    if prod == "ProdA":
        global_variable.FEED_COUNT_A += 1
        j = Job(job_id=f"{prod}-{global_variable.FEED_COUNT_A:04d}",
                product=prod, max_cycles=global_variable.CURRENT_CFG.job_cycles)
    else:
        global_variable.FEED_COUNT_B += 1
        j = Job(job_id=f"{prod}-{global_variable.FEED_COUNT_B:04d}",
                product=prod, max_cycles=global_variable.CURRENT_CFG.job_cycles)

    # 창고에 입고
    global_variable.WAREHOUSE.put(j)
    log(f"원자재 생성 {j.job_id}({j.product}) → Warehouse")
    return j


def _exists_priority_job_for_A() -> bool:
    """
    E→A 재가공품이 존재하는지 확인
    
    Returns:
        bool: True면 재가공품 존재, False면 없음
    
    조건:
        - E공정 설비의 output_buf에 제품이 있음
        - 해당 제품이 예약되지 않았고 이송 중도 아님
        - 다음 스테이지가 A (재가공)
        - cycle_idx >= 1 (2사이클 차)
    
    용도:
        창고→A 신규 투입보다 E→A 재가공품을 우선 처리하기 위해
        try_dispatch_from_warehouse_to_A()에서 이 함수로 확인합니다.
    
    우선순위 이유:
        재가공품은 이미 4개 공정을 거쳤으므로, 완성까지 남은 공정이
        신규품보다 적습니다. 따라서 재가공품 우선 처리가 효율적입니다.
    """
    for m in global_variable.MACHINES.get("E", []):
        j = m.output_buf
        if j and (not j.reserved) and (not j.in_transit):
            nxt = next_stage_for(j, m.stage)
            if nxt == "A" and getattr(j, "cycle_idx", 0) >= 1:
                return True
    return False
