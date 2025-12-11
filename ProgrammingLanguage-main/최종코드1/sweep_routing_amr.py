"""
Routing + AMR Count Sweep Test (Parallel Version)
Tests different routing strategies with varying AMR counts to find the global optimum.
"""
import sim_core
from config import global_variable, schedule, next_stage_for, load_time_for, unload_time_for, log, process_time_for
from data_structures import Machine
import multiprocessing as mp
import math

# Configuration
SIM_TIME = 1296000
SEED = 20
AMR_RANGE = range(3, 31)  # 3 to 30 AMRs

machine_positions = {
    "A": [(14, 3), (14, 7), (14, 13), (14, 15), (14, 17)],
    "B": [(14, 5), (22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17), (38, 15)],
    "C": [(30, 3), (30, 5), (30, 7), (30, 13), (30, 15), (30, 17)],
    "D": [(38, 3), (38, 5), (38, 7), (38, 13), (38, 17)],
    "E": [(46, 3), (46, 5), (46, 7), (46, 13), (46, 15)],
}
machine_counts = {"A": 5, "B": 8, "C": 6, "D": 5, "E": 5}

# Global routing mode (set by worker process)
ROUTING_MODE = "round_robin"

def calculate_profit(amr_count):
    parameter = {"A": 4, "B": 9, "C": 8, "D": 8, "E": 5.5}
    t = sum(count * parameter[stage] for stage, count in machine_counts.items())
    
    stk = global_variable.STOCKERS.get("STK-01")
    if not stk:
        return 0
    
    count_a = len(stk.list_jobs_A())
    count_b = len(stk.list_jobs_B())
    feed = global_variable.FEED_COUNT_A + global_variable.FEED_COUNT_B
    
    p = 100 * min(count_a, count_b) - 5 * feed
    profit = p / (t + 0.011 * amr_count) * 100000
    return profit

# Original function storage
original_move_to_next = None

def patch_routing():
    """Patch sim_core to use the current ROUTING_MODE (Global)"""
    global original_move_to_next
    
    # Store original function if not already stored
    if original_move_to_next is None:
        original_move_to_next = sim_core.move_to_next_stage_from_output
    
    def patched_move_to_next_stage_from_output(m):
        """Patched version that respects ROUTING_MODE"""
        job = m.output_buf
        if job is None or job.reserved or job.in_transit:
            return
        
        nxt = next_stage_for(job, m.stage)
        if nxt is None:
            # Go to Stocker (use original logic)
            original_move_to_next(m)
            return
        
        next_machines = global_variable.MACHINES.get(nxt, [])
        if not next_machines:
            return
        
        slot_ok = [x for x in next_machines if sim_core.has_free_input(x)]
        
        if not slot_ok:
            return
        
        # Select machine based on ROUTING_MODE
        if ROUTING_MODE == "round_robin":
            rr = global_variable.ROUND_ROBIN_IDX.get(nxt, 0)
            drop_m = slot_ok[rr % len(slot_ok)]
            global_variable.ROUND_ROBIN_IDX[nxt] = rr + 1
            
        elif ROUTING_MODE == "nearest":
            def dist_cost(target_m):
                # Use raw distance for nearest
                return sim_core.dist(m.output_port, target_m.input_port)
            drop_m = min(slot_ok, key=dist_cost)
            
        elif ROUTING_MODE == "shortest_queue":
            # [Max Throughput] Select machine with fewest pending jobs (Load Balancing)
            drop_m = min(slot_ok, key=lambda x: len(x.input_buf))

        elif ROUTING_MODE == "cost_based":
            amr_speed = getattr(global_variable.CURRENT_CFG, "amr_speed", 1.0)
            def cost(target_m):
                d = sim_core.dist(m.output_port, target_m.input_port)
                travel_t = d / max(amr_speed, 1e-9)
                wait_t = 0.0
                # (a) Input queue wait
                for q_job in target_m.input_buf:
                    wait_t += process_time_for(target_m.stage, q_job, target_m)
                # (b) Processing job remaining time
                if target_m.processing_job and target_m.processing_start_time is not None:
                    full_pt = process_time_for(target_m.stage, target_m.processing_job, target_m)
                    passed = global_variable.now - target_m.processing_start_time
                    remaining = max(0.0, full_pt - passed)
                    wait_t += remaining
                
                return travel_t + wait_t
            drop_m = min(slot_ok, key=cost)
        else:
            # Fallback
            rr = global_variable.ROUND_ROBIN_IDX.get(nxt, 0)
            drop_m = slot_ok[rr % len(slot_ok)]
            global_variable.ROUND_ROBIN_IDX[nxt] = rr + 1
        
        # Dispatch
        if not sim_core.reserve_input(drop_m):
            return
        
        drop_xy = drop_m.input_port
        load_sec = load_time_for(m.stage)
        unload_sec = unload_time_for(nxt)
        res = sim_core.reserve_amr(m.output_port, drop_xy, request_time=global_variable.now,
                          load_sec=load_sec, unload_sec=unload_sec, job_id=job.job_id)

        job.reserved = True
        amr = res["amr"]
        depart_at, arrive_pick, depart_pick = res["depart_at"], res["arrive_pick"], res["depart_pick"]
        arrive_drop, depart_drop = res["arrive_drop"], res["depart_drop"]
        future_start = res["future_start"]

        def go_pickup():
            path = global_variable.path_cache.get((amr.xy, m.output_port), None)
            sim_core.record_amr_run(amr, job, depart_at, arrive_pick, future_start, m.output_port, loaded=False, path=path)
            amr.xy = m.output_port

        def pickup_start():
            log(f"{job.job_id}: {amr.name} 적재 중 ({load_sec:.2f}s) @ {m.name}")

        def pickup_end():
            if m.output_buf is job:
                m.output_buf = None
                job.in_transit = True
                path = global_variable.path_cache.get((m.output_port, drop_xy), None)
                sim_core.record_amr_run(amr, job, depart_pick, arrive_drop, m.output_port, drop_xy, loaded=True, path=path)

            if m.waiting_done is not None and m.output_buf is None:
                moved = m.waiting_done
                m.waiting_done = None
                m.output_buf = moved
                patched_move_to_next_stage_from_output(m)
            sim_core.try_start_processing(m)

        def drop_arrive():
            amr.xy = drop_xy
            log(f"{job.job_id}: {amr.name} 도착 (하차 대기 시작, {unload_sec:.2f}s) → {drop_xy}")

        def drop_end():
            job.in_transit = False
            job.reserved = False
            sim_core.enqueue_to_machine(drop_m, job)
            sim_core.release_input(drop_m)
            from logger import _amr_pop_task
            _amr_pop_task(amr, job_id=job.job_id, depart_drop=res["depart_drop"])
            sim_core.kick_dispatch_from_prev_stage(nxt)

        schedule(depart_at, go_pickup)
        schedule(arrive_pick, pickup_start)
        schedule(depart_pick, pickup_end)
        schedule(arrive_drop, drop_arrive)
        schedule(depart_drop, drop_end)

        global_variable.amr_waits.setdefault(amr.name, []).append((arrive_pick, depart_pick, job.job_id, "load", m.output_port))
        global_variable.amr_waits.setdefault(amr.name, []).append((arrive_drop, depart_drop, job.job_id, "unload", drop_xy))
    
    # Apply patch
    sim_core.move_to_next_stage_from_output = patched_move_to_next_stage_from_output


