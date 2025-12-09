"""
pathfinding obstacle 디버깅
"""

from pathfinding import init_obstacle_map, get_path, path_graph

machine_positions = {
    "A": [(14, 3), (14, 5), (14, 7), (14, 13), (14, 15)],
    "B": [(22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17), (30, 3), (30, 5)],
    "C": [(30, 7), (30, 13), (30, 15), (30, 17), (38, 3), (38, 5)],
    "D": [(38, 7), (38, 13), (38, 15), (38, 17), (46, 3)],
    "E": [(46, 5), (46, 7), (46, 13), (46, 15), (46, 17)],
}

print("=" * 70)
print("Pathfinding Obstacle 디버깅")
print("=" * 70)

# 초기화
init_obstacle_map(machine_positions)

print(f"\nObstacles 개수: {len(path_graph.obstacles)}")
print(f"Nodes 개수: {len(path_graph.nodes)}")

print(f"\n처음 3개 obstacles:")
for i, obs in enumerate(path_graph.obstacles[:3]):
    print(f"  {i+1}. center={obs.center}, x=[{obs.x_min:.1f}, {obs.x_max:.1f}], y=[{obs.y_min:.1f}, {obs.y_max:.1f}]")

# 테스트 경로
test_cases = [
    ((4, 10), (12, 3), "Warehouse → A-1"),
    ((4, 10), (14, 3), "Warehouse → A-1 center (should go around)"),
    ((12, 3), (20, 3), "A-1 → B-1 (should avoid obstacles)"),
]

print(f"\n경로 테스트:")
for start, end, desc in test_cases:
    path = get_path(start, end)
    print(f"\n  {desc}")
    print(f"    시작: {start}, 끝: {end}")
    print(f"    경로 길이: {len(path)}개 waypoints")
    
    if len(path) <= 5:
        print(f"    전체 경로: {path}")
    else:
        print(f"    경로: {path[:2]} ... {path[-2:]}")
    
    # 직선 이동 가능 여부
    can_direct = path_graph.can_move_direct(start, end)
    print(f"    직선 이동 가능: {can_direct}")
    
    # 각 장애물과의 교차 확인
    intersecting_obs = []
    for i, obs in enumerate(path_graph.obstacles):
        if obs.intersects_line(start, end):
            intersecting_obs.append((i, obs.center))
    
    if intersecting_obs:
        print(f"    ⚠️ 교차하는 장애물: {len(intersecting_obs)}개")
        for idx, center in intersecting_obs[:3]:
            print(f"      - Obstacle {idx}: center={center}")
    
    if can_direct and len(path) == 2:
        print(f"    ⚠️ 장애물이 있어야 하는데 직선으로 감!")
