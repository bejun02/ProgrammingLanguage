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
            "A": [(14,3), (14,7), (14,13), (14,17)],
            "B": [(22,3), (22,7), (22,13), (22,17)],
            "C": [(30,3), (30,7), (30,13), (30,17)],
            "D": [(38,3), (38,7), (38,13), (38,17)],
            "E": [(46,3), (46,7), (46,13), (46,17)],
        }
    # 설비 개수
    machine_counts={"A":4,"B":4,"C":4,"D":4,"E":4}
    # AMR 대수
    amr_count = 3
    cfg = sim_core.FactoryConfig(sim_time=1296000, seed=20, feed_sequence=("ProdA","ProdB"), amr_count=amr_count, machine_counts=machine_counts,machine_positions= machine_positions)
    sim_core.simulate(cfg)
    # result 
    information()
    profit(amr_count=amr_count,machine_counts=machine_counts)
    # animate_from_amr_runs(global_variable.amr_runs,interval_ms=100,frames=1000,trail=True,machine_positions=machine_positions)



