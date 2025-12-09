"""
AMR Count Sweep - Parallel Version
Uses multiprocessing to test multiple AMR counts simultaneously.
"""
import multiprocessing as mp
import subprocess
import sys
import json
import os

# Configuration
SIM_TIME = 1296000
SEED = 20
AMR_MIN = 1
AMR_MAX = 30
NUM_WORKERS = min(8, mp.cpu_count())  # Use up to 8 parallel workers

# Script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def run_single_simulation(amr_count):
    """Run a single simulation with given AMR count (in separate process)"""
    worker_script = '''
import sys
sys.path.insert(0, r"''' + SCRIPT_DIR + '''")
import sim_core
from config import global_variable

machine_positions = {
    "A": [(14, 3), (14, 7), (14, 13), (14, 15), (14, 17)],
    "B": [(14, 5), (22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17), (38, 15)],
    "C": [(30, 3), (30, 5), (30, 7), (30, 13), (30, 15), (30, 17)],
    "D": [(38, 3), (38, 5), (38, 7), (38, 13), (38, 17)],
    "E": [(46, 3), (46, 5), (46, 7), (46, 13), (46, 15)],
}
machine_counts = {"A": 5, "B": 8, "C": 6, "D": 5, "E": 5}

cfg = sim_core.FactoryConfig(
    sim_time=''' + str(SIM_TIME) + ''',
    seed=''' + str(SEED) + ''',
    feed_sequence=("ProdA", "ProdB"),
    amr_count=''' + str(amr_count) + ''',
    machine_counts=machine_counts,
    machine_positions=machine_positions
)

sim_core.simulate(cfg)

parameter = {"A": 4, "B": 9, "C": 8, "D": 8, "E": 5.5}
t = sum(count * parameter[stage] for stage, count in machine_counts.items())

stk = global_variable.STOCKERS.get("STK-01")
count_a = len(stk.list_jobs_A()) if stk else 0
count_b = len(stk.list_jobs_B()) if stk else 0
feed = global_variable.FEED_COUNT_A + global_variable.FEED_COUNT_B

p = 100 * min(count_a, count_b) - 5 * feed
profit = p / (t + 0.011 * ''' + str(amr_count) + ''') * 100000

print(f"RESULT:''' + str(amr_count) + ''':{profit:.0f}:{count_a}:{count_b}")
'''
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", worker_script],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=SCRIPT_DIR
        )
        
        # Parse result from output
        for line in result.stdout.split('\n'):
            if line.startswith("RESULT:"):
                parts = line.split(":")
                return int(parts[1]), float(parts[2]), int(parts[3]), int(parts[4])
        
        return amr_count, 0, 0, 0
    except Exception as e:
        print(f"Error for AMR={amr_count}: {e}")
        return amr_count, 0, 0, 0

def run_parallel_sweep():
    print("=" * 60)
    print(f"AMR Count Sweep (Parallel - {NUM_WORKERS} workers)")
    print("=" * 60)
    print(f"Testing AMR counts from {AMR_MIN} to {AMR_MAX}...")
    print()
    
    # Create pool and run in parallel
    with mp.Pool(processes=NUM_WORKERS) as pool:
        results = pool.map(run_single_simulation, range(AMR_MIN, AMR_MAX + 1))
    
    # Sort by AMR count
    results.sort(key=lambda x: x[0])
    
    # Find best
    best = max(results, key=lambda x: x[1])
    
    # Print results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"{'AMR':>4} | {'Profit':>14} | {'A':>5} | {'B':>5}")
    print("-" * 40)
    
    for amr_n, profit, a, b in results:
        marker = " ★" if amr_n == best[0] else ""
        print(f"{amr_n:>4} | {profit:>14,.0f} | {a:>5} | {b:>5}{marker}")
    
    print("\n" + "=" * 60)
    print(f"🏆 BEST: AMR={best[0]}, Profit={best[1]:,.0f} KRW")
    print("=" * 60)

if __name__ == "__main__":
    # Windows requires this for multiprocessing
    mp.freeze_support()
    run_parallel_sweep()
