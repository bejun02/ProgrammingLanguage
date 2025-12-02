"""
공정 플래닝 / 생산계획 최적화 코드
- 설비 종류: A, B, C, D, E
- 제품: ProductA, ProductB (pair로 완제품 1개)
- 브루트포스 탐색으로 최적 설비 조합 탐색
"""

import math
from itertools import product

# =============================================================================
# 파라미터 정의 (수정 용이하도록 상단에 모아서 정의)
# =============================================================================

# 하루 작업시간 (분)
H = 480

# 설비 설치 가능 위치 최대 개수
MAX_POSITIONS = 30

# 설비별 비용 (대당)
TOOL_COST = {
    'A': 4,
    'B': 9,
    'C': 8,
    'D': 8,
    'E': 5.5
}

# 설비별 pair당 부하 (분)
# ProductA: 각 설비당 30분 (15분 × 2회)
# ProductB: A=15, B=50, C=30, D=12, E=20
# pair 1개당 총 부하 = ProductA + ProductB
LOAD_PER_PAIR = {
    'A': 30 + 15,   # 45분
    'B': 30 + 50,   # 80분
    'C': 30 + 30,   # 60분
    'D': 30 + 12,   # 42분
    'E': 30 + 20    # 50분
}

# 설비 목록 (순서 고정)
EQUIPMENT_LIST = ['A', 'B', 'C', 'D', 'E']

# 상위 몇 개 결과를 출력할지
TOP_K = 5


# =============================================================================
# AMR 비용 함수 (향후 수정 가능하도록 별도 함수로 분리)
# =============================================================================

def amr_cost(x_A, x_B, x_C, x_D, x_E):
    """
    AMR 비용을 계산하는 함수.
    현재는 0으로 설정되어 있으며, 향후 필요시 이 함수 내부만 수정하면 됨.
    
    예시 (향후 적용 가능):
        return 0.5 * (x_A + x_B + x_C + x_D + x_E)
        또는 더 복잡한 수식 적용 가능
    """
    return 0


# =============================================================================
# 용량 계산 함수
# =============================================================================

def compute_capacity(equipment_counts, H=H, load_per_pair=LOAD_PER_PAIR):
    """
    각 설비별 하루 처리 가능한 pair 수(용량)를 계산한다.
    
    Args:
        equipment_counts: dict, 설비별 대수 {'A': x_A, 'B': x_B, ...}
        H: int, 하루 작업시간 (분)
        load_per_pair: dict, 설비별 pair당 부하 (분)
    
    Returns:
        dict: 설비별 용량 {'A': cap_A, 'B': cap_B, ...}
    """
    capacities = {}
    for equip in EQUIPMENT_LIST:
        x = equipment_counts[equip]
        load = load_per_pair[equip]
        # cap_k = x_k * H / load_k
        capacities[equip] = x * H / load
    return capacities


def compute_production(equipment_counts, H=H, load_per_pair=LOAD_PER_PAIR):
    """
    주어진 설비 조합에서 하루 생산 가능한 pair 수 N을 계산한다.
    N = floor(min(cap_A, cap_B, cap_C, cap_D, cap_E))
    
    Args:
        equipment_counts: dict, 설비별 대수
        H: int, 하루 작업시간 (분)
        load_per_pair: dict, 설비별 pair당 부하 (분)
    
    Returns:
        int: 생산 가능한 pair 수 N
        str: 병목 설비 (가장 낮은 용량을 가진 설비)
    """
    capacities = compute_capacity(equipment_counts, H, load_per_pair)
    
    # 병목 설비 찾기
    bottleneck = min(capacities, key=capacities.get)
    min_capacity = capacities[bottleneck]
    
    # N = floor(min(cap_k))
    N = math.floor(min_capacity)
    
    return N, bottleneck, capacities


# =============================================================================
# 비용 및 Profit 계산 함수
# =============================================================================

