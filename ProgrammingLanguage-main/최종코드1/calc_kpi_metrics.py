
import sim_core
from config import global_variable, schedule, next_stage_for, load_time_for, unload_time_for, log, process_time_for
from data_structures import Machine
import math
import statistics
import sweep_routing_amr
import types

# --- Configurations ---
SIM_TIME = 1296000
ROUTING_MODE = "cost_based" # Default

# AS-IS Params
CFG_BASE = {
    "amr_count": 4,
    "wip_limit": 9999, # Unlimited
    "routing": "round_robin",
    "cutoff": 0,
    "machine_counts": {"A": 4, "B": 4, "C": 4, "D": 4, "E": 4},
    "layout_mode": "uniform"
}

# TO-BE Params
CFG_OPT = {
    "amr_count": 9,
    "wip_limit": 46,
    "routing": "cost_based",
    "cutoff": 11200,
    "machine_counts": {"A": 5, "B": 8, "C": 6, "D": 5, "E": 5},
    "layout_mode": "optimal"
}

# --- Patching Logic ---
original_move_to_next = sim_core.move_to_next_stage_from_output
original_dist = sim_core.dist  # Save GLOBAL original

def run_scenario(name, scfg):
    print(f"\n--- Running {name} Scenario ---")
    
    # 1. Setup Layout
    machine_positions = {}
    if scfg["layout_mode"] == "uniform":
         # Simple Uniform Layout
         # Just creating dummy positions
         for s in "ABCDE":
             machine_positions[s] = [(10 + 10*i, 10 + 5*("ABCDE".index(s))) for i in range(scfg["machine_counts"][s])]
             # Make them spread out so not exactly starting 0,0
    else:
        # Optimal Positions (from main.py)
        machine_positions = {
            "A": [(14, 3), (14, 7), (14, 13), (14, 15), (14, 17)],
            "B": [(14, 5), (22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17), (38, 15)],
            "C": [(30, 3), (30, 5), (30, 7), (30, 13), (30, 15), (30, 17)],
            "D": [(38, 3), (38, 5), (38, 7), (38, 13), (38, 17)],
            "E": [(46, 3), (46, 5), (46, 7), (46, 13), (46, 15)],
        }
    
    # 2. Patch Routing & Pathfinding
    sweep_routing_amr.ROUTING_MODE = scfg["routing"]
    sweep_routing_amr.patch_routing()
    
    if scfg["layout_mode"] == "uniform":
        # Force Euclidean
        def simple_dist(a, b):
            return math.hypot(a[0]-b[0], a[1]-b[1])
        sim_core.dist = simple_dist
    else:
        # Restore original (Optimal Layout + Cache)
        sim_core.dist = original_dist
             
    # 3. Patch CONWIP & Cutoff (Monkey patch reset)
    orig_reset = global_variable.reset
    def my_reset(self):
        orig_reset()
        self.MAX_WIP = scfg["wip_limit"]
        self.MIN_COMPLETION_TIME = scfg["cutoff"]
        if scfg["routing"] == "round_robin":
             self.PREPOS_WINDOW_MIN = 9999
             self.PREPOS_WINDOW_MAX = -9999
        else:
             self.PREPOS_WINDOW_MIN = -20
             self.PREPOS_WINDOW_MAX = 50
             
    global_variable.reset = types.MethodType(my_reset, global_variable)
    
    # 4. Run Sim
    cfg = sim_core.FactoryConfig(
        sim_time=SIM_TIME, seed=20, 
        amr_count=scfg["amr_count"],
        machine_counts=scfg["machine_counts"],
        machine_positions=machine_positions
    )
    sim_core.simulate(cfg)
    
    # 5. Calculate Metrics
    # Profit Logic
    stk = global_variable.STOCKERS["STK-01"]
    out_a = len(stk.list_jobs_A())
    out_b = len(stk.list_jobs_B())
    feeds = global_variable.FEED_COUNT_A + global_variable.FEED_COUNT_B
    
    param = {"A": 4, "B": 9, "C": 8, "D": 8, "E": 5.5}
    m_cost = sum(c * param[s] for s,c in scfg["machine_counts"].items())
    profit = (100 * min(out_a, out_b) - 5 * feeds)
    inv_cost = m_cost + 0.011 * scfg["amr_count"]
    profit_score = (profit / inv_cost) * 100000
    
    # Throughput (Sets per Hour)
    throughput = min(out_a, out_b) / (SIM_TIME / 3600.0)
    
    # Lead Time (Avg)
    lead_times = []
    # FIX: Use helper functions to list jobs
    completed_job_ids = stk.list_jobs_A() + stk.list_jobs_B()
    
    for jid in completed_job_ids:
        if jid in global_variable.job_runs:
            history = global_variable.job_runs[jid]
            if history:
                history.sort(key=lambda x: x[1])
                start_t = history[0][1] # First Process Start
                end_t = history[-1][2] # Last Process End (E end)
                lead_times.append(end_t - start_t)
            
    avg_lead_time = statistics.mean(lead_times) if lead_times else 0
    
    # Utilization
    total_mach_time = 0
    total_run_time = 0
    stage_utils = {} # For LOB
    
    for stage in "ABCDE":
        s_vals = []
        for m in global_variable.MACHINES[stage]:
            runs = global_variable.machine_runs.get(m.name, [])
            run_sum = sum(e-s for s,e,_,_ in runs)
            util = run_sum / SIM_TIME
            s_vals.append(util)
            total_run_time += run_sum
            total_mach_time += SIM_TIME
        stage_utils[stage] = statistics.mean(s_vals) if s_vals else 0
            
    avg_util = (total_run_time / total_mach_time) if total_mach_time > 0 else 0
    
    # LOB = Avg / Max
    vals = list(stage_utils.values())
    lob = (statistics.mean(vals) / max(vals)) if vals and max(vals) > 0 else 0
    
    # WIP (Estimated)
    rate_per_sec = len(completed_job_ids) / SIM_TIME
    littles_wip = rate_per_sec * avg_lead_time

    # New: AMR Travel Distance (Avg per Job)
    total_dist = 0.0
    # Create an index of AMR drops: {job_id: [end_time, ...]} (Naive approx)
    # Better: List of drops.
    # amr_runs structure: (start, end, job_id, start_xy, end_xy, loaded)
    amr_drops = {} # job_id -> list of end_time
    
    for amr_name, runs in global_variable.amr_runs.items():
         for r in runs:
             s_xy = r[3]
             e_xy = r[4]
             loaded = r[5]
             d = math.hypot(s_xy[0]-e_xy[0], s_xy[1]-e_xy[1])
             total_dist += d
             
             if loaded:
                 jid = r[2]
                 if jid not in amr_drops: amr_drops[jid] = []
                 amr_drops[jid].append(r[1]) # end_time

    avg_dist = total_dist / len(completed_job_ids) if completed_job_ids else 0
    
    # New: Buffer Wait Time (Product Wait in Queue)
    # Compare Machine Start Time with AMR Arrival Time
    total_buf_wait = 0.0
    buf_wait_count = 0
    
    for jid, history in global_variable.job_runs.items():
        # history: [(mach_name, start, end, step_name), ...]
        history.sort(key=lambda x: x[1])
        if jid in amr_drops:
            arrivals = sorted(amr_drops[jid])
            # We hope arrivals match history steps.
            # Usually: arrive A, start A, arrive B, start B...
            # But history[0] is Step A.
            # Arrival for Step A is the 1st drop.
            # Note: 1st drop is WH -> A.
            min_len = min(len(history), len(arrivals))
            for i in range(min_len):
                arr_t = arrivals[i]
                start_t = history[i][1]
                wait = start_t - arr_t
                if wait > 0:
                     total_buf_wait += wait
                buf_wait_count += 1
                
    avg_buf_wait = total_buf_wait / buf_wait_count if buf_wait_count > 0 else 0

    return {
        "profit": profit_score,
        "throughput": throughput,
        "lead_time": avg_lead_time,
        "util": avg_util,
        "lob": lob,
        "wip": littles_wip,
        "out_a": out_a,
        "out_b": out_b,
        "avg_dist": avg_dist,
        "avg_buf_wait": avg_buf_wait
    }

