import math, random
import heapq
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from data_structures import *
from config import *
from config import global_variable
from logger import _amr_push_task,_amr_pop_task

# ==============================
# AMR 네비게이션 그래프 & Dijkstra (과업 1)
# ------------------------------
# - 공장 레이아웃을 격자 그래프로 표현
# - 설비 주변은 obstacle(금지 구역)으로 설정
# - 8방향(대각선 포함) 이동 + 설비에서 일정 거리 이상 떨어져서 이동
#   → "안전거리"를 고려한 라우팅 = 너희 팀만의 차별점
# ==============================

NAV_ADJ = {}          # node -> 인접 node 리스트 (격자 그래프)
NAV_READY = False     # 그래프가 준비되었는지 여부 플래그


def _round_xy(xy: Tuple[float, float]) -> Tuple[int, int]:
    """
    연속 좌표(실수)를 격자 좌표(정수)로 스냅하는 함수.
    - 시뮬레이션 내부 좌표는 실수일 수 있음.
    - 그래프 노드는 (정수, 정수) 단위로 관리.
    """
    return (int(round(xy[0])), int(round(xy[1])))


def build_nav_graph(cfg):
    """
    설비/창고 좌표를 기반으로 AMR 네비게이션 격자 그래프 생성.

    ⚙ 아이디어(차별점)
    - 설비 중심 주변으로 일정 반경을 obstacle로 설정해서 "안전거리" 확보
    - 8방향(상하좌우 + 대각선) 이동 허용 → 로봇이 자연스럽게 우회하는 경로 생성
    """
    global NAV_ADJ, NAV_READY

    # cfg 또는 설비 좌표가 없으면 그래프를 만들 수 없음
    machine_positions = getattr(cfg, "machine_positions", None)
    if cfg is None or not machine_positions:
        NAV_ADJ = {}
        NAV_READY = False
        return

    # 1) 좌표들 수집 (창고, 스토커, 설비 중심)
    pts = []
    wh_xy = getattr(cfg, "warehouse_xy", None)
    stk_xy = getattr(cfg, "stocker_xy", None)
    if wh_xy:
        pts.append(wh_xy)
    if stk_xy:
        pts.append(stk_xy)
    for lst in machine_positions.values():
        pts.extend(lst)

    if not pts:
        NAV_ADJ = {}
        NAV_READY = False
        return

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    # 설비 영역 주변으로 약간 여유 있는 격자 범위
    xmin, xmax = math.floor(min(xs)) - 3, math.ceil(max(xs)) + 3
    ymin, ymax = math.floor(min(ys)) - 3, math.ceil(max(ys)) + 3

    # 2) 설비 주변 안전거리(반경 2칸)를 obstacle로 설정
    obstacles = set()
    SAFE_MARGIN = 2  # 설비에서 몇 칸 떨어져야 하는지 (차별점: 단순 충돌 회피가 아니라 안전거리 확보)
    for lst in machine_positions.values():
        for cx, cy in lst:   # 설비 중심 좌표
            for dx in range(-SAFE_MARGIN, SAFE_MARGIN + 1):
                for dy in range(-SAFE_MARGIN, SAFE_MARGIN + 1):
                    obstacles.add((cx + dx, cy + dy))

    # 3) 격자 노드 및 인접 관계 생성 (8방향 이동)
    adj = {}
    directions = [
        (1, 0), (-1, 0), (0, 1), (0, -1),   # 상/하/좌/우
        (1, 1), (1, -1), (-1, 1), (-1, -1)  # 대각선 4방향 (차별점: 4방향이 아닌 8방향 허용)
    ]

    for x in range(xmin, xmax + 1):
        for y in range(ymin, ymax + 1):
            if (x, y) in obstacles:
                # 설비 안전거리 내 격자는 AMR가 못 지나감
                continue
            node = (x, y)
            neigh = []
            for dx, dy in directions:
                nb = (x + dx, y + dy)
                if nb in obstacles:
                    continue
                if xmin <= nb[0] <= xmax and ymin <= nb[1] <= ymax:
                    neigh.append(nb)
            if neigh:
                adj[node] = neigh

    NAV_ADJ = adj
    NAV_READY = True


