import sim_core
from config import global_variable
import sweep_routing_amr
from sweep_routing_amr import patch_routing, ROUTING_MODE
import multiprocessing as mp

# Champion Config
BEST_ROUTING = "cost_based"
BEST_AMR = 9
WIP_RANGE = [30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59]

def worker_task(args):
    wip_limit, run_idx = args
    
    # Patch Routing
    sweep_routing_amr.ROUTING_MODE = BEST_ROUTING
    sweep_routing_amr.patch_routing()
    
    # Set WIP Limit (Needs to be set before simulate call, but reset clears it?
    # reset_sim() calls init_all(). init_all sets MAX_WIP = 50 default.
    # So we must set it AFTER config/reset, or modify init logic.
    # Actually sim_core.simulate calls reset_sim().
    # So we need to patch sim_core.simulate or GlobalVariable.init_all?
    # Easier: Just set global_variable.MAX_WIP *after* simulate starts? No.
    # simulate -> reset_sim -> build_factory -> schedule -> run.
    # We can set it after reset_sim? But reset_sim is inside simulate.
    # We should modify how we pass it.
    # OR: sim_core.simulate takes cfg.
    # But MAX_WIP is in global_variable.
    # We can Monkey Patch GlobalVariable.init_all to set our value.
    
    original_init = global_variable.init_all
    def patched_init():
        original_init()
        global_variable.MAX_WIP = wip_limit
    
    # Apply patch to the instance method? No, init_all is instance method.
    # GlobalVariable is a class. global_variable is an instance.
    # But sim_core uses the singleton `global_variable`.
    # When reset_sim() is called, it calls global_variable.reset() -> init_all().
    # So we need to patch the method on the OBJECT or CLASS.
    
    # Safe way:
    import config
    original_reset = config.global_variable.reset
    
    def patched_reset():
        original_reset()
        config.global_variable.MAX_WIP = wip_limit
        
    config.global_variable.reset = patched_reset
    
    # Run Sim
    cfg = sim_core.FactoryConfig(
        sim_time=1296000,
        seed=20,
        feed_sequence=("ProdA", "ProdB"),
        amr_count=BEST_AMR,
        machine_counts={"A": 5, "B": 8, "C": 6, "D": 5, "E": 5},
        machine_positions=sweep_routing_amr.machine_positions
    )
    
    sim_core.simulate(cfg)
    profit = sweep_routing_amr.calculate_profit(BEST_AMR)
    
    return (wip_limit, profit)

def run_wip_sweep():
    print("="*60)
    print(f"WIP Limit Optimization Sweep (Routing={BEST_ROUTING}, AMR={BEST_AMR})")
    print("="*60)
    
    tasks = [(w, i) for i, w in enumerate(WIP_RANGE)]
    
    # Sequential execution is safer for patching globals if method is spawn?
    # If spawn, globals are reset. We rely on worker setting it up.
    # But worker_task sets it up.
    
    # Windows default is spawn. Fresh process.
    # So patching inside worker_task works perfectly.
    
    with mp.Pool(processes=min(len(tasks), 10)) as pool:
        results = pool.map(worker_task, tasks)
        
    print(f"\n{'WIP Limit':<10} | {'Profit':<15}")
    print("-" * 30)
    
    best_wip = 50
    best_profit = 0
    
    for w, p in results:
        print(f"{w:<10} | {p:,.0f}")
        if p > best_profit:
            best_profit = p
            best_wip = w
            
    print("-" * 30)
    print(f"🏆 Best WIP Limit: {best_wip} (Profit: {best_profit:,.0f})")

if __name__ == "__main__":
    mp.freeze_support()
    run_wip_sweep()
