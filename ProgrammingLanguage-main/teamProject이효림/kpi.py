# kpi.py  (과업4 완성 버전)

import math
from typing import Dict, Tuple
from config import global_variable


# -----------------------------
# 내부: AMR 관련 KPI 계산
# -----------------------------
def _compute_amr_kpis() -> Tuple[float, float, float]:
    """
    반환:
      - total_dist : AMR 총 이동거리 (격자 기준, 유클리드 거리 합)
      - total_move_time : AMR 실제 이동에 사용된 총 시간 (s)
      - total_wait_time : load/unload 대기 시간 합 (s)
    """
    total_dist = 0.0
    total_move_time = 0.0

    # AMR 이동 기록: amr_runs[amr_name] = [(s,e,job_id, frm, to, loaded), ...]
    for runs in global_variable.amr_runs.values():
        for s, e, job_id, frm, to, loaded in runs:
            dx = to[0] - frm[0]
            dy = to[1] - frm[1]
            d = math.hypot(dx, dy)
            total_dist += d
            total_move_time += (e - s)

    # AMR 대기 기록: amr_waits[amr_name] = [(s,e,job_id,"load"/"unload", xy), ...]
    total_wait_time = 0.0
    for waits in global_variable.amr_waits.values():
        for s, e, job_id, kind, xy in waits:
            total_wait_time += (e - s)

    return total_dist, total_move_time, total_wait_time


# -----------------------------
# 내부: 설비 가동률/idle 시간 KPI 계산
# -----------------------------
def _compute_machine_kpis() -> Tuple[Dict[str, float], float]:
    """
    반환:
      - stage_util : {stage: 해당 스테이지 평균 가동률}
      - total_idle_time : 전체 설비 idle 시간 합 (s) (blocked 포함한 '바쁘지 않은 시간' 근사)
    """
    sim_time = global_variable.now
    if sim_time <= 0:
        return {}, 0.0

    # 설비별 busy 시간 합산
    busy_by_machine = {}
    for mname, runs in global_variable.machine_runs.items():
        busy = 0.0
        for s, e, job_id, stage in runs:
            busy += (e - s)
        busy_by_machine[mname] = busy

    stage_util: Dict[str, float] = {}
    total_idle_time = 0.0

    # 실제 존재하는 설비 기준
    for stage, machines in global_variable.MACHINES.items():
        if not machines:
            continue
        stage_busy_sum = 0.0
        for m in machines:
            stage_busy_sum += busy_by_machine.get(m.name, 0.0)

        # 스테이지 평균 가동률 = (모든 설비 busy 합) / (설비 수 * 전체 시뮬 시간)
        avg_util = stage_busy_sum / (len(machines) * sim_time)
        stage_util[stage] = avg_util

        # idle 시간 = 설비 수 * 전체 시간 - busy 합 (blocked + idle 모두 포함)
        idle = max(0.0, len(machines) * sim_time - stage_busy_sum)
        total_idle_time += idle

    return stage_util, total_idle_time


# -----------------------------
# 내부: Job 흐름 시간 / 평균 WIP 계산
# -----------------------------
def _compute_flow_kpis() -> Tuple[int, float, float]:
    """
    반환:
      - throughput : 출하 완료된 제품 수 (A+B 합)
      - avg_flow_time : 완료된 제품들의 평균 흐름 시간 (s)
      - avg_wip : Little's Law 기반 평균 WIP 근사
    """
    sim_time = global_variable.now
    stk = global_variable.STOCKERS.get("STK-01")
    if not stk or sim_time <= 0:
        return 0, 0.0, 0.0

    completed_ids = set(stk.list_jobs_A()) | set(stk.list_jobs_B())
    flow_times = []

    # job_runs[job_id] = [(stage, s, e, mname), ...]
    for jid in completed_ids:
        runs = global_variable.job_runs.get(jid)
        if not runs:
            continue
        starts = [s for (_, s, _, _) in runs]
        ends = [e for (_, _, e, _) in runs]
        if not starts or not ends:
            continue
        flow_times.append(max(ends) - min(starts))

    if not flow_times:
        return 0, 0.0, 0.0

    throughput = len(flow_times)
    avg_flow_time = sum(flow_times) / len(flow_times)

    # Little's Law: L ≈ λ * W = (throughput / T) * avg_flow_time
    avg_wip = throughput * avg_flow_time / sim_time
    return throughput, avg_flow_time, avg_wip