def path_distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """
    Dijkstra를 이용해 obstacle을 피한 최단 이동 거리 계산.
    (heapq 없이, O(N^2) 방식으로 구현한 버전)

    - NAV_ADJ가 준비되지 않았거나,
    - 시작/목표 노드가 그래프 밖인 경우

    → 기존 직선거리 dist(a, b)를 fallback으로 사용.
    """
    if not NAV_READY or not NAV_ADJ:
        return dist(a, b)

    start = _round_xy(a)
    goal = _round_xy(b)

    if start not in NAV_ADJ or goal not in NAV_ADJ:
        return dist(a, b)

    start = _round_xy(a)
    goal = _round_xy(b)

    if start not in NAV_ADJ or goal not in NAV_ADJ:
        return dist(a, b)

    INF = float("inf")
    # (현재까지 거리, 노드) 튜플을 담는 우선순위 큐
    hq = [(0.0, start)]
    best = {start: 0.0}

    while hq:
        d, u = heapq.heappop(hq)
        if u == goal:
            return d
        if d > best.get(u, INF):
            continue

        ux, uy = u
        for v in NAV_ADJ.get(u, []):
            vx, vy = v
            step_cost = math.hypot(vx - ux, vy - uy)  # 4방향은 1, 대각선은 √2
            nd = d + step_cost
            if nd < best.get(v, INF):
                best[v] = nd
                heapq.heappush(hq, (nd, v))

    # 경로를 찾지 못하면 직선 거리로 대체
    return dist(a, b)

def simulate(cfg: FactoryConfig):
    '''시나리오별 설정으로 실행'''
    reset_sim() 
    global_variable.CURRENT_CFG = cfg 
    global_variable.SIM_END = float(cfg.sim_time) if cfg.sim_time and cfg.sim_time > 0 else float("inf")

    # 설비/AMR 객체 구성
    build_factory(cfg)

    # ✅ 과업 1: 설비 배치를 기반으로 AMR 네비게이션 그래프 생성
    #    - 이후 AMR 이동 시간/경로 계산에서 path_distance()를 사용하게 됨
    build_nav_graph(cfg)

    random.seed(cfg.seed) 
    global_variable.FEED_SEQ = list(cfg.feed_sequence) if cfg.feed_sequence else ["ProdA","ProdB"] 
    global_variable.FEED_IDX = 0
    schedule(0.0, bootstrap_start)
    run()

def enqueue_to_machine(m: Machine, job: Job):
    '''설비 input_buf에 제품'''
    was_idle = (m.processing_job is None) and (m.waiting_done is None)
    m.input_buf.append(job)
    release_input(m)
    if was_idle:
        log(f"{job.job_id}: {m.name} input_buf 적재 → 즉시 가공 시도 (len={len(m.input_buf)})")
    else:
        log(f"{job.job_id}: {m.name} input_buf 대기 (len={len(m.input_buf)})")
    try_start_processing(m)


def on_finish_processing(m: Machine):
    '''Machine 공정 완료'''
    job = m.processing_job
    m.processing_job = None
    log(f"{job.job_id}: {m.stage} 완료 @ {m.name}")

    if m.output_buf is None: 
        m.output_buf = job
        log(f"{m.name} output_buf ← {job.job_id}")
        move_to_next_stage_from_output(m)   
        try_start_processing(m)             
    else:
        m.waiting_done = job 
        log(f"{m.name} output 꽉참 → {job.job_id} waiting_done 대기")

def bootstrap_start():
    """시뮬레이션 시작 시 한 번만 호출: A가 비어있으면 WH→A 바로 투입"""
    while True:
        next_machines = global_variable.MACHINES.get("A", [])
        if not next_machines:
            break
        slot_ok = [m for m in next_machines if has_free_input(m)]
        if not slot_ok:
            break

        if not global_variable.WAREHOUSE or not global_variable.WAREHOUSE.inventory:
            generate_one_job()

        if not global_variable.WAREHOUSE.inventory:
            break
        
        try_dispatch_from_warehouse_to_A()

