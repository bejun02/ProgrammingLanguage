from config import global_variable
from typing import Dict

def information():
    print("=== 생산 요약 ===")
    print(f"Stocker K | Out제품 수: {global_variable.FEED_COUNT}")
    print(f"  - ProdA: {global_variable.FEED_COUNT_A}")
    print(f"  - ProdB: {global_variable.FEED_COUNT_B}")
    print("A 총 보관 수:", len(global_variable.STOCKERS["STK-01"].list_jobs_A()))
    print("B 총 보관 수:", len(global_variable.STOCKERS["STK-01"].list_jobs_B()))

def profit(amr_count,machine_counts:Dict):
    parameter = [4,9,8,8,5.5]
    t = 0
    for i in machine_counts.values():
        t += i*parameter[i]
    p = (100*min(len(global_variable.STOCKERS["STK-01"].list_jobs_A()),len(global_variable.STOCKERS["STK-01"].list_jobs_B())) - 5*(global_variable.FEED_COUNT_A+global_variable.FEED_COUNT_B)) 
    profit = p / (t-0.011*amr_count)
    print("profit: ", round(profit,2)*100000,"원")