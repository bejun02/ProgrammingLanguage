"""
================================================================================
main.py - 시뮬레이션 실행 진입점
================================================================================
이 파일은 반도체 공장 시뮬레이션의 메인 실행 파일입니다.

실행 순서:
    1. 설비 위치 및 개수 설정 (최적화 대상)
    2. AMR 대수 설정 (최적화 대상)
    3. FactoryConfig 생성
    4. simulate() 실행
    5. 결과 출력 (information, profit)
    6. 시각화 (animate_from_amr_runs)

최적화 변수:
    - machine_positions: 30개 고정 좌표 중 선택
    - machine_counts: 스테이지별 설비 대수 (총 30대 제한)
    - amr_count: AMR 대수 (최대 30대)

과제 조건:
    - 시뮬레이션 시간: 15일 = 1,296,000초
    - 설비 위치: 30개 고정 좌표 (6열×5행 + Warehouse + Stocker)
    - 공정 순서: A(산화) → B(노광) → C(식각) → D(증착) → E(계측)
    - 사이클: 2회 반복 후 완성

실행 방법:
    python main.py
================================================================================
"""

import sim_core
from sim_core import *
from kpi import information, profit
from config import global_variable
from visualization import animate_from_amr_runs

# ================================================================================
# 공정 및 위치 설명
# ================================================================================
# A(산화)  - Oxidation: 웨이퍼 표면 산화막 형성
# B(노광)  - Photolithography: 회로 패턴 전사 (가장 비싼 장비)
# C(식각)  - Etching: 불필요한 부분 제거
# D(증착)  - Deposition: 박막 증착
# E(계측)  - Metrology: 품질 검사

# Stocker: STK-01 (완제품 보관소, 위치: 56,10)
# Warehouse: WH-01 (원자재 창고, 위치: 4,10)

# ================================================================================
# 메인 실행 블록
# ================================================================================
if __name__ == "__main__":
    
    # ===== 1. 설비 위치 좌표 설정 =====
    # 30개 고정 좌표 중에서 각 공정별로 선택
    # 좌표 형식: (x, y) - x는 공정 방향, y는 위아래
    # 과제에서 주어진 6열(A~E + 여유) × 5행 격자 중 선택
    machine_positions = {
        "A": [(14, 3), (14, 7), (14, 13), (14, 17)],   # A공정: x=14 열에 4대
        "B": [(22, 3), (22, 7), (22, 13), (22, 17)],   # B공정: x=22 열에 4대
        "C": [(30, 3), (30, 7), (30, 13), (30, 17)],   # C공정: x=30 열에 4대
        "D": [(38, 3), (38, 7), (38, 13), (38, 17)],   # D공정: x=38 열에 4대
        "E": [(46, 3), (46, 7), (46, 13), (46, 17)],   # E공정: x=46 열에 4대
    }
    
    # ===== 2. 설비 개수 설정 =====
    # 각 공정별 설비 대수 (총합 ≤ 30대 권장)
    # 병목 공정(B)에 더 많은 설비 배치 고려
    machine_counts = {
        "A": 4,  # 산화 설비 4대
        "B": 4,  # 노광 설비 4대 (가장 비싼 장비, 병목 가능)
        "C": 4,  # 식각 설비 4대
        "D": 4,  # 증착 설비 4대
        "E": 4,  # 계측 설비 4대
    }
    # 총 설비: 20대
    
    # ===== 3. AMR 대수 설정 =====
    # AMR이 많을수록 이송 대기시간 감소, 비용 증가
    amr_count = 3
    
    # ===== 4. FactoryConfig 생성 =====
    # sim_time: 시뮬레이션 시간 (초)
    #   - 15일 = 15 × 24 × 60 × 60 = 1,296,000초
    # seed: 랜덤 시드 (재현성 확보)
    # feed_sequence: 제품 투입 순서 (ProdA, ProdB 교대)
    cfg = sim_core.FactoryConfig(
        sim_time=1296000,                        # 15일 = 1,296,000초
        seed=20,                                  # 랜덤 시드
        feed_sequence=("ProdA", "ProdB"),        # A, B 교대 투입
        amr_count=amr_count,                      # AMR 대수
        machine_counts=machine_counts,            # 설비 개수
        machine_positions=machine_positions       # 설비 위치
    )
    
    # ===== 5. 시뮬레이션 실행 =====
    sim_core.simulate(cfg)
    
    # ===== 6. 결과 출력 =====
    information()  # 생산 요약
    profit(amr_count=amr_count, machine_counts=machine_counts)  # Profit 계산
    
    # ===== 7. 시각화 (선택) =====
    # AMR 이동 애니메이션 생성
    # interval_ms: 프레임 간격 (ms)
    # frames: 총 프레임 수
    # trail: 이동 경로 표시 여부
    animate_from_amr_runs(
        global_variable.amr_runs,
        interval_ms=100,
        frames=1000,
        trail=True,
        machine_positions=machine_positions
    )