def reserve_amr(pick_xy: Tuple[float, float],
                drop_xy: Tuple[float, float],
                request_time: float,
                load_sec: float,
                unload_sec: float,
                job_id: Optional[str] = None): 
    """
    AMR 예약 (ETA 최소 AMR 선택)

    - 입력 변수
      * pick_xy   : 픽업 좌표 (현재 FOUP 위치)
      * drop_xy   : 드롭 좌표 (다음 설비 in port 또는 Stocker)
      * request_time : 이 이동 요청이 발생한 현재 시각
      * load_sec  : 적재 시간
      * unload_sec: 하역 시간

    ⚙ 변경/차별점
    - 기존: dist(직선 거리)로 이동 시간을 계산
    - 변경: path_distance(설비 obstacle + 안전거리 + 8방향 라우팅 고려 최단거리)를 사용
      → "설비를 우회하면서도 가장 빠른 경로"를 기준으로 AMR를 고름
    """
    if not global_variable.AMRS:
        raise RuntimeError("No AMRs available.")

    cands = []  # (완료 시각, 기타 정보...) 목록

    for a in global_variable.AMRS:
        # 이 AMR이 실제로 출발 가능한 시각 (현재 요청 시각 vs AMR free_time)
        depart_at = max(request_time, a.free_time)

        # 이미 예약된 다음 이동이 있다면 그 이후 위치(planned_xy), 아니면 현재 위치(a.xy)를 시작 위치로 사용
        future_start = a.planned_xy if (a.planned_xy is not None and a.free_time > request_time) else a.xy

        # ✅ 여기서부터는 '직선거리 dist' 대신 'path_distance' 사용
        t_pick = path_distance(future_start, pick_xy) / max(a.speed, 1e-9)
        t_drop = path_distance(pick_xy, drop_xy) / max(a.speed, 1e-9)

        # 각 단계별 시각 계산
        arrive_pick = depart_at + t_pick            # 픽업 지점 도착 시각
        depart_pick = arrive_pick + load_sec        # 적재 완료 후 출발 시각
        arrive_drop = depart_pick + t_drop          # 드롭 지점 도착 시각
        depart_drop = arrive_drop + unload_sec      # 하역 완료 후 다시 free

        cands.append((depart_drop, arrive_drop, depart_pick, arrive_pick, depart_at, a.name, a, future_start))

    # 완료 시각이 가장 빠른 AMR 선택
    cands.sort()
    depart_drop, arrive_drop, depart_pick, arrive_pick, depart_at, _, amr, future_start = cands[0]

    log(
        f"[Reserve-FINAL] pick={pick_xy} drop={drop_xy} "
        f"chosen={amr.name} | depart@{depart_at:.2f} → arrive_pick@{arrive_pick:.2f} "
        f"(load {depart_pick - arrive_pick:.2f}s) → arrive_drop@{arrive_drop:.2f} "
        f"(unload {depart_drop - arrive_drop:.2f}s) → free@{depart_drop:.2f}"
    )

    # 선택된 AMR 상태 업데이트
    amr.free_time = depart_drop
    amr.planned_xy = drop_xy

    # 타임라인 기록 (나중에 애니메이션/분석용)
    _amr_push_task(
        amr,
        job_id=job_id,
        pick_xy=pick_xy, drop_xy=drop_xy,
        depart_at=depart_at,
        arrive_pick=arrive_pick, depart_pick=depart_pick,
        arrive_drop=arrive_drop, depart_drop=depart_drop,
    )

    # 필요 시 밖에서 참조할 수 있게 정보 반환
    return {
        "depart_at": depart_at,
        "arrive_pick": arrive_pick,
        "depart_pick": depart_pick,
        "arrive_drop": arrive_drop,
        "depart_drop": depart_drop,
        "amr": amr,
        "future_start": future_start,
    }

def try_start_processing(m: Machine):
    '''설비 작업 시작'''
    if (m.processing_job is None) and (not m.input_buf):
        if m.stage == "A":
            pull_from_prev_to(m, policy="cyclemax")
            if not _exists_priority_job_for_A():
                try_dispatch_from_warehouse_to_A()
        else:
            pull_from_prev_to(m, policy="eta")
    if m.waiting_done is not None:
        return
    if m.processing_job is None and m.input_buf:
        max_idx = max(range(len(m.input_buf)), key=lambda i: m.input_buf[i].cycle_idx)
        job = m.input_buf.pop(max_idx)
        s = global_variable.now
        pt = process_time_for(m.stage, job, m); e = s + pt
        m.processing_job = job

        def start():
            log(f"{job.job_id}({job.product}): {m.stage} 시작 @ {m.name} (dur={pt}s, cycle_idx={job.cycle_idx})")
            record_machine_run(m, job, s, e)
            if m.stage == "A":
                kick_dispatch_from_prev_stage("A")
            else:
                kick_dispatch_from_prev_stage(m.stage)
            schedule(e, lambda: on_finish_processing(m))
        schedule(s, start)

