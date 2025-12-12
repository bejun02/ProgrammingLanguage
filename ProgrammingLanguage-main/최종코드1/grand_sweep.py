import sim_core
import config
from config import global_variable
import sweep_routing_amr
import multiprocessing as mp

# Search Space (Expanded)
WIP_RANGE = [40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60, 65, 70]
AMR_RANGE = [8, 9, 10, 11, 12, 13, 14, 15]
MIN_C_RANGE = [10000, 11000, 11500, 11800, 12000, 12050, 12100, 12150, 12200, 12500, 13000, 14000, 15000]

def worker_task(args):
    wip, amr_n, min_c = args
    
    # Patch Global Variable Setup
    original_reset = config.global_variable.reset
    def patched_reset():
        original_reset()
        config.global_variable.MAX_WIP = wip
        config.global_variable.MIN_COMPLETION_TIME = min_c
        
    config.global_variable.reset = patched_reset
    
    # Configure Factory
    machine_counts = {"A": 5, "B": 8, "C": 6, "D": 5, "E": 5}
    machine_positions = sweep_routing_amr.machine_positions
    
    cfg = sim_core.FactoryConfig(
        sim_time=1296000,
        seed=20,
        feed_sequence=("ProdA","ProdB"),
        amr_count=amr_n,
        machine_counts=machine_counts,
        machine_positions=machine_positions
    )
    
    # Run Simulation
    sim_core.simulate(cfg)
    
    # Calculate Profit
    profit = sweep_routing_amr.calculate_profit(amr_n)
    return (wip, amr_n, min_c, profit)

def run_grand_sweep():
    tasks = []
    for wip in WIP_RANGE:
        for amr in AMR_RANGE:
            for min_c in MIN_C_RANGE:
                tasks.append((wip, amr, min_c))
                
    print(f"Starting Grand Sweep with {len(tasks)} combinations...")
    
    with mp.Pool(processes=10) as pool:
        results = pool.map(worker_task, tasks)
        
    # Sort by profit descending
    results.sort(key=lambda x: x[3], reverse=True)
    
    print("\n=== Top 10 Configurations ===")
    print(f"{'Rank':<5} | {'WIP':<5} | {'AMR':<5} | {'MinCutoff':<10} | {'Profit':<15}")
    print("-" * 50)
    
    for i, (w, a, c, p) in enumerate(results[:10]):
        print(f"{i+1:<5} | {w:<5} | {a:<5} | {c:<10} | {p:,.0f}")
        
    best = results[0]
    print("\n🏆 GLOBAL BEST FOUND:")
    print(f"WIP: {best[0]}")
    print(f"AMR: {best[1]}")
    print(f"MinCutoff: {best[2]}")
    print(f"Profit: {best[3]:,.0f}")

if __name__ == "__main__":
    mp.freeze_support()
    run_grand_sweep()
