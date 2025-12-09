"""
유전 알고리즘을 이용한 설비 배치 최적화
- 설비 개수: A=5, B=8, C=6, D=5, E=5 (총 29대)
- 목표: Profit 최대화
- 알고리즘: Genetic Algorithm with Multi-Objective Optimization
"""

import sim_core
from sim_core import *
from config import global_variable
import random
import numpy as np
from typing import List, Dict, Tuple
import copy
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing as mp
from functools import partial

# 설비 개수 (고정)
MACHINE_COUNTS = {"A": 5, "B": 8, "C": 6, "D": 5, "E": 5}
AMR_COUNT = 4  # main.py와 동일하게 4대로 설정
CPU_CORES = mp.cpu_count()  # 사용 가능한 CPU 코어 수

# 사용 가능한 위치 좌표
ALL_POSITIONS = [
    # 열1 (x=14) - Warehouse와 가장 가까움
    (14, 3), (14, 5), (14, 7), (14, 13), (14, 15), (14, 17),
    # 열2 (x=22)
    (22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17),
    # 열3 (x=30) - 중앙
    (30, 3), (30, 5), (30, 7), (30, 13), (30, 15), (30, 17),
    # 열4 (x=38)
    (38, 3), (38, 5), (38, 7), (38, 13), (38, 15), (38, 17),
    # 열5 (x=46) - Stocker와 가장 가까움
    (46, 3), (46, 5), (46, 7), (46, 13), (46, 15), (46, 17),
]

# 유전 알고리즘 파라미터 - 배치 검증 모드
POPULATION_SIZE = 40        # 세대당 개체 수 (다양한 배치 비교)
GENERATIONS = 25            # 진화 세대 수
MUTATION_RATE = 0.15        # 돌연변이 확률
ELITE_SIZE = 5              # 엘리트 개체 수
TOURNAMENT_SIZE = 3         # 토너먼트 선택 크기
SIM_TIME = 1296000          # 시뮬레이션 시간 (15일 전체 - 정확한 비교)
FULL_SIM_TIME = 1296000     # 최종 검증용 전체 시간 (15일)
MAX_WORKERS = min(CPU_CORES * 3, 32)  # 하이퍼스레딩 최대 활용
CONVERGENCE_THRESHOLD = 8   # 수렴 판단: 8세대 동안 개선 없으면 종료
BASELINE_PROFIT = 91099000  # 기준 수익 (현재 배치로 나오는 값)
USE_DISTANCE_HEURISTIC = False  # 실제 시뮬레이션 사용
VERIFY_BASELINE = True      # 첫 개체로 현재 배치 평가

# Simulated Annealing 파라미터 (현실적으로 조정)
SA_INITIAL_TEMP = 100.0     # 초기 온도 (낮춤)
SA_COOLING_RATE = 0.90      # 냉각 속도 (빠르게)
SA_ITERATIONS = 3           # 각 온도에서 시도 횟수 (대폭 감소)
SA_MIN_TEMP = 1.0           # 최소 온도 (높임)
SA_USE_PARALLEL = True      # 병렬 처리 사용


def manhattan_distance(p1, p2):
    """맨하탄 거리 계산"""
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])


def avg_distance(positions1: List[Tuple], positions2: List[Tuple]) -> float:
    """두 설비 그룹 간 평균 거리"""
    if not positions1 or not positions2:
        return 0
    total = sum(manhattan_distance(p1, p2) for p1 in positions1 for p2 in positions2)
    return total / (len(positions1) * len(positions2))


def evaluate_by_distance(layout: Dict[str, List[Tuple[int, int]]]) -> float:
    """거리 기반 빠른 평가 (시뮬레이션 없이)"""
    WH_POS = (3, 10)   # Warehouse 위치
    STK_POS = (50, 10) # Stocker 위치
    
    # 1. 공정 흐름 거리 (A->B->C->D->E)
    flow_distance = (
        avg_distance([WH_POS], layout["A"]) +
        avg_distance(layout["A"], layout["B"]) * 2 +  # B는 병목이라 2배 가중치
        avg_distance(layout["B"], layout["C"]) * 1.5 +
        avg_distance(layout["C"], layout["D"]) +
        avg_distance(layout["D"], layout["E"]) +
        avg_distance(layout["E"], [STK_POS])
    )
    
    # 2. 설비 분산도 (너무 퍼져있으면 안 좋음)
    all_positions = []
    for positions in layout.values():
        all_positions.extend(positions)
    
    if all_positions:
        center_x = sum(p[0] for p in all_positions) / len(all_positions)
        center_y = sum(p[1] for p in all_positions) / len(all_positions)
        spread = sum(manhattan_distance(p, (center_x, center_y)) for p in all_positions) / len(all_positions)
    else:
        spread = 0
    
    # 3. B 공정 중앙 배치 보너스 (병목이므로)
    b_center_x = sum(p[0] for p in layout["B"]) / len(layout["B"])
    b_center_y = sum(p[1] for p in layout["B"]) / len(layout["B"])
    b_centrality = manhattan_distance((b_center_x, b_center_y), (30, 10))
    
    # 적합도: 거리가 짧을수록 좋음 (음수로 최대화)
    fitness = -(flow_distance + spread * 0.3 + b_centrality * 0.5)
    
    return fitness


