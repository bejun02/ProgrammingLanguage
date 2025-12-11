import sim_core
from config import global_variable, process_time_for
import numpy as np
from sweep_routing_amr import patch_routing, ROUTING_MODE
import sweep_routing_amr

# Configuration matches the best cases found
# RR: AMR 11
# Cost: AMR 19
SCENARIOS = [
    ("Round Robin", "round_robin", 11),
    ("Cost Based", "cost_based", 19)
]

def run_investigation():
    print("="*60)
    print("Routing Strategy Deep Dive: Machine Utilization Analysis")
    print("="*60)

    for name, mode, amr_count in SCENARIOS:
        print(f"\n👉 Analyzing: {name} (AMR={amr_count})")
        
        # 1. Setup Patching
        sweep_routing_amr.ROUTING_MODE = mode
        sweep_routing_amr.patch_routing()
        
        # 2. Setup Counters
        # We need to reset counters. We'll attach a 'processed_count' to machines.
        # But machines are re-created in sim_core.simulate -> build_factory.
        # So we hook into simulate.
        
        # 3. Configure
        cfg = sim_core.FactoryConfig(
            sim_time=1296000,
            seed=20,
            feed_sequence=("ProdA", "ProdB"),
            amr_count=amr_count,
            machine_counts={"A": 5, "B": 8, "C": 6, "D": 5, "E": 5},
            machine_positions=sweep_routing_amr.machine_positions
        )
        
        # 4. Run
        sim_core.simulate(cfg)
        
        # 5. Analyze "Processed Count"
        # Since we didn't count in real-time, we can count by checking the output logs? No.
        # We can perform a 'post-mortem' check if machines tracked their history.
        # Current code doesn't track history per machine easily.
        # Alternative: Monkey patch try_start_processing here to count.
        pass

def patch_and_count(cfg):
    # Store original
    orig_start = sim_core.try_start_processing
    
    # Reset counts
    counts = {} # machine_name -> int
    
    def tracked_start(m):
        # Call original
        res = orig_start(m)
        # If job started (m.processing_job represents current job)
        if m.processing_job and m.processing_start_time == global_variable.now:
             counts[m.name] = counts.get(m.name, 0) + 1
             
    sim_core.try_start_processing = tracked_start
    
    sim_core.simulate(cfg)
    
    # Restore
    sim_core.try_start_processing = orig_start
    
    return counts

def analyze_counts(counts):
    # Group by stage
    stages = {}
    for m_name, count in counts.items():
        # Name format "StageName-No", e.g. "A-01"
        stage = m_name.split("-")[0]
        stages.setdefault(stage, []).append(count)
        
    print(f"{'Stage':<5} | {'Total':<6} | {'Avg':<6} | {'StdDev':<6} | {'Min':<4} | {'Max':<4} | {'Balance Score'}")
    print("-" * 65)
    
    total_balance_score = 0
    
    for stage in sorted(stages.keys()):
        data = stages[stage]
        if not data: continue
        
        avg = np.mean(data)
        std = np.std(data)
        min_v = np.min(data)
        max_v = np.max(data)
        total = sum(data)
        
        # cv (Coefficient of Variation) = StdDev / Mean (Lower is better balance)
        cv = (std / avg) if avg > 0 else 0
        
        print(f"{stage:<5} | {total:<6d} | {avg:<6.1f} | {std:<6.1f} | {min_v:<4} | {max_v:<4} | {cv:.3f}")
        total_balance_score += cv
        
    print("-" * 65)
    print(f"Total CV Sum (Lower is Equal): {total_balance_score:.3f}")
    if total_balance_score < 0.1:
        print("Verdict: Excellent Load Balancing ✅")
    else:
        print("Verdict: Imbalanced Workload ⚠️")

if __name__ == "__main__":
    for name, mode, amr_count in SCENARIOS:
        print(f"\n\n👉 Analyzing: {name} (AMR={amr_count})")
        sweep_routing_amr.ROUTING_MODE = mode
        sweep_routing_amr.patch_routing()
        
        cfg = sim_core.FactoryConfig(
            sim_time=1296000, # 15 days
            seed=20,
            feed_sequence=("ProdA", "ProdB"),
            amr_count=amr_count,
            machine_counts={"A": 5, "B": 8, "C": 6, "D": 5, "E": 5},
            machine_positions=sweep_routing_amr.machine_positions
        )
        
        counts = patch_and_count(cfg)
        analyze_counts(counts)