def move_to_next_stage_from_output(m: Machine):
    '''다음 설비로 이동'''
    job = m.output_buf
    if job is None or job.reserved or job.in_transit:
        return
    nxt = next_stage_for(job, m.stage)
    if nxt is None: 
        stk = global_variable.STOCKERS.get("STK-01") 
        if not stk:
            m.output_buf = None
            log(f"{job.job_id}: 출하 완료 (Stocker 미구성)")
            if m.waiting_done is not None and m.output_buf is None:
                moved = m.waiting_done; m.waiting_done = None
                m.output_buf = moved
                move_to_next_stage_from_output(m)
            try_start_processing(m)
            return

        drop_xy = stk.xy
        load_sec = load_time_for(m.stage)
        unload_sec = unload_time_for("STK")
        res = reserve_amr(m.output_port, drop_xy, request_time=global_variable.now, load_sec=load_sec, unload_sec=unload_sec,job_id=job.job_id)
        job.reserved = True
        amr = res["amr"]
        depart_at, arrive_pick, depart_pick = res["depart_at"], res["arrive_pick"], res["depart_pick"]
        arrive_drop, depart_drop = res["arrive_drop"], res["depart_drop"]
        future_start = res["future_start"]

        def go_pickup():
            log(f"{amr.name}: 픽업지({m.name}={m.output_port})로 이동 중")
            record_amr_run(amr, job, depart_at, arrive_pick, future_start, m.output_port, loaded=False)
            amr.xy = m.output_port

        def pickup_start():
            log(f"{job.job_id}: {amr.name} 적재 중 ({load_sec:.2f}s) @ {m.name}")

        def pickup_end():
            if m.output_buf is job:
                m.output_buf = None
                job.in_transit = True
                log(f"{job.job_id}: {amr.name} 적재 완료 & 출발 → {drop_xy}")
                record_amr_run(amr, job, depart_pick, arrive_drop, m.output_port, drop_xy, loaded=True)
                
            if m.waiting_done is not None and m.output_buf is None:
                moved = m.waiting_done; m.waiting_done = None
                m.output_buf = moved
                move_to_next_stage_from_output(m)
            try_start_processing(m)

        def drop_arrive():
            amr.xy = drop_xy
            log(f"{job.job_id}: {amr.name} 도착 (하차 대기 시작, {unload_sec:.2f}s) → {drop_xy}")

        def drop_end():
            job.in_transit = False
            job.reserved = False
            log(f"{job.job_id}: {amr.name} 하차 완료 @ Stocker")
            log(f"{job.job_id}: 출하 완료 → Stocker에 보관")
            stk.store(job.job_id)

            if m.waiting_done is not None and m.output_buf is None:
                moved = m.waiting_done; m.waiting_done = None
                m.output_buf = moved
                move_to_next_stage_from_output(m)
            try_start_processing(m)
            _amr_pop_task(amr, job_id=job.job_id, depart_drop=res["depart_drop"])

        schedule(depart_at, go_pickup)
        schedule(arrive_pick, pickup_start)
        schedule(depart_pick, pickup_end)
        schedule(arrive_drop, drop_arrive)
        schedule(depart_drop, drop_end)

        global_variable.amr_waits.setdefault(amr.name, []).append((arrive_pick, depart_pick, job.job_id, "load", m.output_port))
        global_variable.amr_waits.setdefault(amr.name, []).append((arrive_drop, depart_drop, job.job_id, "unload", drop_xy))
        return
    
    next_machines: List[Machine] = global_variable.MACHINES.get(nxt, [])
    if not next_machines:
        log(f"다음 스테이지 '{nxt}' 없음")
        return

    slot_ok = [x for x in next_machines if has_free_input(x)]

    if not slot_ok:
        log(f"{nxt}: 모든 설비 입력 슬롯 꽉참 → {job.job_id} output 대기 유지")
        return
    

    # ============================
    # 과업 2: 설비 선택 로직 개선 (내부 공정)
    # ----------------------------
    # - 기존: slot_ok 중 라운드로빈으로 설비 선택
    # - 변경: m.output_port → 각 후보 설비 input_port까지의
    #         AMR ETA + 설비 WIP(혼잡도)를 함께 고려
    #   score = ETA + WIP_WEIGHT * WIP
    #   (WIP가 많은 설비는 일부러 덜 선택되도록 페널티 부여)
    # ============================
    load_sec = load_time_for(m.stage)
    unload_sec = unload_time_for(nxt)
    pick_xy = m.output_port
    WIP_WEIGHT = 10.0  # 설비 하나당 평균 처리시간 정도로 잡는 가중치 (팀 고유 설정)

    best_m = None
    best_score = float("inf")

    for cand in slot_ok:
        drop_xy_cand = cand.input_port
        eta_cand = _predict_eta_for_pick(
            global_variable.AMRS,
            start_xy=None,
            pick_xy=pick_xy,
            drop_xy=drop_xy_cand,
            load_sec=load_sec,
            unload_sec=unload_sec,
            now=global_variable.now,
        )
        # cand 설비의 WIP(= input_buf + processing + waiting_done)
        wip_cand = len(cand.input_buf) + (1 if cand.processing_job else 0) + (1 if cand.waiting_done else 0)
        score_cand = eta_cand + WIP_WEIGHT * wip_cand

        if score_cand < best_score:
            best_score = score_cand
            best_m = cand

    if best_m is None:
        log(f"{nxt}: ETA/WIP 기준 후보 설비를 찾지 못함 → {job.job_id} output 대기 유지")
        return

    drop_m = best_m
    log(f"{nxt}: ETA+WIP 기준 {drop_m.name} 선택 (free {len(slot_ok)}대 중 최적)")


    if not reserve_input(drop_m):
        log(f"{drop_m.name}: 입력 슬롯 선점 실패(경합). 다시 탐색/대기")
        return
    
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

    def go_pickup():
        log(f"{amr.name}: 픽업지({m.name}={m.output_port})로 이동 중")
        record_amr_run(amr, job, depart_at, arrive_pick, future_start, m.output_port, loaded=False)
        amr.xy = m.output_port

    def pickup_start():
        log(f"{job.job_id}: {amr.name} 적재 중 ({load_sec:.2f}s) @ {m.name}")

    def pickup_end():
        if m.output_buf is job:
            m.output_buf = None
            job.in_transit = True
            log(f"{job.job_id}: {amr.name} 적재 완료 & 출발 → {drop_xy}")
            record_amr_run(amr, job, depart_pick, arrive_drop, m.output_port, drop_xy, loaded=True)

        if m.waiting_done is not None and m.output_buf is None:
            moved = m.waiting_done; m.waiting_done = None
            m.output_buf = moved
            move_to_next_stage_from_output(m)
        try_start_processing(m)

    def drop_arrive():
        amr.xy = drop_xy
        log(f"{job.job_id}: {amr.name} 도착 (하차 대기 시작, {unload_sec:.2f}s) → {drop_xy}")

    def drop_end():
        job.in_transit = False
        job.reserved = False
        log(f"{job.job_id}: {amr.name} 하차 완료 @ {drop_m.name}")
        
        enqueue_to_machine(drop_m, job)
        release_input(drop_m)  

        _amr_pop_task(amr, job_id=job.job_id, depart_drop=res["depart_drop"])
    
        kick_dispatch_from_prev_stage(nxt)

    schedule(depart_at, go_pickup)
    schedule(arrive_pick, pickup_start)
    schedule(depart_pick, pickup_end)
    schedule(arrive_drop, drop_arrive)
    schedule(depart_drop, drop_end)

    global_variable.amr_waits.setdefault(amr.name, []).append((arrive_pick, depart_pick, job.job_id, "load", m.output_port))
    global_variable.amr_waits.setdefault(amr.name, []).append((arrive_drop, depart_drop, job.job_id, "unload", drop_xy))
    
    
