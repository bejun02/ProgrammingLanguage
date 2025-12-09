import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_factory_layout():
    # Machine positions from the user's main.py
    machine_positions = {
        "A": [(14, 3), (14, 7), (14, 13), (14, 15), (14, 17)],
        "B": [(14, 5), (22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17), (38, 15)],
        "C": [(30, 3), (30, 5), (30, 7), (30, 13), (30, 15), (30, 17)],
        "D": [(38, 3), (38, 5), (38, 7), (38, 13), (38, 17)],
        "E": [(46, 3), (46, 5), (46, 7), (46, 13), (46, 15)],
    }

    # Warehouse and Stocker positions
    warehouse_xy = (4, 10)
    stocker_xy = (56, 10)

    # Colors for each machine type
    colors = {
        "A": "#f4cccc",  # Red-ish
        "B": "#c9daf8",  # Blue-ish
        "C": "#d9ead3",  # Green-ish
        "D": "#fff2cc",  # Yellow-ish
        "E": "#ead1dc",  # Purple-ish
        "WH": "#eeeeee",
        "STK": "#eeeeee"
    }

    fig, ax = plt.subplots(figsize=(12, 6))

    # Draw grid lines
    X_MIN, X_MAX = 0, 60
    Y_MIN, Y_MAX = 0, 20
    for x in range(X_MIN, X_MAX + 1):
        ax.plot([x, x], [Y_MIN, Y_MAX], linewidth=0.3, color="lightgray", zorder=1)
    for y in range(Y_MIN, Y_MAX + 1):
        ax.plot([X_MIN, X_MAX], [y, y], linewidth=0.3, color="lightgray", zorder=1)

    # Function to draw a machine block
    def draw_machine(center, type_name, color):
        x, y = center
        
        # Machine size 3x2, centered at (x, y)
        # Lower left corner: (x - 1.5, y - 1)
        width = 3
        height = 2
        rect = patches.Rectangle((x - 1.5, y - 1), width, height, linewidth=1, edgecolor='black', facecolor=color, zorder=2)
        ax.add_patch(rect)
        ax.text(x, y, type_name, ha='center', va='center', fontsize=10, fontweight='bold', zorder=3)

        # Input Port at (x-2, y)
        input_port = plt.Circle((x - 2, y), 0.2, color='blue', zorder=4)
        ax.add_patch(input_port)

        # Output Port at (x+2, y)
        output_port = plt.Circle((x + 2, y), 0.2, color='red', zorder=4)
        ax.add_patch(output_port)

    # Draw Machines
    for m_type, positions in machine_positions.items():
        for pos in positions:
            draw_machine(pos, m_type, colors[m_type])

    # Draw Warehouse
    ax.scatter(warehouse_xy[0], warehouse_xy[1], s=300, marker='s', edgecolors='black', facecolor='white', zorder=5, label="Warehouse")
    ax.text(warehouse_xy[0], warehouse_xy[1], "WH", ha='center', va='center', fontweight='bold')
    # Warehouse Output Port (Exact location)
    ax.add_patch(plt.Circle(warehouse_xy, 0.4, color='red', zorder=6))

    # Draw Stocker
    ax.scatter(stocker_xy[0], stocker_xy[1], s=300, marker='s', edgecolors='black', facecolor='white', zorder=5, label="Stocker")
    ax.text(stocker_xy[0], stocker_xy[1], "STK", ha='center', va='center', fontweight='bold')
    # Stocker Input Port (Exact location)
    ax.add_patch(plt.Circle(stocker_xy, 0.4, color='blue', zorder=6))

    # Settings
    ax.set_xlim(X_MIN, X_MAX)
    ax.set_ylim(Y_MIN, Y_MAX)
    ax.set_aspect('equal')
    ax.set_title("Factory Layout Visualization")
    ax.set_xlabel("X Coordinate")
    ax.set_ylabel("Y Coordinate")

    # Legend
    legend_elements = [patches.Patch(facecolor=colors[k], edgecolor='black', label=f'Machine {k}') for k in "ABCDE"]
    ax.legend(handles=legend_elements, loc='upper right')

    plt.tight_layout()
    output_path = "factory_layout.png"
    plt.savefig(output_path, dpi=150)
    print(f"Layout saved to {output_path}")

if __name__ == "__main__":
    draw_factory_layout()
