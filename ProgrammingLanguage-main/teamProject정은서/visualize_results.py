"""
최적화 결과 시각화 모듈
"""

import json
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from typing import Dict, List

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'  # Windows
plt.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지


def plot_optimization_history(history: List[Dict], save_path: str = "optimization_history.png"):
    """최적화 과정 시각화"""
    generations = [h['generation'] for h in history]
    best_fitness = [h['best_fitness'] for h in history]
    avg_fitness = [h['avg_fitness'] for h in history]
    
    plt.figure(figsize=(12, 6))
    
    plt.subplot(1, 2, 1)
    plt.plot(generations, best_fitness, 'b-o', label='최고 Fitness', linewidth=2)
    plt.plot(generations, avg_fitness, 'r--s', label='평균 Fitness', linewidth=2)
    plt.xlabel('세대 (Generation)', fontsize=12)
    plt.ylabel('Fitness (Profit)', fontsize=12)
    plt.title('세대별 Fitness 변화', fontsize=14, fontweight='bold')
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)
    
    plt.subplot(1, 2, 2)
    improvement = [(best_fitness[i] - best_fitness[0]) / abs(best_fitness[0]) * 100 
                   if best_fitness[0] != 0 else 0
                   for i in range(len(best_fitness))]
    plt.plot(generations, improvement, 'g-^', linewidth=2)
    plt.xlabel('세대 (Generation)', fontsize=12)
    plt.ylabel('초기 대비 개선율 (%)', fontsize=12)
    plt.title('최적화 개선 추이', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.axhline(y=0, color='k', linestyle='--', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"히스토리 그래프가 '{save_path}'에 저장되었습니다.")
    plt.close()


def plot_best_solution(solution: Dict, save_path: str = "best_solution.png"):
    """최적 솔루션 시각화"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # 1. 공정 순서
    ax = axes[0, 0]
    route = solution['route']
    stages_str = ' → '.join(route)
    ax.text(0.5, 0.5, f"공정 순서:\n{stages_str}", 
            ha='center', va='center', fontsize=16, fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))
    ax.axis('off')
    ax.set_title('최적 공정 순서', fontsize=14, fontweight='bold')
    
    # 2. 설비 구성
    ax = axes[0, 1]
    machine_counts = solution['machine_counts']
    stages = list(machine_counts.keys())
    counts = list(machine_counts.values())
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8']
    bars = ax.bar(stages, counts, color=colors, edgecolor='black', linewidth=1.5)
    ax.set_ylabel('설비 대수', fontsize=12)
    ax.set_xlabel('공정 스테이지', fontsize=12)
    ax.set_title('스테이지별 설비 구성', fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    
    # 막대 위에 값 표시
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}대',
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # 3. 설비 배치 맵
    ax = axes[1, 0]
    machine_layout = solution['machine_layout']
    
    # 모든 가능한 위치 표시 (회색)
    from optimizer import AVAILABLE_POSITIONS
    all_x = [pos[0] for pos in AVAILABLE_POSITIONS]
    all_y = [pos[1] for pos in AVAILABLE_POSITIONS]
    ax.scatter(all_x, all_y, c='lightgray', s=100, alpha=0.3, marker='s', label='사용 가능 위치')
    
    # 각 스테이지별 설비 위치 표시
    stage_colors = {'A': '#FF6B6B', 'B': '#4ECDC4', 'C': '#45B7D1', 'D': '#FFA07A', 'E': '#98D8C8'}
    for stage, positions in machine_layout.items():
        x = [pos[0] for pos in positions]
        y = [pos[1] for pos in positions]
        ax.scatter(x, y, c=stage_colors.get(stage, 'blue'), s=200, 
                  marker='o', edgecolors='black', linewidths=2, label=f'{stage} 설비', alpha=0.8)
    
    ax.set_xlabel('X 좌표', fontsize=12)
    ax.set_ylabel('Y 좌표', fontsize=12)
    ax.set_title('설비 배치 지도', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal')
    
    # 4. 성능 지표
    ax = axes[1, 1]
    metrics = {
        'AMR 대수': solution['amr_count'],
        '총 설비 대수': sum(machine_counts.values()),
        '완성품 A': solution['completed_A'],
        '완성품 B': solution['completed_B'],
        'Profit': round(solution['profit'], 2)
    }
    
    text_str = "=== 최적화 결과 ===\n\n"
    for key, value in metrics.items():
        if key == 'Profit':
            text_str += f"{key}: {value:.2f}\n"
        else:
            text_str += f"{key}: {value}\n"
    
    ax.text(0.5, 0.5, text_str, 
            ha='center', va='center', fontsize=13, family='monospace',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
    ax.axis('off')
    ax.set_title('성능 지표', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"최적 솔루션 그래프가 '{save_path}'에 저장되었습니다.")
    plt.close()


def generate_report(results_file: str = "optimization_results.json"):
    """최적화 결과 리포트 생성"""
    with open(results_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    # 그래프 생성
    plot_optimization_history(results['history'])
    plot_best_solution(results['best_solution'])
    
    # 텍스트 리포트
    report_file = "optimization_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("="*60 + "\n")
        f.write("공정 최적화 결과 리포트\n")
        f.write("="*60 + "\n\n")
        
        f.write("1. 최적화 파라미터\n")
        f.write("-"*60 + "\n")
        params = results['parameters']
        f.write(f"  개체군 크기: {params['population_size']}\n")
        f.write(f"  세대 수: {params['generations']}\n")
        f.write(f"  변이율: {params['mutation_rate']}\n")
        f.write(f"  엘리트 크기: {params['elite_size']}\n")
        f.write(f"  시뮬레이션 시간: {params['sim_time']}초\n\n")
        
        f.write("2. 최적 솔루션\n")
        f.write("-"*60 + "\n")
        best = results['best_solution']
        f.write(f"  공정 순서: {' → '.join(best['route'])}\n")
        f.write(f"  AMR 대수: {best['amr_count']}대\n")
        f.write(f"  총 설비 대수: {sum(best['machine_counts'].values())}대\n")
        f.write(f"\n  설비 구성:\n")
        for stage in best['route']:
            count = best['machine_counts'][stage]
            positions = best['machine_layout'][stage]
            f.write(f"    {stage}: {count}대 - {positions}\n")
        
        f.write(f"\n  생산 성과:\n")
        f.write(f"    완성품 A: {best['completed_A']}개\n")
        f.write(f"    완성품 B: {best['completed_B']}개\n")
        f.write(f"    페어 완성품: {min(best['completed_A'], best['completed_B'])}개\n")
        
        f.write(f"\n  경제 지표:\n")
        f.write(f"    Profit: {best['profit']:.2f}\n")
        f.write(f"    Fitness: {best['fitness']:.2f}\n\n")
        
        f.write("3. 최적화 과정\n")
        f.write("-"*60 + "\n")
        history = results['history']
        f.write(f"  초기 최고 Fitness: {history[0]['best_fitness']:.2f}\n")
        f.write(f"  최종 최고 Fitness: {history[-1]['best_fitness']:.2f}\n")
        improvement = ((history[-1]['best_fitness'] - history[0]['best_fitness']) 
                      / abs(history[0]['best_fitness']) * 100 
                      if history[0]['best_fitness'] != 0 else 0)
        f.write(f"  개선율: {improvement:.2f}%\n\n")
        
        f.write("4. 세대별 진화\n")
        f.write("-"*60 + "\n")
        f.write(f"{'세대':<6} {'최고 Fitness':<15} {'평균 Fitness':<15} {'최고 AMR':<10}\n")
        f.write("-"*60 + "\n")
        for h in history:
            f.write(f"{h['generation']:<6} {h['best_fitness']:<15.2f} "
                   f"{h['avg_fitness']:<15.2f} {h['best_amr']:<10}\n")
        
        f.write("\n" + "="*60 + "\n")
        f.write("리포트 생성 완료\n")
        f.write("="*60 + "\n")
    
    print(f"\n텍스트 리포트가 '{report_file}'에 저장되었습니다.")


if __name__ == "__main__":
    # 결과 파일이 있으면 리포트 생성
    import os
    if os.path.exists("optimization_results.json"):
        print("최적화 결과를 시각화하고 리포트를 생성합니다...")
        generate_report()
    else:
        print("optimization_results.json 파일을 찾을 수 없습니다.")
        print("먼저 optimizer.py를 실행하여 최적화를 수행하세요.")
