"""
최적화 실행 스크립트
사용법:
  python run_optimization.py --population 30 --generations 50 --sim_time 1296000
"""

import argparse
from optimizer import run_optimization
from visualize_results import generate_report


def main():
    parser = argparse.ArgumentParser(description='공정 최적화 실행')
    parser.add_argument('--population', type=int, default=20, help='개체군 크기 (기본: 20)')
    parser.add_argument('--generations', type=int, default=30, help='세대 수 (기본: 30)')
    parser.add_argument('--sim_time', type=int, default=1296000, help='시뮬레이션 시간(초) (기본: 1296000)')
    parser.add_argument('--seed', type=int, default=42, help='랜덤 시드 (기본: 42)')
    parser.add_argument('--quick', action='store_true', help='빠른 테스트 모드 (population=10, generations=5)')
    
    args = parser.parse_args()
    
    if args.quick:
        print("\n[빠른 테스트 모드]")
        population = 10
        generations = 5
    else:
        population = args.population
        generations = args.generations
    
    print("\n" + "="*70)
    print("공정 최적화 시작")
    print("="*70)
    print(f"파라미터:")
    print(f"  - 개체군 크기: {population}")
    print(f"  - 세대 수: {generations}")
    print(f"  - 시뮬레이션 시간: {args.sim_time}초")
    print(f"  - 랜덤 시드: {args.seed}")
    print("="*70 + "\n")
    
    # 최적화 실행
    best_solution, ga_instance = run_optimization(
        population_size=population,
        generations=generations,
        sim_time=args.sim_time,
        seed=args.seed
    )
    
    # 결과 시각화 및 리포트 생성
    print("\n결과를 시각화하고 리포트를 생성합니다...")
    generate_report()
    
    print("\n" + "="*70)
    print("모든 작업이 완료되었습니다!")
    print("생성된 파일:")
    print("  - optimization_results.json (결과 데이터)")
    print("  - optimization_history.png (최적화 과정 그래프)")
    print("  - best_solution.png (최적 솔루션 시각화)")
    print("  - optimization_report.txt (텍스트 리포트)")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