# --- Main Comp ---
print("Starting...")
res_base = run_scenario("BASELINE", CFG_BASE)
res_opt = run_scenario("OPTIMAL", CFG_OPT)

print("\n=== FINAL KPI COMPARISON ===")
print(f"{'Metric':<20} | {'AS-IS (Base)':<15} | {'TO-BE (Opt)':<15} | {'Improvement'}")
print("-" * 65)

# 1. Profit
p_diff = res_opt['profit'] - res_base['profit']
p_pct = (p_diff / res_base['profit']) * 100 if res_base['profit'] else 0
print(f"{'Net Profit':<20} | {res_base['profit']:,.0f} KRW     | {res_opt['profit']:,.0f} KRW     | +{p_diff:,.0f} ({p_pct:+.1f}%)")

# 2. Throughput
t_diff = res_opt['throughput'] - res_base['throughput']
print(f"{'Throughput':<20} | {res_base['throughput']:.1f} sets/hr     | {res_opt['throughput']:.1f} sets/hr     | +{t_diff:.1f}")

# 3. Lead Time (Lower is better)
l_diff = res_base['lead_time'] - res_opt['lead_time']
print(f"{'Avg Lead Time':<20} | {res_base['lead_time']:.1f} sec      | {res_opt['lead_time']:.1f} sec      | -{l_diff:.1f} sec")

# 4. LOB (Balance) - Higher is better
lob_diff = res_opt['lob'] - res_base['lob']
print(f"{'Line Balance (LOB)':<20} | {res_base['lob']*100:.1f}%              | {res_opt['lob']*100:.1f}%              | {lob_diff*100:+.1f}%p")

# 5. WIP (Stability)
wip_diff = res_base['wip'] - res_opt['wip']
print(f"{'Avg WIP Level':<20} | {res_base['wip']:.1f} ea          | {res_opt['wip']:.1f} ea          | {wip_diff:+.1f} ea")

# 6. Utilization
u_diff = res_opt['util'] - res_base['util']
print(f"{'Avg Utilization':<20} | {res_base['util']*100:.1f}%              | {res_opt['util']*100:.1f}%              | {u_diff*100:+.1f}%p")

# 7. AMR Distance
d_diff = res_base['avg_dist'] - res_opt['avg_dist']
print(f"{'Avg AMR Dist':<20} | {res_base['avg_dist']:.1f} m            | {res_opt['avg_dist']:.1f} m            | -{d_diff:.1f} m")

# 8. Buffer Wait
b_diff = res_base['avg_buf_wait'] - res_opt['avg_buf_wait']
print(f"{'Avg Machine Wait':<20} | {res_base['avg_buf_wait']:.1f} sec        | {res_opt['avg_buf_wait']:.1f} sec        | -{b_diff:.1f} sec")
