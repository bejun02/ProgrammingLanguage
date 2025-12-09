import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pickle
from main import machine_positions

def visualize_all_paths():
    # Load cache
    try:
        with open("path_cache.pkl", "rb") as f:
            cache = pickle.load(f)
    except FileNotFoundError:
        print("Error: path_cache.pkl not found. Run generate_paths.py first.")
        return

    print(f"Loaded {len(cache)} paths.")

    fig, ax = plt.subplots(figsize=(12, 6))

    # Draw Obstacles (Machines)
    for m_type, positions in machine_positions.items():
        for (x, y) in positions:
            # 3x2 Rectangle centered at x,y -> [x-1.5, y-1]
            rect = patches.Rectangle((x - 1.5, y - 1), 3, 2, linewidth=1, edgecolor='black', facecolor='lightgray', zorder=2)
            ax.add_patch(rect)
            
            # Ports
            ax.add_patch(plt.Circle((x - 2, y), 0.2, color='blue', zorder=4)) # Input
            ax.add_patch(plt.Circle((x + 2, y), 0.2, color='red', zorder=4))  # Output

    # Draw Warehouse & Stocker
    wh_xy = (4, 10)
    stk_xy = (56, 10)
    
    ax.scatter(wh_xy[0], wh_xy[1], s=200, marker='s', edgecolors='black', facecolor='white', zorder=5)
    ax.add_patch(plt.Circle(wh_xy, 0.4, color='red', zorder=6)) # WH Output (exact center based on user update? wait user said WH output is 4,10)
    # User said "warehouse의 투출 포트는 4,10". So the port IS the center in this context, or just the coordinate is (4,10).
    # Previous viz used circle at (4,10).
    
    ax.scatter(stk_xy[0], stk_xy[1], s=200, marker='s', edgecolors='black', facecolor='white', zorder=5)
    ax.add_patch(plt.Circle(stk_xy, 0.4, color='blue', zorder=6)) # Stocker Input
    
    # Draw Paths
    # Use very low alpha to handle 900 overlapping paths
    for path in cache.values():
        xs = [p[0] for p in path]
        ys = [p[1] for p in path]
        ax.plot(xs, ys, color='green', linewidth=0.5, alpha=0.05, zorder=3)

    ax.set_xlim(0, 60)
    ax.set_ylim(0, 20)
    ax.set_aspect('equal')
    ax.set_title(f"Visualization of All {len(cache)} Pre-calculated Paths")

    plt.savefig("all_paths_visualization.png", dpi=300) # Higher DPI for detail
    print("Saved all_paths_visualization.png")

if __name__ == "__main__":
    visualize_all_paths()
