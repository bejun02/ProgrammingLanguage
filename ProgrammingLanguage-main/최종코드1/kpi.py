from config import global_variable
from typing import Dict

def information():
    print("=== 생산 요약 ===")
    print(f"Stocker K | Out제품 수: {global_variable.FEED_COUNT}")
    print(f"  - ProdA: {global_variable.FEED_COUNT_A}")
    print(f"  - ProdB: {global_variable.FEED_COUNT_B}")
    print("A 총 보관 수:", len(global_variable.STOCKERS["STK-01"].list_jobs_A()))
    print("B 총 보관 수:", len(global_variable.STOCKERS["STK-01"].list_jobs_B()))

def profit(amr_count, machine_counts: Dict): 
    parameter = {"A": 4, "B": 9, "C": 8, "D": 8, "E": 5.5}
    t = 0
    for machine_type, count in machine_counts.items():
        t += count * parameter[machine_type]
    p = (100*min(len(global_variable.STOCKERS["STK-01"].list_jobs_A()),
                 len(global_variable.STOCKERS["STK-01"].list_jobs_B()))
         - 5*(global_variable.FEED_COUNT_A+global_variable.FEED_COUNT_B))
    profit = p / (t + 0.011*amr_count)
    print("profit: ", round(profit, 2)*100000, "원")

def print_utilization():
    print("=== 설비 가동률 ===")
    
    # machine_runs: {m_name: [(start, end, ...), ...]}
    # Iterate all machines to include 0% ones
    
    # Sort machines by Name
    all_machines = []
    for stage, m_list in global_variable.MACHINES.items():
        all_machines.extend(m_list)
    all_machines.sort(key=lambda m: m.name)

    sim_duration = global_variable.SIM_END if global_variable.SIM_END and global_variable.SIM_END != float("inf") else global_variable.now
    
    print(f"총 {len(all_machines)}대 설비 집계 완료.")

    for m in all_machines:
        runs = global_variable.machine_runs.get(m.name, [])
        busy_time = sum(r[1] - r[0] for r in runs)
        
        # If machine is currently validly processing at end of sim, add partial?
        # Typically runs are recorded at 'end'. If sim ends mid-process, it might not be recorded.
        # But for 'sim_core.py', record happens at 'start'. 
        # Wait, check sim_core: record_machine_run is called inside 'start()' with (s, e).
        # So it is recorded at START time with expected End time.
        # If e > sim_duration, we should cap it.
        
        # Actually simplest way is using logged runs.
        # Let's refine busy_time calculation to respect sim_duration.
        
        # Re-calc busy with cap
        real_busy = 0.0
        for r in runs:
            s, e = r[0], r[1]
            if s >= sim_duration: continue
            eff_e = min(e, sim_duration)
            real_busy += (eff_e - s)
            
        util = (real_busy / sim_duration) * 100.0 if sim_duration > 0 else 0.0
        print(f"{m.name}: {util:6.2f}%")

def print_amr_utilization():
    print("=== AMR 가동률 ===")
    
    sim_duration = global_variable.SIM_END if global_variable.SIM_END and global_variable.SIM_END != float("inf") else global_variable.now
    
    amr_names = sorted(global_variable.amr_runs.keys())
    
    if not amr_names:
        print("AMR 운행 기록 없음.")
        return
    
    total_busy = 0.0
    total_capacity = sim_duration * len(global_variable.AMRS)
    
    for amr_name in amr_names:
        runs = global_variable.amr_runs.get(amr_name, [])
        # runs: [(start, end, job_id, from, to, loaded, path), ...]
        busy_time = 0.0
        for r in runs:
            s, e = r[0], r[1]
            if s >= sim_duration:
                continue
            eff_e = min(e, sim_duration)
            busy_time += (eff_e - s)
        
        total_busy += busy_time
        util = (busy_time / sim_duration) * 100.0 if sim_duration > 0 else 0.0
        print(f"{amr_name}: {util:6.2f}%")
    
    avg_util = (total_busy / total_capacity) * 100.0 if total_capacity > 0 else 0.0
    print(f"--- 평균 AMR 가동률: {avg_util:.2f}% ---")

def print_output_wait_times():
    """Output Buffer 대기시간 분석 - 스테이지별 평균 대기시간 출력"""
    print("=== Output Buffer 대기시간 ===")
    
    if not global_variable.output_wait_times:
        print("대기시간 데이터 없음")
        return
    
    # Group by stage
    stage_waits: Dict[str, List[float]] = {}
    
    for m_name, waits in global_variable.output_wait_times.items():
        # Extract stage from machine name (e.g., "A-1" -> "A")
        stage = m_name.split("-")[0]
        if stage not in stage_waits:
            stage_waits[stage] = []
        stage_waits[stage].extend([w[1] for w in waits])  # w = (job_id, wait_time)
    
    # Print by stage
    for stage in ["A", "B", "C", "D", "E"]:
        if stage in stage_waits and stage_waits[stage]:
            waits = stage_waits[stage]
            avg = sum(waits) / len(waits)
            max_w = max(waits)
            print(f"Stage {stage}: 평균 {avg:6.1f}s, 최대 {max_w:6.1f}s ({len(waits)}건)")
        else:
            print(f"Stage {stage}: 데이터 없음")