from pathfinding import PathFinder
from main import machine_positions

def generate_paths():
    # 1. Setup
    pf = PathFinder(machine_positions, x_max=60, y_max=20, resolution=0.5)
    
    # 2. Define Points
    sources = []
    destinations = []
    
    # Key Points
    wh_out = (4, 10)
    stk_in = (56, 10)
    
    # Initial AMR Positions (Support up to 30 AMRs for flexibility)
    max_amr_count = 30
    initial_positions = [(4.0, i * 0.1) for i in range(max_amr_count)]
    
    # Collect all relevant points
    all_outputs = [wh_out] # Pickup locations
    all_inputs = [stk_in]  # Drop locations
    
    for m_type, positions in machine_positions.items():
        for (x, y) in positions:
            all_outputs.append((x + 2, y)) # Machine Output
            all_inputs.append((x - 2, y))  # Machine Input
            
    # Logic:
    # 1. Initial -> Any Pickup (Output)
    # 2. Pickup (Output) -> Drop (Input)  (Travel with load)
    # 3. Drop (Input) -> Any Pickup (Output) (Travel empty to next task)
    
    # Case 1
    for init in initial_positions:
        sources.append(init)
    
    # Case 2 & 3: Outputs and Inputs can be Sources
    # Outputs are sources for Loaded Travel
    # Inputs are sources for Empty Travel (after drop)
    
    potential_starts = all_outputs + all_inputs + initial_positions
    potential_ends = all_outputs + all_inputs
    
    # Remove duplicates
    potential_starts = list(set(potential_starts))
    potential_ends = list(set(potential_ends))
    
    sources = potential_starts
    destinations = potential_ends

    # 3. Generate and Save
    print(f"Sources: {len(sources)}, Destinations: {len(destinations)}")
    pf.precalculate_and_save(sources, destinations, "path_cache.pkl")

if __name__ == "__main__":
    generate_paths()