def try_dispatch_from_warehouse_to_A():
    # === [추가] 전체 라인 WIP 기반 투입 억제 ===
    total_wip = sum(
        len(m.input_buf) 
        + (1 if m.processing_job else 0) 
        + (1 if m.waiting_done else 0)
        for stage in global_variable.ROUTE
        for m in global_variable.MACHINES[stage]
    )
    # 기준값은 실험적으로 40~80 사이가 적당함
    if total_wip > 60:
        return   # 이번 사이클에서는 투입하지 않음
    
    # 이렇게 하면 재공(WIP,생산 중에 있는 제품)이 너무 많아졌을 때 
    # 투입을 멈춰서 라인이 안정됨

    # === [추가] 병목 공정 WIP 기반 투입 억제 ===
    def avg_wip(stage):
        ms = global_variable.MACHINES[stage]
        return sum(
            len(m.input_buf) + (1 if m.processing_job else 0)
            for m in ms
        ) / len(ms)

    # B 공정은 ProdB 영향 때문에 병목 가장 큼
    if avg_wip("B") > 5:
        return

    # C 공정도 포화되면 투입 중단
    if avg_wip("C") > 5:
        return

    # B/C WIP가 가득 차면 새로운 투입을 막아야 전체가 안정됨.

    '''원자재 창고에서 설비A(산화)로 AMR dispatch'''
    if _exists_priority_job_for_A():
        return

    next_machines = global_variable.MACHINES.get("A", [])
    if not next_machines:
        return
    slot_ok = [m for m in next_machines if has_free_input(m)]
    if not slot_ok:
        return

    # WH 비어 있으면 기본 1개 생성
    if global_variable.WAREHOUSE is None or not global_variable.WAREHOUSE.inventory:
        generate_one_job()
    if not global_variable.WAREHOUSE.inventory:
        return

    # [추가] A/B 투입 비율 동적 조정 ★
    # ============================
    if len(global_variable.WAREHOUSE.inventory) < 3:
        A_in = global_variable.FEED_COUNT_A
        B_in = global_variable.FEED_COUNT_B

        # 비율이 1:1에서 너무 벌어지면 부족한 제품을 강제로 생성
        if A_in > B_in + 2:
            generate_one_job(product="ProdB")
        elif B_in > A_in + 2:
            generate_one_job(product="ProdA")


    # ============================
    # 과업 2: 설비 선택 로직 개선 (A 공정)
    # ----------------------------
    # - 기존: 입력 가능 설비들(slot_ok) 중 라운드로빈으로 선택
    # - 변경: WH → 각 A 설비까지의 AMR ETA를 예측해서
    #         "가장 빨리 처리할 수 있는 설비"를 선택
    # ============================
    pick_xy = global_variable.WAREHOUSE.xy
    load_sec = load_time_for("WH")
    unload_sec = unload_time_for("A")

    best_m = None
    best_eta = float("inf")
    for cand in slot_ok:
        drop_xy_cand = cand.input_port
        eta_cand = _predict_eta_for_pick(
            global_variable.AMRS,
            start_xy=None,
            pick_xy=pick_xy,
            drop_xy=drop_xy_cand,
            load_sec=load_sec,
            unload_sec=unload_sec,
            now=global_variable.now,
        )
        if eta_cand < best_eta:
            best_eta = eta_cand
            best_m = cand

    if best_m is None:
        return

    drop_m = best_m


    if not reserve_input(drop_m):
        return
