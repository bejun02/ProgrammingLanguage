"""
간단한 기여도 테스트 - 설비 배분만 테스트
"""
import sys
import time
import io
from contextlib import redirect_stdout

SIM_TIME = 1296000

# 설비 위치 (30개)
ALL_POS = [
    (14, 3), (14, 5), (14, 7), (14, 13), (14, 15), (14, 17),
    (22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17),
    (30, 3), (30, 5), (30, 7), (30, 13), (30, 15), (30, 17),
    (38, 3), (38, 5), (38, 7), (38, 13), (38, 15), (38, 17),
    (46, 3), (46, 5), (46, 7), (46, 13), (46, 15), (46, 17),
]

def test_config(name, counts, use_pathfinding=True, use_heuristic=True):
    """설정으로 테스트"""
    print(f"\n테스트: {name}")
    print(f"  설비: A:{counts['A']}, B:{counts['B']}, C:{counts['C']}, D:{counts['D']}, E:{counts['E']}")
    print(f"  Pathfinding: {use_pathfinding}, Heuristic: {use_heuristic}")
    
    # 모듈 캐시 삭제
    for m in list(sys.modules.keys()):
        if any(m.startswith(x) for x in ['sim_core', 'config', 'heuristic', 
                                          'pathfinding', 'data_structures', 'kpi', 'logger']):
            del sys.modules[m]
    
    # 설비 위치 생성
    idx = 0
    positions = {}
    for stage in ["A", "B", "C", "D", "E"]:
        positions[stage] = ALL_POS[idx:idx+counts[stage]]
        idx += counts[stage]
    
    # 출력 억제하고 실행
    start = time.perf_counter()
    
    f = io.StringIO()
    with redirect_stdout(f):
        import sim_core
        import config
        
        sim_core.USE_PATHFINDING = use_pathfinding
        sim_core.USE_HEURISTIC = use_heuristic
        config.VERBOSE = False
        
        cfg = sim_core.FactoryConfig(
            sim_time=SIM_TIME,
            seed=20,
            feed_sequence=("ProdA", "ProdB"),
            amr_count=3,
            machine_counts=counts,
            machine_positions=positions
        )
        
        sim_core.simulate(cfg)
        
        from config import global_variable
        stk = global_variable.STOCKERS.get("STK-01")
        prod_a = len(stk.stored_jobs_A) if stk else 0
        prod_b = len(stk.stored_jobs_B) if stk else 0
        pairs = min(prod_a, prod_b)
        total_out = global_variable.FEED_COUNT
    
    elapsed = time.perf_counter() - start
    
    # Profit 계산
    cost = (counts["A"]*4 + counts["B"]*9 + counts["C"]*8 + counts["D"]*8 + counts["E"]*5.5 + 3*0.011)
    profit = (100*pairs - 5*total_out) / cost * 100000
    
    print(f"  결과: {pairs}쌍, Profit: {profit:,.0f}원 ({elapsed:.1f}초)")
    return {"pairs": pairs, "profit": profit, "name": name}


if __name__ == "__main__":
    print("=" * 60)
    print("개선점별 Profit 기여도 분석")
    print("=" * 60)
    
    optimal = {"A": 5, "B": 8, "C": 6, "D": 5, "E": 6}
    baseline = {"A": 5, "B": 9, "C": 6, "D": 5, "E": 5}
    
    results = []
    
    # 1. 전체 적용
    r1 = test_config("전체 적용 (기준)", optimal, True, True)
    results.append(r1)
    
    # 2. 다익스트라 OFF
    r2 = test_config("과업1 OFF (다익스트라)", optimal, False, True)
    results.append(r2)
    
    # 3. 휴리스틱 OFF  
    r3 = test_config("과업2 OFF (휴리스틱)", optimal, True, False)
    results.append(r3)
    
    # 4. 설비배분 OFF
    r4 = test_config("과업4 OFF (설비배분)", baseline, True, True)
    results.append(r4)
    
    # 5. 전체 OFF
    r5 = test_config("전체 OFF", baseline, False, False)
    results.append(r5)
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("기여도 분석 결과")
    print("=" * 60)
    
    base = r1["profit"]
    
    contrib = {
        "과업1_다익스트라": base - r2["profit"],
        "과업2_휴리스틱": base - r3["profit"],
        "과업4_설비배분": base - r4["profit"],
    }
    
    total_imp = base - r5["profit"]
    contrib["과업3_Pull방식"] = total_imp - sum(contrib.values())
    
    print(f"\n기준 Profit: {base:,.0f}원")
    print(f"최저 Profit: {r5['profit']:,.0f}원")
    print(f"총 개선액:   {total_imp:,.0f}원")
    
    print("\n개선점별 기여도:")
    print("-" * 50)
    
    for name, val in sorted(contrib.items(), key=lambda x: -x[1]):
        pct = val / total_imp * 100 if total_imp > 0 else 0
        print(f"  {name:20s}: {val:+10,.0f}원 ({pct:5.1f}%)")
    
    print("\n★ 가장 큰 기여:", max(contrib.items(), key=lambda x: x[1])[0])