# -----------------------------
# 외부: 정보 출력 (KPI 요약)
# -----------------------------
def information():
    print("=== 생산 요약 (KPI) ===")

    stk = global_variable.STOCKERS.get("STK-01")
    output_A = len(stk.list_jobs_A()) if stk else 0
    output_B = len(stk.list_jobs_B()) if stk else 0

    print(f"[투입 수량] 총: {global_variable.FEED_COUNT}  (A={global_variable.FEED_COUNT_A}, B={global_variable.FEED_COUNT_B})")
    print(f"[출하 수량] A={output_A}, B={output_B},  Min(A,B)={min(output_A, output_B)}")

    # AMR KPI
    total_dist, total_move_time, total_wait_time = _compute_amr_kpis()
    print("\n[AMR KPI]")
    print(f"  - 총 이동거리        : {total_dist:.2f} (격자 거리 단위)")
    print(f"  - 총 이동 시간       : {total_move_time/3600:.2f} 시간 ({total_move_time:.0f} s)")
    print(f"  - Load/Unload 대기시간: {total_wait_time/3600:.2f} 시간 ({total_wait_time:.0f} s)")

    # 설비 KPI
    stage_util, total_idle_time = _compute_machine_kpis()
    print("\n[설비 KPI]")
    sim_time = global_variable.now
    print(f"  - 시뮬레이션 시간     : {sim_time/3600:.2f} 시간 ({sim_time:.0f} s)")
    for stage in global_variable.ROUTE:
        if stage in stage_util:
            print(f"  - Stage {stage} 가동률: {stage_util[stage]*100:5.1f}%")
    print(f"  - 전체 설비 idle 시간 : {total_idle_time/3600:.2f} 시간")

    # 흐름/재공 KPI
    throughput, avg_flow_time, avg_wip = _compute_flow_kpis()
    print("\n[흐름/재공 KPI]")
    print(f"  - 완료된 제품 수(Throughput) : {throughput}")
    print(f"  - 평균 흐름 시간(lead time)  : {avg_flow_time/60:.2f} 분 ({avg_flow_time:.0f} s)")
    print(f"  - 평균 재공량(평균 WIP, 근사) : {avg_wip:.2f}")


# -----------------------------
# 외부: Profit 계산
# -----------------------------
def profit(amr_count: int, machine_counts: Dict[str, int]) -> float:
    """
    과업 4용 Profit 함수

    Profit = Revenue - Cost

    - Revenue:
        * 수율이 맞아야 출하 가능한 pair: min(OutputA, OutputB)
        * Revenue = UNIT_REVENUE * min(OutputA, OutputB)

    - Cost:
        * 자재비: MATERIAL_COST * (InputA + InputB)
        * 설비 고정비: EQUIP_COST * (설비 대수 합)
        * AMR 고정비: AMR_FIXED_COST * amr_count
        * AMR 운행비: AMR_MOVE_COST * (AMR 총 이동거리)
        * AMR 대기비: AMR_WAIT_COST * (AMR 대기시간, 분 단위)
        * 재공 패널티: WIP_COST * 평균 WIP
    """
    stk = global_variable.STOCKERS.get("STK-01")
    output_A = len(stk.list_jobs_A()) if stk else 0
    output_B = len(stk.list_jobs_B()) if stk else 0
    input_A = global_variable.FEED_COUNT_A
    input_B = global_variable.FEED_COUNT_B

    total_machines = sum(machine_counts.values())

    # KPI 계산 재사용
    total_dist, total_move_time, total_wait_time = _compute_amr_kpis()
    throughput, avg_flow_time, avg_wip = _compute_flow_kpis()

    # ---------------- Revenue ----------------
    UNIT_REVENUE = 2000  # pair 하나당 매출 (임의 단위)
    pair_throughput = min(output_A, output_B)
    revenue = UNIT_REVENUE * pair_throughput

    # ---------------- Cost ----------------
    # 자재비
    MATERIAL_COST = 5.0
    material_cost = MATERIAL_COST * (input_A + input_B)

    # 설비 고정비
    EQUIP_COST = 20.0
    equip_cost = EQUIP_COST * total_machines

    # AMR 고정비
    AMR_FIXED_COST = 50.0
    amr_fixed_cost = AMR_FIXED_COST * amr_count

    # AMR 이동 비용 (이동거리 비례)
    AMR_MOVE_COST = 0.01
    amr_move_cost = AMR_MOVE_COST * total_dist

    # AMR 대기 비용 (분 단위로 환산)
    AMR_WAIT_COST = 0.03
    amr_wait_cost = AMR_WAIT_COST * (total_wait_time / 60.0)

    # 재공(WIP) 패널티
    WIP_COST = 0.1
    wip_cost = WIP_COST * avg_wip

    total_cost = material_cost + equip_cost + amr_fixed_cost + amr_move_cost + amr_wait_cost + wip_cost

    profit_value = revenue - total_cost

    print("\n=== Profit 계산 ===")
    print(f"  · Revenue (매출)             : {revenue:10.2f}")
    print(f"  · Material Cost (자재비)     : {material_cost:10.2f}")
    print(f"  · Equip Cost (설비 고정비)   : {equip_cost:10.2f}")
    print(f"  · AMR Fixed Cost             : {amr_fixed_cost:10.2f}")
    print(f"  · AMR Move Cost              : {amr_move_cost:10.2f}")
    print(f"  · AMR Wait Cost              : {amr_wait_cost:10.2f}")
    print(f"  · WIP Cost                   : {wip_cost:10.2f}")
    print(f"  => Profit                    : {profit_value:10.2f}")

    return profit_value
