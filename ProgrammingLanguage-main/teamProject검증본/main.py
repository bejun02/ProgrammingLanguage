import sim_core
from sim_core import *
from kpi import information,profit
from config import global_variable
from visualization import animate_from_amr_runs

# A(산화),B(노광),C(식각),D(증착),E(계측)
# 제품 A : ProdA / 제품 B : ProdB
# Stocker : STK-01
# warehouse : WH-01
if __name__ == "__main__":
    # 설비 위치 좌표
    machine_positions = {
        "A": [(14, 3), (14, 5), (14, 7), (14, 13), (14, 15)],   # A공정: 5대
        "B": [(22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17), (30, 3), (30, 5)],   # B공정: 8대
        "C": [(30, 7), (30, 13), (30, 15), (30, 17), (38, 3), (38, 5)],   # C공정: 6대
        "D": [(38, 7), (38, 13), (38, 15), (38, 17), (46, 3)],   # D공정: 5대
        "E": [(46, 5), (46, 7), (46, 13), (46, 15), (46, 17)],   # E공정: 5대
    }
    # 설비 개수 (좌표와 맞춤: 29대)
    machine_counts={"A":5,"B":8,"C":6,"D":5,"E":5}
    # AMR 대수
    amr_count = 4
    cfg = sim_core.FactoryConfig(sim_time=1296000, seed=20, feed_sequence=("ProdA","ProdB"), amr_count=amr_count, machine_counts=machine_counts,machine_positions= machine_positions)
    sim_core.simulate(cfg)
    # result 
    information()
    print(amr_count)
    profit(amr_count=amr_count,machine_counts=machine_counts)
    animate_from_amr_runs(global_variable.amr_runs,interval_ms=10,frames=1296000,trail=True,machine_positions=machine_positions)



