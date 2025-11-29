"""
================================================================================
pathfinding.py - AMR 경로 탐색 모듈 (과업 1)
================================================================================
이 파일은 AMR의 이동 경로를 계산하는 다익스트라 알고리즘을 구현합니다.

주요 기능:
1. 설비 포트, Warehouse, Stocker를 노드로 하는 그래프 구성
2. 설비 금지 구역을 우회하는 경로 탐색
3. 다익스트라 알고리즘으로 최단 경로 계산

노드 구성:
    - Warehouse: (4, 10)
    - Stocker: (56, 10)
    - 각 설비의 입력포트: (center_x - 2, center_y)
    - 각 설비의 출력포트: (center_x + 2, center_y)

설비 금지 구역:
    - 설비 크기: 3m x 2m
    - 중심 (14,3) → 금지구역 x: 12.5~15.5, y: 2~4
    - 입력포트 (12,3), 출력포트 (16,3)은 금지구역 바깥

================================================================================
"""

import heapq
import math
from typing import List, Tuple, Dict, Optional, Set
from functools import lru_cache

# ================================================================================
# 성능 최적화: 경로 캠시
# ================================================================================
# 동일한 출발점-도착점 쿼리에 대해 결과 재사용
_path_cache: Dict[Tuple[Tuple[float, float], Tuple[float, float]], Tuple[float, List[Tuple[float, float]]]] = {}
ENABLE_PATH_CACHE = True  # 캠시 활성화 여부

# ================================================================================
# 상수 정의
# ================================================================================
# 맵 크기 (미터 단위)
MAP_WIDTH = 61   # x: 0 ~ 60
MAP_HEIGHT = 21  # y: 0 ~ 20

# 설비 크기 (미터 단위) - 중심 기준
MACHINE_HALF_WIDTH = 1.5   # 3m / 2
MACHINE_HALF_HEIGHT = 1.0  # 2m / 2

# 포트 오프셋 (설비 중심에서 포트까지 거리)
PORT_OFFSET = 2  # 입력포트: x-2, 출력포트: x+2

# Warehouse, Stocker 위치 (고정)
WAREHOUSE_XY = (4, 10)
STOCKER_XY = (56, 10)


