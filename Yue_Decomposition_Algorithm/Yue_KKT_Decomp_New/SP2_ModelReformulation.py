import gurobipy as gp
from gurobipy import GRB
import logging

from .MP_KKT_ModelReformulation import MasterSolution
from .SP1_ModelReformulation import SubProblem1Solution
from Instances.instance_loader import InstanceData

from typing import Dict, Tuple
from dataclasses import dataclass

@dataclass
class SubProblem2Solution:
    '''Data class to hold Subproblem 2 solution'''
    feasible: bool                                     # Indicates if SP2 is feasible (followers' reaction from SP1 is feasible for the given leader decisions)
    sp2_obj: float | None                              # Objective value of SP2 (equals objective of leader)
    x_ck: Dict[Tuple[int, int], float] | None          # Investment decision of capacity k for cement plant c
    q_cf: Dict[Tuple[int, int], float] | None          # Quantity of coal f processed at cement plant c
    r_sw: Dict[Tuple[int, int], float] | None          # Residual waste w at transfer station s after allocation (not utilized by cement plants)
    q_scw: Dict[Tuple[int, int, int], float] | None    # Quantity of waste w from transfer station s to cement plant c

class SubProblem2:
    '''
    Subproblem 2: Follower feasibility problem

    This class models the subproblem (SP2) in the bilevel optimization framework of Yue et al. (2017). 
    It takes the leaders' optimal decisions from the master problem (MP) and optimal followers reaction value from Subproblem 1 (SP1) to check
    the feasibility of the followers reaction by looking for lower level variables satisfying all constraints (leader and follower) while achieving
    an objective value at least as good as the optimal reaction value from SP1. If SP2 is infeasible, it indicates that the followers' reaction 
    from SP1 is not feasible for the given leader decisions (leader decision is inconsistent with rational follower behaviour), and we can generate a 
    feasibility cut for the master problem. If SP2 is feasible, it confirms that the followers' reaction from SP1 is indeed feasible for the given 
    leader decisions, and we can proceed to generate an optimality cut based on the dual information from SP2. 
    '''

    def __init__(self, instance: InstanceData):
        '''Initialize SP2 with instance data'''
        self.instance = instance
        self._build = False
        self.model = None

        # Variable containers (filled during build() )
        # Follower variables
        self.x_ck = None  # Investment decision of capacity k for cement plant c
        self.q_cf = None  # Quantity of coal f processed at cement plant c
        self.r_sw = None  # Residual waste w at transfer station s after allocation (not utilized by cement plants)
        self.q_scw = None  # Quantity of waste w from transfer station s to cement plant c

        # fixed leader decisions from MP solution (input to SP1, filled in build() method)
        self.mu_kiln = None
        self.z_wh = None
        self.q_gsw = None
        self.q_slw = None
        self.q_siw = None

        # obtained optimal reaction value from SP1 (input to SP2, filled in build() method)
        self.sp1_optimal_value = None

        # Objective unction components of lower level problem for posterior analysis
        self.obj_cost_coal = None
        self.obj_cost_invest = None
        self.obj_cost_preproc = None
        self.obj_cost_penalty = None
        self.obj_cost_tiebreak = None
        self.obj_revenue_subsidy = None
        self.obj_total_follower = None

    def build(self, mp_solution: MasterSolution, sp1_solution: SubProblem1Solution, *, name: str = "SubProblem2", output_flag: int = 0):
        '''Build the Subproblem 2 model '''
        if self._build:
            raise RuntimeError("SP2 was already built.")
        
        self.model = gp.Model(name)
        self.model.setParam('OutputFlag', output_flag)

        # Extract fixed leader decisions from MP solution
        self.mu_kiln = mp_solution.mu_kiln
        self.mu_land = mp_solution.mu_land
        self.mu_inc = mp_solution.mu_inc
        self.z_wh = mp_solution.z_wh
        self.q_gsw = mp_solution.q_gsw
        self.q_slw = mp_solution.q_slw
        self.q_siw = mp_solution.q_siw

        # Extract optimal reaction value from SP1 solution
        self.sp1_optimal_value = sp1_solution.sp1_obj

        #  ---- add variables / constraints / objective ----
        self._add_variables()
        self._add_constraints()
        self._set_objective()
        # self.model.setObjective(0.0, GRB.MINIMIZE)  # Objective is zero because we are only checking feasibility of achieving SP1 optimal reaction value with the given leader decisions (SP2 is a feasibility problem)
        self.model.update()

        logging.info("\nSubproblem 2 model structure:\n")
        logging.info(f"  → Total created variables: {self.model.NumVars}")
        logging.info(f"  → Thereof binary variables: {self.model.NumBinVars}")
        logging.info(f"  → Thereof continuous variables: {self.model.NumVars - self.model.NumBinVars}")

        logging.info(f"  → Total created constraints: {self.model.NumConstrs}\n")

        self._build = True

    def solve(self, *, time_limit: int = GRB.INFINITY) -> None:
        '''Solve SP2'''
        assert self.model is not None, "Model is not built yet. Call build() before solve()."
        self.model.Params.TimeLimit = time_limit

        """Solve the Subproblem 2"""
        logging.info("\n" + "-"*60)
        logging.info("Solving Subproblem 2...")
        logging.info(f"  → Time limit: {time_limit} seconds")
        logging.info("-"*60)
        self.model.optimize()

    def _set_gurobi_parameters(self) -> None:           # only needed if feasibility problem considered with 0 objective, otherwise not necessary to set special parameters for optimality focus
        '''Set some specific parameters for solution run'''
        self.model.setParam('MIPFocus', 1)  # Focus on finding a feasible solution
        self.model.Params.SolutionLimit = 1  # Stop after finding the first feasible solution (if any)
        # self.model.NoRelHeurTime = 300  # Heuristic to find feasible solutions (if any) for up to 5 minutes

    def extract_solution(self) -> None:
        data = self.instance
        is_feasible = self.model.status in [GRB.OPTIMAL, GRB.SUBOPTIMAL]
        is_time_limit_reached = self.model.status == GRB.TIME_LIMIT
        
        if is_feasible:
            if self.model.status == GRB.OPTIMAL:
                logging.info('✓ Subproblem 2 solved optimally.')
            else:
                logging.info('⚠ Subproblem 2 solved suboptimally.')
            return SubProblem2Solution(
                feasible=True,
                sp2_obj=self.model.ObjVal,
                x_ck = {(c,k): int(round(self.x_ck[c, k].X)) for c in data.C for k in data.K},       # rounding because of floating-point relaxation within gurobi (0.9999997 or 1.0000002 possible)
                q_cf = {(c,f): self.q_cf[c, f].X for c in data.C for f in data.F},
                r_sw = {(s,w): self.r_sw[s, w].X for s in data.S for w in data.W},
                q_scw = {(s,c,w): self.q_scw[s, c, w].X for s in data.S for c in data.C for w in data.W}
            )
        elif is_time_limit_reached and self.model.SolCount > 0:
            logging.info('⚠ Subproblem 2 solve time limit reached. Best solution found will be extracted.')
            return SubProblem2Solution(
                feasible=True,
                sp2_obj=self.model.ObjVal,
                x_ck = {(c,k): int(round(self.x_ck[c, k].X)) for c in data.C for k in data.K},       # rounding because of floating-point relaxation within gurobi (0.9999997 or 1.0000002 possible)
                q_cf = {(c,f): self.q_cf[c, f].X for c in data.C for f in data.F},
                r_sw = {(s,w): self.r_sw[s, w].X for s in data.S for w in data.W},
                q_scw = {(s,c,w): self.q_scw[s, c, w].X for s in data.S for c in data.C for w in data.W}
            )
        else:       # alternative: just 'return None' and check in decomposition algorithm 'if: sp2_sol = None'
            logging.info('✗ Subproblem 2 is infeasible.')
            return SubProblem2Solution(
                feasible=False,
                sp2_obj=None,
                x_ck=None,
                q_cf=None,
                r_sw=None,
                q_scw=None
            )

    def _add_variables(self) -> None:
        '''Add decision variables for SP2'''
        data = self.instance
        m = self.model

        # Follower variables
        self.x_ck = m.addVars(data.C, data.K, vtype=GRB.BINARY, name="x_ck")
        self.q_cf = m.addVars(data.C, data.F, lb=0.0, vtype=GRB.CONTINUOUS, name="q_cf")
        self.r_sw = m.addVars(data.S, data.W, lb=0.0, vtype=GRB.CONTINUOUS, name="r_sw")
        self.q_scw = m.addVars(data.S, data.C, data.W, lb=0.0, vtype=GRB.CONTINUOUS, name="q_scw")

    def _add_constraints(self) -> None:
        '''Add constraints for SP2 (leader constraints, follower constraints, and the optimality constraint to ensure SP1 optimal reaction value is achieved)'''
        data = self.instance
        m = self.model

        # ==================================================== 
        # Leader constraints 
        # ====================================================
        # region Leader Constraints
        
        # ---
        # The leader constraints (L1)-(L5), (L7)-(L10), and (L11)-(L15) are not needed in SP2 because the leader decisions are fixed 
        # based on the MP solution and already satisfy these constraints by construction (the MP solution is feasible for the MP 
        # constraints, which include all leader constraints).
        # ---

        # Coupling constraint:
        # (L6) Incinerator capacity must compensate declined waste from cement kilns
        m.addConstr(
            gp.quicksum(self.q_siw[s,i,w] for s in data.S for i in data.I for w in data.W) + gp.quicksum(self.r_sw[s,w] for s in data.S for w in data.W)
            <= gp.quicksum(data.Q_i[i] for i in data.I),
        name="L6_incineratorCoupling"
        )

        # Coupling constraint
        # (L10) Total subsidy cost cannot exceed municipality budget
        m.addConstr(
            gp.quicksum(self.q_scw[s,c,w] * gp.quicksum(data.phi_wh[w][h]*self.z_wh[w,h] for h in data.H) for s in data.S for c in data.C for w in data.W) <= data.budget_municipality,
        name="L10_municipalityBudget"
        )
        
        #endregion


        # ====================================================
        # Follower constraints
        # ====================================================
        # region Follower Constraints

        # (F1) # Only one pre- and co-processing capacity per cement facility feasible
        m.addConstrs(
            (gp.quicksum(self.x_ck[c,k] for k in data.K) <= 1 for c in data.C),
        name="F1_capacityChoice"
        )

        # (F2) Cement facility budget constraint for investing in pre- & co-processing
        m.addConstr(
            gp.quicksum(self.x_ck[c,k]*data.c_invest_k[k] for c in data.C for k in data.K) <= data.budget_cem,
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

        #endregion

        # ====================================================
        # Optimality constraint to ensure SP1 optimal reaction value is achieved
        # ====================================================
        # region Optimality constraint

        # 1) Cost of coal
        self.obj_cost_coal = gp.quicksum(self.q_cf[c,f] * data.price_f[f] for c in data.C for f in data.F)
        # 2) Investment cost
        self.obj_cost_invest = gp.quicksum(data.fixcost_invest_k[k] * self.x_ck[c,k] for c in data.C for k in data.K)
        # 3) Pre-processing cost
        self.obj_cost_preproc = gp.quicksum(data.c_preproc_w[w] * self.q_scw[s,c,w] for s in data.S for c in data.C for w in data.W)
        # 4) Penalty cost
        self.obj_cost_penalty = data.c_penalty * gp.quicksum(self.r_sw[s,w] for s in data.S for w in data.W)
        # 5) Small tie-breaking cost to avoid symmetries
        self.obj_cost_tiebreak = data.tau * gp.quicksum(self.q_scw[s,c,w] * data.TD_sc[s][c] for s in data.S for c in data.C for w in data.W)
        # 6) Subsidy revenue
        # revenue_subsidy = gp.quicksum(data.phi_wh[w][h] * self.y_cwh[c,w,h] for c in data.C for w in data.W for h in data.H)
        self.obj_revenue_subsidy = gp.quicksum(self.q_scw[s,c,w] * gp.quicksum(data.phi_wh[w][h] * self.z_wh[w,h] for h in data.H) for s in data.S for c in data.C for w in data.W)  # equivalent formulation based on subsidy level choice z_wh

        # Optimal value constraint
        m.addConstr(
            self.obj_cost_coal + self.obj_cost_invest + self.obj_cost_preproc + self.obj_cost_penalty + self.obj_cost_tiebreak - self.obj_revenue_subsidy <= self.sp1_optimal_value + 1e-6,  # small tolerance to account for numerical issues
        name="OptimalityConstraint"
        )

        self.obj_total_follower = self.obj_cost_coal + self.obj_cost_invest + self.obj_cost_preproc + self.obj_cost_penalty + self.obj_cost_tiebreak - self.obj_revenue_subsidy
        #endregion

    def get_objective_components(self):
        '''Evaluate objective components at current incubent solution for posterior analysis'''
        if self.model is None:
            raise RuntimeError("Model is not built yet. Call build() before getting objective components.")
        elif self.model.SolCount == 0:
            raise RuntimeError("SP2 is infeasible / has no solution at the limited iterations. Cannot get objective components.")
        
        return {
            "Coal cost": self.obj_cost_coal.getValue(),
            "Investment cost": self.obj_cost_invest.getValue(),
            "Pre-processing cost": self.obj_cost_preproc.getValue(),
            "Penalty cost": self.obj_cost_penalty.getValue(),
            "Tie-breaking cost": self.obj_cost_tiebreak.getValue(),
            "Subsidies received": self.obj_revenue_subsidy.getValue(),
            "Objective value": self.obj_total_follower.getValue()
        }

    def _set_objective(self) -> None:
        '''
        Set objective function for SP2 (can be zero if only feasibility check, but for Yue logic equals leader objective
        to allow dual information for optimality cut generation)
        '''
        data = self.instance
        m = self.model

        # ===== LEADER OBJECTIVE =====
        # 1) Transport emissions
        emission_transport = data.epsilon_truck * (
            gp.quicksum(self.q_gsw[g,s,w] * data.TD_gs[g][s] for g in data.G for s in data.S for w in data.W) +
            gp.quicksum(self.q_slw[s,l,w] * data.TD_sl[s][l] for s in data.S for l in data.L for w in data.W) +
            gp.quicksum(self.q_siw[s,i,w] * data.TD_si[s][i] for s in data.S for i in data.I for w in data.W) +
            gp.quicksum(self.q_scw[s,c,w] * data.TD_sc[s][c] for s in data.S for c in data.C for w in data.W)
        )

        # 2) Treatment emissions
        emission_treatment = (
            gp.quicksum(data.epsilon_land[w] * self.q_slw[s,l,w] for s in data.S for l in data.L for w in data.W) +
            gp.quicksum(data.epsilon_inc[w] * self.q_siw[s,i,w] for s in data.S for i in data.I for w in data.W) +
            gp.quicksum(data.epsilon_inc[w] * self.r_sw[s,w] for s in data.S for w in data.W)
        )

        # 3) Fuel emissions (cement kiln)
        emission_fuel = (
            gp.quicksum(data.epsilon_kiln_f[f] * self.q_cf[c,f] for c in data.C for f in data.F) +
            gp.quicksum(data.epsilon_kiln_w[w] * self.q_scw[s,c,w] for s in data.S for c in data.C for w in data.W)
        )

        # 4) Transport costs
        cost_transport = data.c_truck * (
            gp.quicksum(self.q_gsw[g,s,w] * data.TD_gs[g][s] for g in data.G for s in data.S for w in data.W) +
            gp.quicksum(self.q_slw[s,l,w] * data.TD_sl[s][l] for s in data.S for l in data.L for w in data.W) +
            gp.quicksum(self.q_siw[s,i,w] * data.TD_si[s][i] for s in data.S for i in data.I for w in data.W) +
            gp.quicksum(self.q_scw[s,c,w] * data.TD_sc[s][c] for s in data.S for c in data.C for w in data.W) +
            gp.quicksum(self.r_sw[s,w] * data.TD_si_avg for s in data.S for w in data.W)
        )

        # 5) Treatment costs
        cost_treatment = (
            data.c_land * gp.quicksum(self.q_slw[s,l,w] for s in data.S for l in data.L for w in data.W) +
            data.c_inc * gp.quicksum(self.q_siw[s,i,w] for s in data.S for i in data.I for w in data.W) +
            # (data.c_inc-data.c_penalty) * gp.quicksum(self.r_sw[s,w] for s in data.S for w in data.W)
            data.c_inc * gp.quicksum(self.r_sw[s,w] for s in data.S for w in data.W)
            # (data.c_inc-1) * gp.quicksum(self.r_sw[s,w] for s in data.S for w in data.W)
        )

        # 6) Subsidy cost
        # cost_subsidy = gp.quicksum(data.phi_wh[w][h] * self.y_cwh[c,w,h] for c in data.C for w in data.W for h in data.H)
        cost_subsidy = gp.quicksum(self.q_scw[s,c,w] * gp.quicksum(data.phi_wh[w][h]*self.z_wh[w,h] for h in data.H) for s in data.S for c in data.C for w in data.W)

        m.setObjective(
            data.weight_env*(emission_transport + emission_treatment + emission_fuel) +
            data.weight_mon*(cost_transport + cost_treatment + cost_subsidy),
            # data.weight_mon*(cost_transport + cost_treatment),
            GRB.MINIMIZE)