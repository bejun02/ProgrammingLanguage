import sim_core
from config import global_variable
from sweep_routing_amr import patch_routing, ROUTING_MODE
import sweep_routing_amr

# Champion Settings
BEST_AMR = 11
BEST_ROUTING = "round_robin"

# Original Layout
layout_original = sweep_routing_amr.machine_positions

# Optimized Layout: Consolidate B to x=22
# Current B: [(14, 5), (22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17), (38, 15)]
# New B: All at x=22. We use y=9, 11 for the extras.
layout_optimized = layout_original.copy()
layout_optimized["B"] = [
    (22, 3), (22, 5), (22, 7), 
    (22, 9), (22, 11),  # New slots replacing (14, 5) and (38, 15)
    (22, 13), (22, 15), (22, 17)
]
# Ensure A doesn't overlap? A is at x=14. B was at (14,5). Now (14,5) is empty. Safe.
# Ensure D doesn't overlap? D is at x=38. B was at (38,15). Now (38,15) is empty. Safe.

def run_layout_test():
    print("="*60)
    print("Layout Optimization Test: Consolidating B Machines")
    print("="*60)
    
    layouts = [
        ("Original Layout", layout_original),
        ("Optimized Layout (B grouped at x=22)", layout_optimized)
    ]
    
    sweep_routing_amr.ROUTING_MODE = BEST_ROUTING
    sweep_routing_amr.patch_routing()
    
    results = []
    
    for name, pos in layouts:
        print(f"\n--- Testing: {name} ---")
        cfg = sim_core.FactoryConfig(
            sim_time=1296000,
            seed=20,
            feed_sequence=("ProdA", "ProdB"),
            amr_count=BEST_AMR,
            machine_counts={"A": 5, "B": 8, "C": 6, "D": 5, "E": 5},
            machine_positions=pos
        )
        
        sim_core.simulate(cfg)
        
        profit = sweep_routing_amr.calculate_profit(BEST_AMR)
        stk = global_variable.STOCKERS.get("STK-01")
        a_jobs = len(stk.list_jobs_A()) if stk else 0
        b_jobs = len(stk.list_jobs_B()) if stk else 0
        
        print(f"Result: Profit={profit:,.0f} (A:{a_jobs}, B:{b_jobs})")
        results.append((name, profit))

    print("\n" + "="*60)
    print("COMPARISON RESULTS")
    print("="*60)
    base_profit = results[0][1]
    for name, p in results:
        diff = p - base_profit
        diff_str = f"({diff:+,.0f})" if diff != 0 else "(Baseline)"
        print(f"{name:35s}: {p:,.0f} {diff_str}")

if __name__ == "__main__":
    run_layout_test()
