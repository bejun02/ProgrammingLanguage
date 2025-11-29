from config import global_variable
from typing import Dict

def information():
    print("=== 생산 요약 ===")
    print(f"Stocker K | Out제품 수: {global_variable.FEED_COUNT}")
    print(f"  - ProdA: {global_variable.FEED_COUNT_A}")
    print(f"  - ProdB: {global_variable.FEED_COUNT_B}")
    print("A 총 보관 수:", len(global_variable.STOCKERS["STK-01"].list_jobs_A()))
    print("B 총 보관 수:", len(global_variable.STOCKERS["STK-01"].list_jobs_B()))

def profit(amr_count: int, machine_counts: Dict):
    """
    Profit = [[100 * Min(OutputA, OutputB)] - 5 * (InputA + InputB)]
             / [fac - 0.011 * AMR] * 100000

    fac = 4(산화공정수) + 9(노광공정수) + 8(식각공정수)
          + 8(증착공정수) + 5.5(계측공정수)

    machine_counts.values() 는 위 순서대로 들어온다고 가정함.
    """

    # fac 계산 (산화, 노광, 식각, 증착, 계측 순서)
    weights = [4, 9, 8, 8, 5.5]
    fac = sum(cnt * w for cnt, w in zip(machine_counts.values(), weights))

    # Output, Input 계산
    output_A = len(global_variable.STOCKERS["STK-01"].list_jobs_A())
    output_B = len(global_variable.STOCKERS["STK-01"].list_jobs_B())
    input_A = global_variable.FEED_COUNT_A
    input_B = global_variable.FEED_COUNT_B

    # 분자: 100 * Min(OutputA, OutputB) - 5 * (InputA + InputB)
    numerator = 100 * min(output_A, output_B) - 5 * (input_A + input_B)

    # 분모: fac - 0.011 * AMR
    denominator = fac + 0.011 * amr_count
    if denominator <= 0:
        print("profit: (fac + 0.011 * AMR)가 0 이하입니다.")
        return

    profit_value = numerator / denominator * 100000
    print(f"profit: {profit_value:.2f}원")