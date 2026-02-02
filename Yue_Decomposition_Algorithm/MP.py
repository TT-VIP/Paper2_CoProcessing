import gurobipy as gp
from gurobipy import GRB
from instance_loader import InstanceData

class MasterProblem:
    """
    Master Problem (Leader Problem - Municipality)
    
    The leader (municipality) determines:
    - Waste quotas "µ" for landfills, incinerators and cement facilities
    - Waste routing decisions "q" (to landfills, incinerators, cement facilities)
    - Subsidy "phi" levels for waste at each generation spot and transfer station
    
    Decision variables:
    - q_gsw: Continuous variable indicating waste "w" flow from generation "g" to transfer station "s"
    - q_slw: Continuous variable indicating waste "w" flow from transfer station "s" to landfill "l"
    - q_siw: Continuous variable indicating waste "w" flow from transfer station "s" to incinerator "i"
    - µ_land: Continuous variable indicating waste capacity quota allocated to landfills
    - µ_inc: Continuous variable indicating waste capacity quota allocated to incinerators
    - µ_kiln: Continuous variable indicating waste capacity quota allocated to cement kilns
    - z_wh: Binary variable for choice of discrete subsidy level "h" for waste type "w"
    - theta: Auxiliary variable for profit function approximation (cut generation)
    """

    # everything after * are keyword-only arguments, i.e. must be specified by name when calling
    # output_flag: 1 to show Gurobi output, 0 to suppress
    def __init__(self, instance: InstanceData, *, name: str = "MP", output_flag: int = 1):
        self.instance = instance
        self.model = None
