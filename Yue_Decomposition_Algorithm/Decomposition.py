from instance_loader import InstanceData
from MP import MasterProblem
from shanghai_instance import make_shanghai_instance


def main() -> None:
    # data = InstanceData()
    # data.validate()
    shanghai_data = make_shanghai_instance()
    

    mp = MasterProblem(shanghai_data)
    mp.build(output_flag=1)
    mp.solve()

    sol = mp.extract_solution()
    print(sol)


if __name__ == "__main__":
    main()