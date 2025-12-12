import sim_core
import config
from config import global_variable
import sweep_routing_amr
import multiprocessing as mp

# Ultra Fine-Tuning Ranges
WIP_RANGE = [45, 46, 47]
MIN_C_RANGE = [10800, 11000, 11200]
PREPOS_MAX_RANGE = [50, 60, 70, 80]
PREPOS_MIN_RANGE = [-20, -30, -40]
FIXED_AMR = 9

def worker_task(args):
    wip, min_c, p_max, p_min = args
    
    # Patch Global Variable Setup
    original_reset = config.global_variable.reset
    def patched_reset():
        original_reset()
        config.global_variable.MAX_WIP = wip
        config.global_variable.MIN_COMPLETION_TIME = min_c
        config.global_variable.PREPOS_WINDOW_MAX = p_max
        config.global_variable.PREPOS_WINDOW_MIN = p_min
        
        
    config.global_variable.reset = patched_reset
    
    # Configure Factory
    machine_counts = {"A": 5, "B": 8, "C": 6, "D": 5, "E": 5}
    machine_positions = sweep_routing_amr.machine_positions
    
    cfg = sim_core.FactoryConfig(
        sim_time=1296000,
        seed=20,
        feed_sequence=("ProdA","ProdB"),
        amr_count=FIXED_AMR,
        machine_counts=machine_counts,
        machine_positions=machine_positions
    )
    
    # Run Simulation
    sim_core.simulate(cfg)
    
    # Calculate Profit
    profit = sweep_routing_amr.calculate_profit(FIXED_AMR)
    return (wip, min_c, p_max, p_min, profit)

def run_ultra_sweep():
    tasks = []
    print(f"Generating tasks...")
    for wip in WIP_RANGE:
        for min_c in MIN_C_RANGE:
            for p_max in PREPOS_MAX_RANGE:
                for p_min in PREPOS_MIN_RANGE:
                    tasks.append((wip, min_c, p_max, p_min))
                
    print(f"Starting Ultra Sweep with {len(tasks)} combinations...")
    print(f"Target: Break 93,000,000 KRW")
    
    with mp.Pool(processes=10) as pool:
        results = pool.map(worker_task, tasks)
        
    # Sort by profit descending
    results.sort(key=lambda x: x[4], reverse=True)
    
    print("\n=== Top 5 Configurations ===")
    print(f"{'Rank':<5} | {'WIP':<5} | {'Cutoff':<8} | {'WinMax':<6} | {'WinMin':<6} | {'Profit':<15}")
    print("-" * 60)
    
    for i, (w, c, pmax, pmin, p) in enumerate(results[:5]):
        print(f"{i+1:<5} | {w:<5} | {c:<8} | {pmax:<6} | {pmin:<6} | {p:,.0f}")
        
    best = results[0]
    print("\n🏆 ULTRA BEST FOUND:")
    print(f"WIP: {best[0]}")
    print(f"MinCutoff: {best[1]}")
    print(f"PreposWindow: ({best[3]}, {best[2]})")
    print(f"Profit: {best[4]:,.0f}")
    
    if best[4] > 93000000:
        print("\n🚀 MISSION ACCOMPLISHED: 93M BARRIER BROKEN!")
    else:
        print("\n⚠️ Still under 93M. Try wider ranges or acceptable limit reached.")

if __name__ == "__main__":
    mp.freeze_support()
    run_ultra_sweep()
