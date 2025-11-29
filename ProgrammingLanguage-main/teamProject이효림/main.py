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
        "A": [(10,-4),(10,-2),(10,0),(10,2),(10,4)],
        "B": [(20,-7),(20,-5),(20,-3),(20,-1),(20,1),(20,3),(20,5),(20,7)],
        "C": [(30,-5),(30,-3),(30,-1),(30,1),(30,3),(30,5)],
        "D": [(40,-5),(40,-3),(40,-1),(40,1),(40,3),(40,5)],
        "E": [(50,-4),(50,-2),(50,0),(50,2),(50,4)],
    }
    # 설비 개수
    machine_counts={"A":5,"B":8,"C":6,"D":5,"E":5}
    # warehouse& stocker 위치
    warehouse_xy = (0, 0)
    stocker_xy   = (60, 0)
    # AMR 대수
    amr_count = 3
    # AMR 위치
    amr_positions = [(2,-1),(2,1),(2,0)]

    cfg = sim_core.FactoryConfig(sim_time=1296000, seed=20, feed_sequence=("ProdA","ProdB"), amr_count=amr_count, machine_counts=machine_counts,machine_positions= machine_positions,warehouse_xy=warehouse_xy,amr_positions=amr_positions,amr_speed=1.0,)
    sim_core.simulate(cfg)
    # result 
    information()
    profit(amr_count=amr_count,machine_counts=machine_counts)
    animate_from_amr_runs(global_variable.amr_runs,interval_ms=100,frames=1000,trail=True,machine_positions=machine_positions)
    # Visualization
    # ============================
    animate_from_amr_runs(
        global_variable.amr_runs,
        interval_ms=100,
        frames=1000,
        trail=True,
        machine_positions=machine_positions
    )


