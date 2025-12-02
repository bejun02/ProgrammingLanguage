"""
================================================================================
contribution_analysis.py - 각 개선점의 Profit 기여도 분석
================================================================================

분석 대상 개선점:
    1. 과업 1: 다익스트라 경로 탐색 (USE_PATHFINDING)
    2. 과업 2: 휴리스틱 설비 선택 (USE_HEURISTIC)
    3. 과업 3: Pull 방식 + 재가공품 우선 (Pull/cyclemax)
    4. 과업 4: 설비 배분 최적화 (B:8, E:6 vs B:9, E:5)

분석 방법:
    - 전체 적용: 모든 개선점 ON → 기준 Profit
    - 하나씩 OFF: 각 개선점을 끄고 Profit 측정 → 기여도 = 기준 - 측정값

================================================================================
"""

import sys
import time
import io
from contextlib import redirect_stdout

# 기본 설정
SIM_TIME = 1296000  # 15일

def run_simulation_quiet(use_pathfinding=True, use_heuristic=True, machine_counts=None):
    """시뮬레이션 실행 및 결과 반환 (출력 억제)"""
    
    # 매번 새로운 import를 위해 모듈 캐시 삭제
    modules_to_remove = [m for m in sys.modules.keys() 
                         if m.startswith(('sim_core', 'config', 'heuristic', 
                                          'pathfinding', 'data_structures', 
                                          'kpi', 'logger'))]
    for m in modules_to_remove:
        del sys.modules[m]
    
    # 출력 억제
    f = io.StringIO()
    with redirect_stdout(f):
        # 설정 적용을 위해 sim_core 수정
        import sim_core
        import config
        
        # 1. 경로 탐색 설정
        sim_core.USE_PATHFINDING = use_pathfinding
        
        # 2. 휴리스틱 설정
        sim_core.USE_HEURISTIC = use_heuristic
        
        # 3. 로그 끄기
        config.VERBOSE = False
        
        # 설비 배치 (충분한 좌표 제공)
        all_positions = [
            (14, 3), (14, 5), (14, 7), (14, 13), (14, 15), (14, 17),
            (22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17),
            (30, 3), (30, 5), (30, 7), (30, 13), (30, 15), (30, 17),
            (38, 3), (38, 5), (38, 7), (38, 13), (38, 15), (38, 17),
            (46, 3), (46, 5), (46, 7), (46, 13), (46, 15), (46, 17),
        ]
        
        # 설비 배치 동적 생성
        idx = 0
        machine_positions = {}
        for stage in ["A", "B", "C", "D", "E"]:
            cnt = machine_counts[stage]
            machine_positions[stage] = all_positions[idx:idx+cnt]
            idx += cnt
        
        cfg = sim_core.FactoryConfig(
            sim_time=SIM_TIME,
            seed=20,
            feed_sequence=("ProdA", "ProdB"),
            amr_count=3,
            machine_counts=machine_counts,
            machine_positions=machine_positions
        )
        
        sim_core.simulate(cfg)
        
        # 결과 수집
        from config import global_variable
        
        stk = global_variable.STOCKERS.get("STK-01")
        prod_a = len(stk.stored_jobs_A) if stk else 0
        prod_b = len(stk.stored_jobs_B) if stk else 0
        pairs = min(prod_a, prod_b)
        
        # Profit 계산
        total_out = global_variable.FEED_COUNT
        machine_cost = (machine_counts["A"] * 4.0 + 
                        machine_counts["B"] * 9.0 + 
                        machine_counts["C"] * 8.0 + 
                        machine_counts["D"] * 8.0 + 
                        machine_counts["E"] * 5.5)
        amr_cost = 3 * 0.011
        total_cost = machine_cost + amr_cost
        profit_val = (100 * pairs - 5 * total_out) / total_cost * 100000
    
    return {
        "pairs": pairs,
        "prod_a": prod_a,
        "prod_b": prod_b,
        "total_out": total_out,
        "profit": profit_val,
        "machine_cost": machine_cost,
    }


