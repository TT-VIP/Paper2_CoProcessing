"""
Master Problem (MP) Module
Implements the Master Problem for the Yue et al. decomposition algorithm
The Master Problem is solved by the leader (Municipality)
"""

import gurobipy as gp
from gurobipy import GRB
from instance_loader import InstanceData


class MasterProblem:
    """
    Master Problem (Leader Problem - Municipality)
    
    The leader (municipality) determines:
    - Waste quotas for landfills, incinerators and cement facilities
    - Waste routing decisions (to landfills, incinerators, cement facilities)
    - Subsidy levels for waste at each generation spot and transfer station
    
    Decision variables:
    - x_gsl: Binary variable indicating waste flow from generation g via transfer s to landfill l
    - x_gsi: Binary variable indicating waste flow from generation g via transfer s to incinerator i
    - x_gsc: Binary variable indicating waste flow from generation g via transfer s to cement facility c
    - y_gsh: Continuous variable for waste quantity from generation g to transfer s with subsidy level h
    - y_scw: Continuous variable for waste quantity from transfer s to cement facility c of type w
    - z_ck: Binary variable indicating if cement facility c invests in capacity option k
    - theta: Auxiliary variable for profit function approximation (cut generation)
    """
    
    def __init__(self, instance: InstanceData):
        """
        Initialize the Master Problem
        
        Parameters
        ----------
        instance : InstanceData
            Instance data containing all sets and parameters
        """
        self.instance = instance
        self.model = None
        self.variables = {}
        self.constraints = {}
        
    def build(self):
        """Build the Master Problem optimization model"""
        print("\n" + "="*60)
        print("Building Master Problem (MP)")
        print("="*60)
        
        # Create a new Gurobi model
        self.model = gp.Model("MasterProblem")
        self.model.setParam("OutputFlag", 1)  # Enable logging
        
        inst = self.instance
        
        # ===== DECISION VARIABLES =====
        print("\n[1] Creating decision variables...")
        
        # Waste routing variables (continuous, represent quantities in tons)
        self.variables['x_gsl'] = {}  # waste to landfill
        for g in inst.G:
            for s in inst.S:
                for l in inst.L:
                    self.variables['x_gsl'][(g, s, l)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS,
                        name=f"x_gsl[{g},{s},{l}]"
                    )
        
        self.variables['x_gsi'] = {}  # waste to incinerator
        for g in inst.G:
            for s in inst.S:
                for i in inst.I:
                    self.variables['x_gsi'][(g, s, i)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS,
                        name=f"x_gsi[{g},{s},{i}]"
                    )
        
        self.variables['x_gsc'] = {}  # waste to cement facility
        for g in inst.G:
            for s in inst.S:
                for c in inst.C:
                    self.variables['x_gsc'][(g, s, c)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS,
                        name=f"x_gsc[{g},{s},{c}]"
                    )
        
        # Subsidy variables (continuous, represent waste quantities at each subsidy level)
        self.variables['y_gsh'] = {}  # waste from generation g at subsidy level h
        for g in inst.G:
            for s in inst.S:
                for h in inst.H:
                    self.variables['y_gsh'][(g, s, h)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS,
                        name=f"y_gsh[{g},{s},{h}]"
                    )
        
        # Waste type variables to cement facilities
        self.variables['y_scw'] = {}  # waste from transfer s to cement c of type w
        for s in inst.S:
            for c in inst.C:
                for w in inst.W:
                    self.variables['y_scw'][(s, c, w)] = self.model.addVar(
                        lb=0, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS,
                        name=f"y_scw[{s},{c},{w}]"
                    )
        
        # Investment variables for cement facilities
        self.variables['z_ck'] = {}  # investment indicator for cement facility c, capacity k
        for c in inst.C:
            for k in inst.K:
                self.variables['z_ck'][(c, k)] = self.model.addVar(
                    vtype=GRB.BINARY,
                    name=f"z_ck[{c},{k}]"
                )
        
        # Auxiliary variable for lower-level objective (profit function approximation via cuts)
        self.variables['theta'] = self.model.addVar(
            lb=-GRB.INFINITY, ub=GRB.INFINITY, vtype=GRB.CONTINUOUS,
            name="theta"
        )
        
        self.model.update()
        print(f"  → Created {self.model.NumVars} variables")
        
        # ===== OBJECTIVE FUNCTION =====
        print("\n[2] Setting up objective function...")
        
        # Transportation cost to landfill
        cost_truck_land = gp.quicksum(
            inst.c_truck * inst.TD_gs[g][s] * self.variables['x_gsl'][(g, s, l)] +
            inst.c_truck * inst.TD_sl[s][l] * self.variables['x_gsl'][(g, s, l)]
            for g in inst.G for s in inst.S for l in inst.L
        )
        
        # Transportation cost to incinerator
        cost_truck_inc = gp.quicksum(
            inst.c_truck * inst.TD_gs[g][s] * self.variables['x_gsi'][(g, s, i)] +
            inst.c_truck * inst.TD_si[s][i] * self.variables['x_gsi'][(g, s, i)]
            for g in inst.G for s in inst.S for i in inst.I
        )
        
        # Transportation cost to cement facility
        cost_truck_cem = gp.quicksum(
            inst.c_truck * inst.TD_gs[g][s] * self.variables['x_gsc'][(g, s, c)] +
            inst.c_truck * inst.TD_sc[s][c] * self.variables['x_gsc'][(g, s, c)]
            for g in inst.G for s in inst.S for c in inst.C
        )
        
        # Landfill processing cost
        cost_landfill = gp.quicksum(
            inst.c_land * self.variables['x_gsl'][(g, s, l)]
            for g in inst.G for s in inst.S for l in inst.L
        )
        
        # Incineration processing cost
        cost_incineration = gp.quicksum(
            inst.c_inc * self.variables['x_gsi'][(g, s, i)]
            for g in inst.G for s in inst.S for i in inst.I
        )
        
        # Subsidy cost (negative because it's an expenditure)
        cost_subsidy = gp.quicksum(
            inst.phi_wh[w][h] * self.variables['y_gsh'][(g, s, h)]
            for g in inst.G for s in inst.S for h in inst.H for w in inst.W
        )
        
        # Total monetary cost for municipality
        cost_monetary = (cost_truck_land + cost_truck_inc + cost_truck_cem + 
                        cost_landfill + cost_incineration + cost_subsidy)
        
        # Environmental cost (emissions)
        # Landfill emissions (assume average moisture content)
        em_landfill = gp.quicksum(
            inst.epsilon_land[w] * self.variables['x_gsl'][(g, s, l)]
            for g in inst.G for s in inst.S for l in inst.L for w in inst.W
        ) / inst.W_max  # Simplified: average over waste types
        
        # Incinerator emissions
        em_incineration = gp.quicksum(
            inst.epsilon_inc[w] * self.variables['x_gsi'][(g, s, i)]
            for g in inst.G for s in inst.S for i in inst.I for w in inst.W
        ) / inst.W_max
        
        # Cement kiln emissions (from waste)
        em_cement_waste = gp.quicksum(
            inst.epsilon_kiln_w[w] * self.variables['y_scw'][(s, c, w)]
            for s in inst.S for c in inst.C for w in inst.W
        )
        
        # Total environmental impact
        env_objective = em_landfill + em_incineration + em_cement_waste
        
        # Combined objective: minimize weighted sum
        objective = inst.weight_env * env_objective + inst.weight_mon * cost_monetary - self.variables['theta']
        
        self.model.setObjective(objective, GRB.MINIMIZE)
        print("  → Objective function set")
        
        # ===== CONSTRAINTS =====
        print("\n[3] Adding constraints...")
        
        # 1. Demand satisfaction constraints: all waste must be routed
        for g in inst.G:
            for w in inst.W:
                total_waste = gp.quicksum(
                    self.variables['x_gsl'][(g, s, l)]
                    for s in inst.S for l in inst.L
                ) + gp.quicksum(
                    self.variables['x_gsi'][(g, s, i)]
                    for s in inst.S for i in inst.I
                ) + gp.quicksum(
                    self.variables['x_gsc'][(g, s, c)]
                    for s in inst.S for c in inst.C
                )
                self.model.addConstr(
                    total_waste == inst.Q_gw[g][w],
                    name=f"demand_g{g}_w{w}"
                )
        
        # 2. Transfer station capacity constraints
        for s in inst.S:
            incoming = gp.quicksum(
                self.variables['x_gsl'][(g, s, l)] +
                self.variables['x_gsi'][(g, s, i)] +
                self.variables['x_gsc'][(g, s, c)]
                for g in inst.G for l in inst.L for i in inst.I for c in inst.C
            )
            self.model.addConstr(
                incoming <= inst.Q_s[s],
                name=f"transfer_capacity_s{s}"
            )
        
        # 3. Landfill capacity constraints
        for l in inst.L:
            landfill_in = gp.quicksum(
                self.variables['x_gsl'][(g, s, l)]
                for g in inst.G for s in inst.S
            )
            self.model.addConstr(
                landfill_in <= inst.Q_l[l],
                name=f"landfill_capacity_l{l}"
            )
        
        # 4. Incinerator capacity constraints
        for i in inst.I:
            inc_in = gp.quicksum(
                self.variables['x_gsi'][(g, s, i)]
                for g in inst.G for s in inst.S
            )
            self.model.addConstr(
                inc_in <= inst.Q_i[i],
                name=f"incinerator_capacity_i{i}"
            )
        
        # 5. Landfill quota constraint (maximum landfill percentage)
        total_waste_generated = sum(inst.Q_gw[g][w] for g in inst.G for w in inst.W)
        landfill_total = gp.quicksum(
            self.variables['x_gsl'][(g, s, l)]
            for g in inst.G for s in inst.S for l in inst.L
        )
        self.model.addConstr(
            landfill_total <= inst.kappa_land * total_waste_generated,
            name="landfill_quota"
        )
        
        # 6. Budget constraint for subsidies
        subsidy_cost = gp.quicksum(
            inst.phi_wh[w][h] * self.variables['y_gsh'][(g, s, h)]
            for g in inst.G for s in inst.S for h in inst.H for w in inst.W
        )
        self.model.addConstr(
            subsidy_cost <= inst.budget_municipality,
            name="subsidy_budget"
        )
        
        # 7. Investment constraint: at most one capacity level per cement facility
        for c in inst.C:
            self.model.addConstr(
                gp.quicksum(self.variables['z_ck'][(c, k)] for k in inst.K) <= 1,
                name=f"investment_choice_c{c}"
            )
        
        self.model.update()
        print(f"  → Added {self.model.NumConstrs} constraints")
        
        print("\n" + "="*60)
        print("Master Problem built successfully!")
        print("="*60)
        
    def optimize(self):
        """Solve the Master Problem"""
        if self.model is None:
            raise ValueError("Model not built. Call build() first.")
        
        print("\n" + "-"*60)
        print("Solving Master Problem...")
        print("-"*60)
        
        self.model.optimize()
        
        if self.model.status == GRB.OPTIMAL:
            print(f"\n✓ Optimal solution found!")
            print(f"  Objective value: {self.model.ObjVal:.2f}")
            return self.model.ObjVal
        else:
            print(f"\n✗ Optimization failed with status: {self.model.status}")
            return None
    
    def get_solution(self):
        """Extract solution from the Master Problem"""
        if self.model is None or self.model.status != GRB.OPTIMAL:
            return None
        
        solution = {
            'x_gsl': {k: v.X for k, v in self.variables['x_gsl'].items() if v.X > 1e-6},
            'x_gsi': {k: v.X for k, v in self.variables['x_gsi'].items() if v.X > 1e-6},
            'x_gsc': {k: v.X for k, v in self.variables['x_gsc'].items() if v.X > 1e-6},
            'y_gsh': {k: v.X for k, v in self.variables['y_gsh'].items() if v.X > 1e-6},
            'y_scw': {k: v.X for k, v in self.variables['y_scw'].items() if v.X > 1e-6},
            'z_ck': {k: v.X for k, v in self.variables['z_ck'].items() if v.X > 0.5},
            'theta': self.variables['theta'].X,
            'obj_value': self.model.ObjVal
        }
        return solution
    
    def write_model(self, filename: str = "master_problem.lp"):
        """Export the model to a file for inspection"""
        if self.model is not None:
            self.model.write(filename)
            print(f"\n✓ Model written to {filename}")


if __name__ == "__main__":
    # Test the Master Problem
    instance = InstanceData()
    instance.validate()
    
    mp = MasterProblem(instance)
    mp.build()
    # mp.optimize()
    # solution = mp.get_solution()
    # if solution:
    #     print("\nMaster Problem Solution:")
    #     print(f"  Objective: {solution['obj_value']:.2f}")