#--------------------------------------------------
    job = global_variable.WAREHOUSE.pop()
    if job is None:
        release_input(drop_m)
        return

    
    drop_xy = drop_m.input_port

    res = reserve_amr(pick_xy, drop_xy, request_time=global_variable.now,
                      load_sec=load_sec, unload_sec=unload_sec, job_id=job.job_id)
    amr = res["amr"]
    depart_at, arrive_pick, depart_pick = res["depart_at"], res["arrive_pick"], res["depart_pick"]
    arrive_drop, depart_drop = res["arrive_drop"], res["depart_drop"]
    future_start = res["future_start"]

    job.reserved = True

    def go_pickup():
        log(f"{amr.name}: 픽업지(Warehouse={pick_xy})로 이동 중")
        record_amr_run(amr, job, depart_at, arrive_pick, future_start, pick_xy, loaded=False)
        amr.xy = pick_xy

    def pickup_start():
        log(f"{job.job_id}: {amr.name} 창고 적재 중 ({load_sec:.2f}s)")

    def pickup_end():
        job.in_transit = True
        log(f"{job.job_id}: {amr.name} 적재 완료 & 출발 → {drop_m.name}@{drop_xy}")
        record_amr_run(amr, job, depart_pick, arrive_drop, pick_xy, drop_xy, loaded=True)

    def drop_arrive():
        amr.xy = drop_xy
        log(f"{job.job_id}: {amr.name} A 도착 (하차 대기 시작, {unload_sec:.2f}s) → {drop_xy}")

    def drop_end():
        job.in_transit = False
        job.reserved = False
        enqueue_to_machine(drop_m, job)
        release_input(drop_m)
        try_dispatch_from_warehouse_to_A()
        _amr_pop_task(amr, job_id=job.job_id, depart_drop=res["depart_drop"])

    schedule(depart_at, go_pickup)
    schedule(arrive_pick, pickup_start)
    schedule(depart_pick, pickup_end)
    schedule(arrive_drop, drop_arrive)
    schedule(depart_drop, drop_end)

    global_variable.amr_waits.setdefault(amr.name, []).append((arrive_pick, depart_pick, job.job_id, "load", pick_xy))
    global_variable.amr_waits.setdefault(amr.name, []).append((arrive_drop, depart_drop, job.job_id, "unload", drop_xy))


    
    
def dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    '''유클리드 거리 계산'''
    return math.hypot(a[0]-b[0], a[1]-b[1])

def has_free_input(m: Machine) -> bool:
    ''''''
    return (len(m.input_buf) < m.input_capacity) and (not m.input_reserved)



def reserve_input(m: Machine) -> bool:
    """도착 전에 슬롯 홀드. 성공하면 True"""
    if has_free_input(m):
        m.input_reserved = True
        return True
    return False

def release_input(m: Machine):
    """드롭 완료 직후 혹은 가공 시작 시점에 예약 해제"""
    m.input_reserved = False

def kick_dispatch_from_prev_stage(stage: str):
    prevs = PREV_OF.get(stage, [])
    for prev in prevs:
        if prev == "WH":
            try_dispatch_from_warehouse_to_A() 
        else:
            for m_prev in global_variable.MACHINES.get(prev, []):
                move_to_next_stage_from_output(m_prev)


def _predict_eta_for_pick(amrs, start_xy, pick_xy, drop_xy, load_sec, unload_sec, now):
    """reserve 없이 ETA만 대략 예측(가장 빨리 비는 AMR 기준). 예약은 하지 않음."""
    best = float("inf")
    for a in amrs:
        depart_at = max(now, a.free_time)
        future_start = a.planned_xy if (a.planned_xy is not None and a.free_time > now) else a.xy
        
        # Dijkstra 기반 최단거리로 ETA를 예측 (직선 거리 대신)
        t_pick = path_distance(future_start, pick_xy) / max(a.speed, 1e-9)
        t_drop = path_distance(pick_xy, drop_xy) / max(a.speed, 1e-9)
        
        eta = depart_at + t_pick + load_sec + t_drop + unload_sec
        if eta < best:
            best = eta
    return best

def select_upstream_source(prev_machines: List[Machine],
                           drop_xy: Tuple[float,float],
                           policy: str = "eta") -> Optional[Tuple[Machine, Job]]:
    """
    prev_machines 중 '지금 당장 보낼 수 있는' 소스(= output_buf에 job 있고 예약/이송중 아님)만 후보로.
    policy:
      - 'eta'      : AMR ETA + load/unload 합이 최소 (추천)
      - 'nearby'   : drop_xy와 거리가 가장 가까운 설비의 출구
      - 'oldest'   : 가장 오래된/작은 job_id(혹은 created_at) 우선
      - 'cyclemax' : cycle_idx가 큰 작업 우선(재가공 우선 처리)
      - 'wipbal'   : 해당 설비의 WIP(= input_buf + processing + waiting_done)가 큰 쪽에서 먼저 빼줌(라인 밸런싱)
    """
    cands = []
    for m in prev_machines:
        job = m.output_buf
        if job is None or job.reserved or job.in_transit:
            continue
        pick_xy = m.output_port
        
        if policy == "nearby":
            # 설비 → drop 지점까지 실제 우회 경로 기준 거리 사용 (직선 거리 X)
            score = path_distance(pick_xy, drop_xy)
        elif policy == "oldest":
            try:
                num = int(job.job_id.split("-")[-1])
            except:
                num = 10**9
            score = num
        elif policy == "cyclemax":
            score = -job.cycle_idx  
        elif policy == "wipbal":
            wip = len(m.input_buf) + (1 if m.processing_job else 0) + (1 if m.waiting_done else 0)
            score = -wip 
        else: 
            load_sec = load_time_for(m.stage)
            unload_sec =  unload_time_for(next_stage_for(job, m.stage) or "STK")
            score = _predict_eta_for_pick(global_variable.AMRS, 
                                          start_xy=None, 
                                          pick_xy=pick_xy, drop_xy=drop_xy,
                                          load_sec=load_sec, unload_sec=unload_sec,
                                          now=global_variable.now)
        cands.append((score, m, job))

    if not cands:
        return None

    cands.sort(key=lambda x: (x[0], getattr(x[2], "job_id", ""), x[1].name))
    _, src_m, job = cands[0]
    return src_m, job

