"""
최적화 모듈: 유전 알고리즘을 사용하여 공정 순서, 설비 배치, AMR 대수를 최적화
목표: Profit 최대화
"""

import random
import copy
import json
from typing import List, Tuple, Dict
from itertools import permutations
import sim_core
from config import global_variable
from kpi import profit as calculate_profit

# 30개의 설비 설치 가능 위치 (고정)
AVAILABLE_POSITIONS = [
    (14,3), (14,5), (14,7), (14,13), (14,15), (14,17),
    (22,3), (22,5), (22,7), (22,13), (22,15), (22,17),
    (30,3), (30,5), (30,7), (30,13), (30,15), (30,17),
    (38,3), (38,5), (38,7), (38,13), (38,15), (38,17),
    (46,3), (46,5), (46,7), (46,13), (46,15), (46,17)
]

class Chromosome:
    """염색체: (공정순서, 설비배치, AMR대수)"""
    def __init__(self, route: List[str], machine_layout: Dict[str, List[Tuple[int, int]]], 
                 machine_counts: Dict[str, int], amr_count: int):
        self.route = route  # 예: ["A", "B", "C", "D", "E"]
        self.machine_layout = machine_layout  # 예: {"A": [(14,3), (14,5)], "B": [...]}
        self.machine_counts = machine_counts  # 예: {"A": 2, "B": 3, ...}
        self.amr_count = amr_count  # 1~30
        self.fitness = 0.0
        self.profit = 0.0
        self.completed_A = 0
        self.completed_B = 0
        
    def evaluate(self, sim_time: int = 1296000, seed: int = 42, verbose: bool = False) -> float:
        """시뮬레이션 실행 후 fitness(profit) 계산"""
        try:
            cfg = sim_core.FactoryConfig(
                sim_time=sim_time,
                seed=seed,
                feed_sequence=("ProdA", "ProdB"),
                amr_count=self.amr_count,
                machine_counts=self.machine_counts,
                machine_positions=self.machine_layout
            )
            
            # ROUTE 변경
            global_variable.ROUTE = self.route.copy()
            
            # 시뮬레이션 실행
            sim_core.simulate(cfg)
            
            # Profit 계산
            parameter = [4, 9, 8, 8, 5.5]
            total_equipment_cost = sum(
                self.machine_counts.get(stage, 0) * parameter[i] 
                for i, stage in enumerate(["A", "B", "C", "D", "E"])
            )
            
            completed_A = len(global_variable.STOCKERS["STK-01"].list_jobs_A())
            completed_B = len(global_variable.STOCKERS["STK-01"].list_jobs_B())
            total_output = global_variable.FEED_COUNT
            
            revenue = 100 * min(completed_A, completed_B) - 5 * total_output
            self.profit = revenue / (total_equipment_cost + 0.011 * self.amr_count)
            self.fitness = self.profit
            
            self.completed_A = completed_A
            self.completed_B = completed_B
            
            if verbose:
                print(f"  Route: {self.route}")
                print(f"  Machine counts: {self.machine_counts}")
                print(f"  AMR: {self.amr_count}대")
                print(f"  완성품 A: {completed_A}, B: {completed_B}")
                print(f"  Profit: {self.profit:.2f}")
            
            return self.fitness
            
        except Exception as e:
            print(f"  평가 중 오류: {e}")
            self.fitness = -1e9
            return self.fitness
    
    def __repr__(self):
        return (f"Chromosome(route={self.route}, AMR={self.amr_count}, "
                f"machines={self.machine_counts}, fitness={self.fitness:.2f})")