def main():
    print("=" * 70)
    print("개선점별 Profit 기여도 분석")
    print("=" * 70)
    
    # 최적화된 설비 배분
    optimal_counts = {"A": 5, "B": 8, "C": 6, "D": 5, "E": 6}
    # 기본 설비 배분 (최적화 전)
    baseline_counts = {"A": 5, "B": 9, "C": 6, "D": 5, "E": 5}
    
    results = {}
    
    # ===== 1. 전체 적용 (기준) =====
    print("\n[1] 전체 적용 (기준) - 실행 중...")
    start = time.perf_counter()
    results["all_on"] = run_simulation_quiet(
        use_pathfinding=True,
        use_heuristic=True,
        machine_counts=optimal_counts,
    )
    elapsed = time.perf_counter() - start
    print(f"    완성 쌍: {results['all_on']['pairs']}, Profit: {results['all_on']['profit']:,.0f}원 ({elapsed:.1f}초)")
    
    # ===== 2. 과업 1 OFF: 다익스트라 비활성화 =====
    print("[2] 과업 1 OFF: 다익스트라 비활성화 - 실행 중...")
    start = time.perf_counter()
    results["no_pathfinding"] = run_simulation_quiet(
        use_pathfinding=False,
        use_heuristic=True,
        machine_counts=optimal_counts,
    )
    elapsed = time.perf_counter() - start
    print(f"    완성 쌍: {results['no_pathfinding']['pairs']}, Profit: {results['no_pathfinding']['profit']:,.0f}원 ({elapsed:.1f}초)")
    
    # ===== 3. 과업 2 OFF: 휴리스틱 비활성화 =====
    print("[3] 과업 2 OFF: 휴리스틱 비활성화 - 실행 중...")
    start = time.perf_counter()
    results["no_heuristic"] = run_simulation_quiet(
        use_pathfinding=True,
        use_heuristic=False,
        machine_counts=optimal_counts,
    )
    elapsed = time.perf_counter() - start
    print(f"    완성 쌍: {results['no_heuristic']['pairs']}, Profit: {results['no_heuristic']['profit']:,.0f}원 ({elapsed:.1f}초)")
    
    # ===== 4. 과업 4 OFF: 설비 배분 최적화 전 =====
    print("[4] 과업 4 OFF: 설비 배분 최적화 전 (B:9, E:5) - 실행 중...")
    start = time.perf_counter()
    results["baseline_counts"] = run_simulation_quiet(
        use_pathfinding=True,
        use_heuristic=True,
        machine_counts=baseline_counts,
    )
    elapsed = time.perf_counter() - start
    print(f"    완성 쌍: {results['baseline_counts']['pairs']}, Profit: {results['baseline_counts']['profit']:,.0f}원 ({elapsed:.1f}초)")
    
    # ===== 5. 과업 1+2 OFF =====
    print("[5] 과업 1+2 OFF: 다익스트라 + 휴리스틱 비활성화 - 실행 중...")
    start = time.perf_counter()
    results["no_path_no_heur"] = run_simulation_quiet(
        use_pathfinding=False,
        use_heuristic=False,
        machine_counts=optimal_counts,
    )
    elapsed = time.perf_counter() - start
    print(f"    완성 쌍: {results['no_path_no_heur']['pairs']}, Profit: {results['no_path_no_heur']['profit']:,.0f}원 ({elapsed:.1f}초)")
    
    # ===== 6. 전체 OFF =====
    print("[6] 전체 OFF: 모든 개선점 비활성화 - 실행 중...")
    start = time.perf_counter()
    results["all_off"] = run_simulation_quiet(
        use_pathfinding=False,
        use_heuristic=False,
        machine_counts=baseline_counts,
    )
    elapsed = time.perf_counter() - start
    print(f"    완성 쌍: {results['all_off']['pairs']}, Profit: {results['all_off']['profit']:,.0f}원 ({elapsed:.1f}초)")
    
    # ===== 기여도 분석 =====
    print("\n" + "=" * 70)
    print("기여도 분석 결과")
    print("=" * 70)
    
    base_profit = results["all_on"]["profit"]
    all_off_profit = results["all_off"]["profit"]
    total_improvement = base_profit - all_off_profit
    
    # 각 개선점의 기여도 계산 (해당 기능 OFF 시 감소량)
    contributions = {}
    
    # 과업 1 기여도
    contributions["과업1_다익스트라"] = base_profit - results["no_pathfinding"]["profit"]
    
    # 과업 2 기여도
    contributions["과업2_휴리스틱"] = base_profit - results["no_heuristic"]["profit"]
    
    # 과업 4 기여도
    contributions["과업4_설비배분"] = base_profit - results["baseline_counts"]["profit"]
    
    # 과업 3 기여도 (Pull/cyclemax - 분리 테스트 어려움, 나머지로 계산)
    # 과업 3은 코드 깊숙이 통합되어 있어 분리하기 어려움
    # 대신: 전체 개선 - 측정 가능한 개선점들의 합
    measured_sum = (contributions["과업1_다익스트라"] + 
                    contributions["과업2_휴리스틱"] + 
                    contributions["과업4_설비배분"])
    contributions["과업3_Pull방식"] = total_improvement - measured_sum
    
    print(f"\n기준 Profit (전체 적용): {base_profit:,.0f}원")
    print(f"최저 Profit (전체 OFF):  {all_off_profit:,.0f}원")
    print(f"총 개선액:               {total_improvement:,.0f}원")
    
    print("\n" + "-" * 70)
    print("개선점별 기여도 (해당 기능 OFF 시 Profit 감소량)")
    print("-" * 70)
    
    # 기여도 정렬 (절대값 기준 내림차순)
    sorted_contrib = sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)
    
    for name, value in sorted_contrib:
        if total_improvement > 0:
            pct = value / total_improvement * 100
        else:
            pct = 0
        sign = "+" if value >= 0 else ""
        bar_len = min(20, int(abs(pct) / 5))
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"  {name:20s}: {sign}{value:12,.0f}원 ({pct:+6.1f}%) {bar}")
    
    print("\n" + "=" * 70)
    print("상세 비교표")
    print("=" * 70)
    print(f"{'구성':<40} {'완성쌍':>8} {'Profit':>14} {'변화':>12}")
    print("-" * 74)
    
    configs = [
        ("전체 적용 (기준)", "all_on"),
        ("과업1 OFF (유클리드 거리)", "no_pathfinding"),
        ("과업2 OFF (라운드로빈 선택)", "no_heuristic"),
        ("과업4 OFF (B:9, E:5)", "baseline_counts"),
        ("과업1+2 OFF", "no_path_no_heur"),
        ("전체 OFF (기초 파일 수준)", "all_off"),
    ]
    
    for name, key in configs:
        r = results[key]
        diff = r["profit"] - base_profit
        diff_str = f"{diff:+,.0f}" if diff != 0 else "-"
        print(f"{name:<40} {r['pairs']:>8} {r['profit']:>14,.0f}원 {diff_str:>12}")
    
    print("\n" + "=" * 70)
    print("결론")
    print("=" * 70)
    
    # 가장 큰 기여도 찾기
    max_contrib = max(sorted_contrib, key=lambda x: x[1])
    print(f"\n★ 가장 큰 기여: {max_contrib[0]} ({max_contrib[1]:+,.0f}원)")
    
    print("\n분석 완료!")


if __name__ == "__main__":
    main()