def evaluate_individual(layout: Dict[str, List[Tuple[int, int]]]) -> Tuple[float, Dict]:
    """개체 평가 함수 (병렬 처리용 독립 함수)"""
    try:
        # 거리 기반 빠른 평가 사용
        if USE_DISTANCE_HEURISTIC:
            fitness = evaluate_by_distance(layout)
            metrics = {
                "fitness": fitness,
                "distance_based": True,
                "profit": 0,  # 추정치 없음
                "pair": 0,
                "a_count": 0,
                "b_count": 0,
                "feed_total": 0,
                "balance": 0
            }
            return fitness, metrics
        
        # 기존 시뮬레이션 평가
        sim_core.reset_sim()
        
        cfg = sim_core.FactoryConfig(
            sim_time=SIM_TIME,
            seed=20,
            feed_sequence=("ProdA", "ProdB"),
            amr_count=AMR_COUNT,
            machine_counts=MACHINE_COUNTS,
            machine_positions=layout
        )
        sim_core.simulate(cfg)
        
        # Profit 계산
        parameter = {"A": 4, "B": 9, "C": 8, "D": 8, "E": 5.5}
        t = sum(MACHINE_COUNTS[k] * parameter[k] for k in MACHINE_COUNTS)
        
        a_count = len(global_variable.STOCKERS["STK-01"].list_jobs_A())
        b_count = len(global_variable.STOCKERS["STK-01"].list_jobs_B())
        feed_total = global_variable.FEED_COUNT_A + global_variable.FEED_COUNT_B
        
        pair = min(a_count, b_count)
        p = 100 * pair - 5 * feed_total
        profit_raw = p / (t + 0.011 * AMR_COUNT) * 100000
        
        metrics = {
            "profit": profit_raw,
            "pair": pair,
            "a_count": a_count,
            "b_count": b_count,
            "feed_total": feed_total,
            "balance": min(a_count, b_count) / (max(a_count, b_count) + 1) if max(a_count, b_count) > 0 else 0,
            "distance_based": False
        }
        
        balance_bonus = metrics["balance"] * 10000
        fitness = profit_raw + balance_bonus
        
        return fitness, metrics
        
    except Exception as e:
        return -1e9, {"error": str(e), "distance_based": False}