def compute_tool_cost(equipment_counts, tool_cost=TOOL_COST):
    """
    설비 비용을 계산한다.
    tool_cost = 4*x_A + 9*x_B + 8*x_C + 8*x_D + 5.5*x_E
    
    Args:
        equipment_counts: dict, 설비별 대수
        tool_cost: dict, 설비별 단가
    
    Returns:
        float: 총 설비 비용
    """
    total = 0
    for equip in EQUIPMENT_LIST:
        total += tool_cost[equip] * equipment_counts[equip]
    return total


def compute_profit(equipment_counts, H=H, load_per_pair=LOAD_PER_PAIR, tool_cost=TOOL_COST):
    """
    주어진 설비 조합에서의 Profit을 계산한다.
    
    Profit = [100 × N - 5 × (2N)] / [tool_cost + amr_cost] × 10000
           = [90 × N] / [tool_cost + amr_cost] × 10000
    
    Args:
        equipment_counts: dict, 설비별 대수
        H: int, 하루 작업시간 (분)
        load_per_pair: dict, 설비별 pair당 부하 (분)
        tool_cost: dict, 설비별 단가
    
    Returns:
        float: Profit 값 (생산 불가시 -inf)
        int: 생산 pair 수 N
        str: 병목 설비
        dict: 설비별 용량
    """
    # 생산량 계산
    N, bottleneck, capacities = compute_production(equipment_counts, H, load_per_pair)
    
    # N <= 0이면 생산 불가
    if N <= 0:
        return float('-inf'), N, bottleneck, capacities
    
    # 설비 비용 계산
    total_tool_cost = compute_tool_cost(equipment_counts, tool_cost)
    
    # AMR 비용 계산
    total_amr_cost = amr_cost(
        equipment_counts['A'],
        equipment_counts['B'],
        equipment_counts['C'],
        equipment_counts['D'],
        equipment_counts['E']
    )
    
    # 분모가 0이 되지 않도록 방어
    denominator = total_tool_cost + total_amr_cost
    if denominator <= 0:
        return float('-inf'), N, bottleneck, capacities
    
    # Profit 계산
    # 완제품 수 = N, 총출고수 = 2N
    # Profit = [100*N - 5*(2N)] / (tool_cost + amr_cost) * 10000
    #        = [90*N] / (tool_cost + amr_cost) * 10000
    revenue = 100 * N
    shipping_cost = 5 * (2 * N)
    profit = (revenue - shipping_cost) / denominator * 10000
    
    return profit, N, bottleneck, capacities


# =============================================================================
# 브루트포스 탐색 함수
# =============================================================================

def brute_force_search(H=H, max_positions=MAX_POSITIONS, load_per_pair=LOAD_PER_PAIR, 
                       tool_cost=TOOL_COST, top_k=TOP_K):
    """
    브루트포스 방식으로 모든 가능한 설비 조합을 탐색하여 최적해를 찾는다.
    
    제약조건:
        - 각 설비 대수: 1 이상, max_positions 이하
        - 총 설비 대수: x_A + x_B + x_C + x_D + x_E <= max_positions
    
    Args:
        H: int, 하루 작업시간 (분)
        max_positions: int, 설비 설치 가능 위치 최대 개수
        load_per_pair: dict, 설비별 pair당 부하 (분)
        tool_cost: dict, 설비별 단가
        top_k: int, 상위 몇 개 결과를 반환할지
    
    Returns:
        list: 상위 top_k개의 결과 [(profit, equipment_counts, N, bottleneck, capacities), ...]
    """
    results = []
    
    # 각 설비는 최소 1대 이상 필요하므로, 최소 5대 필요
    # x_A + x_B + x_C + x_D + x_E <= max_positions
    # 각 설비의 최대값은 max_positions - 4 (다른 4개가 각각 1대씩)
    max_per_equip = max_positions - 4
    
    # 브루트포스 탐색
    for x_A in range(1, max_per_equip + 1):
        for x_B in range(1, max_per_equip + 1):
            if x_A + x_B > max_positions - 3:
                break
            for x_C in range(1, max_per_equip + 1):
                if x_A + x_B + x_C > max_positions - 2:
                    break
                for x_D in range(1, max_per_equip + 1):
                    if x_A + x_B + x_C + x_D > max_positions - 1:
                        break
                    # x_E의 최대값 계산
                    remaining = max_positions - (x_A + x_B + x_C + x_D)
                    for x_E in range(1, remaining + 1):
                        # 설비 조합 생성
                        equipment_counts = {
                            'A': x_A,
                            'B': x_B,
                            'C': x_C,
                            'D': x_D,
                            'E': x_E
                        }
                        
                        # Profit 계산
                        profit, N, bottleneck, capacities = compute_profit(
                            equipment_counts, H, load_per_pair, tool_cost
                        )
                        
                        # N > 0인 경우만 유효한 결과로 저장
                        if N > 0:
                            results.append((profit, equipment_counts.copy(), N, bottleneck, capacities.copy()))
    
    # Profit 기준 내림차순 정렬
    results.sort(key=lambda x: x[0], reverse=True)
    
    # 상위 top_k개 반환
    return results[:top_k]