# ================================================================================
# 설비 금지 구역 관리
# ================================================================================
class ObstacleZone:
    """
    설비 금지 구역 (사각형)
    
    Attributes:
        x_min, x_max: x 범위
        y_min, y_max: y 범위
    """
    def __init__(self, center_x: float, center_y: float):
        """
        설비 중심 좌표로 금지 구역 생성
        
        예: 중심 (14,3) → 금지구역 x: 12.5~15.5, y: 2~4
        """
        self.x_min = center_x - MACHINE_HALF_WIDTH   # 12.5
        self.x_max = center_x + MACHINE_HALF_WIDTH   # 15.5
        self.y_min = center_y - MACHINE_HALF_HEIGHT  # 2
        self.y_max = center_y + MACHINE_HALF_HEIGHT  # 4
        self.center = (center_x, center_y)
    
    def contains_point(self, x: float, y: float) -> bool:
        """점이 금지 구역 내부에 있는지 확인"""
        return (self.x_min < x < self.x_max and 
                self.y_min < y < self.y_max)
    
    def intersects_line(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> bool:
        """
        선분이 금지 구역과 교차하는지 확인
        
        Args:
            p1: 시작점 (x, y)
            p2: 끝점 (x, y)
        
        Returns:
            True면 교차, False면 교차 안함
        """
        x1, y1 = p1
        x2, y2 = p2
        
        # 두 점 모두 금지 구역 밖의 같은 쪽에 있으면 교차 안함
        if x1 <= self.x_min and x2 <= self.x_min:
            return False
        if x1 >= self.x_max and x2 >= self.x_max:
            return False
        if y1 <= self.y_min and y2 <= self.y_min:
            return False
        if y1 >= self.y_max and y2 >= self.y_max:
            return False
        
        # 한 점이라도 내부에 있으면 교차
        if self.contains_point(x1, y1) or self.contains_point(x2, y2):
            return True
        
        # 사각형의 4개 변과 선분의 교차 검사
        corners = [
            (self.x_min, self.y_min),
            (self.x_max, self.y_min),
            (self.x_max, self.y_max),
            (self.x_min, self.y_max),
        ]
        
        for i in range(4):
            c1 = corners[i]
            c2 = corners[(i + 1) % 4]
            if segments_intersect(p1, p2, c1, c2):
                return True
        
        return False


def segments_intersect(p1: Tuple[float, float], p2: Tuple[float, float],
                       p3: Tuple[float, float], p4: Tuple[float, float]) -> bool:
    """
    두 선분이 교차하는지 확인 (CCW 알고리즘)
    
    Args:
        p1, p2: 첫 번째 선분의 양 끝점
        p3, p4: 두 번째 선분의 양 끝점
    """
    def ccw(A, B, C):
        return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
    
    return (ccw(p1, p3, p4) != ccw(p2, p3, p4) and 
            ccw(p1, p2, p3) != ccw(p1, p2, p4))


# ================================================================================
# 경로 탐색 그래프
# ================================================================================
class PathGraph:
    """
    AMR 경로 탐색용 그래프
    
    노드: Warehouse, Stocker, 각 설비의 입력/출력 포트
    엣지: 설비 금지 구역을 통과하지 않는 직선 경로
    
    Attributes:
        nodes: 모든 노드 좌표 집합
        obstacles: 설비 금지 구역 리스트
        warehouse_xy: Warehouse 좌표
        stocker_xy: Stocker 좌표
        port_info: 포트 정보 {좌표: (설비명, 포트타입)}
    """
    
    def __init__(self):
        self.nodes: Set[Tuple[float, float]] = set()
        self.obstacles: List[ObstacleZone] = []
        self.warehouse_xy: Tuple[float, float] = WAREHOUSE_XY
        self.stocker_xy: Tuple[float, float] = STOCKER_XY
        self.port_info: Dict[Tuple[float, float], Tuple[str, str]] = {}
        
        # 기본 노드 추가
        self.nodes.add(self.warehouse_xy)
        self.nodes.add(self.stocker_xy)
    
    def add_machine(self, stage: str, center_x: float, center_y: float, machine_name: str = None):
        """
        설비 추가 (금지 구역 + 포트 노드)
        
        Args:
            stage: 공정 스테이지 (A, B, C, D, E)
            center_x, center_y: 설비 중심 좌표
            machine_name: 설비 이름 (예: "A-1")
        """
        # 금지 구역 추가
        self.obstacles.append(ObstacleZone(center_x, center_y))
        
        # 포트 좌표 계산
        input_port = (center_x - PORT_OFFSET, center_y)   # 입력포트 (왼쪽)
        output_port = (center_x + PORT_OFFSET, center_y)  # 출력포트 (오른쪽)
        
        # 노드에 포트 추가
        self.nodes.add(input_port)
        self.nodes.add(output_port)
        
        # 포트 정보 저장
        name = machine_name or f"{stage}-{len([o for o in self.obstacles])}"
        self.port_info[input_port] = (name, "input")
        self.port_info[output_port] = (name, "output")
    
    def add_machines_from_dict(self, machine_positions: Dict[str, List[Tuple[float, float]]]):
        """
        딕셔너리 형태의 설비 위치 정보로 설비 추가
        
        Args:
            machine_positions: {"A": [(14,3), (14,7)], "B": [(22,3)], ...}
        """
        for stage, positions in machine_positions.items():
            for idx, pos in enumerate(positions):
                machine_name = f"{stage}-{idx + 1}"
                self.add_machine(stage, pos[0], pos[1], machine_name)
    
    def can_move_direct(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> bool:
        """
        두 점 사이에 직선 이동이 가능한지 확인 (금지 구역 통과 여부)
        
        Args:
            p1, p2: 시작점, 끝점
        
        Returns:
            True면 직선 이동 가능, False면 금지 구역 통과
        """
        for obs in self.obstacles:
            if obs.intersects_line(p1, p2):
                return False
        return True
    
    def get_distance(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """
        두 점 사이 유클리드 거리
        """
        return math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    
    def dijkstra(self, start: Tuple[float, float], end: Tuple[float, float]) -> Tuple[float, List[Tuple[float, float]]]:
        """
        다익스트라 알고리즘으로 최단 경로 탐색
        
        Args:
            start: 시작점 좌표
            end: 도착점 좌표
        
        Returns:
            (총 거리, 경로 리스트)
            경로를 찾지 못하면 (직선거리, [start, end]) 반환
        """
        # 시작점, 끝점을 임시로 노드에 추가
        temp_nodes = self.nodes.copy()
        temp_nodes.add(start)
        temp_nodes.add(end)
        
        # 직선 이동 가능하면 바로 반환
        if self.can_move_direct(start, end):
            return (self.get_distance(start, end), [start, end])
        
        # 우선순위 큐: (거리, 현재노드)
        pq = [(0.0, start)]
        
        # 최단 거리 기록
        dist_map: Dict[Tuple[float, float], float] = {start: 0.0}
        
        # 경로 역추적용
        parent: Dict[Tuple[float, float], Optional[Tuple[float, float]]] = {start: None}
        
        while pq:
            curr_dist, curr = heapq.heappop(pq)
            
            # 도착점 도달
            if curr == end:
                path = []
                node = end
                while node is not None:
                    path.append(node)
                    node = parent.get(node)
                path.reverse()
                return (curr_dist, path)
            
            # 이미 더 짧은 경로로 방문했으면 스킵
            if curr_dist > dist_map.get(curr, float('inf')):
                continue
            
            # 모든 노드로의 이동 시도
            for next_node in temp_nodes:
                if next_node == curr:
                    continue
                
                # 직선 이동 가능한지 확인
                if not self.can_move_direct(curr, next_node):
                    continue
                
                new_dist = curr_dist + self.get_distance(curr, next_node)
                
                if new_dist < dist_map.get(next_node, float('inf')):
                    dist_map[next_node] = new_dist
                    parent[next_node] = curr
                    heapq.heappush(pq, (new_dist, next_node))
        
        # 경로를 찾지 못함 - 직선 거리 반환 (fallback)
        return (self.get_distance(start, end), [start, end])
    
    def clear(self):
        """그래프 초기화"""
        self.nodes.clear()
        self.obstacles.clear()
        self.port_info.clear()
        self.nodes.add(self.warehouse_xy)
        self.nodes.add(self.stocker_xy)


# ================================================================================
# 전역 그래프 인스턴스
# ================================================================================
path_graph = PathGraph()


# ================================================================================
# 외부 인터페이스 함수
# ================================================================================
def init_obstacle_map(machine_positions: Dict[str, List[Tuple[float, float]]]):
    """
    설비 위치 정보로 경로 그래프 초기화
    
    Args:
        machine_positions: {"A": [(14,3), (14,7)], "B": [(22,3)], ...}
    """
    global path_graph, _path_cache
    path_graph.clear()
    path_graph.add_machines_from_dict(machine_positions)
    
    # 캐시 초기화 (설비 배치가 변경되면 캐시 무효화)
    _path_cache.clear()
    
    print(f"[Pathfinding] 경로 그래프 초기화 완료:")
    print(f"  - 노드 수: {len(path_graph.nodes)}개 (포트 + Warehouse + Stocker)")
    print(f"  - 금지 구역: {len(path_graph.obstacles)}개 (설비)")


def pathfinding_dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """
    다익스트라 알고리즘을 사용한 실제 이동 거리 계산 (캐싱 적용)
    
    Args:
        a: 시작 좌표
        b: 도착 좌표
    
    Returns:
        최단 경로 거리 (설비 우회)
    
    Note:
        ENABLE_PATH_CACHE=True일 때 동일 쿼리 결과 재사용 (성능 향상)
    """
    # 캐시 키 생성
    cache_key = (a, b)
    
    if ENABLE_PATH_CACHE and cache_key in _path_cache:
        return _path_cache[cache_key][0]
    
    distance, path = path_graph.dijkstra(a, b)
    
    if ENABLE_PATH_CACHE:
        _path_cache[cache_key] = (distance, path)
    
    return distance


def get_path(a: Tuple[float, float], b: Tuple[float, float]) -> List[Tuple[float, float]]:
    """
    두 점 사이의 최단 경로 반환 (캐싱 적용)
    
    Args:
        a: 시작 좌표
        b: 도착 좌표
    
    Returns:
        경로 좌표 리스트
    """
    # 캐시 확인
    cache_key = (a, b)
    if ENABLE_PATH_CACHE and cache_key in _path_cache:
        return _path_cache[cache_key][1]
    
    distance, path = path_graph.dijkstra(a, b)
    
    if ENABLE_PATH_CACHE:
        _path_cache[cache_key] = (distance, path)
    
    return path


def euclidean_dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """
    유클리드 거리 계산 (비교용)
    """
    return math.hypot(a[0] - b[0], a[1] - b[1])


# ================================================================================
# 하위 호환성을 위한 래퍼
# ================================================================================
class ObstacleMap:
    """하위 호환성을 위한 래퍼 클래스"""
    @property
    def obstacles(self):
        return path_graph.obstacles
    
    @property
    def machine_positions(self):
        return [obs.center for obs in path_graph.obstacles]

obstacle_map = ObstacleMap()


# ================================================================================
# 테스트
# ================================================================================
if __name__ == "__main__":
    # 테스트 설비 배치
    test_positions = {
        "A": [(14, 3), (14, 7), (14, 13), (14, 17)],
        "B": [(22, 3), (22, 7), (22, 13), (22, 17)],
        "C": [(30, 3), (30, 7), (30, 13), (30, 17)],
        "D": [(38, 3), (38, 7), (38, 13), (38, 17)],
        "E": [(46, 3), (46, 7), (46, 13), (46, 17)],
    }
    
    init_obstacle_map(test_positions)
    
    print(f"\n등록된 노드들:")
    for node in sorted(path_graph.nodes):
        info = path_graph.port_info.get(node, ("", ""))
        if info[0]:
            print(f"  {node} - {info[0]} {info[1]}")
        else:
            if node == WAREHOUSE_XY:
                print(f"  {node} - Warehouse")
            elif node == STOCKER_XY:
                print(f"  {node} - Stocker")
    
    # 경로 테스트
    print("\n=== 경로 테스트 ===")
    
    # 테스트 1: Warehouse → A설비 입력포트
    start = WAREHOUSE_XY  # (4, 10)
    end = (12, 3)  # A-1 입력포트
    eucl = euclidean_dist(start, end)
    dist, path = path_graph.dijkstra(start, end)
    print(f"\n1. Warehouse {start} → A-1 입력포트 {end}")
    print(f"   유클리드: {eucl:.2f}m")
    print(f"   다익스트라: {dist:.2f}m")
    print(f"   경로: {path}")
    
    # 테스트 2: A설비 출력포트 → B설비 입력포트
    start = (16, 3)  # A-1 출력포트
    end = (20, 3)    # B-1 입력포트
    eucl = euclidean_dist(start, end)
    dist, path = path_graph.dijkstra(start, end)
    print(f"\n2. A-1 출력포트 {start} → B-1 입력포트 {end}")
    print(f"   유클리드: {eucl:.2f}m")
    print(f"   다익스트라: {dist:.2f}m")
    print(f"   경로: {path}")
    
    # 테스트 3: E설비 출력포트 → Stocker
    start = (48, 3)  # E-1 출력포트
    end = STOCKER_XY  # (56, 10)
    eucl = euclidean_dist(start, end)
    dist, path = path_graph.dijkstra(start, end)
    print(f"\n3. E-1 출력포트 {start} → Stocker {end}")
    print(f"   유클리드: {eucl:.2f}m")
    print(f"   다익스트라: {dist:.2f}m")
    print(f"   경로: {path}")
