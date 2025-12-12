# 필요한 패키지: pulp
# 설치: pip install pulp

import pulp

# -----------------------------
# 데이터 정의
# -----------------------------

MACHINES = ["A", "B", "C", "D", "E"]

# 설비 설치 비용
install_cost = {
    "A": 4.0,
    "B": 9.0,
    "C": 8.0,
    "D": 8.0,
    "E": 5.5,
}

# 시간 제약
TOTAL_TIME = 21600.0   # 각 설비당 사용 가능한 총 시간 (분)
MAX_MACHINES = 30      # 설비 총 대수 상한

# 제품 A: A,B,C,D,E 각각 두 번 × 15분 = 30분
time_A = {
    "A": 30.0,
    "B": 30.0,
    "C": 30.0,
    "D": 30.0,
    "E": 30.0,
}

# 제품 B:  공정 시간 합산
time_B = {
    "A": 15.0,
    "B": 50.0,
    "C": 30.0,
    "D": 12.0,
    "E": 20.0,
}

# AMR 비용 (네가 실제 상황에 맞게 설정)
AMR_COST = 100.0


# -----------------------------
# Dinkelbach + MILP로 최적해 탐색
# -----------------------------

def solve_ab_production(
    amr_cost=AMR_COST,
    max_iter=20,
    tol=1e-6,
    verbose=True
):
    """
    Dinkelbach 알고리즘으로
    Profit = f / g 를 최대화하는 설비 구성 및 생산량을 찾는다.

    f = 100*S - 5*(A+B)
    g = sum(install_cost[m] * x[m]) + amr_cost

    반환: dict (해, 이익 등)
    """
    lambda_val = 0.0  # 초기 λ
    best_solution = None
    best_profit = None

    for it in range(1, max_iter + 1):
        # MILP 모델 생성
        prob = pulp.LpProblem(f"AB_Production_iter_{it}", pulp.LpMaximize)

        # 결정변수
        # 설비 대수: 정수 변수
        x = {
            m: pulp.LpVariable(f"x_{m}", lowBound=0, cat="Integer")
            for m in MACHINES
        }
        # 생산량: 연속 변수 (필요하다면 Integer로 바꿔도 됨)
        A = pulp.LpVariable("A", lowBound=0)
        B = pulp.LpVariable("B", lowBound=0)
        S = pulp.LpVariable("S", lowBound=0)

        # 제약식 1: 설비 총 대수 제한
        prob += pulp.lpSum(x[m] for m in MACHINES) <= MAX_MACHINES, "TotalMachines"

        # 제약식 2: 생산을 하려면 최소 한 대는 설치 (0/0 방지용)
        prob += pulp.lpSum(x[m] for m in MACHINES) >= 1, "AtLeastOneMachine"

        # 제약식 3: 각 설비의 시간 제약
        for m in MACHINES:
            prob += (
                time_A[m] * A + time_B[m] * B
                <= TOTAL_TIME * x[m]
            ), f"Capacity_{m}"

        # 제약식 4: 세트 수는 A, B 각각을 초과할 수 없음
        prob += S <= A, "Set_le_A"
        prob += S <= B, "Set_le_B"

        # 목적함수 구성: f - λ g
        f_expr = 100.0 * S - 5.0 * (A + B)
        g_expr = pulp.lpSum(install_cost[m] * x[m] for m in MACHINES) + amr_cost

        prob += f_expr - lambda_val * g_expr, "Dinkelbach_Objective"

        # 풀기
        solver = pulp.PULP_CBC_CMD(msg=0)  # msg=1로 하면 로그 출력
        prob.solve(solver)

        status = pulp.LpStatus[prob.status]
        if status != "Optimal":
            if verbose:
                print(f"[Iter {it}] Solver status: {status}, 최적해를 찾지 못함.")
            break

        # 해 추출
        A_val = pulp.value(A)
        B_val = pulp.value(B)
        S_val = pulp.value(S)
        x_val = {m: pulp.value(x[m]) for m in MACHINES}

        f_val = 100.0 * S_val - 5.0 * (A_val + B_val)
        g_val = sum(install_cost[m] * x_val[m] for m in MACHINES) + amr_cost

        if g_val <= 0:
            if verbose:
                print(f"[Iter {it}] 분모 g가 0 이하 (g={g_val}), 중단.")
            break

        profit = f_val / g_val

        if verbose:
            print(f"[Iter {it}] f={f_val:.4f}, g={g_val:.4f}, λ={lambda_val:.6f}, Profit={profit:.6f}")

        # 최적해 갱신
        if best_profit is None or profit > best_profit:
            best_profit = profit
            best_solution = {
                "A": A_val,
                "B": B_val,
                "S": S_val,
                "x": x_val,
                "f": f_val,
                "g": g_val,
                "profit": profit,
                "lambda": lambda_val,
                "iter": it,
            }

        # Dinkelbach 종료 조건: f - λ g ≈ 0
        improvement = f_val - lambda_val * g_val
        if abs(improvement) < tol:
            if verbose:
                print(f"[Iter {it}] |f - λg| = {abs(improvement):.6e} < tol, 수렴.")
            break

        # λ 갱신
        lambda_val = profit

    return best_solution


if __name__ == "__main__":
    sol = solve_ab_production(amr_cost=AMR_COST, max_iter=30, tol=1e-6, verbose=True)

    if sol is not None:
        print("\n===== 최적 해 요약 =====")
        print(f"반복 횟수(iter): {sol['iter']}")
        print(f"최대 Profit: {sol['profit']:.6f}")
        print(f"f (분자): {sol['f']:.4f}")
        print(f"g (분모): {sol['g']:.4f}")
        print(f"A 생산량: {sol['A']:.4f}")
        print(f"B 생산량: {sol['B']:.4f}")
        print(f"세트 수 S: {sol['S']:.4f}")
        print("설비 대수:")
        for m in MACHINES:
            print(f"  {m}: {sol['x'][m]:.0f}")
    else:
        print("해를 찾지 못했습니다.")
