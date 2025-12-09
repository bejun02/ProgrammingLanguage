"""
pathfinding 거리 비교 테스트
"""

from pathfinding import pathfinding_dist, euclidean_dist, init_obstacle_map

machine_positions = {
    "A": [(14, 3), (14, 5), (14, 7), (14, 13), (14, 15)],
    "B": [(22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17), (30, 3), (30, 5)],
    "C": [(30, 7), (30, 13), (30, 15), (30, 17), (38, 3), (38, 5)],
    "D": [(38, 7), (38, 13), (38, 15), (38, 17), (46, 3)],
    "E": [(46, 5), (46, 7), (46, 13), (46, 15), (46, 17)],
}

init_obstacle_map(machine_positions)

test_routes = [
    ((4, 10), (12, 3), "WH → A-1"),
    ((12, 3), (20, 3), "A-1 → B-1"),
    ((20, 3), (28, 7), "B-1 → C-1"),
    ((4, 10), (54, 10), "WH → STK"),
]

print("=" * 70)
print("거리 비교 (Pathfinding vs Euclidean)")
print("=" * 70)

total_path = 0
total_eucl = 0

for start, end, desc in test_routes:
    path_dist = pathfinding_dist(start, end)
    eucl_dist = euclidean_dist(start, end)
    ratio = (path_dist / eucl_dist - 1) * 100
    
    total_path += path_dist
    total_eucl += eucl_dist
    
    print(f"\n{desc}")
    print(f"  Pathfinding: {path_dist:.2f}m")
    print(f"  Euclidean:   {eucl_dist:.2f}m")
    print(f"  증가율:      +{ratio:.1f}%")

print("\n" + "=" * 70)
print(f"전체 합계:")
print(f"  Pathfinding: {total_path:.2f}m")
print(f"  Euclidean:   {total_eucl:.2f}m")
print(f"  평균 증가율: +{(total_path/total_eucl-1)*100:.1f}%")
print("=" * 70)

# 이동 시간 영향 계산 (AMR 속도 1m/s 가정)
time_increase = total_path - total_eucl
print(f"\n⏱️ 이동 시간 증가: {time_increase:.2f}초")
print(f"   하루(86400초) 기준: 약 {(time_increase/total_eucl)*100:.1f}% 느림")
