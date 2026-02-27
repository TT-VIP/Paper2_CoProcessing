from instance_loader import InstanceData
from MP_KKT import MasterProblem
from SP1 import SubProblem1
from SP2 import SubProblem2
from shanghai_instance import make_shanghai_instance


def main() -> None:
    # data = InstanceData()
    # data.validate()
    shanghai_data = make_shanghai_instance()
    

    mp = MasterProblem(shanghai_data)
    mp.build(output_flag=1)
    mp.solve()

    mp_sol = mp.extract_solution()
    print(mp_sol)

    sp1 = SubProblem1(shanghai_data)
    sp1.build(mp_sol, output_flag=1)
    sp1.solve()

    sp1_sol = sp1.extract_solution()
    print(sp1_sol)

    sp2 = SubProblem2(shanghai_data)
    sp2.build(mp_sol, sp1_sol)
    sp2.solve()
    sp2_sol = sp2.extract_solution()
    if sp2_sol.feasible:
        print(sp2_sol)
    else:
        print("Subproblem 2 is infeasible -> generate feasibility cut for MP")

    if sp2_sol.feasible:
        mp._add_kkt_oc_block(sp2_sol.x_ck)
        mp.solve()
        mp_sol = mp.extract_solution()
        print(mp_sol)
    else:
        mp._add_kkt_oc_block(sp1_sol.x_ck)
        mp.solve()
        mp_sol = mp.extract_solution()
        print(mp_sol)
    


if __name__ == "__main__":
    main()