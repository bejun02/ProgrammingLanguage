"""
================================================================================
data_structures.py - 데이터 구조 정의 모듈
================================================================================
이 파일은 반도체 공장 시뮬레이션에 필요한 모든 데이터 클래스를 정의합니다.

주요 클래스:
- Job: 생산 제품 (ProdA, ProdB)
- Warehouse: 원자재 창고
- Machine: 공정 설비 (A~E)
- AMR: 자율이동로봇
- Stocker: 완제품 보관소
- FactoryConfig: 공장 설정
- GlobalVariable: 전역 상태 관리

공정 흐름:
    Warehouse → A(산화) → B(노광) → C(식각) → D(증착) → E(계측) → Stocker
                 ↑                                              │
                 └──────────── 2사이클 반복 ────────────────────┘
================================================================================
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Any


# ================================================================================
# Job 클래스 - 생산 제품 (FOUP) 정보
# ================================================================================
@dataclass
class Job:
    """
    생산 제품(FOUP) 정보를 담는 클래스
    
    반도체 공정에서 하나의 제품이 A→B→C→D→E 공정을 2회 반복하며,
    이 클래스는 해당 제품의 상태를 추적합니다.
    
    Attributes:
        job_id (str): 제품 고유 ID (예: "ProdA-0001", "ProdB-0002")
        product (str): 제품 종류 ("ProdA" 또는 "ProdB")
        reserved (bool): AMR에 의해 예약되었는지 여부
                        - True: 이미 AMR이 픽업 예약함 (중복 예약 불가)
                        - False: 예약 가능 상태
        in_transit (bool): 현재 AMR에 의해 이송 중인지 여부
                          - True: AMR이 들고 이동 중
                          - False: 설비에 있거나 대기 중
        cycle_idx (int): 현재 사이클 인덱스 (0: 첫 번째, 1: 두 번째)
        max_cycles (int): 최대 사이클 수 (기본값: 2, 과제 조건 고정)
        pending_stage (str): 다음에 가야 할 스테이지 (중복 계산 방지용)
    """
    job_id: str                              # 제품 고유 ID (예: "ProdA-0001")
    product: str                             # 제품 종류 (ProdA/ProdB)
    reserved: bool = False                   # AMR 예약 여부
    in_transit: bool = False                 # 이송 중 여부
    cycle_idx: int = 0                       # 현재 사이클 (0 또는 1)
    max_cycles: int = 1                      # 최대 반복 횟수 (과제: 2회)
    pending_stage: Optional[str] = None      # 다음 목적지 스테이지


# ================================================================================
# Warehouse 클래스 - 원자재 창고
# ================================================================================
@dataclass
class Warehouse:
    """
    원자재 창고 클래스
    
    시뮬레이션 시작 시 빈 상태로 시작하며, 필요할 때마다 원자재(Job)가 
    생성되어 이 창고에 입고됩니다. AMR이 A공정으로 이송할 때 출고됩니다.
    
    Attributes:
        name (str): 창고 이름 (예: "WH-01")
        xy (Tuple[float, float]): 창고 위치 좌표 - 고정값 (4, 10)
        inventory (List[Job]): 현재 보관 중인 원자재 목록 (FIFO 방식)
    
    위치: 공장 레이아웃의 왼쪽에 위치 (4, 10)
    """
    name: str                                           # 창고 이름
    xy: Tuple[float, float]                             # 창고 위치 (4, 10) 고정
    inventory: List[Job] = field(default_factory=list)  # 보관 중인 원자재 목록

    def put(self, job: Job):
        """
        원자재를 창고에 입고
        
        Args:
            job (Job): 입고할 제품
        
        Note:
            - generate_one_job()에서 제품 생성 시 호출됨
            - inventory 리스트 끝에 추가 (FIFO를 위해)
        """
        self.inventory.append(job)
        #print(f"{self.name}: {job.job_id} 입고 (재고 {len(self.inventory)}개)")

    def pop(self) -> Optional[Job]:
        """
        원자재를 창고에서 출고 (FIFO - 선입선출)
        
        Returns:
            Job: 출고된 제품, 재고가 없으면 None
        
        Note:
            - try_dispatch_from_warehouse_to_A()에서 호출
            - 가장 먼저 들어온 제품이 먼저 출고됨
        """
        if not self.inventory:
            return None
        job = self.inventory.pop(0)  # 첫 번째 항목 출고 (FIFO)
        #print(f"{self.name}: {job.job_id} 출고 (재고 {len(self.inventory)}개)")
        return job


# ================================================================================
# Machine 클래스 - 공정 설비
# ================================================================================
@dataclass
class Machine:
    """
    공정 설비 클래스
    
    반도체 제조의 각 공정(A:산화, B:노광, C:식각, D:증착, E:계측)을 수행하는 설비.
    각 설비는 입력 포트와 출력 포트를 가지며, 한 번에 하나의 제품만 가공합니다.
    
    Attributes:
        name (str): 설비 이름 (예: "A-1", "B-2")
        stage (str): 공정 스테이지 ("A", "B", "C", "D", "E")
        xy (Tuple): 설비 중심 좌표 (과제에서 30개 고정 좌표 중 선택)
        process_time (float): 기본 공정 시간
        
        input_buf (List[Job]): 입력 버퍼 - 가공 대기 중인 제품들
        input_capacity (int): 입력 버퍼 용량 (기본 1개)
        input_reserved (bool): 입력 슬롯 예약 여부 (AMR 도착 전 선점)
        
        processing_job (Job): 현재 가공 중인 제품
        output_buf (Job): 출력 버퍼 - 가공 완료 후 AMR 대기 중인 제품
        waiting_done (Job): output_buf 꽉 찼을 때 설비 내부 대기 제품
        
        port_offset (int): 포트와 설비 중심 간 거리 (2m)
        input_port (Tuple): 입력 포트 좌표 (설비 왼쪽, x-2)
        output_port (Tuple): 출력 포트 좌표 (설비 오른쪽, x+2)
    
    설비 내부 흐름:
        [입력포트] → [input_buf] → [가공중] → [output_buf] → [출력포트]
                        대기열    processing_job   AMR 픽업 대기
    
    설비 크기: 3m x 2m (과제 조건)
    """
    name: str                                              # 설비 이름 (예: "A-1")
    stage: str                                             # 공정 스테이지 (A~E)
    xy: Tuple[float, float]                                # 설비 중심 좌표
    process_time: float                                    # 기본 공정 시간

    # === 입력 버퍼 관련 ===
    input_buf: List["Job"] = field(default_factory=list)   # 입력 버퍼 (대기열)
    input_capacity: int = 1                                # 입력 버퍼 용량
    input_reserved: bool = False                           # 입력 슬롯 예약 상태
    
    # === 가공/출력 관련 ===
    processing_job: Optional["Job"] = None                 # 현재 가공 중인 제품
    output_buf: Optional["Job"] = None                     # 출력 버퍼 (가공 완료품)
    waiting_done: Optional["Job"] = None                   # output_buf 꽉참 시 대기

    # === 포트 위치 관련 ===
    port_offset: int = 2                                   # 포트 오프셋 (2m)
    input_port: Tuple[float, float] = field(init=False)    # 입력 포트 좌표
    output_port: Tuple[float, float] = field(init=False)   # 출력 포트 좌표

    def __post_init__(self):
        """
        설비 생성 후 자동으로 입출력 포트 좌표 계산
        
        예시 (설비 중심이 (14, 3)일 때):
            - input_port = (12, 3)   ← 왼쪽으로 2m
            - output_port = (16, 3)  ← 오른쪽으로 2m
        """
        x, y = self.xy
        self.input_port = (x - self.port_offset, y)   # 왼쪽 = 입력
        self.output_port = (x + self.port_offset, y)  # 오른쪽 = 출력


# ================================================================================
# AMR 클래스 - 자율이동로봇
# ================================================================================
@dataclass
class AMR:
    """
    AMR(Autonomous Mobile Robot) - 자율이동로봇 클래스
    
    공정 간 제품(FOUP)을 이송하는 로봇. 
    창고→A, A→B, ... E→Stocker 등의 경로로 제품을 운반합니다.
    
    Attributes:
        name (str): AMR 이름 (예: "AMR-01")
        xy (Tuple): 현재 위치 좌표
        speed (float): 이동 속도 (1 m/s 고정)
        free_time (float): 다음 작업 가능 시점
        planned_xy (Tuple): 현재 작업 완료 후 도착 예정 위치
        tasks (List[Dict]): 예약된 작업 목록
    
    AMR 작업 흐름:
        1. reserve_amr()로 예약
        2. 픽업 위치로 이동 (depart_at → arrive_pick)
        3. 적재 10초 (arrive_pick → depart_pick)
        4. 드롭 위치로 이동 (depart_pick → arrive_drop)
        5. 하역 10초 (arrive_drop → depart_drop)
        6. 작업 완료 → 다음 예약 대기
    
    과제 조건:
        - 속도: 1 m/s
        - 적재/하역: 각 10초
        - AMR 간 충돌 미고려
        - 최대 30대
    """
    name: str                                              # AMR 이름
    xy: Tuple[float, float]                                # 현재 위치
    speed: float                                           # 이동 속도 (1 m/s)
    free_time: float = 0.0                                 # 작업 가능 시점
    planned_xy: Optional[Tuple[float, float]] = None       # 작업 완료 후 예정 위치
    tasks: List[Dict[str, Any]] = field(default_factory=list)  # 예약된 작업 목록


# ================================================================================
# Stocker 클래스 - 완제품 보관소
# ================================================================================
@dataclass
class Stocker:
    """
    완제품 보관소 (Stocker) 클래스
    
    2사이클(A→B→C→D→E×2) 완료 제품이 최종 보관되는 장소.
    ProductA와 ProductB를 분리 보관하며, 이 수량으로 Profit을 계산합니다.
    
    Attributes:
        name (str): Stocker 이름 (예: "STK-01")
        xy (Tuple): 위치 좌표 - 고정값 (56, 10)
        stored_jobs_A (List[str]): 보관 중인 ProdA ID 목록
        stored_jobs_B (List[str]): 보관 중인 ProdB ID 목록
    
    Profit 계산에 사용:
        Profit = [100 × min(A완성품, B완성품) - 5 × 총출고수] / [설비비용 + AMR비용]
    
    위치: 공장 레이아웃의 오른쪽 끝 (56, 10)
    """
    name: str                                                      # Stocker 이름
    xy: Tuple[float, float]                                        # 위치 (56, 10)
    stored_jobs_A: List[str] = field(default_factory=list)         # ProdA 목록
    stored_jobs_B: List[str] = field(default_factory=list)         # ProdB 목록
    
    def store(self, job_id: str):
        """
        완제품을 Stocker에 보관
        
        Args:
            job_id (str): 제품 ID (예: "ProdA-0001")
        
        분류 기준:
            - "ProdA-XXXX" → stored_jobs_A에 저장
            - "ProdB-XXXX" → stored_jobs_B에 저장
        """
        #print("Store에 저장되는 제품", job_id)
        productType = job_id.split("-")[0]  # "ProdA" 또는 "ProdB"
        
        if "A" in productType:
            self.stored_jobs_A.append(job_id)
        elif "B" in productType:
            self.stored_jobs_B.append(job_id)
        else:
            print("ERROR: 알 수 없는 제품 타입")
            
        #print(f"보관 중 ProductA (총 {len(self.stored_jobs_A)}개)")
        #print(f"보관 중 ProductB (총 {len(self.stored_jobs_B)}개)")

    def list_jobs_A(self) -> List[str]:
        """보관 중인 ProdA 목록 반환 (Profit 계산용)"""
        return self.stored_jobs_A.copy()
    
    def list_jobs_B(self) -> List[str]:
        """보관 중인 ProdB 목록 반환 (Profit 계산용)"""
        return self.stored_jobs_B.copy()


# ================================================================================
# FactoryConfig 클래스 - 공장 시뮬레이션 설정
# ================================================================================
@dataclass
class FactoryConfig:
    """
    공장 시뮬레이션 설정 클래스
    
    시뮬레이션 실행에 필요한 모든 설정값을 담고 있습니다.
    main.py에서 이 객체를 생성하여 simulate() 함수에 전달합니다.
    
    === 고정값 (과제 조건) ===
    - warehouse_xy: (4, 10)
    - stocker_xy: (56, 10)
    - amr_speed: 1 m/s
    - job_cycles: 2회
    - amr_load_time/unload_time: 각 10초
    - process_times_by_product_cycle: 제품별 공정시간
    
    === 최적화 대상 변수 ===
    - machine_counts: 공정별 설비 대수
    - machine_positions: 설비 위치 (30개 좌표 중 선택)
    - amr_count: AMR 대수 (최대 30대)
    
    제품별 공정시간 (분):
    ┌──────────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
    │          │ A1 │ B1 │ C1 │ D1 │ E1 │ A2 │ B2 │ C2 │ D2 │ E2 │
    ├──────────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
    │ ProdA    │ 15 │ 15 │ 15 │ 15 │ 15 │ 15 │ 15 │ 15 │ 15 │ 15 │
    │ ProdB    │  5 │ 40 │ 25 │ 25 │ 15 │ 10 │ 20 │ 10 │ 10 │ 15 │
    └──────────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘
    """
    # === 고정값 (과제 조건) ===
    warehouse_xy: Tuple[float, float] = (4, 10)           # 원자재 창고 위치
    stocker_xy: Tuple[float, float] = (56, 10)            # 완제품 보관소 위치
    amr_speed: float = 1.0                                # AMR 속도 (m/s)
    amr_positions: Optional[List[Tuple[float, float]]] = None  # AMR 초기 위치
    job_cycles: int = 2                                   # 사이클 수 (2회 반복)
    
    # === 조절 가능값 ===
    sim_time: float = 3600.0                              # 시뮬레이션 시간 (초)
    feed_sequence: Tuple[str, ...] = ("ProdA", "ProdB")   # 제품 투입 순서
    
    # 공정별 설비 대수 (최적화 대상)
    machine_counts: Dict[str, int] = field(
        default_factory=lambda: {"A": 1, "B": 1, "C": 1, "D": 1, "E": 1}
    )
    
    # 기본 공정 시간 (실제로는 아래 테이블 사용)
    process_times: Dict[str, float] = field(
        default_factory=lambda: {"A": 1, "B": 1, "C": 1, "D": 1, "E": 1}
    )
    
    # === 제품별/사이클별 공정시간 (초 단위) - 과제 조건 고정 ===
    process_times_by_product_cycle: Dict[str, Dict[int, Dict[str, float]]] = field(
        default_factory=lambda: {
            # ProdA: 모든 공정 15분(900초)
            "ProdA": {
                0: {"A": 15*60, "B": 15*60, "C": 15*60, "D": 15*60, "E": 15*60},
                1: {"A": 15*60, "B": 15*60, "C": 15*60, "D": 15*60, "E": 15*60},
            },
            # ProdB: 공정별로 상이 (README 기준)
            # 1사이클: A=5, B=40, C=25, D=2, E=5
            # 2사이클: A=10, B=10, C=5, D=10, E=15
            "ProdB": {
                0: {"A": 5*60, "B": 40*60, "C": 25*60, "D": 2*60, "E": 5*60},
                1: {"A": 10*60, "B": 10*60, "C": 5*60, "D": 10*60, "E": 15*60},
            },
        }
    )
    
    # 설비 위치 좌표 (main.py에서 설정, 30개 좌표 중 선택)
    machine_positions: Optional[Dict[str, List[Tuple[float, float]]]] = None
    machine_names: Optional[Dict[str, List[str]]] = None  # 설비 이름 (선택)
    
    jobs_by_product: Dict[str, int] = field(default_factory=dict)
    shuffle_product_feeds: bool = True                    # 제품 투입 순서 섞기
    seed: int = 42                                        # 랜덤 시드
    
    # === AMR 관련 (고정값) ===
    amr_load_time: float = 10                             # 적재 시간 (10초)
    amr_unload_time: float = 10                           # 하역 시간 (10초)
    amr_count: int = 1                                    # AMR 대수 (최적화 대상)


# ================================================================================
# GlobalVariable 클래스 - 전역 상태 관리
# ================================================================================
class GlobalVariable:
    """
    시뮬레이션 전역 상태 관리 클래스
    
    시뮬레이션 중 공유되는 모든 상태를 관리합니다.
    config.py에서 인스턴스 생성 후 다른 모듈에서 import하여 사용합니다.
    
    주요 속성:
    - now: 현재 시뮬레이션 시간
    - pq: 이벤트 우선순위 큐 (힙)
    - ROUTE: 공정 순서 ["A","B","C","D","E"]
    - MACHINES: 스테이지별 설비 목록
    - AMRS: AMR 목록
    - FEED_COUNT_A/B: 제품별 투입 수
    - machine_runs/amr_runs: 기록 데이터 (시각화용)
    """
    
    def __init__(self):
        """전역 변수 초기화"""
        self.init_all()

    def init_all(self):
        """
        모든 전역 변수 초기화
        시뮬레이션 시작 시 또는 재실행 시 호출됩니다.
        """
        # === 시뮬레이션 시간 관리 ===
        self.now = 0.0              # 현재 시뮬레이션 시간
        self._seq = 0               # 이벤트 순서 (동시 이벤트 정렬용)
        self.pq = []                # 이벤트 우선순위 큐 (heapq)

        # === 공정 순서 (고정) ===
        self.ROUTE = ["A", "B", "C", "D", "E"]  # 산화→노광→식각→증착→계측

        # === 공장 구성 요소 ===
        self.MACHINES: Dict[str, List[Machine]] = {}       # 스테이지별 설비
        self.AMRS: List[AMR] = []                          # AMR 목록
        self.STAGE_Q: Dict[str, List[Job]] = {s: [] for s in self.ROUTE}
        self.STOCKERS: Dict[str, Stocker] = {}             # Stocker
        self.WAREHOUSE: Optional[Warehouse] = None          # 원자재 창고

        # === 설정 참조 ===
        self.CURRENT_CFG: Optional[FactoryConfig] = None   # 현재 설정
        self.SIM_END: float = float("inf")                 # 시뮬레이션 종료 시간

        # === 라운드로빈 인덱스 (설비 선택용) ===
        self.ROUND_ROBIN_IDX: Dict[str, int] = {s: 0 for s in self.ROUTE}
        
        # === AMR 기본 시간 (고정) ===
        self.DEFAULT_AMR_LOAD = 10      # 적재 시간 (10초)
        self.DEFAULT_AMR_UNLOAD = 10    # 하역 시간 (10초)

        # === 생산 통계 ===
        self.FEED_SEQ: List[str] = []   # 제품 투입 순서
        self.FEED_IDX: int = 0          # 현재 투입 인덱스
        self.FEED_COUNT = 0             # 총 투입 수
        self.FEED_COUNT_A = 0           # ProdA 투입 수
        self.FEED_COUNT_B = 0           # ProdB 투입 수

        # === 기록 데이터 (시각화/분석용) ===
        self.machine_runs: Dict[str, List[Tuple[float, float, str, str]]] = {}
        self.job_runs: Dict[str, List[Tuple[str, float, float, str]]] = {}
        self.amr_runs: Dict[str, List[Tuple[float, float, str, Tuple[float,float], Tuple[float,float], bool]]] = {}
        self.amr_waits: Dict[str, List[Tuple[float, float, str, str, Tuple[float,float]]]] = {}

    def reset(self):
        """시나리오 재실행을 위한 완전 초기화"""
        self.init_all()


# ================================================================================
# PREV_OF - 공정 간 의존 관계 정의
# ================================================================================
# 각 스테이지의 이전 스테이지를 정의합니다.
# pull_from_prev_to() 함수에서 이전 설비에서 제품을 당겨올 때 사용합니다.
#
# 흐름:
#     WH(창고) → A → B → C → D → E → Stocker
#                ↑                    │
#                └──── 2사이클 반복 ──┘
PREV_OF = {
    "WH": ["A"],         # 창고는 A로 공급
    "A":  ["E", "WH"],   # A는 E(2사이클 반복)와 WH(신규)에서 받음
    "B":  ["A"],         # B는 A에서만 받음
    "C":  ["B"],         # C는 B에서만 받음
    "D":  ["C"],         # D는 C에서만 받음
    "E":  ["D"],         # E는 D에서만 받음
}