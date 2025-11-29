"""
기여도 분석 - 각 테스트를 별도 프로세스로 실행
"""
import subprocess
import time

def run_test(name, pathfinding, heuristic, a, b, c, d, e):
    """별도 프로세스로 테스트 실행"""
    print(f"\n[{name}]")
    print(f"  설비: A:{a}, B:{b}, C:{c}, D:{d}, E:{e}")
    print(f"  Pathfinding: {pathfinding}, Heuristic: {heuristic}")
    
    start = time.perf_counter()
    
    cmd = ["python", "single_test.py", 
           "1" if pathfinding else "0",
           "1" if heuristic else "0",
           str(a), str(b), str(c), str(d), str(e)]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
    
    elapsed = time.perf_counter() - start
    
    # 결과 파싱
    for line in result.stdout.split('\n'):
        if line.startswith("RESULT:"):
            parts = line.split(":")
            pairs = int(parts[1])
            profit = float(parts[2])
            print(f"  결과: {pairs}쌍, Profit: {profit:,.0f}원 ({elapsed:.1f}초)")
            return {"name": name, "pairs": pairs, "profit": profit}
    
    print(f"  오류: {result.stderr[:200]}")
    return None


def main():
    print("=" * 60)
    print("개선점별 Profit 기여도 분석")
    print("=" * 60)
    
    results = {}
    
    # 1. 전체 적용 (기준)
    r = run_test("전체 적용 (기준)", True, True, 5, 8, 6, 5, 6)
    if r: results["all_on"] = r
    
    # 2. 다익스트라 OFF
    r = run_test("과업1 OFF (다익스트라)", False, True, 5, 8, 6, 5, 6)
    if r: results["no_path"] = r
    
    # 3. 휴리스틱 OFF
    r = run_test("과업2 OFF (휴리스틱)", True, False, 5, 8, 6, 5, 6)
    if r: results["no_heur"] = r
    
    # 4. 설비배분 OFF (B:9, E:5)
    r = run_test("과업4 OFF (설비배분)", True, True, 5, 9, 6, 5, 5)
    if r: results["baseline"] = r
    
    # 5. 전체 OFF
    r = run_test("전체 OFF", False, False, 5, 9, 6, 5, 5)
    if r: results["all_off"] = r
    
    # 결과 분석
    if len(results) == 5:
        print("\n" + "=" * 60)
        print("기여도 분석 결과")
        print("=" * 60)
        
        base = results["all_on"]["profit"]
        
        contrib = {
            "과업1_다익스트라": base - results["no_path"]["profit"],
            "과업2_휴리스틱": base - results["no_heur"]["profit"],
            "과업4_설비배분": base - results["baseline"]["profit"],
        }
        
        total_imp = base - results["all_off"]["profit"]
        contrib["과업3_Pull방식"] = total_imp - sum(contrib.values())
        
        print(f"\n기준 Profit: {base:,.0f}원")
        print(f"최저 Profit: {results['all_off']['profit']:,.0f}원")
        print(f"총 개선액:   {total_imp:,.0f}원")
        
        print("\n개선점별 기여도:")
        print("-" * 50)
        
        for name, val in sorted(contrib.items(), key=lambda x: -x[1]):
            pct = val / total_imp * 100 if total_imp > 0 else 0
            bar = "█" * max(0, int(pct/5)) + "░" * (20 - max(0, int(pct/5)))
            print(f"  {name:20s}: {val:+10,.0f}원 ({pct:5.1f}%) {bar}")
        
        max_c = max(contrib.items(), key=lambda x: x[1])
        print(f"\n★ 가장 큰 기여: {max_c[0]} ({max_c[1]:+,.0f}원)")


if __name__ == "__main__":
    main()
