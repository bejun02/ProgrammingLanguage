import heapq
import math
import pickle
from typing import List, Tuple, Dict, Set

class PathFinder:
    def __init__(self, machine_positions: Dict[str, List[Tuple[float, float]]], 
                 x_max=60, y_max=20, resolution=0.5):
        self.resolution = resolution
        self.width = int(x_max / resolution) + 1
        self.height = int(y_max / resolution) + 1
        self.grid = [[False for _ in range(self.width)] for _ in range(self.height)]
        self.machine_positions = machine_positions
        self._mark_obstacles()

    def _to_grid(self, x: float, y: float) -> Tuple[int, int]:
        return int(round(x / self.resolution)), int(round(y / self.resolution))

    def _to_world(self, gx: int, gy: int) -> Tuple[float, float]:
        return gx * self.resolution, gy * self.resolution

    def _mark_obstacles(self):
        # Machines are 3x2 size centered at (x, y)
        # Blocked: [x-1.5, x+1.5] x [y-1, y+1]
        
        for m_type, positions in self.machine_positions.items():
            for (mx, my) in positions:
                gx, gy = self._to_grid(mx, my)
                w_half = int(1.5 / self.resolution)
                h_half = int(1.0 / self.resolution)
                
                for y in range(gy - h_half, gy + h_half + 1):
                    for x in range(gx - w_half, gx + w_half + 1):
                        if 0 <= x < self.width and 0 <= y < self.height:
                            self.grid[y][x] = True

    def find_path(self, start: Tuple[float, float], end: Tuple[float, float]) -> List[Tuple[float, float]]:
        start_grid = self._to_grid(*start)
        end_grid = self._to_grid(*end)
        
        if self._is_blocked(end_grid):
            print(f"Warning: Destination {end} is blocked.")
            return []

        # A* Algorithm with 8-connectivity
        open_set = []
        heapq.heappush(open_set, (0, start_grid))
        came_from = {}
        g_score = {start_grid: 0}
        f_score = {start_grid: self._heuristic(start_grid, end_grid)}
        
        while open_set:
            _, current = heapq.heappop(open_set)
            
            if current == end_grid:
                raw_path = self._reconstruct_path(came_from, current)
                return self.smooth_path(raw_path)
            
            # 8 neighbors
            neighbors = [
                (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
                (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)
            ]
            
            for dx, dy, cost in neighbors:
                neighbor = (current[0] + dx, current[1] + dy)
                
                if not (0 <= neighbor[0] < self.width and 0 <= neighbor[1] < self.height):
                    continue
                if self.grid[neighbor[1]][neighbor[0]]: # Blocked
                    continue
                
                # Check diagonal passage
                if dx != 0 and dy != 0:
                    if self.grid[current[1]][neighbor[0]] or self.grid[neighbor[1]][current[0]]:
                        continue

                tentative_g = g_score[current] + cost
                
                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self._heuristic(neighbor, end_grid)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))
                    
        return []

    def _heuristic(self, a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def _is_blocked(self, grid_pos):
        gx, gy = grid_pos
        if not (0 <= gx < self.width and 0 <= gy < self.height):
            return True
        return self.grid[gy][gx]

    def _reconstruct_path(self, came_from, current):
        total_path = [current]
        while current in came_from:
            current = came_from[current]
            total_path.append(current)
        total_path.reverse()
        return [self._to_world(gx, gy) for gx, gy in total_path]

    def has_line_of_sight(self, start: Tuple[float, float], end: Tuple[float, float]) -> bool:
        """Check if straight line matches any obstacle using simple stepping."""
        x0, y0 = self._to_grid(*start)
        x1, y1 = self._to_grid(*end)
        
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        
        while True:
            if self.grid[y0][x0]:
                return False
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy
                
        return True

    def smooth_path(self, path: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Simplify path using Line-of-Sight (String Pulling)."""
        if len(path) < 3:
            return path
            
        smoothed_path = [path[0]]
        current_idx = 0
        
        while current_idx < len(path) - 1:
            next_idx = current_idx + 1
            for i in range(len(path) - 1, current_idx, -1):
                if self.has_line_of_sight(path[current_idx], path[i]):
                    next_idx = i
                    break
            
            smoothed_path.append(path[next_idx])
            current_idx = next_idx
            
        return smoothed_path

    def precalculate_and_save(self, sources: List[Tuple[float, float]], destinations: List[Tuple[float, float]], filename: str):
        """Calculate and save all paths from sources to destinations."""
        cache = {}
        total = len(sources) * len(destinations)
        print(f"Pre-calculating {total} paths...")
        
        count = 0
        for src in sources:
            for dst in destinations:
                if src == dst:
                    continue
                
                path = self.find_path(src, dst)
                if path:
                    cache[(src, dst)] = path
                count += 1
                if count % 100 == 0:
                    print(f"Calculated {count}/{total}")
        
        print(f"Saving {len(cache)} paths to {filename}")
        with open(filename, 'wb') as f:
            pickle.dump(cache, f)
        print("Done.")

    def load_cache(self, filename: str) -> Dict:
        with open(filename, 'rb') as f:
            return pickle.load(f)
