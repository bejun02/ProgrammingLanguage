# 프로젝트 개선 및 수정 내역 요약 (Key Code 포함)

본 문서는 프로젝트의 주요 개선 사항과 핵심 구현 코드를 정리한 것입니다. 시행착오는 제외하고, **최종적으로 적용된 방식과 기술적 구현 내용**을 중심으로 기술합니다.

## 1. 공장 레이아웃 정밀화
### 수정 내역
- 설비 크기(`3x2`) 및 입출력 포트 위치 표준화 (Input: `x-2`, Output: `x+2`).
- Warehouse(`4,10`) 및 Stocker(`56,10`) 좌표 확정.

## 2. 고도화된 경로 탐색 시스템 (A* & Smoothing)
### 수정 내역
- 8방향 이동(대각선 포함)이 가능한 A* 알고리즘 적용.
- 유클리드 거리 휴리스틱 및 Line-of-sight 기반 Path Smoothing 적용.

## 3. Strict Path Caching (완전 경로 캐싱 및 강제)
### 수정 이유
- 실시간 계산 비용 제거 및 안전하지 않은 경로(설비 관통 등) 이동 원천 차단.
- `amr_count` 변경 시 발생하는 "Path not found" 에러 해결을 위해 캐시 범위 확장.

### 핵심 구현 코드
#### 1) `generate_paths.py`: 캐시 생성 범위 확장 (최대 30대 지원)
AMR 초기 위치(`Initial`)를 최대 30대분까지 포함하여, `Initial -> Output`, `Output -> Input`, `Input -> Output`의 모든 조합(약 5,340개 경로)을 미리 계산합니다.
```python
# generate_paths.py
# Initial AMR Positions (Support up to 30 AMRs for flexibility)
max_amr_count = 30
initial_positions = [(4.0, i * 0.1) for i in range(max_amr_count)]

# Collect all relevant points
potential_starts = all_outputs + all_inputs + initial_positions
potential_ends = all_outputs + all_inputs
# ... (precalculate_and_save 호출)
```

#### 2) `sim_core.py`: Strict Mode 강제 (실시간 계산 차단)
캐시에 경로가 없으면 `RuntimeError`를 발생시켜, 검증되지 않은 경로 이동을 방지합니다.
```python
# sim_core.py
def dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    '''경로 기반 거리 계산 (Strict Mode: 캐시 필수)'''
    if a == b: return 0.0
        
    # 1. Check Cache
    if (a, b) in global_variable.path_cache:
        path = global_variable.path_cache[(a, b)]
        return _calculate_path_length(path)
    
    # 2. Strict Error
    raise RuntimeError(f"Path not found in cache: {a} -> {b}. Strict caching is enabled.")
```

#### 3) `sim_core.py`: 상세 경로 데이터 저장
단순 출발/도착 좌표뿐만 아니라, 캐시된 전체 경로(`path`)를 기록에 남깁니다.
```python
# sim_core.py
def record_amr_run(..., path: List[Tuple[float,float]] = None):
    # path가 없으면 [frm, to]를 기본 경로로 사용 (직선)
    if not path:
        path = [frm, to]
    global_variable.amr_runs.setdefault(a.name, []).append((s, e, job.job_id, frm, to, loaded, path))
```

## 4. 시각화 보간 로직 개선 (Path Interpolation)
### 수정 이유
- 단순 직선 연결 시 시각화에서 벽을 뚫고 가는 오류 발생.
- 실제 저장된 경로를 따라가도록 보간 로직 개선.

### 핵심 구현 코드
#### `visualization.py`: 경로 기반 보간 로직
시간 $t$에 따른 위치를 계산할 때, 전체 경로(Waypoints)를 따라 이동 거리를 비례 배분합니다.
```python
# visualization.py
def _pos_loaded_at_t(runs, t):
    # ... (생략)
    if path and len(path) > 1:
        # 1. 전체 경로 길이 계산
        # ...
        # 2. 현재 진행률(progress)에 해당하는 위치(Target Distance) 탐색
        target_dist = total_len * progress
        current_dist = 0.0
        
        for i, seg_len in enumerate(dists):
            if current_dist + seg_len >= target_dist:
                # 해당 세그먼트 내에서 보간
                ratio = (target_dist - current_dist) / seg_len
                # ... (좌표 계산 후 반환)
```

## 5. 파라미터 보정
- **Cycle Time**: Product B Deposition 시간 2분 (`2*60`) 적용.
- **Profit**: `+ 0.011 * amr_count` 비용 항 추가.

## 6. 수익 최적화: Feed Cutoff (투입 중단 시점)
### 수정 이유
- 시뮬레이션 종료 직전에 투입된 제품은 완성되지 못하고 WIP(Work In Progress)로 남음.
- 수익 공식에서 `-5 × Feed` 항이 있으므로, 완성 못 할 제품을 투입하면 오히려 손해.