def worker_task(args):
    """
    Executed by each worker process.
    args: (method_name, amr_count)
    """
    method, amr_n = args
    
    # 1. Set global routing mode and patch
    global ROUTING_MODE
    ROUTING_MODE = method
    patch_routing()
    
    # 2. Configure Simulation
    cfg = sim_core.FactoryConfig(
        sim_time=SIM_TIME,
        seed=SEED,
        feed_sequence=("ProdA", "ProdB"),
        amr_count=amr_n,
        machine_counts=machine_counts,
        machine_positions=machine_positions
    )
    
    # 3. Running Simulation
    # Note: simulate() resets globals, so we are good.
    sim_core.simulate(cfg)
    
    # 4. Calculate Profit
    profit_val = calculate_profit(amr_n)
    
    stk = global_variable.STOCKERS.get("STK-01")
    count_a = len(stk.list_jobs_A()) if stk else 0
    count_b = len(stk.list_jobs_B()) if stk else 0
    
    return (method, amr_n, profit_val, count_a, count_b)


def run_sweep():
    # User-selectable methods
    routing_methods = [
        "round_robin",
        # "shortest_queue",
        # "nearest",      # Uncomment to test
        "cost_based",   # Uncomment to test
    ]
    
    # Build task list
    tasks = []
    for method in routing_methods:
        for amr_n in AMR_RANGE:
            tasks.append((method, amr_n))
            
    num_workers = min(mp.cpu_count(), 10)
    print("=" * 60)
    print(f"Routing + AMR Sweep Test (Parallel - {num_workers} Workers)")
    print(f"Total Simulations: {len(tasks)}")
    print("=" * 60)
    
    # Run Parallel
    results = []
    with mp.Pool(processes=num_workers) as pool:
        # pool.imap_unordered for real-time results, or map for batch
        # Let's use map and sort later
        results = pool.map(worker_task, tasks)
    
    # Process Results
    results.sort(key=lambda x: (x[0], x[1])) # Sort by method, then amr
    
    # Display grouped by method
    method_best = {}
    
    current_method = None
    best_profit = -1
    best_amr = -1
    
    for r in results:
        method, amr, profit, a, b = r
        
        if method != current_method:
            if current_method is not None:
                method_best[current_method] = (best_amr, best_profit)
                print(f">>> Best for {current_method}: AMR={best_amr}, Profit={best_profit:,.0f}\n")
            
            print(f"--- Testing: {method.upper()} ---")
            current_method = method
            best_profit = -1
            best_amr = -1
            
        print(f"AMR={amr:2d}: Profit={profit:,.0f} (A:{a}, B:{b})")
        
        if profit > best_profit:
            best_profit = profit
            best_amr = amr
            
    # Last method
    if current_method is not None:
        method_best[current_method] = (best_amr, best_profit)
        print(f">>> Best for {current_method}: AMR={best_amr}, Profit={best_profit:,.0f}\n")
        
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    global_best_p = -1
    global_best_m = ""
    global_best_a = -1
    
    for m, (ba, bp) in method_best.items():
        print(f"{m:15s}: AMR={ba:2d}, Profit={bp:,.0f}")
        if bp > global_best_p:
            global_best_p = bp
            global_best_m = m
            global_best_a = ba
            
    print(f"\n🏆 GLOBAL BEST: {global_best_m} with AMR={global_best_a}, Profit={global_best_p:,.0f}")

if __name__ == "__main__":
    mp.freeze_support()
    run_sweep()
