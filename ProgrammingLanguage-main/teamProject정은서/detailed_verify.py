# 세부 검증: 실제 완성 과정 추적
import sys
sys.path.insert(0, '.')

# VERBOSE 설정
import config
config.VERBOSE = False

from data_structures import FactoryConfig, Stocker
from config import global_variable

# 설정
sim_time = 1296000  # 15일
machine_counts = {"A": 5, "B": 9, "C": 6, "D": 5, "E": 5}

# 스토커 직접 확인을 위한 래퍼
original_store = Stocker.store

completed_jobs = []

def tracking_store(self, job_id):
    """완성품 추적"""
    completed_jobs.append(job_id)
    return original_store(self, job_id)

Stocker.store = tracking_store

# 시뮬레이션 실행
import sim_core

print("=== 시뮬레이션 시작 ===")
print(f"설정: {machine_counts}, AMR 3대, 15일")
print()

cfg = FactoryConfig(
    sim_time=sim_time,
    seed=42,
    feed_sequence=("ProdA", "ProdB"),
    amr_count=3,
    machine_counts=machine_counts,
    machine_positions={
        "A": [(14,3), (14,5), (14,7), (14,13), (14,15)],
        "B": [(22,3), (22,5), (22,7), (22,13), (22,15), (22,17), (30,3), (30,5), (30,7)],
        "C": [(30,13), (30,15), (30,17), (38,3), (38,5), (38,7)],
        "D": [(38,13), (38,15), (38,17), (46,3), (46,5)],
        "E": [(46,7), (46,13), (46,15), (46,17), (14,17)]
    }
)

sim_core.simulate(cfg)

print("\n=== 결과 분석 ===")
stk = global_variable.STOCKERS["STK-01"]
completed_A = len(stk.list_jobs_A())
completed_B = len(stk.list_jobs_B())
total_feed = global_variable.FEED_COUNT
pairs = min(completed_A, completed_B)

print(f"투입량: {total_feed} (A:{global_variable.FEED_COUNT_A}, B:{global_variable.FEED_COUNT_B})")
print(f"완성품 A: {completed_A}")
print(f"완성품 B: {completed_B}")
print(f"완성 페어: {pairs}")
print()

# 이론적 최대와 비교
theoretical_max = 2160  # C, E 병목
ratio = pairs / theoretical_max * 100
print(f"이론적 최대: {theoretical_max}")
print(f"달성률: {ratio:.1f}%")

if pairs > theoretical_max:
    print(f"\n⚠️ 경고: 결과 {pairs}가 이론적 최대 {theoretical_max}를 초과!")
    print("   시뮬레이션에 버그가 있습니다!")
else:
    print(f"\n✓ 결과가 이론적 범위 내에 있습니다.")

# 처음 10개 완성품 확인
print("\n=== 처음 10개 완성품 ===")
for i, job_id in enumerate(completed_jobs[:10]):
    print(f"  {i+1}. {job_id}")

# 마지막 10개 완성품 확인  
print("\n=== 마지막 10개 완성품 ===")
for i, job_id in enumerate(completed_jobs[-10:]):
    idx = len(completed_jobs) - 10 + i + 1
    print(f"  {idx}. {job_id}")