### 핵심 구현 코드
```python
# sim_core.py - generate_one_job()
def generate_one_job():
    # [Feed Cutoff] 남은 시간이 제품 완성에 필요한 최소 시간보다 작으면 투입 중단
    # 277분 = 16620초 (2회 사이클 완성에 필요한 최소 시간)
    MIN_COMPLETION_TIME = 16620  # seconds (277 minutes)
    remaining_time = global_variable.SIM_END - global_variable.now
    if remaining_time < MIN_COMPLETION_TIME:
        return None  # 투입 중단
    
    # ... (이하 기존 로직)
```

### 효과
- 기존: Feed=4283개, 완성품=4221개 → **62개 낭비**
- 개선 후: 낭비 감소 → **수익 +2만원**

## 7. 수익 및 운영 최적화: CONWIP (Constant Work In Process)
### 7.1 개요 및 이론적 배경
**CONWIP**은 공장 내에 투입되어 가공 중인 **활성 작업(WIP, Work In Process)의 총량을 일정 수준으로 유지**하는 생산 제어 방식입니다.
- **기존 Push 방식**: 설비 상태와 무관하게 자재를 밀어 넣음 → 공장 내 자재가 쌓이고 병목 발생.
- **CONWIP (Hybrid Pull)**: 공장 전체를 하나의 큰 시스템으로 보고, **"하나가 나가면 하나를 투입(One-in-One-out)"** 하는 원칙을 따릅니다.
- **Little's Law ($L = \lambda W$)**: 재공품($L$)이 일정할 때, 공정 시간($W$)을 줄이면 처리량($\lambda$)이 늘어납니다. CONWIP은 $L$을 고정하여 $W$가 폭증(Traffic Jam)하는 것을 막습니다.

### 7.2 구현 메커니즘 (`active_wip_count`)
`최종코드1`에서는 `data_structures.py`와 `sim_core.py`를 통해 이 로직을 정교하게 구현했습니다.

#### A. 전역 상태 추적
`active_wip_count` 변수는 현재 공장 바닥(Floor)에 있는 **'이동 중이거나 가공 중인 모든 제품의 수'**를 실시간으로 추적합니다.
- 창고(Warehouse)와 완성품 적재소(Stocker)에 있는 물건은 WIP에 포함되지 않습니다.

```python
# data_structures.py
@dataclass
class GlobalVariable:
    # ...
    active_wip_count: int = 0  # [핵심] 현재 공장 내 활성 Job 개수
```

#### B. 투입 제어 (Gating Mechanism)
`sim_core.py`의 `try_dispatch_from_warehouse_to_A` 함수는 원자재 투입의 관문(Gate) 역할을 합니다.
1. **조건 검사**: `active_wip_count`가 **설정된 상한선(`MAX_WIP = 50`)**보다 크거나 같으면 투입을 강제로 **중단(Return)**합니다.
2. **투입 실행**: WIP 여유가 있을 때만 새로운 작업을 창고에서 꺼냅니다(`pop`).
3. **카운트 증가**: 투입 즉시 `active_wip_count += 1`.

#### C. 출하 완료 (WIP 해제)
`sim_core.py`의 `drop_end` (Stocker 하차 시점)에서 작업이 시스템을 완전히 빠져나갔다고 간주합니다.
- **카운트 감소**: `active_wip_count -= 1`.
- **선순환**: 카운트가 감소하면, 대기 중이던 투입 함수가 다시 활성화되어 새로운 자재가 들어옵니다.

### 7.3 기대 효과 및 수익 개선
1. **Deadlock(교착 상태) 완전 차단**:
   - WIP 제한이 없으면 설비 A, B, C, D의 입력 버퍼가 모두 가득 차게 되고, AMR이 물건을 들고 있어도 내려놓을 곳이 없는 상황이 발생합니다. CONWIP은 이를 물리적으로 차단합니다.
2. **AMR 이동 효율 증가**:
   - 공장 내 이동하는 AMR의 수가 적절히 유지되므로, 교차로 병목이나 경로 충돌(Traffic Jam) 확률이 획기적으로 낮아집니다.
3. **Cycle Time 단축**:
   - 불필요한 대기 시간이 줄어들어 제품 하나가 완성되는 시간(Lead Time)이 빨라지고, 이는 곧 단위 시간당 **Profit 증가**로 직결됩니다.

---
**최종 상태**:
이 시스템은 **최대 30대**의 AMR이 **100% 검증된 경로**만 사용하여 안전하게 이동하며, 그 모습을 **시각적으로 정확하게** 사용자에게 보여줍니다. 또한 **Feed Cutoff 최적화**로 불필요한 원자재 낭비를 방지합니다.
