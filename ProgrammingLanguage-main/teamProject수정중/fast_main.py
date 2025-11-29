"""
반도체 공정 시뮬레이션 - 빠른 실행 버전
애니메이션 OFF, 결과만 빠르게 출력

최적 설비 배분 (B-1, E+1):
- A: 5대, B: 8대, C: 6대, D: 5대, E: 6대
- 예상 결과: 2,118쌍, Profit: 89,347,660원
"""

import time
import sim_core
from kpi import information, profit

def fast_run():
    """빠른 시뮬레이션 실행 - 결과만 출력"""
    
    # 최적화된 설비 배치 (B-1, E+1)
    machine_positions = {
        "A": [(14, 3), (14, 5), (14, 7), (14, 13), (14, 15)],   # 5대
        "B": [(22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17), (30, 3), (30, 5)],   # 8대
        "C": [(30, 7), (30, 13), (30, 15), (30, 17), (38, 3), (38, 5)],   # 6대
        "D": [(38, 7), (38, 13), (38, 15), (38, 17), (46, 3)],   # 5대
        "E": [(46, 5), (46, 7), (46, 13), (46, 15), (46, 17), (14, 17)],   # 6대
    }
    
    machine_counts = {"A": 5, "B": 8, "C": 6, "D": 5, "E": 6}  # 총 30대
    amr_count = 3  # 최적 AMR 수
    
    print("=" * 60)
    print("반도체 공정 시뮬레이션 - 빠른 실행")
    print("=" * 60)
    print(f"설비 배분: A:{machine_counts['A']}, B:{machine_counts['B']}, C:{machine_counts['C']}, D:{machine_counts['D']}, E:{machine_counts['E']}")
    print(f"AMR: {amr_count}대")
    print(f"시뮬레이션 시간: 1,296,000초 (15일)")
    print("-" * 60)
    print("시뮬레이션 실행 중...")
    
    # 시뮬레이션 실행
    start_time = time.time()
    
    cfg = sim_core.FactoryConfig(
        sim_time=1296000,                        # 15일 = 1,296,000초
        seed=20,                                  # 랜덤 시드
        feed_sequence=("ProdA", "ProdB"),        # A, B 교대 투입
        amr_count=amr_count,
        machine_counts=machine_counts,
        machine_positions=machine_positions
    )
    
    sim_core.simulate(cfg)
    
    elapsed = time.time() - start_time
    
    # 결과 출력
    print("\n" + "=" * 60)
    print("시뮬레이션 결과")
    print("=" * 60)
    
    information()  # 생산 요약
    profit(amr_count=amr_count, machine_counts=machine_counts)  # Profit 계산
    
    print("-" * 60)
    print(f"실행 시간: {elapsed:.2f}초")
    print("=" * 60)

if __name__ == "__main__":
    fast_run()
