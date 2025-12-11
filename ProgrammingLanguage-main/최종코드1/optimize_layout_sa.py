import sim_core
from config import global_variable
import sweep_routing_amr
import random
import math
import copy

# Configuration
ITERATIONS = 50   # Number of layout attempts
START_TEMP = 1000
COOLING_RATE = 0.95
AMR_COUNT = 11    # Global Best AMR

# Current Best Layout (Starting Point)
initial_layout = sweep_routing_amr.machine_positions

def layout_to_genome(layout):
    """Convert layout dict to a list of assignments [(x, y, type), ...] for swapping."""
    # We need to map slots to machine types.
    # Empty slots are also a type 'None'.
    # Slots defined in previous files:
    slots = []
    for x in [14, 22, 30, 38, 46]:
        for y in [3, 5, 7, 13, 15, 17]:
            slots.append((x, y))
    
    # Map current layout to these slots
    slot_map = {s: None for s in slots}
    for m_type, coords in layout.items():
        for xy in coords:
            if xy in slot_map:
                slot_map[xy] = m_type
    
    return slots, [slot_map[s] for s in slots]

def genome_to_layout(slots, genome):
    """Convert genome back to layout dict."""
    new_layout = {"A": [], "B": [], "C": [], "D": [], "E": []}
    for i, m_type in enumerate(genome):
        if m_type is not None:
            new_layout[m_type].append(slots[i])
    return new_layout

def evaluate(layout):
    """Run simulation and return profit."""
    # Patch for Fallback Pathfinding is assumed active in sim_core.py
    # We must reset path cache or allow fallback. (We added fallback earlier)
    
    # We must use Round Robin as it is the champion
    sweep_routing_amr.ROUTING_MODE = "round_robin"
    sweep_routing_amr.patch_routing()
    
    cfg = sim_core.FactoryConfig(
        sim_time=1296000,
        seed=20,
        feed_sequence=("ProdA", "ProdB"),
        amr_count=AMR_COUNT,
        machine_counts={"A": 5, "B": 8, "C": 6, "D": 5, "E": 5},
        machine_positions=layout
    )
    
    try:
        sim_core.simulate(cfg)
        return sweep_routing_amr.calculate_profit(AMR_COUNT)
    except Exception as e:
        print(f" Sim failed: {e}")
        return 0

def run_optimization():
    print("="*60)
    print(f"Layout Optimization (Simulated Annealing) - {ITERATIONS} Iterations")
    print("="*60)
    
    slots, current_genome = layout_to_genome(initial_layout)
    current_profit = evaluate(initial_layout)
    
    best_genome = current_genome[:]
    best_profit = current_profit
    
    temp = START_TEMP
    
    print(f"Initial Profit: {best_profit:,.0f}")
    
    for i in range(ITERATIONS):
        # 1. Mutate: Swap two random positions
        idx1, idx2 = random.sample(range(len(slots)), 2)
        
        # Skip useless swaps (A <-> A)
        if current_genome[idx1] == current_genome[idx2]:
            continue
            
        new_genome = current_genome[:]
        new_genome[idx1], new_genome[idx2] = new_genome[idx2], new_genome[idx1]
        
        # 2. Evaluate
        new_layout = genome_to_layout(slots, new_genome)
        new_profit = evaluate(new_layout)
        
        # 3. Acceptance Probability
        diff = new_profit - current_profit
        
        accept = False
        if diff > 0:
            accept = True
        else:
            # Metropolis criterion
            p = math.exp(diff / max(temp, 1e-9)) * 100000 # Scale profit diff? Profit is 90M. diff is ~100k.
            # Normalizing diff is hard. Let's simplfy: Accept only improvements or small drops?
            # For this strict logic, Simple Hill Climbing might be safer.
            # But let's allow small randomness.
            if random.random() < 0.1: # 10% chance to explore bad moves?
                accept = True
        
        if accept:
            current_genome = new_genome
            current_profit = new_profit
            print(f"Iter {i+1}: New Gen Selected (Profit: {new_profit:,.0f}) {'UP 🔼' if diff>0 else 'down 🔽'}")
            
            if current_profit > best_profit:
                best_profit = current_profit
                best_genome = current_genome[:]
                print(f"  >>> NEW RECORD! {best_profit:,.0f}")
        else:
            print(f"Iter {i+1}: Rejected (Profit: {new_profit:,.0f})")
            
        temp *= COOLING_RATE
        
    print("="*60)
    print(f"Optimization Finished. Best Profit: {best_profit:,.0f}")
    
    final_layout = genome_to_layout(slots, best_genome)
    print("Best Layout Configuration:")
    for k in sorted(final_layout.keys()):
        print(f"  '{k}': {final_layout[k]},")

if __name__ == "__main__":
    run_optimization()
