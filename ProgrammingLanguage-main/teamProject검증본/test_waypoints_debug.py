"""
waypoints 디버깅 테스트
"""

import sim_core
from sim_core import *
from kpi import information, profit
from config import global_variable
from visualization import animate_from_amr_runs

if __name__ == "__main__":
    # 설비 위치 좌표
    machine_positions = {
        "A": [(14, 3), (14, 5), (14, 7), (14, 13), (14, 15)],
        "B": [(22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17), (30, 3), (30, 5)],
        "C": [(30, 7), (30, 13), (30, 15), (30, 17), (38, 3), (38, 5)],
        "D": [(38, 7), (38, 13), (38, 15), (38, 17), (46, 3)],
        "E": [(46, 5), (46, 7), (46, 13), (46, 15), (46, 17)],
    }
    
    machine_counts = {"A": 5, "B": 8, "C": 6, "D": 5, "E": 5}
    amr_count = 4
    
    # 짧은 시뮬레이션
    cfg = sim_core.FactoryConfig(
        sim_time=5000,  # 짧게
        seed=20,
        feed_sequence=("ProdA", "ProdB"),
        amr_count=amr_count,
        machine_counts=machine_counts,
        machine_positions=machine_positions
    )
    
    print("=" * 70)
    print("🔍 Waypoints 디버깅 테스트")
    print("=" * 70)
    
    sim_core.simulate(cfg)
    
    # waypoints 확인
    print("\n" + "=" * 70)
    print("📋 AMR Runs 데이터 확인:")
    print("=" * 70)
    
    for amr_name, runs in global_variable.amr_runs.items():
        print(f"\n{amr_name}: {len(runs)}개 이동")
        for i, run in enumerate(runs[:3]):  # 처음 3개만
            print(f"  Run {i+1}: {len(run)}개 요소")
            if len(run) == 7:
                s, e, job, frm, to, loaded, waypoints = run
                print(f"    시작: {frm}, 끝: {to}, loaded: {loaded}")
                if waypoints:
                    print(f"    ✓ Waypoints: {len(waypoints)}개 지점")
                    print(f"      경로: {waypoints[:3]}... → {waypoints[-1]}")
                else:
                    print(f"    ✗ Waypoints 없음!")
            else:
                print(f"    ✗ 구버전 포맷 (6-tuple)")
        if len(runs) > 3:
            print(f"  ... 외 {len(runs)-3}개")
    
    # 시각화
    print("\n" + "=" * 70)
    print("📊 시각화 시작...")
    print("=" * 70)
    
    animate_from_amr_runs(
        global_variable.amr_runs,
        interval_ms=100,
        frames=200,
        trail=True,
        machine_positions=machine_positions
    )
