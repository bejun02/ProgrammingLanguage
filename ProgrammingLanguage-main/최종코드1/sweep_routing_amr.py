"""
Routing + AMR Count Sweep Test
Tests different routing strategies with varying AMR counts to find the global optimum.
"""
import sim_core
from config import global_variable
from data_structures import Machine
import math

# Configuration
SIM_TIME = 1296000
SEED = 20
AMR_RANGE = range(5, 21)  # 5 to 20 AMRs

machine_positions = {
    "A": [(14, 3), (14, 7), (14, 13), (14, 15), (14, 17)],
    "B": [(14, 5), (22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17), (38, 15)],
    "C": [(30, 3), (30, 5), (30, 7), (30, 13), (30, 15), (30, 17)],
    "D": [(38, 3), (38, 5), (38, 7), (38, 13), (38, 17)],
    "E": [(46, 3), (46, 5), (46, 7), (46, 13), (46, 15)],
}
machine_counts = {"A": 5, "B": 8, "C": 6, "D": 5, "E": 5}

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

# Global routing mode flag
ROUTING_MODE = "round_robin"  # Will be changed during sweep

# Monkey-patch the routing logic
original_move_to_next = None

def patch_routing():
    """Patch sim_core to use the current ROUTING_MODE"""
    global original_move_to_next
    
    # Store original function if not already stored
    if original_move_to_next is None:
        original_move_to_next = sim_core.move_to_next_stage_from_output
    
    def patched_move_to_next_stage_from_output(m):
        """Patched version that respects ROUTING_MODE"""
        job = m.output_buf
        if job is None or job.reserved or job.in_transit:
            return
        
        from config import next_stage_for, load_time_for, unload_time_for, log, process_time_for
        
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
                return sim_core.dist(m.output_port, target_m.input_port)
            drop_m = min(slot_ok, key=dist_cost)
            
        elif ROUTING_MODE == "cost_based":
            amr_speed = getattr(global_variable.CURRENT_CFG, "amr_speed", 1.0)
            def cost(target_m):
                d = sim_core.dist(m.output_port, target_m.input_port)
                travel_t = d / max(amr_speed, 1e-9)
                wait_t = 0.0
                for q_job in target_m.input_buf:
                    wait_t += process_time_for(target_m.stage, q_job, target_m)
                if target_m.processing_job:
                    wait_t += process_time_for(target_m.stage, target_m.processing_job, target_m)
                return travel_t + wait_t
            drop_m = min(slot_ok, key=cost)
        else:
            # Fallback to round robin
            rr = global_variable.ROUND_ROBIN_IDX.get(nxt, 0)
            drop_m = slot_ok[rr % len(slot_ok)]
            global_variable.ROUND_ROBIN_IDX[nxt] = rr + 1
        
        # Continue with the rest of the original logic
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

        def drop_end():
            job.in_transit = False
            job.reserved = False
            sim_core.enqueue_to_machine(drop_m, job)
            sim_core.release_input(drop_m)
            from logger import _amr_pop_task
            _amr_pop_task(amr, job_id=job.job_id, depart_drop=res["depart_drop"])
            sim_core.kick_dispatch_from_prev_stage(nxt)

        from config import schedule
        schedule(depart_at, go_pickup)
        schedule(arrive_pick, lambda: None)
        schedule(depart_pick, pickup_end)
        schedule(arrive_drop, lambda: None)
        schedule(depart_drop, drop_end)

        global_variable.amr_waits.setdefault(amr.name, []).append((arrive_pick, depart_pick, job.job_id, "load", m.output_port))
        global_variable.amr_waits.setdefault(amr.name, []).append((arrive_drop, depart_drop, job.job_id, "unload", drop_xy))
    
    # Apply patch
    sim_core.move_to_next_stage_from_output = patched_move_to_next_stage_from_output

def run_sweep():
    global ROUTING_MODE
    
    routing_methods = ["round_robin", "nearest", "cost_based"]
    results = []
    
    print("=" * 60)
    print("Routing + AMR Sweep Test")
    print("=" * 60)
    
    for method in routing_methods:
        ROUTING_MODE = method
        patch_routing()
        
        print(f"\n--- Testing: {method.upper()} ---")
        
        best_profit = 0
        best_amr = 0
        
        for amr_n in AMR_RANGE:
            cfg = sim_core.FactoryConfig(
                sim_time=SIM_TIME,
                seed=SEED,
                feed_sequence=("ProdA", "ProdB"),
                amr_count=amr_n,
                machine_counts=machine_counts,
                machine_positions=machine_positions
            )
            
            sim_core.simulate(cfg)
            profit = calculate_profit(amr_n)
            
            count_a = len(global_variable.STOCKERS["STK-01"].list_jobs_A())
            count_b = len(global_variable.STOCKERS["STK-01"].list_jobs_B())
            
            print(f"AMR={amr_n:2d}: Profit={profit:,.0f} (A:{count_a}, B:{count_b})")
            
            if profit > best_profit:
                best_profit = profit
                best_amr = amr_n
        
        results.append((method, best_amr, best_profit))
        print(f">>> Best for {method}: AMR={best_amr}, Profit={best_profit:,.0f}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for method, amr, profit in results:
        print(f"{method:15s}: AMR={amr:2d}, Profit={profit:,.0f}")
    
    # Find global best
    best = max(results, key=lambda x: x[2])
    print(f"\n🏆 GLOBAL BEST: {best[0]} with AMR={best[1]}, Profit={best[2]:,.0f}")

if __name__ == "__main__":
    run_sweep()
