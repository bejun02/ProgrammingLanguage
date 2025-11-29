# 실제 공정 시간 확인
import sys
sys.path.insert(0, '.')

import config
config.VERBOSE = True  # 로그 켜기

import sim_core
from data_structures import FactoryConfig

# 짧은 시간 시뮬레이션
cfg = FactoryConfig(
    sim_time=10000,  # 약 2.8시간만 
    seed=42,
    feed_sequence=("ProdA", "ProdB"),
    amr_count=3,
    machine_counts={"A": 5, "B": 9, "C": 6, "D": 5, "E": 5},
    machine_positions={
        "A": [(14,3), (14,5), (14,7), (14,13), (14,15)],
        "B": [(22,3), (22,5), (22,7), (22,13), (22,15), (22,17), (30,3), (30,5), (30,7)],
        "C": [(30,13), (30,15), (30,17), (38,3), (38,5), (38,7)],
        "D": [(38,13), (38,15), (38,17), (46,3), (46,5)],
        "E": [(46,7), (46,13), (46,15), (46,17), (14,17)]
    }
)

print("=== 공정 시간이 올바르게 적용되는지 확인 ===")
print("ProdA 모든 공정: 15분(900초) 예상")
print("ProdB A: 5분(300초), B: 40분(2400초), C: 25분(1500초), D: 2분(120초), E: 5분(300초) 예상")
print()

sim_core.simulate(cfg)