class GeneticAlgorithm:
    """유전 알고리즘 최적화"""
    
    def __init__(self, population_size: int = 20, generations: int = 30, 
                 mutation_rate: float = 0.2, elite_size: int = 2,
                 sim_time: int = 1296000, seed: int = 42):
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.elite_size = elite_size
        self.sim_time = sim_time
        self.seed = seed
        self.best_solution = None
        self.history = []
        
    def create_random_chromosome(self) -> Chromosome:
        """랜덤 염색체 생성"""
        # 1. 공정 순서: A,B,C,D,E의 순열 중 하나
        stages = ["A", "B", "C", "D", "E"]
        route = random.sample(stages, len(stages))
        
        # 2. AMR 대수: 1~30
        amr_count = random.randint(5, 30)
        
        # 3. 각 설비 개수: 1~6개 (총 30개 위치 제약)
        machine_counts = {}
        total_machines = 0
        for stage in stages:
            # 각 스테이지별 최소 1대, 최대 6대
            count = random.randint(1, min(6, 30 - total_machines - (5 - len(machine_counts))))
            machine_counts[stage] = count
            total_machines += count
        
        # 4. 설비 배치: 30개 위치 중 랜덤 선택
        available = AVAILABLE_POSITIONS.copy()
        random.shuffle(available)
        
        machine_layout = {}
        idx = 0
        for stage in stages:
            count = machine_counts[stage]
            machine_layout[stage] = available[idx:idx+count]
            idx += count
            
        return Chromosome(route, machine_layout, machine_counts, amr_count)
    
    def initialize_population(self) -> List[Chromosome]:
        """초기 개체군 생성"""
        print(f"\n=== 초기 개체군 생성 (크기: {self.population_size}) ===")
        population = []
        for i in range(self.population_size):
            chromo = self.create_random_chromosome()
            population.append(chromo)
            print(f"  [{i+1}/{self.population_size}] 생성 완료")
        return population
    
    def evaluate_population(self, population: List[Chromosome], generation: int):
        """개체군 평가"""
        print(f"\n=== 세대 {generation}: 평가 중 ===")
        for i, chromo in enumerate(population):
            print(f"  개체 {i+1}/{len(population)} 평가 중...")
            chromo.evaluate(sim_time=self.sim_time, seed=self.seed + generation * 100 + i)
            
        population.sort(key=lambda x: x.fitness, reverse=True)
        
        best = population[0]
        avg = sum(c.fitness for c in population) / len(population)
        print(f"  최고 Fitness: {best.fitness:.2f} (A:{best.completed_A}, B:{best.completed_B})")
        print(f"  평균 Fitness: {avg:.2f}")
        
        self.history.append({
            'generation': generation,
            'best_fitness': best.fitness,
            'avg_fitness': avg,
            'best_route': best.route,
            'best_amr': best.amr_count,
            'best_machines': best.machine_counts
        })
        
    def selection(self, population: List[Chromosome]) -> List[Chromosome]:
        """선택: 토너먼트 방식"""
        selected = []
        for _ in range(self.population_size - self.elite_size):
            # 토너먼트: 3개 중 최고 선택
            candidates = random.sample(population, min(3, len(population)))
            winner = max(candidates, key=lambda x: x.fitness)
            selected.append(winner)
        return selected
    
    def crossover(self, parent1: Chromosome, parent2: Chromosome) -> Chromosome:
        """교차: 두 부모로부터 자식 생성"""
        # Route: 50% 확률로 부모 중 하나 선택
        if random.random() < 0.5:
            route = parent1.route.copy()
        else:
            route = parent2.route.copy()
            
        # AMR: 부모의 평균
        amr_count = (parent1.amr_count + parent2.amr_count) // 2
        amr_count = max(1, min(30, amr_count))
        
        # Machine counts: 각 스테이지별로 부모 중 랜덤 선택
        machine_counts = {}
        for stage in ["A", "B", "C", "D", "E"]:
            if random.random() < 0.5:
                machine_counts[stage] = parent1.machine_counts[stage]
            else:
                machine_counts[stage] = parent2.machine_counts[stage]
        
        # 총 설비 수가 30개를 초과하면 조정
        total = sum(machine_counts.values())
        if total > 30:
            scale = 30 / total
            for stage in machine_counts:
                machine_counts[stage] = max(1, int(machine_counts[stage] * scale))
        
        # Layout: 새로 배치
        available = AVAILABLE_POSITIONS.copy()
        random.shuffle(available)
        machine_layout = {}
        idx = 0
        for stage in ["A", "B", "C", "D", "E"]:
            count = machine_counts[stage]
            machine_layout[stage] = available[idx:idx+count]
            idx += count
            
        return Chromosome(route, machine_layout, machine_counts, amr_count)
    
    def mutate(self, chromo: Chromosome):
        """변이"""
        if random.random() < self.mutation_rate:
            # Route 변이: 두 위치 교환
            if random.random() < 0.3:
                i, j = random.sample(range(5), 2)
                chromo.route[i], chromo.route[j] = chromo.route[j], chromo.route[i]
            
            # AMR 변이: ±3
            if random.random() < 0.3:
                chromo.amr_count += random.randint(-3, 3)
                chromo.amr_count = max(1, min(30, chromo.amr_count))
            
            # Machine count 변이: 랜덤 스테이지 ±1
            if random.random() < 0.4:
                stage = random.choice(["A", "B", "C", "D", "E"])
                change = random.choice([-1, 1])
                new_count = chromo.machine_counts[stage] + change
                if 1 <= new_count <= 6 and sum(chromo.machine_counts.values()) + change <= 30:
                    chromo.machine_counts[stage] = new_count
                    
                    # Layout 재구성
                    available = AVAILABLE_POSITIONS.copy()
                    random.shuffle(available)
                    machine_layout = {}
                    idx = 0
                    for s in ["A", "B", "C", "D", "E"]:
                        count = chromo.machine_counts[s]
                        machine_layout[s] = available[idx:idx+count]
                        idx += count
                    chromo.machine_layout = machine_layout
    
    def optimize(self) -> Chromosome:
        """최적화 실행"""
        print("\n" + "="*60)
        print("유전 알고리즘 최적화 시작")
        print("="*60)
        
        # 초기 개체군
        population = self.initialize_population()
        self.evaluate_population(population, 0)
        
        # 세대 진화
        for gen in range(1, self.generations + 1):
            print(f"\n{'='*60}")
            print(f"세대 {gen}/{self.generations}")
            print('='*60)
            
            # 엘리트 보존
            elite = population[:self.elite_size]
            
            # 선택
            selected = self.selection(population)
            
            # 교차 및 변이
            offspring = []
            for _ in range(self.population_size - self.elite_size):
                p1, p2 = random.sample(selected, 2)
                child = self.crossover(p1, p2)
                self.mutate(child)
                offspring.append(child)
            
            # 새 세대
            population = elite + offspring
            self.evaluate_population(population, gen)
            
            # 최고 해 업데이트
            if self.best_solution is None or population[0].fitness > self.best_solution.fitness:
                self.best_solution = copy.deepcopy(population[0])
                print(f"  ★ 최고 해 갱신! Fitness: {self.best_solution.fitness:.2f}")
        
        print("\n" + "="*60)
        print("최적화 완료!")
        print("="*60)
        return self.best_solution
    
    def save_results(self, filename: str = "optimization_results.json"):
        """결과 저장"""
        if self.best_solution is None:
            print("저장할 결과가 없습니다.")
            return
            
        results = {
            "best_solution": {
                "route": self.best_solution.route,
                "amr_count": self.best_solution.amr_count,
                "machine_counts": self.best_solution.machine_counts,
                "machine_layout": {k: [list(pos) for pos in v] 
                                 for k, v in self.best_solution.machine_layout.items()},
                "fitness": self.best_solution.fitness,
                "profit": self.best_solution.profit,
                "completed_A": self.best_solution.completed_A,
                "completed_B": self.best_solution.completed_B
            },
            "history": self.history,
            "parameters": {
                "population_size": self.population_size,
                "generations": self.generations,
                "mutation_rate": self.mutation_rate,
                "elite_size": self.elite_size,
                "sim_time": self.sim_time
            }
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n결과가 '{filename}'에 저장되었습니다.")


def run_optimization(population_size: int = 20, generations: int = 30, 
                    sim_time: int = 1296000, seed: int = 42):
    """최적화 실행 함수"""
    ga = GeneticAlgorithm(
        population_size=population_size,
        generations=generations,
        mutation_rate=0.2,
        elite_size=2,
        sim_time=sim_time,
        seed=seed
    )
    
    best = ga.optimize()
    
    print("\n" + "="*60)
    print("최종 최적 솔루션")
    print("="*60)
    print(f"공정 순서: {' → '.join(best.route)}")
    print(f"AMR 대수: {best.amr_count}대")
    print(f"설비 구성:")
    for stage in best.route:
        count = best.machine_counts[stage]
        positions = best.machine_layout[stage]
        print(f"  {stage}: {count}대 - {positions}")
    print(f"\n완성품: A={best.completed_A}개, B={best.completed_B}개")
    print(f"Profit: {best.profit:.2f}")
    print(f"Fitness: {best.fitness:.2f}")
    print("="*60)
    
    # 결과 저장
    ga.save_results()
    
    return best, ga


if __name__ == "__main__":
    # 테스트 실행 (작은 규모)
    print("최적화 테스트 시작...")
    best_solution, ga_instance = run_optimization(
        population_size=10,  # 테스트용 작은 크기
        generations=5,       # 테스트용 적은 세대
        sim_time=1296000,
        seed=42
    )
