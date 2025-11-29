"""
단일 테스트 실행 스크립트 - 명령줄 인자로 설정 받음
사용법: python single_test.py <pathfinding> <heuristic> <A> <B> <C> <D> <E>
예: python single_test.py 1 1 5 8 6 5 6
"""
import sys
import io
from contextlib import redirect_stdout

SIM_TIME = 1296000

ALL_POS = [
    (14, 3), (14, 5), (14, 7), (14, 13), (14, 15), (14, 17),
    (22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17),
    (30, 3), (30, 5), (30, 7), (30, 13), (30, 15), (30, 17),
    (38, 3), (38, 5), (38, 7), (38, 13), (38, 15), (38, 17),
    (46, 3), (46, 5), (46, 7), (46, 13), (46, 15), (46, 17),
]

def main():
    if len(sys.argv) < 8:
        print("사용법: python single_test.py <pathfinding> <heuristic> <A> <B> <C> <D> <E>")
        sys.exit(1)
    
    use_pathfinding = sys.argv[1] == "1"
    use_heuristic = sys.argv[2] == "1"
    counts = {
        "A": int(sys.argv[3]),
        "B": int(sys.argv[4]),
        "C": int(sys.argv[5]),
        "D": int(sys.argv[6]),
        "E": int(sys.argv[7]),
    }
    
    # 설비 위치 생성
    idx = 0
    positions = {}
    for stage in ["A", "B", "C", "D", "E"]:
        positions[stage] = ALL_POS[idx:idx+counts[stage]]
        idx += counts[stage]
    
    # 출력 억제
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
    
    # Profit 계산
    cost = (counts["A"]*4 + counts["B"]*9 + counts["C"]*8 + counts["D"]*8 + counts["E"]*5.5 + 3*0.011)
    profit = (100*pairs - 5*total_out) / cost * 100000
    
    # 결과 출력 (파싱용)
    print(f"RESULT:{pairs}:{profit:.0f}")

if __name__ == "__main__":
    main()
