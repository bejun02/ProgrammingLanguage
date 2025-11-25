"""

================================================================================
kpi.py - KPI(핵심성과지표) 계산 모듈
================================================================================
이 파일은 시뮬레이션 결과를 평가하는 KPI 함수들을 제공합니다.

주요 함수:
- information(): 생산 요약 정보 출력
- profit(): 수익률(Profit) 계산

Profit 계산식 (과제 조건):
    Profit = [100×min(A완성품, B완성품) - 5×총출고수] / [설비비용 + AMR비용] × 100000

설비 비용 테이블:
    - A공정(산화): 4억원
    - B공정(노광): 9억원  
    - C공정(식각): 8억원
    - D공정(증착): 8억원
    - E공정(계측): 5.5억원
    - AMR: 0.011억원(1100만원)
================================================================================
"""

from config import global_variable
from typing import Dict


def information():
    """
    생산 요약 정보 출력
    
    출력 내용:
        - 총 출고 제품 수 (FEED_COUNT)
        - ProdA 출고 수 (FEED_COUNT_A)
        - ProdB 출고 수 (FEED_COUNT_B)
        - Stocker에 보관 중인 ProdA 완성품 수
        - Stocker에 보관 중인 ProdB 완성품 수
    
    Note:
        - 출고 수 ≠ 완성품 수 (공정 중인 제품이 있음)
        - 완성품만 Profit 계산에 포함됨
    """
    print("=== 생산 요약 ===")
    print(f"Stocker K | Out제품 수: {global_variable.FEED_COUNT}")
    print(f"  - ProdA: {global_variable.FEED_COUNT_A}")
    print(f"  - ProdB: {global_variable.FEED_COUNT_B}")
    print("A 총 보관 수:", len(global_variable.STOCKERS["STK-01"].list_jobs_A()))
    print("B 총 보관 수:", len(global_variable.STOCKERS["STK-01"].list_jobs_B()))


def profit(amr_count: int, machine_counts: Dict[str, int]):
    """
    수익률(Profit) 계산 및 출력
    
    Args:
        amr_count (int): 사용한 AMR 대수
        machine_counts (Dict[str, int]): 스테이지별 설비 대수
                                          예: {"A": 4, "B": 4, "C": 4, "D": 4, "E": 4}
    
    Profit 계산 공식:
        매출 = 100 × min(A완성품, B완성품)
        비용(원자재) = 5 × 총출고수
        설비비용 = Σ(설비대수 × 단가)
        AMR비용 = 0.011 × AMR대수
        
        Profit = (매출 - 원자재비용) / (설비비용 + AMR비용) × 100000
    
    설비 단가 (억원):
        - A(산화): 4
        - B(노광): 9 (가장 비쌈)
        - C(식각): 8
        - D(증착): 8
        - E(계측): 5.5
    """
    # 설비별 비용 리스트: [A=4, B=9, C=8, D=8, E=5.5]
    parameter = [4, 9, 8, 8, 5.5]
    
    # 설비 비용 계산
    t = 0
    s = 0
    for i in machine_counts.values():
        t += i * parameter[s]
        s += 1
    
    # Profit 계산: (매출 - 원자재비용) / (설비비용 + AMR비용)
    p = (100 * min(len(global_variable.STOCKERS["STK-01"].list_jobs_A()), len(global_variable.STOCKERS["STK-01"].list_jobs_B())) - 5 * (global_variable.FEED_COUNT_A + global_variable.FEED_COUNT_B))
    profit = p / (t + 0.011 * amr_count)
    
    print("profit: ", round(profit, 2) * 100000, "원")