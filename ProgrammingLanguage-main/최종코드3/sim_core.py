import math, random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from data_structures import *
from config import *
from config import global_variable
from logger import _amr_push_task,_amr_pop_task

def simulate(cfg: FactoryConfig):
    '''시나리오별 설정으로 실행'''
    reset_sim() 
    global_variable.CURRENT_CFG = cfg 
    global_variable.SIM_END = float(cfg.sim_time) if cfg.sim_time and cfg.sim_time > 0 else float("inf")
    build_factory(cfg) 
    random.seed(cfg.seed) 
    global_variable.FEED_SEQ = list(cfg.feed_sequence) if cfg.feed_sequence else ["ProdA","ProdB"] 
    global_variable.FEED_IDX = 0
    schedule(0.0, bootstrap_start)
    run()

def enqueue_to_machine(m: Machine, job: Job):
    '''설비 input_buf에 제품'''
    was_idle = (m.processing_job is None) and (m.waiting_done is None)
    m.input_buf.append(job)
    job.pending_stage = None # 추가된 코드
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

def reserve_amr(pick_xy: Tuple[float, float],drop_xy: Tuple[float, float],request_time: float,load_sec: float,unload_sec: float,job_id: Optional[str] = None): 
    '''AMR 예약 (ETA 최소) -> 학생들 확장 가능, 입력 변수 (픽업좌표,드롭좌표,요청시간,적재시간,하역시간)
    현재·미래 위치를 모두 고려해 각 AMR의 완료 시각을 예측하고, 가장 빨리 비는 AMR을 뽑아 예약 상태를 즉시 반영'''
    
    if not global_variable.AMRS:
        raise RuntimeError("No AMRs available.")

    cands = []
    
    for a in global_variable.AMRS:
        depart_at = max(request_time, a.free_time) 
        future_start = a.planned_xy if (a.planned_xy is not None and a.free_time > request_time) else a.xy
        t_pick = dist(future_start, pick_xy) / max(a.speed, 1e-9)
        t_drop = dist(pick_xy, drop_xy) / max(a.speed, 1e-9)
        arrive_pick = depart_at + t_pick
        depart_pick = arrive_pick + load_sec         
        arrive_drop = depart_pick + t_drop
        depart_drop = arrive_drop + unload_sec      
        cands.append((depart_drop, arrive_drop, depart_pick, arrive_pick, depart_at, a.name, a, future_start))

    cands.sort()
    depart_drop, arrive_drop, depart_pick, arrive_pick, depart_at, _, amr, future_start = cands[0]

    log(
        f"[Reserve-FINAL] pick={pick_xy} drop={drop_xy} "
        f"chosen={amr.name} | depart@{depart_at:.2f} → arrive_pick@{arrive_pick:.2f} "
        f"(load {depart_pick - arrive_pick:.2f}s) → arrive_drop@{arrive_drop:.2f} "
        f"(unload {depart_drop - arrive_drop:.2f}s) → free@{depart_drop:.2f}"
    )
    
    amr.free_time = depart_drop
    amr.planned_xy = drop_xy

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
        m.processing_start_time = s  # Track start time for Smart Routing

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

    if slot_ok:
        # [Smart Routing] Cost-Based (Travel + Wait)
        amr_speed = getattr(global_variable.CURRENT_CFG, "amr_speed", 1.0)

        def cost_func(target_m):
            # 1. Travel Time
            d = dist(m.output_port, target_m.input_port)
            travel_t = d / max(amr_speed, 1e-9)
            
            # 2. Wait Time
            wait_t = 0.0
            # (a) Input Buffer Queue
            for q_job in target_m.input_buf:
                wait_t += process_time_for(target_m.stage, q_job, target_m)
            
            # (b) Currently Processing Job (Remaining Time only)
            if target_m.processing_job and target_m.processing_start_time is not None:
                full_pt = process_time_for(target_m.stage, target_m.processing_job, target_m)
                passed = global_variable.now - target_m.processing_start_time
                remaining = max(0.0, full_pt - passed)
                wait_t += remaining
            
            return travel_t + wait_t

        drop_m = min(slot_ok, key=cost_func)
        log(f"{nxt}: Smart Routing 선택 -> {drop_m.name} (Cost 최소, free {len(slot_ok)}대)")
    else:
        log(f"{nxt}: 모든 설비 입력 슬롯 꽉참 → {job.job_id} output 대기 유지")
        return
    
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
    '''원자재 창고에서 설비A(산화)로 AMR dispatch'''
    if _exists_priority_job_for_A():
        return

    next_machines = global_variable.MACHINES.get("A", [])
    if not next_machines:
        return
    slot_ok = [m for m in next_machines if has_free_input(m)]
    if not slot_ok:
        return

    if global_variable.WAREHOUSE is None or not global_variable.WAREHOUSE.inventory:
        generate_one_job()
    if not global_variable.WAREHOUSE.inventory:
        return

    rr = global_variable.ROUND_ROBIN_IDX.get("A", 0)
    drop_m = slot_ok[rr % len(slot_ok)]
    global_variable.ROUND_ROBIN_IDX["A"] = rr + 1

    if not reserve_input(drop_m):
        return

    job = global_variable.WAREHOUSE.pop()
    if job is None:
        release_input(drop_m)
        return

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
        t_pick = dist(future_start, pick_xy) / max(a.speed, 1e-9)
        t_drop = dist(pick_xy, drop_xy) / max(a.speed, 1e-9)
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
            score = dist(pick_xy, drop_xy)
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
    
def generate_one_job():
    """필요 시점에 1개만 생성해서 WAREHOUSE에 넣는다."""
    if not global_variable.FEED_SEQ:
        prod = "ProdA"
    else:
        idx = global_variable.FEED_IDX % len(global_variable.FEED_SEQ)
        prod = global_variable.FEED_SEQ[idx]
        global_variable.FEED_IDX += 1

    global_variable.FEED_COUNT += 1
    if prod == "ProdA":
        global_variable.FEED_COUNT_A += 1
        j = Job(job_id=f"{prod}-{global_variable.FEED_COUNT_A:04d}",
                product=prod, max_cycles=global_variable.CURRENT_CFG.job_cycles)
    else:
        global_variable.FEED_COUNT_B += 1
        j = Job(job_id=f"{prod}-{global_variable.FEED_COUNT_B:04d}",
                product=prod, max_cycles=global_variable.CURRENT_CFG.job_cycles)

    global_variable.WAREHOUSE.put(j)
    log(f"원자재 생성 {j.job_id}({j.product}) → Warehouse")
    return j

def _exists_priority_job_for_A() -> bool:
    """E 출력에서 A로 돌아갈 수 있는 (cycle_idx>=1) 대기품이 있는지 검사"""
    for m in global_variable.MACHINES.get("E", []):
        j = m.output_buf
        if j and (not j.reserved) and (not j.in_transit):
            nxt = next_stage_for(j, m.stage)
            if nxt == "A" and getattr(j, "cycle_idx", 0) >= 1:
                return True
    return False
