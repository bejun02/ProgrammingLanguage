# 공정시간 검증
import sys
sys.path.insert(0, '.')

import config
config.VERBOSE = False

from data_structures import Job, FactoryConfig
from config import process_time_for, global_variable

# 설정 초기화
cfg = FactoryConfig()
global_variable.CURRENT_CFG = cfg

# 테스트 Job 생성
job_a = Job(job_id="ProdA-1", product="ProdA", max_cycles=2)
job_b = Job(job_id="ProdB-1", product="ProdB", max_cycles=2)

print("=== 공정 시간 검증 ===")
print()

# ProdA 테스트
print("ProdA:")
for cycle in [0, 1]:
    job_a.cycle_idx = cycle
    for stage in ['A', 'B', 'C', 'D', 'E']:
        pt = process_time_for(stage, job_a)
        print(f"  Cycle {cycle}, Stage {stage}: {pt}초 ({pt/60 if pt else 0}분)")

print()

# ProdB 테스트
print("ProdB:")
for cycle in [0, 1]:
    job_b.cycle_idx = cycle
    for stage in ['A', 'B', 'C', 'D', 'E']:
        pt = process_time_for(stage, job_b)
        print(f"  Cycle {cycle}, Stage {stage}: {pt}초 ({pt/60 if pt else 0}분)")

print()

# 총 공정시간 계산
total_a = 0
total_b = 0
for cycle in [0, 1]:
    job_a.cycle_idx = cycle
    job_b.cycle_idx = cycle
    for stage in ['A', 'B', 'C', 'D', 'E']:
        pt_a = process_time_for(stage, job_a)
        pt_b = process_time_for(stage, job_b)
        if pt_a: total_a += pt_a
        if pt_b: total_b += pt_b

print(f"ProdA 총 공정시간: {total_a}초 ({total_a/60}분)")
print(f"ProdB 총 공정시간: {total_b}초 ({total_b/60}분)")
