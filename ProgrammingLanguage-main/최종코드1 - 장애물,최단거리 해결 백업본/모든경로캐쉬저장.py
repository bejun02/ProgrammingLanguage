from pathfinding import PathFinder
from main import machine_positions

def generate_paths():
    # 1. Setup
    pf = PathFinder(machine_positions, x_max=60, y_max=20, resolution=0.5)
    
    # 2. Define Points
    sources = []
    destinations = []
    
    # Warehouse Output (Source only)
    wh_out = (4, 10)
    sources.append(wh_out)
    
    # Stocker Input (Destination only)
    stk_in = (56, 10)
    destinations.append(stk_in)
    
    # Machines
    # Output Port (Source, x+2)
    # Input Port (Destination, x-2)
    for m_type, positions in machine_positions.items():
        for (x, y) in positions:
            out_port = (x + 2, y)
            in_port = (x - 2, y)
            
            sources.append(out_port)
            destinations.append(in_port)
            
    # 3. Generate and Save
    print(f"Sources: {len(sources)}, Destinations: {len(destinations)}")
    pf.precalculate_and_save(sources, destinations, "path_cache.pkl")

if __name__ == "__main__":
    generate_paths()
