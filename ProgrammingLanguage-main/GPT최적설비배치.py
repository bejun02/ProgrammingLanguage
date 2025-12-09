import pulp

# ============================================================
# 0. 기본 설정
# ============================================================

# 웨어하우스 투출 포트, 스톡커 투입 포트 좌표
WH_OUT = (4, 10)
STOCK_IN = (56, 10)

# 설비 종류별 개수
MACHINE_COUNTS = {
    "q": 5,
    "w": 8,
    "e": 6,
    "r": 5,
    "t": 5,
}

# 설비 설치 가능 슬롯 정의 (슬롯 ID, 중심좌표 x, y)
slot_list = []
slot_id = 0
for x in [14, 22, 30, 38, 46]:
    for y in [3, 5, 7, 13, 15, 17]:
        slot_list.append((slot_id, x, y))
        slot_id += 1

slot_ids = [s[0] for s in slot_list]
slot_coord = {s[0]: (s[1], s[2]) for s in slot_list}  # slot_id -> (x, y)

# 설비 종류별 “이상적인” 중심 x좌표 (flow-line 구조 유도용)
ideal_x = {
    "q": 14,
    "w": 22,
    "e": 30,
    "r": 38,
    "t": 46,
}
ideal_y = 10  # 중앙 높이

# ============================================================
# 1. 설비 인스턴스 생성 (q1, q2, ..., t5)
# ============================================================

items = []        # 개별 설비 인스턴스 이름
item_type = {}    # 인스턴스 -> 설비 종류(q/w/e/r/t)

for m_type, count in MACHINE_COUNTS.items():
    for i in range(1, count + 1):
        name = f"{m_type}{i}"
        items.append(name)
        item_type[name] = m_type

print("총 설비 대수:", len(items))  # 29여야 함

# ============================================================
# 2. 비용 함수 정의 (포트 위치 반영)
# ============================================================

def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

# cost[(item, slot_id)] = 해당 설비 인스턴스를 그 슬롯에 배치했을 때의 비용
cost = {}

for item in items:
    m_type = item_type[item]

    for s_id in slot_ids:
        sx, sy = slot_coord[s_id]

        # 슬롯 중심이 (sx, sy)일 때
        in_port  = (sx - 2, sy)  # 투입 포트
        out_port = (sx + 2, sy)  # 투출 포트

        # 설비 종류별로 다른 기준으로 비용 정의
        if m_type == "q":
            # q는 웨어하우스 출고 포트에서 q의 투입 포트까지 거리
            base = manhattan(WH_OUT, in_port)
        elif m_type == "t":
            # t는 t의 투출 포트에서 스톡커 투입 포트까지 거리
            base = manhattan(out_port, STOCK_IN)
        else:
            # 중간 설비(w, e, r)는 flow-line 형태 유지
            ix = ideal_x[m_type]
            iy = ideal_y
            dist_x = abs(sx - ix)
            dist_y = abs(sy - iy)
            base = 2 * dist_x + 1 * dist_y  # x축을 더 강하게 패널티

        cost[(item, s_id)] = base

# ============================================================
# 3. MIP 모델 구성 (할당 문제)
# ============================================================

prob = pulp.LpProblem("Initial_Layout_Assignment_With_Ports", pulp.LpMinimize)

# 이진 변수: assign[item, slot] = 1 이면 item을 slot에 배치
x_var = pulp.LpVariable.dicts(
    "assign",
    ((item, s_id) for item in items for s_id in slot_ids),
    lowBound=0,
    upBound=1,
    cat="Binary",
)

# (1) 각 설비 인스턴스는 정확히 1개의 슬롯에 배치
for item in items:
    prob += pulp.lpSum(x_var[(item, s_id)] for s_id in slot_ids) == 1, f"OneSlot_{item}"

# (2) 각 슬롯에는 최대 1대의 설비만 설치 (슬롯 30개 중 1개는 비게 됨)
for s_id in slot_ids:
    prob += pulp.lpSum(x_var[(item, s_id)] for item in items) <= 1, f"AtMostOneMachine_{s_id}"

# (3) 목적함수: 전체 비용(포트 기준 거리 기반) 최소화
prob += pulp.lpSum(
    cost[(item, s_id)] * x_var[(item, s_id)]
    for item in items for s_id in slot_ids
), "TotalCost"

# ============================================================
# 4. 최적화 수행
# ============================================================

solver = pulp.PULP_CBC_CMD(msg=1)  # 로그 보고 싶으면 msg=1
result_status = prob.solve(solver)
print("Solver status:", pulp.LpStatus[result_status])

# ============================================================
# 5. 해석: 타입별로 좌표 리스트 출력 (딕셔너리 형식)
# ============================================================

# 슬롯별로 어떤 타입이 들어갔는지 기록
slot_assignment = {s_id: None for s_id in slot_ids}

for item in items:
    for s_id in slot_ids:
        if pulp.value(x_var[(item, s_id)]) > 0.5:
            m_type = item_type[item]
            slot_assignment[s_id] = m_type
            break

# 타입별 중심좌표 리스트 구성
layout_by_type = {m_type: [] for m_type in MACHINE_COUNTS.keys()}

for s_id, (sx, sy) in slot_coord.items():
    m_type = slot_assignment[s_id]
    if m_type is not None:
        layout_by_type[m_type].append((sx, sy))

# 보기 좋게 정렬 (x, y 기준)
for m_type in layout_by_type:
    layout_by_type[m_type].sort(key=lambda p: (p[0], p[1]))

# 최종 딕셔너리 형태로 출력
print("\nlayout = {")
for m_type in sorted(layout_by_type.keys()):
    print(f'    "{m_type}": {layout_by_type[m_type]},')
print("}")
