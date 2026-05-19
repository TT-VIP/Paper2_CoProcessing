import gurobipy as gp
from gurobipy import GRB
import logging

from .MP_numerics import MasterSolution
from Instances.instance_generator_normalized import InstanceData

from typing import Dict, Tuple
from dataclasses import dataclass

@dataclass
class SubProblem1Solution:
    '''Data class to hold SP1 solution'''
    sp1_obj: float
    x_ck: Dict[Tuple[int, int], float]          # Investment decision of capacity k for cement plant c
    q_cf: Dict[Tuple[int, int], float]          # Quantity of coal f processed at cement plant c
    r_sw: Dict[Tuple[int, int], float]          # Residual waste w at transfer station s after allocation (not utilized by cement plants)
    q_scw: Dict[Tuple[int, int, int], float]    # Quantity of waste w from transfer station s to cement plant c


class SubProblem1:
    """Subproblem 1: Follower Optimal reaction Problem
    
    This class models the subproblem (SP1) in the bilevel optimization framework.
    It determines the followers' optimal response for fixed leader decisions x_L*, y_L* from the master problem (MP)
    
    The follower (cement producer) determines:
    - Investment decision for pre- & co-processing capacity expansion at cement plants
    - Quantity of waste and coal processed at cement plants
    - Residual waste (denied quantity) at transfer stations after allocation to cement plants
    - Quantity of waste flow from transfer stations to cement plants (if allocated)
    
    Decision variables:
    - x_ck: Binary variable for investment decision of capacity k for cement plant c
    - q_cf: Continuous variable for quantity of coal f processed at cement plant c
    - r_sw: Continuous variable for residual waste w at transfer station s after allocation (not utilized and denied by cement plants)
    - q_scw: Continuous variable for quantity of waste w from transfer station s to cement plant c (if allocated)
    """
    
    def __init__(self, instance: InstanceData):
        """Initialize SP1 with instance data"""
        self.instance = instance
        self._build = False
        self.model = None

        # Variable Containers (filled during build)
        # Follower variables
        self.x_ck = None
        self.r_sw = None
        self.q_cf = None
        self.q_scw = None

        # fixed leader decisions from MP solution (input to SP1, filled in build() method)
        self.mu_kiln = None
        self.z_wh = None
        self.q_gsw = None
        self.q_slw = None
        self.q_siw = None
    
    def build(self, mp_sol: MasterSolution, *, name: str = "SubProblem1", output_flag: int = 1) -> None:
        if self._build: 
            raise RuntimeError("SP1 model was already built.")
        
        """Build the Subproblem 1 model"""
        self.model = gp.Model(name)
        self.model.setParam('OutputFlag', output_flag)
        
        #  ---- fixed leader decisions from MP solution (input) ----
        # These are the decisions from the master problem that are fixed in SP1
        
        # clean data dictionaries from numerical noise (e.g., 1e-10 instead of 0) to avoid numerical issues in SP1 and improve performance
        def clean_continuous_value(x: float, tol: float = 1e-9) -> float:
            return 0.0 if abs(x) <= tol else float(x)

        def clean_continuous_dict(d: dict, tol: float = 1e-9) -> dict:
            return {k: clean_continuous_value(v, tol) for k, v in d.items()}
        
        self.mu_kiln = clean_continuous_value(mp_sol.mu_kiln)
        self.z_wh = mp_sol.z_wh     # binary variable, no need to clean because already rounded in MP solution
        self.q_gsw = clean_continuous_dict(mp_sol.q_gsw)
        self.q_slw = clean_continuous_dict(mp_sol.q_slw)
        self.q_siw = clean_continuous_dict(mp_sol.q_siw)

        #  ---- add variables / constraints / objective ----
        self._add_variables()
        self._add_constraints()
        self._set_objective()
        self.model.update()

        logging.info("\nSubproblem 1 model structure:\n")
        logging.info(f"  → Total created variables: {self.model.NumVars}")
        logging.info(f"  → Thereof binary variables: {self.model.NumBinVars}")
        logging.info(f"  → Thereof continuous variables: {self.model.NumVars - self.model.NumBinVars}")

        logging.info(f"  → Total created constraints: {self.model.NumConstrs}\n")

        self._build = True

    def solve(self, *, time_limit: int = GRB.INFINITY) -> None:
        assert self.model is not None, "Model is not built yet. Call build() before solve()."
        self.model.Params.TimeLimit = time_limit
        
        """Solve the Subproblem 1"""
        logging.info("\n" + "-"*60)
        logging.info("Solving Subproblem 1...")
        logging.info(f"  → Time limit: {time_limit} seconds")
        logging.info("-"*60)

        self.model.Params.NumericFocus = 0  # Focus on numerical issues to improve solution reliability for SP1
        self.model.optimize()

    def extract_solution(self) -> SubProblem1Solution:
        """Extract solution from the Master Problem"""
        if self.model.status == GRB.OPTIMAL:
            logging.info('✓ Subproblem 1 solved optimally.')
        # elif self.model.status == GRB.SUBOPTIMAL:
        #     logging.info('⚠ Subproblem 1 solved suboptimally.')
        # elif self.model.status == GRB.TIME_LIMIT and self.model.SolCount > 0:
        #     logging.info('⚠ Subproblem 1 solve time limit reached. Best solution found will be extracted.')
        else:
            # raise RuntimeError("✗ No solution for Subproblem 1 found; cannot extract solution.")
            raise RuntimeError(f"✗ Subproblem 1 not solved to optimality. Status={self.model.status}. "
                               f"SolCount={self.model.SolCount}, Gap={getattr(self.model, 'MIPGap', None)}"
                               f"No solution for Subproblem 1 can be extracted, because optimum is required for decomposition logic.")
        
        data = self.instance

        return SubProblem1Solution(
            sp1_obj=self.model.ObjVal,
            x_ck={(c, k): int(round(self.x_ck[c, k].X)) for c in data.C for k in data.K},       # rounding because of floating-point relaxation within gurobi (0.9999997 or 1.0000002 possible)
            q_cf={(c, f): self.q_cf[c, f].X for c in data.C for f in data.F},
            r_sw={(s, w): self.r_sw[s, w].X for s in data.S for w in data.W},
            q_scw={(s, c, w): self.q_scw[s, c, w].X for s in data.S for c in data.C for w in data.W}
        )
    
    def _add_variables(self) -> None:
        """Add decision variables for SP1"""
        data = self.instance
        m = self.model

        self.x_ck = m.addVars(data.C, data.K, vtype=GRB.BINARY, name="x_ck")                # Investment decision of capacity k for cement plant c
        self.q_cf = m.addVars(data.C, data.F, lb=0.0,vtype=GRB.CONTINUOUS, name="q_cf")            # Quantity of coal f processed at cement plant c
        self.r_sw = m.addVars(data.S, data.W, lb=0.0,vtype=GRB.CONTINUOUS, name="r_sw")            # Residual waste w at transfer station s after allocation (not utilized by cement plants)
        self.q_scw = m.addVars(data.S, data.C, data.W, lb=0.0,vtype=GRB.CONTINUOUS, name="q_scw")  # Quantity of waste w from transfer station s to cement plant c (if allocated)

    def _add_constraints(self) -> None:
        """Add constraints for SP1 (equal to the follower's problem constraints with fixed leader decisions)"""
        data = self.instance
        m = self.model

        # (F1) # Only one pre- and co-processing capacity per cement facility feasible
        m.addConstrs(
            (gp.quicksum(self.x_ck[c,k] for k in data.K) <= 1 for c in data.C),
        name="F1_capacityChoice"
        )

        # (F2) Cement facility budget constraint for investing in pre- & co-processing
        # scale numerics for better matrix and RHS vaulues, but keep feasible set untouched (e.g., if costs are in the order of 10,000 and budget is 1,000,000, scale down costs by factor of 1000 to get values in the order of 10 and keep budget at 1000)
        budget_cem_scale = 1_000_000
        m.addConstr(
            gp.quicksum(self.x_ck[c,k]* (data.c_invest_k[k] / budget_cem_scale) for c in data.C for k in data.K) <= data.budget_cem / budget_cem_scale,
        name="F2_cementBudget"
        )

        # (F3) Energy fulfillment in cement kiln
        m.addConstrs(
            (gp.quicksum(self.q_cf[c,f]*data.beta_f[f] for f in data.F) + gp.quicksum(self.q_scw[s,c,w]*data.beta_w[w] for s in data.S for w in data.W) >= data.alpha_c[c] for c in data.C),
        name="F3_energyFulfillment"
        )

        # (F4) Co-processing capacity limitation
        m.addConstrs(
            (gp.quicksum(self.q_scw[s,c,w]*data.beta_w[w] for s in data.S for w in data.W) <= data.kappa_coproc*data.alpha_c[c] for c in data.C),
        name="F4_coprocCapacityLimit"
        )

        # (F5) Pre- & co-processing capacity according to investment decision
        m.addConstrs(
            (gp.quicksum(self.q_scw[s,c,w] for s in data.S for w in data.W) <= gp.quicksum(self.x_ck[c,k]*data.Q_k[k] for k in data.K) for c in data.C),
        name="F5_investmentCapacity"
        )

        # (F6) Waste quota fulfillment at cement facility
        m.addConstr(
            (gp.quicksum(self.q_scw[s,c,w] for s in data.S for c in data.C for w in data.W) + gp.quicksum(self.r_sw[s,w] for s in data.S for w in data.W) ==
            self.mu_kiln*data.Q_gen_total),
        name="F6_wasteQuotaFulfillment",
        )

        # (F7) Waste transport balance
        # usable_kiln_waste = sum(self.q_gsw[g,s,w] for g in data.G) - gp.quicksum(self.q_slw[s,l,w] for l in data.L) - gp.quicksum(self.q_siw[s,i,w] for i in data.I)
        m.addConstrs(
            (gp.quicksum(self.q_gsw[g,s,w] for g in data.G) ==
            gp.quicksum(self.q_slw[s,l,w] for l in data.L) +
            gp.quicksum(self.q_siw[s,i,w] for i in data.I) +
            gp.quicksum(self.q_scw[s,c,w] for c in data.C) + self.r_sw[s,w] for s in data.S for w in data.W),
        name="F7_wasteTransportBalance"
        )

    def _set_objective(self) -> None:
        """Set objective function for SP1 (follower's problem objective)"""
        data = self.instance
        m = self.model

        # ---- Define auxiliary variables for cost components ----
        # 1) Cost of coal
        cost_coal = gp.quicksum(self.q_cf[c,f]*data.price_f[f] for c in data.C for f in data.F)
        # 2) Investment cost
        cost_invest = gp.quicksum(data.fixcost_invest_k[k]*self.x_ck[c,k] for c in data.C for k in data.K)
        # 3) Pre-processing cost
        cost_preproc = gp.quicksum(data.c_preproc_w[w]*self.q_scw[s,c,w] for s in data.S for c in data.C for w in data.W)
        # 4) Penalty cost
        cost_penalty = data.c_penalty*gp.quicksum(self.r_sw[s,w] for s in data.S for w in data.W)
        # 5) Transportation cost
        cost_transport = data.c_truck*gp.quicksum(self.q_scw[s,c,w]*data.TD_sc[s][c] for s in data.S for c in data.C for w in data.W)
        # 6) Subsidy revenue
        revenue_subsidy = gp.quicksum(self.q_scw[s,c,w]*gp.quicksum(data.phi_wh[w][h]*self.z_wh[w,h] for h in data.H) for s in data.S for c in data.C for w in data.W)

        # Objective: Minimize Costs = Coal cost + Investment cost + Pre-processing cost + Penalty cost + Transportation cost - Subsidy revenue
        m.setObjective(cost_coal + cost_invest + cost_preproc + cost_penalty + cost_transport - revenue_subsidy, GRB.MINIMIZE)