class Individual:
    """유전 알고리즘의 개체 (하나의 설비 배치)"""
    def __init__(self, layout: Dict[str, List[Tuple[int, int]]] = None):
        if layout is None:
            self.layout = self.random_layout()
        else:
            self.layout = layout
        self.fitness = None
        self.metrics = None
    
    def random_layout(self) -> Dict[str, List[Tuple[int, int]]]:
        """랜덤 배치 생성 (중복 없이)"""
        available = ALL_POSITIONS.copy()
        random.shuffle(available)
        
        layout = {}
        idx = 0
        for stage in ["A", "B", "C", "D", "E"]:
            count = MACHINE_COUNTS[stage]
            layout[stage] = available[idx:idx + count]
            idx += count
        
        return layout
    
    def evaluate(self) -> float:
        """시뮬레이션 실행 및 적합도 계산"""
        if self.fitness is not None:
            return self.fitness
        
        self.fitness, self.metrics = evaluate_individual(self.layout)
        return self.fitness
    
    def crossover(self, other: 'Individual') -> Tuple['Individual', 'Individual']:
        """교차 연산 (Two-Point Crossover with Stage Preservation)"""
        # 각 공정별로 독립적으로 교차
        child1_layout = {}
        child2_layout = {}
        
        used1 = set()
        used2 = set()
        
        for stage in ["A", "B", "C", "D", "E"]:
            count = MACHINE_COUNTS[stage]
            
            # 랜덤하게 부모로부터 일부 선택
            if random.random() < 0.5:
                # 부모1에서 더 많이
                split = random.randint(count // 2, count)
                child1_layout[stage] = self.layout[stage][:split].copy()
                child2_layout[stage] = other.layout[stage][:split].copy()
            else:
                # 부모2에서 더 많이
                split = random.randint(0, count // 2)
                child1_layout[stage] = other.layout[stage][:split].copy()
                child2_layout[stage] = self.layout[stage][:split].copy()
            
            used1.update(child1_layout[stage])
            used2.update(child2_layout[stage])
        
        # 나머지 위치 채우기
        available1 = [pos for pos in ALL_POSITIONS if pos not in used1]
        available2 = [pos for pos in ALL_POSITIONS if pos not in used2]
        random.shuffle(available1)
        random.shuffle(available2)
        
        idx1 = 0
        idx2 = 0
        for stage in ["A", "B", "C", "D", "E"]:
            count = MACHINE_COUNTS[stage]
            needed1 = count - len(child1_layout[stage])
            needed2 = count - len(child2_layout[stage])
            
            child1_layout[stage].extend(available1[idx1:idx1 + needed1])
            child2_layout[stage].extend(available2[idx2:idx2 + needed2])
            
            idx1 += needed1
            idx2 += needed2
        
        return Individual(child1_layout), Individual(child2_layout)
    
    def mutate(self):
        """돌연변이 (다양한 전략)"""
        if random.random() < MUTATION_RATE:
            strategy = random.random()
            
            # 전략 1: 랜덤 스왑 (50%)
            if strategy < 0.5:
                stages = list(self.layout.keys())
                stage1, stage2 = random.sample(stages, 2)
                
                if self.layout[stage1] and self.layout[stage2]:
                    pos1 = random.randint(0, len(self.layout[stage1]) - 1)
                    pos2 = random.randint(0, len(self.layout[stage2]) - 1)
                    
                    self.layout[stage1][pos1], self.layout[stage2][pos2] = \
                        self.layout[stage2][pos2], self.layout[stage1][pos1]
            
            # 전략 2: 병목 공정(B, C) 중앙 이동 (30%)
            elif strategy < 0.8:
                stage = random.choice(["B", "C"])
                if self.layout[stage]:
                    idx = random.randint(0, len(self.layout[stage]) - 1)
                    old_pos = self.layout[stage][idx]
                    
                    used = set()
                    for s in self.layout.values():
                        used.update(s)
                    
                    available = [p for p in ALL_POSITIONS if p not in used]
                    if available:
                        # 중앙(x=22~38, y=7~13)에 가까운 순
                        available.sort(key=lambda p: abs(p[0] - 30) + abs(p[1] - 10))
                        new_pos = available[0]
                        self.layout[stage][idx] = new_pos
            
            # 전략 3: 공정 간 인접성 개선 (20%)
            else:
                # A→B, B→C, C→D, D→E 흐름을 고려한 인접 배치
                pairs = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")]
                stage1, stage2 = random.choice(pairs)
                
                if self.layout[stage1] and self.layout[stage2]:
                    # stage1의 한 설비를 stage2와 가깝게
                    idx1 = random.randint(0, len(self.layout[stage1]) - 1)
                    avg_x = sum(p[0] for p in self.layout[stage2]) / len(self.layout[stage2])
                    avg_y = sum(p[1] for p in self.layout[stage2]) / len(self.layout[stage2])
                    
                    used = set()
                    for s in self.layout.values():
                        used.update(s)
                    
                    available = [p for p in ALL_POSITIONS if p not in used]
                    if available:
                        available.sort(key=lambda p: abs(p[0] - avg_x) + abs(p[1] - avg_y))
                        self.layout[stage1][idx1] = available[0]
            
            self.fitness = None
    
    def copy(self) -> 'Individual':
        """개체 복사"""
        new_layout = {k: v.copy() for k, v in self.layout.items()}
        ind = Individual(new_layout)
        ind.fitness = self.fitness
        ind.metrics = self.metrics.copy() if self.metrics else None
        return ind


class SimulatedAnnealing:
    """시뮬레이티드 어닐링 최적화 (유전 알고리즘보다 효과적)"""
    
    def __init__(self, initial_layout: Dict = None):
        if initial_layout is None:
            # 현재 배치에서 시작
            self.current_layout = {
                "A": [(14, 3), (14, 5), (14, 7), (14, 13), (14, 15)],
                "B": [(22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17), (30, 3), (30, 5)],
                "C": [(30, 7), (30, 13), (30, 15), (30, 17), (38, 3), (38, 5)],
                "D": [(38, 7), (38, 13), (38, 15), (38, 17), (46, 3)],
                "E": [(46, 5), (46, 7), (46, 13), (46, 15), (46, 17)],
            }
        else:
            self.current_layout = copy.deepcopy(initial_layout)
        
        self.current_fitness, self.current_metrics = evaluate_individual(self.current_layout)
        self.best_layout = copy.deepcopy(self.current_layout)
        self.best_fitness = self.current_fitness
        self.best_metrics = copy.deepcopy(self.current_metrics)
        self.history = []
    
    def get_neighbor(self, layout: Dict) -> Dict:
        """이웃 해 생성 (1~2개 설비만 이동)"""
        new_layout = copy.deepcopy(layout)
        
        # 전략 선택
        strategy = random.random()
        
        if strategy < 0.5:
            # 1. 두 설비 위치 교환 (50%)
            stages = list(new_layout.keys())
            stage1, stage2 = random.sample(stages, 2)
            
            if new_layout[stage1] and new_layout[stage2]:
                idx1 = random.randint(0, len(new_layout[stage1]) - 1)
                idx2 = random.randint(0, len(new_layout[stage2]) - 1)
                new_layout[stage1][idx1], new_layout[stage2][idx2] = \
                    new_layout[stage2][idx2], new_layout[stage1][idx1]
        
        elif strategy < 0.8:
            # 2. 한 설비를 빈 위치로 이동 (30%)
            stage = random.choice(list(new_layout.keys()))
            if new_layout[stage]:
                idx = random.randint(0, len(new_layout[stage]) - 1)
                
                used = set()
                for positions in new_layout.values():
                    used.update(positions)
                
                available = [p for p in ALL_POSITIONS if p not in used]
                if available:
                    new_layout[stage][idx] = random.choice(available)
        
        else:
            # 3. 병목 공정(B, C) 중심으로 재배치 (20%)
            stage = random.choice(["B", "C"])
            if new_layout[stage]:
                idx = random.randint(0, len(new_layout[stage]) - 1)
                
                used = set()
                for positions in new_layout.values():
                    used.update(positions)
                
                available = [p for p in ALL_POSITIONS if p not in used]
                if available:
                    # 중앙에 가까운 위치 우선
                    available.sort(key=lambda p: abs(p[0] - 30) + abs(p[1] - 10))
                    new_layout[stage][idx] = available[0] if available else new_layout[stage][idx]
        
        return new_layout
    
    def accept_probability(self, current_fitness: float, new_fitness: float, temperature: float) -> float:
        """수락 확률 계산 (나쁜 해도 확률적으로 수락)"""
        if new_fitness > current_fitness:
            return 1.0
        else:
            # 볼츠만 분포
            return math.exp((new_fitness - current_fitness) / temperature)
    
    def run(self):
        """시뮬레이티드 어닐링 실행 (병렬 처리 버전)"""
        import time
        print("\n" + "=" * 80)
        print("🔥 Simulated Annealing - 지역 탐색 최적화")
        print(f"📍 시작: 현재 배치 ({self.current_fitness:,.0f})")
        print(f"🌡️  온도: {SA_INITIAL_TEMP} → {SA_MIN_TEMP} (냉각율 {SA_COOLING_RATE})")
        print(f"🔄 반복: 각 온도마다 {SA_ITERATIONS}회")
        
        # 예상 평가 횟수 계산
        temp_steps = int(math.log(SA_MIN_TEMP / SA_INITIAL_TEMP) / math.log(SA_COOLING_RATE))
        total_evals = temp_steps * SA_ITERATIONS
        estimated_time = (total_evals / MAX_WORKERS) * 40 if SA_USE_PARALLEL else total_evals * 40
        
        print(f"📊 예상 평가: {total_evals:,}회 ({temp_steps}단계 × {SA_ITERATIONS}회)")
        if SA_USE_PARALLEL:
            print(f"⚡ 병렬 처리: {MAX_WORKERS}워커 → 약 {estimated_time/60:.1f}분 예상")
        else:
            print(f"⏱️  순차 실행 → 약 {estimated_time/60:.1f}분 예상")
        print("=" * 80)
        
        total_start = time.time()
        temperature = SA_INITIAL_TEMP
        iteration = 0
        accepted = 0
        rejected = 0
        improvements = 0
        
        while temperature > SA_MIN_TEMP:
            temp_start = time.time()
            temp_accepted = 0
            
            # 병렬 처리: SA_ITERATIONS개의 이웃을 한 번에 평가
            if SA_USE_PARALLEL:
                neighbors = [self.get_neighbor(self.current_layout) for _ in range(SA_ITERATIONS)]
                
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    results = list(executor.map(evaluate_individual, neighbors))
                
                for neighbor_layout, (neighbor_fitness, neighbor_metrics) in zip(neighbors, results):
                    iteration += 1
                    
                    # 수락 여부 결정
                    accept_prob = self.accept_probability(self.current_fitness, neighbor_fitness, temperature)
                    
                    if random.random() < accept_prob:
                        self.current_layout = neighbor_layout
                        self.current_fitness = neighbor_fitness
                        self.current_metrics = neighbor_metrics
                        accepted += 1
                        temp_accepted += 1
                        
                        if neighbor_fitness > self.best_fitness:
                            self.best_layout = copy.deepcopy(neighbor_layout)
                            self.best_fitness = neighbor_fitness
                            self.best_metrics = copy.deepcopy(neighbor_metrics)
                            improvements += 1
                            
                            if neighbor_metrics and not neighbor_metrics.get("distance_based"):
                                profit = neighbor_metrics['profit']
                                print(f"  🎯 개선! T={temperature:.1f}, Iter={iteration}, " +
                                      f"Profit={profit:,.0f}원 (+{profit-BASELINE_PROFIT:,.0f})")
                    else:
                        rejected += 1
            
            else:
                # 순차 실행 (기존 방식)
                for i in range(SA_ITERATIONS):
                    iteration += 1
                    
                    neighbor_layout = self.get_neighbor(self.current_layout)
                    neighbor_fitness, neighbor_metrics = evaluate_individual(neighbor_layout)
                    
                    accept_prob = self.accept_probability(self.current_fitness, neighbor_fitness, temperature)
                    
                    if random.random() < accept_prob:
                        self.current_layout = neighbor_layout
                        self.current_fitness = neighbor_fitness
                        self.current_metrics = neighbor_metrics
                        accepted += 1
                        temp_accepted += 1
                        
                        if neighbor_fitness > self.best_fitness:
                            self.best_layout = copy.deepcopy(neighbor_layout)
                            self.best_fitness = neighbor_fitness
                            self.best_metrics = copy.deepcopy(neighbor_metrics)
                            improvements += 1
                            
                            if neighbor_metrics and not neighbor_metrics.get("distance_based"):
                                profit = neighbor_metrics['profit']
                                print(f"  🎯 개선! T={temperature:.1f}, Iter={iteration}, " +
                                      f"Profit={profit:,.0f}원 (+{profit-BASELINE_PROFIT:,.0f})")
                    else:
                        rejected += 1
            
            # 온도별 진행 상황
            elapsed = time.time() - temp_start
            if self.best_metrics and not self.best_metrics.get("distance_based"):
                best_profit = self.best_metrics['profit']
                print(f"  T={temperature:.1f} | {iteration}회 | " +
                      f"Best={best_profit:,.0f}원 | 수락={temp_accepted}/{SA_ITERATIONS} | {elapsed:.1f}초")
            
            # 온도 하강
            temperature *= SA_COOLING_RATE
            
            self.history.append({
                "temperature": temperature,
                "best_fitness": self.best_fitness,
                "current_fitness": self.current_fitness,
                "iteration": iteration
            })
        
        total_time = time.time() - total_start
        
        print(f"\n" + "=" * 80)
        print(f"⏱️  총 소요시간: {total_time:.1f}초 ({total_time/60:.1f}분)")
        print(f"🔄 총 반복: {iteration:,}회")
        print(f"✅ 수락: {accepted:,}회 ({accepted/iteration*100:.1f}%)")
        print(f"❌ 거부: {rejected:,}회 ({rejected/iteration*100:.1f}%)")
        print(f"📈 개선: {improvements:,}회")
        
        if self.best_metrics and not self.best_metrics.get("distance_based"):
            best_profit = self.best_metrics['profit']
            improvement = best_profit - BASELINE_PROFIT
            
            print(f"\n📍 시작: {BASELINE_PROFIT:,}원")
            print(f"🏆 최종: {best_profit:,.0f}원")
            print(f"💰 개선: {improvement:+,.0f}원 ({improvement/BASELINE_PROFIT*100:+.2f}%)")
        
        print("=" * 80)
        
        return self.best_layout, self.best_fitness, self.best_metrics


class GeneticAlgorithm:
    """유전 알고리즘 최적화"""
    def __init__(self):
        self.population: List[Individual] = []
        self.best_individual: Individual = None
        self.history = []
        self.no_improvement_count = 0  # 수렴 판단용
    
    def initialize_population(self):
        """초기 개체군 생성 (현재 배치 포함 및 검증)"""
        print("초기 개체군 생성 중...", end=" ", flush=True)
        import time
        start = time.time()
        
        # 0. 현재 배치를 첫 번째 개체로 추가 (검증 대상!)
        baseline_layout = {
            "A": [(14, 3), (14, 5), (14, 7), (14, 13), (14, 15)],
            "B": [(22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17), (30, 3), (30, 5)],
            "C": [(30, 7), (30, 13), (30, 15), (30, 17), (38, 3), (38, 5)],
            "D": [(38, 7), (38, 13), (38, 15), (38, 17), (46, 3)],
            "E": [(46, 5), (46, 7), (46, 13), (46, 15), (46, 17)],
        }
        baseline_ind = Individual(baseline_layout)
        self.population.append(baseline_ind)
        print("현재배치✓", end="", flush=True)
        
        # 즉시 평가해서 기준선 확인
        if VERIFY_BASELINE:
            print(" 평가중...", end="", flush=True)
            baseline_ind.evaluate()
            if baseline_ind.metrics and not baseline_ind.metrics.get("distance_based"):
                print(f" → {baseline_ind.metrics['profit']:,.0f}원 (현재)", end="", flush=True)
        
        # 1. 현재 배치의 약간의 변형들 (20%)
        variation_count = int(POPULATION_SIZE * 0.2)
        for _ in range(variation_count):
            ind = Individual(copy.deepcopy(baseline_layout))
            # 1~2개만 변형 (현재 배치 근처)
            for _ in range(random.randint(1, 2)):
                ind.mutate()
            self.population.append(ind)
        
        # 2. 완전 랜덤 개체들 (40%)
        random_count = int(POPULATION_SIZE * 0.4)
        for _ in range(random_count):
            self.population.append(Individual())
        
        # 3. 휴리스틱 기반 개체들 (40%)
        heuristics = [
            self._create_sequential_layout,
            self._create_centered_layout,
            self._create_wh_stk_optimized,
            self._create_bottleneck_optimized,
            self._create_balanced_layout,
            self._create_cluster_layout,
        ]
        
        remaining = POPULATION_SIZE - len(self.population)
        for i in range(remaining):
            heuristic = heuristics[i % len(heuristics)]
            layout = heuristic()
            ind = Individual(layout)
            if i >= len(heuristics):
                ind.mutate()
            self.population.append(ind)
        
        elapsed = time.time() - start
        print(f" +{len(self.population)-1}개 완료! ({elapsed:.1f}초)")
    
    def _create_sequential_layout(self) -> Dict:
        """순차 배치 (A→E 순서대로)"""
        available = ALL_POSITIONS.copy()
        layout = {}
        idx = 0
        for stage in ["A", "B", "C", "D", "E"]:
            count = MACHINE_COUNTS[stage]
            layout[stage] = available[idx:idx + count]
            idx += count
        return layout
    
    def _create_centered_layout(self) -> Dict:
        """중앙 집중 배치"""
        positions = sorted(ALL_POSITIONS, key=lambda p: abs(p[0] - 30) + abs(p[1] - 10))
        layout = {}
        idx = 0
        for stage in ["A", "B", "C", "D", "E"]:
            count = MACHINE_COUNTS[stage]
            layout[stage] = positions[idx:idx + count]
            idx += count
        return layout
    
    def _create_wh_stk_optimized(self) -> Dict:
        """WH/STK 최적화 배치"""
        layout = {}
        available = ALL_POSITIONS.copy()
        
        # A는 WH 근처 (x=14)
        a_positions = sorted([p for p in available if p[0] == 14], key=lambda p: abs(p[1] - 10))[:5]
        layout["A"] = a_positions
        for p in a_positions:
            available.remove(p)
        
        # E는 STK 근처 (x=46)
        e_positions = sorted([p for p in available if p[0] == 46], key=lambda p: abs(p[1] - 10))[:5]
        layout["E"] = e_positions
        for p in e_positions:
            available.remove(p)
        
        # 나머지는 중앙
        random.shuffle(available)
        idx = 0
        for stage in ["B", "C", "D"]:
            count = MACHINE_COUNTS[stage]
            layout[stage] = available[idx:idx + count]
            idx += count
        
        return layout
    
    def _create_bottleneck_optimized(self) -> Dict:
        """병목 공정(B) 최적화"""
        layout = {}
        available = ALL_POSITIONS.copy()
        
        # B를 중앙에 집중
        b_positions = sorted(available, key=lambda p: abs(p[0] - 30) + abs(p[1] - 10))[:8]
        layout["B"] = b_positions
        for p in b_positions:
            available.remove(p)
        
        random.shuffle(available)
        idx = 0
        for stage in ["A", "C", "D", "E"]:
            count = MACHINE_COUNTS[stage]
            layout[stage] = available[idx:idx + count]
            idx += count
        
        return layout
    
    def _create_balanced_layout(self) -> Dict:
        """균형 배치 (상하 분산)"""
        layout = {}
        available = ALL_POSITIONS.copy()
        random.shuffle(available)
        
        # 상단/하단 교대로 배치
        for stage in ["A", "B", "C", "D", "E"]:
            count = MACHINE_COUNTS[stage]
            positions = []
            for i in range(count):
                if i % 2 == 0:
                    # 상단 우선
                    pos = next((p for p in available if p[1] <= 7), available[0])
                else:
                    # 하단 우선
                    pos = next((p for p in available if p[1] >= 13), available[0])
                positions.append(pos)
                available.remove(pos)
            layout[stage] = positions
        
        return layout
    
    def _create_cluster_layout(self) -> Dict:
        """클러스터 배치 (공정별 그룹화)"""
        layout = {}
        
        # 각 공정을 특정 열에 집중
        stage_cols = {"A": 14, "B": 22, "C": 30, "D": 38, "E": 46}
        
        for stage, col in stage_cols.items():
            count = MACHINE_COUNTS[stage]
            positions = [p for p in ALL_POSITIONS if p[0] == col][:count]
            if len(positions) < count:
                # 부족하면 인접 열에서 가져오기
                adjacent = [p for p in ALL_POSITIONS if abs(p[0] - col) == 8]
                positions.extend(adjacent[:count - len(positions)])
            layout[stage] = positions[:count]
        
        return layout
    
    def tournament_selection(self) -> Individual:
        """토너먼트 선택"""
        tournament = random.sample(self.population, TOURNAMENT_SIZE)
        return max(tournament, key=lambda ind: ind.fitness if ind.fitness else -1e9)
    
    def evolve(self):
        """한 세대 진화 (최대 병렬 처리 + 배치 처리)"""
        import time
        # 1. 병렬 평가 (배치 처리로 최적화)
        need_eval = [ind for ind in self.population if ind.fitness is None]
        
        if need_eval:
            start_time = time.time()
            print(f"평가중({len(need_eval)}개, {MAX_WORKERS}워커)...", end=" ", flush=True)
            
            # 최대 병렬 처리로 평가 (청크 단위 처리)
            layouts = [ind.layout for ind in need_eval]
            
            # ThreadPoolExecutor로 I/O 바운드 작업 최적화
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # 청크 단위로 제출하여 메모리 효율성 증가
                chunk_size = max(1, len(layouts) // MAX_WORKERS)
                results = list(executor.map(evaluate_individual, layouts, chunksize=chunk_size))
            
            # 결과 저장
            for ind, (fitness, metrics) in zip(need_eval, results):
                ind.fitness = fitness
                ind.metrics = metrics
            
            elapsed = time.time() - start_time
            rate = len(need_eval) / elapsed if elapsed > 0 else 0
            print(f"완료! ({elapsed:.1f}초, {rate:.1f}개/초)", end=" ", flush=True)
        
        # 2. 정렬
        self.population.sort(key=lambda ind: ind.fitness, reverse=True)
        
        # 3. 최고 개체 저장 및 수렴 체크
        prev_best_fitness = self.best_individual.fitness if self.best_individual else -1e9
        
        if self.best_individual is None or self.population[0].fitness > self.best_individual.fitness:
            self.best_individual = self.population[0].copy()
            self.no_improvement_count = 0  # 개선됨
        else:
            self.no_improvement_count += 1  # 개선 없음
        
        # 4. 통계 기록
        avg_fitness = np.mean([ind.fitness for ind in self.population])
        self.history.append({
            "best": self.population[0].fitness,
            "avg": avg_fitness,
            "worst": self.population[-1].fitness
        })
        
        # 5. 새로운 개체군 생성
        new_population = []
        
        # 엘리트 보존
        new_population.extend([ind.copy() for ind in self.population[:ELITE_SIZE]])
        
        # 교차 및 돌연변이
        while len(new_population) < POPULATION_SIZE:
            parent1 = self.tournament_selection()
            parent2 = self.tournament_selection()
            
            child1, child2 = parent1.crossover(parent2)
            child1.mutate()
            child2.mutate()
            
            new_population.extend([child1, child2])
        
        self.population = new_population[:POPULATION_SIZE]
    
    def run(self):
        """최적화 실행 - 현재 배치 검증 모드"""
        import time
        print("=" * 80)
        print("🔍 현재 배치 검증 & 최적 배치 탐색")
        print(f"📍 현재 배치: A={MACHINE_COUNTS['A']}, B={MACHINE_COUNTS['B']}, " +
              f"C={MACHINE_COUNTS['C']}, D={MACHINE_COUNTS['D']}, E={MACHINE_COUNTS['E']}")
        print(f"🎯 현재 수익: {BASELINE_PROFIT:,}원 (검증 대상)")
        print(f"❓ 질문: 이 배치가 최선인가? 더 나은 배치가 있나?")
        print(f"📊 비교: {POPULATION_SIZE * GENERATIONS:,}개 배치 탐색")
        print(f"⏱️  시뮬레이션: 15일 전체 (정확한 비교)")
        print(f"🖥️  병렬 처리: {MAX_WORKERS}워커")
        print("=" * 80)
        
        total_start = time.time()
        
        self.initialize_population()
        
        for gen in range(GENERATIONS):
            gen_start = time.time()
            print(f"\n[세대 {gen + 1}/{GENERATIONS}]", end=" ", flush=True)
            self.evolve()
            
            best = self.history[-1]["best"]
            avg = self.history[-1]["avg"]
            worst = self.history[-1]["worst"]
            improvement = "🔥" if self.no_improvement_count == 0 else f"⏸{self.no_improvement_count}"
            gen_time = time.time() - gen_start
            
            # 거리 기반 평가는 profit 없음
            if USE_DISTANCE_HEURISTIC:
                print(f"→ Best:{best:,.0f} {improvement} Avg:{avg:,.0f} (거리 기반) ({gen_time:.1f}초)")
            else:
                # 기준선 대비 비교 (시뮬레이션 평가만)
                if self.best_individual.metrics and not self.best_individual.metrics.get("distance_based"):
                    current_profit = self.best_individual.metrics["profit"]
                    vs_baseline = current_profit - BASELINE_PROFIT
                    comparison = f"(기준+{vs_baseline:,.0f}✨)" if vs_baseline > 0 else f"(기준{vs_baseline:,.0f})"
                else:
                    comparison = ""
                
                print(f"→ Best:{best:,.0f} {improvement} Avg:{avg:,.0f} {comparison} ({gen_time:.1f}초)")
            
            # 최고 개체 상세 정보 (시뮬레이션 평가만)
            if self.best_individual.metrics and not self.best_individual.metrics.get("distance_based"):
                m = self.best_individual.metrics
                print(f"   💎 Profit={m['profit']:,.0f}원, 완성품={m['pair']}, " +
                      f"A={m['a_count']}, B={m['b_count']}, Balance={m['balance']:.1%}")
            
            # 조기 종료 (수렴)
            if self.no_improvement_count >= CONVERGENCE_THRESHOLD:
                print(f"\n✅ {CONVERGENCE_THRESHOLD}세대 동안 개선 없음 - 최적해 수렴 완료!")
                break
        
        total_time = time.time() - total_start
        avg_gen_time = total_time / len(self.history) if self.history else 0
        print(f"\n" + "=" * 80)
        print(f"⏱️  총 소요시간: {total_time:.1f}초 ({total_time/60:.1f}분)")
        print(f"📊 실행 세대: {len(self.history)}/{GENERATIONS} | 평균 {avg_gen_time:.1f}초/세대")
        print(f"🔬 총 평가: {POPULATION_SIZE * len(self.history):,}개 시뮬레이션")
        
        # 현재 배치와 비교
        if self.population[0].fitness is not None:
            first_profit = self.population[0].metrics.get('profit', 0) if self.population[0].metrics else 0
            best_profit = self.best_individual.metrics.get('profit', 0) if self.best_individual.metrics else 0
            
            print(f"\n📍 현재 배치 (검증): {first_profit:,.0f}원")
            print(f"🏆 최적 배치 (발견): {best_profit:,.0f}원")
            
            diff = best_profit - first_profit
            if abs(diff) < 100000:  # 10만원 미만 차이
                print(f"✅ 결론: 현재 배치가 이미 최적에 가깝습니다! (차이 {diff:+,.0f}원)")
            elif diff > 0:
                pct = (diff / first_profit * 100) if first_profit > 0 else 0
                print(f"✨ 개선 발견: +{diff:,.0f}원 ({pct:+.2f}%) 더 나은 배치를 찾았습니다!")
            else:
                pct = (diff / first_profit * 100) if first_profit > 0 else 0
                print(f"⚠️  경고: {diff:,.0f}원 ({pct:.2f}%) 더 나쁜 배치입니다 (오류 가능성)")
        
        print("=" * 80)
        
        return self.best_individual


def run_full_simulation(layout: Dict, name: str = "최적 배치"):
    """최적 배치로 전체 시뮬레이션 실행 (15일)"""
    print(f"\n{'=' * 70}")
    print(f"{name} - 전체 시뮬레이션 (15일) - 최종 검증")
    print("=" * 70)
    
    sim_core.reset_sim()
    
    cfg = sim_core.FactoryConfig(
        sim_time=FULL_SIM_TIME,  # 15일
        seed=20,
        feed_sequence=("ProdA", "ProdB"),
        amr_count=AMR_COUNT,
        machine_counts=MACHINE_COUNTS,
        machine_positions=layout
    )
    sim_core.simulate(cfg)
    
    # 결과 출력
    from kpi import information, profit
    information()
    profit(AMR_COUNT, MACHINE_COUNTS)
    
    return layout


if __name__ == "__main__":
    import sys
    
    # 최적화 방법 선택
    print("=" * 80)
    print("🎯 설비 배치 최적화 도구")
    print("=" * 80)
    print("선택하세요:")
    print("  1. Simulated Annealing (추천) - 빠르고 효과적")
    print("  2. Genetic Algorithm - 넓은 탐색")
    print("  3. 둘 다 실행 후 비교")
    print("=" * 80)
    
    choice = input("선택 (1/2/3, 기본=1): ").strip() or "1"
    
    results = {}
    
    if choice in ["1", "3"]:
        # Simulated Annealing 실행
        print("\n" + "=" * 80)
        print("🔥 Simulated Annealing 시작...")
        print("=" * 80)
        
        sa = SimulatedAnnealing()
        sa_layout, sa_fitness, sa_metrics = sa.run()
        results["SA"] = (sa_layout, sa_fitness, sa_metrics)
    
    if choice in ["2", "3"]:
        # 유전 알고리즘 실행
        print("\n" + "=" * 80)
        print("🧬 Genetic Algorithm 시작...")
        print("=" * 80)
        
        ga = GeneticAlgorithm()
        ga_best = ga.run()
        results["GA"] = (ga_best.layout, ga_best.fitness, ga_best.metrics)
    
    # 결과 비교
    print("\n" + "=" * 80)
    print("📊 최종 결과 비교")
    print("=" * 80)
    
    best_method = None
    best_profit = BASELINE_PROFIT
    best_layout = None
    
    print(f"📍 현재 배치: {BASELINE_PROFIT:,}원 (기준)")
    
    for method, (layout, fitness, metrics) in results.items():
        if metrics and not metrics.get("distance_based"):
            profit = metrics['profit']
            improvement = profit - BASELINE_PROFIT
            
            print(f"🔍 {method}: {profit:,.0f}원 ({improvement:+,.0f}원, {improvement/BASELINE_PROFIT*100:+.2f}%)")
            
            if profit > best_profit:
                best_profit = profit
                best_method = method
                best_layout = layout
    
    print("=" * 80)
    
    if best_method:
        print(f"\n🏆 최고 성능: {best_method} - {best_profit:,.0f}원")
        
        if best_profit - BASELINE_PROFIT > 50000:
            print("✨ 의미있는 개선 발견!")
        else:
            print("✅ 현재 배치가 이미 거의 최적입니다.")
        
        best = results[best_method]
        layout, fitness, metrics = best
        
        print("\n최적 설비 배치:")
        print("-" * 70)
        for stage in ["A", "B", "C", "D", "E"]:
            positions = layout[stage]
            print(f"{stage}: {positions}")
        
        # Python 코드로 출력
        print("\n" + "=" * 70)
        print("main.py에 적용할 코드:")
        print("=" * 70)
        print("machine_positions = {")
        for stage in ["A", "B", "C", "D", "E"]:
            positions = layout[stage]
            print(f'    "{stage}": {positions},')
        print("}")
        
        # 전체 시뮬레이션 실행 여부 확인
        print("\n" + "=" * 70)
        response = input("전체 시뮬레이션(15일)을 실행하시겠습니까? (y/n): ")
        if response.lower() == 'y':
            run_full_simulation(layout, f"{best_method} 최적 배치")
    else:
        print("\n✅ 현재 배치가 최적입니다!")
    
    print("\n최적화 완료!")