# =============================================================================
# 결과 출력 함수
# =============================================================================

def print_result(rank, result):
    """
    단일 결과를 보기 좋게 출력한다.
    
    Args:
        rank: int, 순위
        result: tuple, (profit, equipment_counts, N, bottleneck, capacities)
    """
    profit, equipment_counts, N, bottleneck, capacities = result
    
    total_equipment = sum(equipment_counts.values())
    total_tool_cost = compute_tool_cost(equipment_counts)
    total_amr = amr_cost(
        equipment_counts['A'],
        equipment_counts['B'],
        equipment_counts['C'],
        equipment_counts['D'],
        equipment_counts['E']
    )
    
    print(f"\n{'='*60}")
    print(f"  순위 {rank}")
    print(f"{'='*60}")
    print(f"  Profit: {profit:,.2f}")
    print(f"  하루 생산 pair 수 (N): {N}")
    print(f"  완제품 수: {N}")
    print(f"  총 출고 수 (ProductA + ProductB): {2*N}")
    print(f"{'─'*60}")
    print(f"  설비 배치:")
    for equip in EQUIPMENT_LIST:
        print(f"    - 설비 {equip}: {equipment_counts[equip]}대 "
              f"(용량: {capacities[equip]:.2f} pairs/day)")
    print(f"  총 설비 대수: {total_equipment}대")
    print(f"  병목 설비: {bottleneck}")
    print(f"{'─'*60}")
    print(f"  비용 정보:")
    print(f"    - 설비 비용: {total_tool_cost:.2f}")
    print(f"    - AMR 비용: {total_amr:.2f}")
    print(f"    - 총 비용: {total_tool_cost + total_amr:.2f}")


def print_summary(results):
    """
    전체 결과 요약을 출력한다.
    
    Args:
        results: list, 상위 결과 리스트
    """
    print("\n" + "="*60)
    print("  공정 플래닝 최적화 결과 요약")
    print("="*60)
    print(f"  하루 작업시간: {H}분")
    print(f"  설비 설치 가능 위치: 최대 {MAX_POSITIONS}개")
    print(f"  설비별 pair당 부하 (분): {LOAD_PER_PAIR}")
    print(f"  설비별 비용: {TOOL_COST}")
    print("="*60)
    
    for i, result in enumerate(results, 1):
        print_result(i, result)
    
    print("\n" + "="*60)
    print("  탐색 완료")
    print("="*60)


# =============================================================================
# 메인 실행
# =============================================================================

def main():
    """
    메인 함수: 브루트포스 탐색 실행 및 결과 출력
    """
    print("\n공정 플래닝 최적화 시작...")
    print(f"탐색 조건: 각 설비 1대 이상, 총 {MAX_POSITIONS}대 이하")
    
    # 브루트포스 탐색 실행
    results = brute_force_search(
        H=H,
        max_positions=MAX_POSITIONS,
        load_per_pair=LOAD_PER_PAIR,
        tool_cost=TOOL_COST,
        top_k=TOP_K
    )
    
    if not results:
        print("유효한 설비 조합을 찾지 못했습니다.")
        return
    
    # 결과 출력
    print_summary(results)
    
    # 최적해 반환 (다른 모듈에서 사용 가능)
    return results


if __name__ == "__main__":
    main()