def pull_from_prev_to(m_next: Machine, policy: str = "eta"):
    """다음 설비 m_next의 입력 슬롯이 열렸을 때, 이전 설비들 중 하나에서 당겨오는 로직."""
    nxt = m_next.stage
    prev_stages = PREV_OF.get(nxt, [])
    prev_machines = []
    for p in prev_stages:
        if p == "WH":
            continue
        prev_machines.extend(global_variable.MACHINES.get(p, []))

 
    if not reserve_input(m_next):
        return  

    drop_xy = m_next.input_port
    pick = select_upstream_source(prev_machines, drop_xy, policy=policy)
    if pick is None:
        release_input(m_next)  
        return

    src_m, job = pick
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

    def go_pickup():
        log(f"{amr.name}: 픽업지({src_m.name}={src_m.output_port})로 이동 중")
        record_amr_run(amr, job, depart_at, arrive_pick, future_start, src_m.output_port, loaded=False)
        amr.xy = src_m.output_port

    def pickup_start():
        log(f"{job.job_id}: {amr.name} 적재 중 ({load_sec:.2f}s) @ {src_m.name}")

    def pickup_end():
        if src_m.output_buf is job:
            src_m.output_buf = None
            job.in_transit = True
            log(f"{job.job_id}: {amr.name} 적재 완료 & 출발 → {m_next.name}@{drop_xy}")
            record_amr_run(amr, job, depart_pick, arrive_drop, src_m.output_port, drop_xy, loaded=True)

        if src_m.waiting_done is not None and src_m.output_buf is None:
            moved = src_m.waiting_done; src_m.waiting_done = None
            src_m.output_buf = moved
            move_to_next_stage_from_output(src_m)
        try_start_processing(src_m)

    def drop_arrive():
        amr.xy = drop_xy
        log(f"{job.job_id}: {amr.name} 도착 (하차 대기 시작, {unload_sec:.2f}s) → {drop_xy}")

    def drop_end():
        job.in_transit = False
        job.reserved = False
        enqueue_to_machine(m_next, job)
        release_input(m_next)  
        _amr_pop_task(amr, job_id=job.job_id, depart_drop=res["depart_drop"])
        pull_from_prev_to(m_next, policy=policy)


    schedule(depart_at, go_pickup)
    schedule(arrive_pick, pickup_start)
    schedule(depart_pick, pickup_end)
    schedule(arrive_drop, drop_arrive)
    schedule(depart_drop, drop_end)

    global_variable.amr_waits.setdefault(amr.name, []).append((arrive_pick, depart_pick, job.job_id, "load", src_m.output_port))
    global_variable.amr_waits.setdefault(amr.name, []).append((arrive_drop, depart_drop, job.job_id, "unload", drop_xy))

def generate_one_job(product=None):
    if product is None:
        product = global_variable.FEED_SEQ[global_variable.FEED_IDX]
        global_variable.FEED_IDX = (global_variable.FEED_IDX + 1) % len(global_variable.FEED_SEQ)

    job_id = f"{product}-{global_variable.FEED_COUNT:04d}"
    job = Job(job_id, product, max_cycles=global_variable.CURRENT_CFG.job_cycles)

    global_variable.WAREHOUSE.put(job)
    global_variable.FEED_COUNT += 1

    if product == "ProdA":
        global_variable.FEED_COUNT_A += 1
    else:
        global_variable.FEED_COUNT_B += 1

        

def _exists_priority_job_for_A() -> bool:
    """E 출력에서 A로 돌아갈 수 있는 (cycle_idx>=1) 대기품이 있는지 검사"""
    for m in global_variable.MACHINES.get("E", []):
        j = m.output_buf
        if j and (not j.reserved) and (not j.in_transit):
            nxt = next_stage_for(j, m.stage)
            if nxt == "A" and getattr(j, "cycle_idx", 0) >= 1:
                return True
    return False
