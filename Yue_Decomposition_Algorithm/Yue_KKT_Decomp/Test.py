import sys
from pathlib import Path

# Ensure project root is importable (so "Instances" resolves)
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Instances.instance_loader import InstanceData
from Yue_Decomposition_Algorithm.Yue_KKT_Decomp_New.MP_KKT_ModelReformulation import MasterProblem
from Yue_Decomposition_Algorithm.Yue_KKT_Decomp_New.SP1_ModelReformulation import SubProblem1
from Yue_Decomposition_Algorithm.Yue_KKT_Decomp_New.SP2_ModelReformulation import SubProblem2
# from shanghai_instance import make_shanghai_instance
from Instances.shanghai_instance_effective import make_shanghai_instance_effective
from Instances.shanghai_instance_scaled import make_shanghai_instance_scaled


def main() -> None:
    # data = InstanceData()
    # data.validate()
    shanghai_data = make_shanghai_instance_effective()
    print(shanghai_data)
    

    # mp = MasterProblem(shanghai_data)
    # mp.build(output_flag=1)
    # mp.solve()

    # mp_sol = mp.extract_solution()
    # print(mp_sol)

    # sp1 = SubProblem1(shanghai_data)
    # sp1.build(mp_sol, output_flag=1)
    # sp1.solve()

    # sp1_sol = sp1.extract_solution()
    # print(sp1_sol)

    # sp2 = SubProblem2(shanghai_data)
    # sp2.build(mp_sol, sp1_sol)
    # sp2.solve()
    # sp2_sol = sp2.extract_solution()
    # if sp2_sol.feasible:
    #     print(sp2_sol)
    # else:
    #     print("Subproblem 2 is infeasible -> generate feasibility cut for MP")

    # if sp2_sol.feasible:
    #     mp._add_kkt_oc_block(sp2_sol.x_ck)
    #     mp.solve()
    #     mp_sol = mp.extract_solution()
    #     print(mp_sol)
    # else:
    #     mp._add_kkt_oc_block(sp1_sol.x_ck)
    #     mp.solve()
    #     mp_sol = mp.extract_solution()
    #     print(mp_sol)
    


if __name__ == "__main__":
    main()