import gurobipy as gp
from gurobipy import GRB
import logging

from Instances.instance_loader import InstanceData

from typing import Dict, Tuple, Any
from dataclasses import dataclass


# Class for storing Master Problem solution
@dataclass
class MasterSolution:
    """Data class to store Master Problem solution"""
    mp_obj: float
    q_gsw: Dict[Tuple[int, int, int], float]    # Waste flow from generation g to transfer s
    q_slw: Dict[Tuple[int, int, int], float]    # Waste flow from transfer s to landfill l
    q_siw: Dict[Tuple[int, int, int], float]    # Waste flow from transfer s to incinerator i
    mu_land: float                              # Waste capacity quota for landfills
    mu_inc: float                               # Waste capacity quota for incinerators
    mu_kiln: float                              # Waste capacity quota for cement kilns
    z_wh: Dict[Tuple[int, int], int]            # Subsidy level choice for waste type w
    y_wh: Dict[Tuple[int, int], float]          # Linearization variable for subsidy cost (y_wh[w,h] = z_wh[w,h] * sum_{s,c} q_scw0[s,c,w])

# Class for storing the KKT optimality cut model components, i.e. all variables and constraints related to the optimality cut for one l in L (for readability and debugging purposes)
@dataclass
class KKTOCBlock:
    """Data class to store variables and constraints related to one KKT optimality cut block for a specific l in L"""
    l: int  # iteration index (1,2,...)
    x_ck_fixed: Dict[Tuple[int, int], int]  # discrete follower pattern for this cut from SP1 (SP2 infeasible) or SP2 (SP2 feasible)

    # primal follower continuous vars for this block
    q_cf: gp.tupledict
    q_scw: gp.tupledict
    r_sw: gp.tupledict
    y_wh_KKT: gp.tupledict

    # dual vars
    # duals for inequalities (with complementarity binaries)
    lam_F3: gp.tupledict
    lam_F4: gp.tupledict
    lam_F5: gp.tupledict
    # duals for equalities (without complementarity binaries)
    nu_F6: gp.Var
    nu_F7: gp.tupledict
    # duals for non-negativity constraints of follower variables (with complementarity binaries)
    pi_q_cf: gp.tupledict
    pi_q_scw: gp.tupledict
    pi_r_sw: gp.tupledict

    # complementarity binaries (one per inequality)
    bin_F3: gp.tupledict
    bin_F4: gp.tupledict
    bin_F5: gp.tupledict
    bin_q_cf: gp.tupledict
    bin_q_scw: gp.tupledict
    bin_r_sw: gp.tupledict

    # optional: store constraint handles for debugging
    constr: Dict[str, Any]

# Class for Master Problem (P1 with limited combinations of follower variables)
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
    - y_wh: Continuous variable for linearization of subsidy cost (y_wh[w,h] = z_wh[w,h] * sum_{s,c} q_scw0[s,c,w])
    - theta_stern: Auxiliary variable for profit function approximation (cut generation)    -> not necessary to define within MP (= solution of MP and no decision variable), but can be helpful for readability and debugging (instead of using a dictionary with keys like "theta_stern_0", "theta_stern_1" etc. for multiple cuts)

    - q_scw: Flow from transfer station "s" to cement facility "c" for waste type "w" (decided in upper or lower level?!)
    """
    #region __init__ method
    # Two options for __init__:
    # (1) Object exists before the model is built 
        # - init stores data and prepares containers
        # - model is built and configured via build() method
    def __init__(self, instance: InstanceData):
        self.instance = instance
        self.model = None
        self._build = False

        # Data containers for KKT optimality cut blocks
        self.kkt_oc_blocks: Dict[int, KKTOCBlock] = {}  # Dictionary to store KKT optimality cut blocks by iteration index l
        self._kkt_oc_counter = 0  # Counter to assign unique indices to KKT optimality cut blocks
        self.no_good_cut_counter = 0  # Counter to assign unique indices to no-good cuts for duplicate patterns

        # Variable Containers (filled in build())
        # Leader
        self.q_gsw = None
        self.q_slw = None
        self.q_siw = None
        self.mu_land = None
        self.mu_inc = None
        self.mu_kiln = None
        self.z_wh = None
        self.y_wh = None

        # Dummy Follower variables
        self.x_ck0 = None
        self.r_sw0 = None
        self.q_cf0 = None
        self.q_scw0 = None

        # Store objective components for posteriori analysis
        self.obj_emission_transport = None
        self.obj_emission_treatment = None
        self.obj_emission_fuel = None
        self.obj_cost_transport = None
        self.obj_cost_treatment = None
        self.obj_cost_subsidy = None
        self.obj_total_env = None
        self.obj_total_env_weighted = None
        self.obj_total_mon = None
        self.obj_total_mon_weighted = None
    #endregion

    # =============================================================================
    ######## public methods to build, solve, extract solution ########
    # =============================================================================

    #region Method to build the Master Problem model
    # everything after '*' are keyword-only arguments, i.e. must be specified by name when calling
    # 'output_flag: 1' to show Gurobi output, 0 to suppress
    # '-> None' indicates that this method does not return any value (optional hint); also '-> int | None', or '-> dict', '-> MasterSolution' etc.
    def build(self, *, name: str = "MasterProblem", output_flag: int = 1) -> None:
        # prevent rebuilding or building a model twice (=silent bug)
        if self._build: 
            raise RuntimeError("Masterproblem model was already built.")
        
        """Build the Master Problem model"""
        self.model = gp.Model(name)
        self.model.setParam('OutputFlag', output_flag)
        
        self._add_variables()
        self._add_constraints()
        self._set_objective()
        self.model.update()
        
        logging.info("\nMaster Problem model structure (build):\n")
        logging.info(f"  → Total created variables: {self.model.NumVars}")
        logging.info(f"  → Thereof binary variables: {self.model.NumBinVars}")
        logging.info(f"  → Thereof continuous variables: {self.model.NumVars - self.model.NumBinVars}")
        logging.info(f"  → Total created constraints: {self.model.NumConstrs}\n\n")
        
        self._build = True
        # if the model shall be rebuild, set object._build = False before calling build() again
    #endregion


    #region Method to solve the Master problem
    def solve(self, *, time_limit: int = GRB.INFINITY) -> None:
        # Not necessary to check, if the model is built directly within __init__
        assert self.model is not None, "Model is not built yet. Call build() before solve()."
        
        """Solve the Master Problem"""
        logging.info("\n" + "-"*60)
        logging.info("Solving Master Problem...")
        logging.info(f"  → Time limit: {time_limit} seconds")
        logging.info("-"*60)
        logging.info("\nMaster Problem model structure:\n")
        logging.info(f"  → Total variables: {self.model.NumVars}")
        logging.info(f"  → Thereof binary variables: {self.model.NumBinVars}")
        logging.info(f"  → Thereof continuous variables: {self.model.NumVars - self.model.NumBinVars}\n")

        logging.info(f"  → Total constraints: {self.model.NumConstrs}")
        self.model.Params.TimeLimit = time_limit
        # self.model.Params.MIPGap = 0.05  # Optional: set MIP gap for faster solves (e.g., 5% gap)
        # self.model.Params.NumericFocus = 3  # Optional: set numeric focus for better numerical stability (at the cost of longer solve times)
        self.model.Params.ScaleFlag = 2
        self.model.Params.FeasibilityTol = 1e-6
        self.model.Params.OptimalityTol = 1e-6
        self.model.Params.IntFeasTol = 1e-6
        self.model.optimize()
    #endregion


    #region Method to store solution within a dataclass
    def extract_solution(self) -> MasterSolution:
        """Extract solution from the Master Problem"""
        if self.model.status == GRB.OPTIMAL:
            logging.info('✓ Master Problem solved optimally.')
        elif self.model.status == GRB.SUBOPTIMAL:
            logging.info('⚠ Master Problem solved suboptimally.')
        elif self.model.status == GRB.TIME_LIMIT and self.model.SolCount > 0:
            logging.info('⚠ Master Problem solve time limit reached. Best solution found will be extracted.')
        else:
            raise RuntimeError("Master Problem is not (sub)optimal; cannot extract solution because no solution is available.")

        data = self.instance

        return MasterSolution(
            mp_obj = self.model.ObjVal,
            q_gsw = {(g, s, w): self.q_gsw[g, s, w].X for g in data.G for s in data.S for w in data.W},
            q_slw = {(s, l, w): self.q_slw[s, l, w].X for s in data.S for l in data.L for w in data.W},
            q_siw = {(s, i, w): self.q_siw[s, i, w].X for s in data.S for i in data.I for w in data.W},
            mu_land = self.mu_land.X,
            mu_inc = self.mu_inc.X,
            mu_kiln = self.mu_kiln.X,
            # rounding because of floating-point relaxation within gurobi (0.9999997 or 1.0000002 possible)
            z_wh = {(w, h): int(round(self.z_wh[w, h].X)) for w in data.W for h in data.H},
            y_wh = {(w, h): self.y_wh[w, h].X for w in data.W for h in data.H}
        )
    #endregion

    # =============================================================================
    ############ internal methods to add variables, constraints, objective ############
    # =============================================================================
    
    #region Method to add variables
    def _add_variables(self) -> None:
        data = self.instance
        m = self.model

        # ===== LEADER VARIABLES =====
        self.q_gsw = m.addVars(data.G, data.S, data.W, lb=0.0, vtype=GRB.CONTINUOUS, name="q_gsw")
        self.q_slw = m.addVars(data.S, data.L, data.W, lb=0.0, vtype=GRB.CONTINUOUS, name="q_slw")
        self.q_siw = m.addVars(data.S, data.I, data.W, lb=0.0, vtype=GRB.CONTINUOUS, name="q_siw")
        self.mu_land = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="mu_land")
        self.mu_inc = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="mu_inc")
        self.mu_kiln = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="mu_kiln")
        self.z_wh = m.addVars(data.W, data.H, vtype=GRB.BINARY, name="z_wh")
        self.y_wh = m.addVars(data.W, data.H, lb=0.0, vtype=GRB.CONTINUOUS, name="y_wh")

        # ===== DUMMY FOLLOWER VARIABLES (FOR CUT GENERATION) =====
        self.x_ck0 = m.addVars(data.C, data.K, vtype=GRB.BINARY, name="x_ck0")
        self.r_sw0 = m.addVars(data.S, data.W, lb=0.0, vtype=GRB.CONTINUOUS, name="r_sw0")
        self.q_cf0 = m.addVars(data.C, data.F, lb=0.0, vtype=GRB.CONTINUOUS, name="q_cf0")
        self.q_scw0 = m.addVars(data.S, data.C, data.W, lb=0.0, vtype=GRB.CONTINUOUS, name="q_scw0")

    #endregion

    #region Method to add constraints
    def _add_constraints(self) -> None:
        data = self.instance
        m = self.model

        # ==================================================== 
        # Leader constraints 
        # ====================================================
        # region Leader Constraints
        # (L1) Waste balance: all generated waste must go to some transfer station
        m.addConstrs(
            (gp.quicksum(self.q_gsw[g,s,w] for s in data.S) == data.Q_gw[g][w] for g in data.G for w in data.W),
        name="L1_wasteBalance"
        )

        # (L2) Waste dispatching: waste at a transfer station must be sent to landfill or incinerator
        # (cement kiln usage is handled by the follower, so not included here)
                # superfluous due to F7-0 !
        # m.addConstrs(
        #     (gp.quicksum(self.q_gsw[g,s,w] for g in data.G) >=
        #     gp.quicksum(self.q_slw[s,l,w] for l in data.L) + gp.quicksum(self.q_siw[s,i,w] for i in data.I)
        #     for s in data.S for w in data.W),
        # name="L2_wasteDispatching"
        # )

        # (L3) Transfer station capacity
        m.addConstrs(
            (gp.quicksum(self.q_gsw[g,s,w] for g in data.G for w in data.W) <= data.Q_s[s] for s in data.S),
        name="L3_transferCapacity"
        )

        # (L4) Landfill capacity
        m.addConstrs(
            (gp.quicksum(self.q_slw[s,l,w] for s in data.S for w in data.W) <= data.Q_l[l] for l in data.L),
        name="L4_landfillCapacity"
        )

        # (L5) Incinerator capacity
        m.addConstrs(
            (gp.quicksum(self.q_siw[s,i,w] for s in data.S for w in data.W) <= data.Q_i[i] for i in data.I),
        name="L5_incineratorCapacity"
        )

        # Coupling constraint:
        # (L6) Incinerator capacity must compensate declined waste from cement kilns
        m.addConstr(
            gp.quicksum(self.q_siw[s,i,w] for s in data.S for i in data.I for w in data.W) + gp.quicksum(self.r_sw0[s,w] for s in data.S for w in data.W)
            <= gp.quicksum(data.Q_i[i] for i in data.I),
        name="L6_incineratorCoupling"
        )

        # (L7) Landfill transport must fulfill landfill quota
        m.addConstr(
            gp.quicksum(self.q_slw[s,l,w] for s in data.S for l in data.L for w in data.W) == self.mu_land * data.Q_gen_total,
        name="L7_landfillTransportQuota"
        )

        # (L8) Incinerator transport must fulfill incineration quota
        m.addConstr(
            gp.quicksum(self.q_siw[s,i,w] for s in data.S for i in data.I for w in data.W) == self.mu_inc * data.Q_gen_total,
        name="L8_incineratorTransportQuota"
        )

        # (L9) For each waste type, exactly one subsidy level is chosen
        m.addConstrs(
            (gp.quicksum(self.z_wh[w,h] for h in data.H) == 1 for w in data.W),
        name="L9_subsidyLevelChoice"
        )

        # Coupling constraint:
        # (L10) Total subsidy cost cannot exceed municipality budget
        m.addConstr(
            gp.quicksum(data.phi_wh[w][h] * self.y_wh[w,h] for w in data.W for h in data.H) <= data.budget_municipality,
        name="L10_municipalityBudget"
        )
        
        # (L11) Quotas must sum to 1
        m.addConstr(
            self.mu_land + self.mu_inc + self.mu_kiln == 1,
        name="L11_quotaBalance"
        )

        # (L12) Landfill quota cannot exceed policy limit
        m.addConstr(
            self.mu_land <= data.kappa_land,
        name="L12_landfillQuotaLimit"
        )

        # Linearization constraints for subsidy cost (y_wh[w,h] = z_wh[w,h] * sum_{s,c} q_scw0[s,c,w]) via McCormick envelopes
        # (L13)
        m.addConstrs(
            (self.y_wh[w,h] <= self.z_wh[w,h] * data.U_w[w] for w in data.W for h in data.H),
        name="L13_subsidyCostLinearization_1"
        )

        # (L14)
        m.addConstrs(
            (self.y_wh[w,h] <= gp.quicksum(self.q_scw0[s,c,w] for s in data.S for c in data.C) for w in data.W for h in data.H),
        name="L14_subsidyCostLinearization_2"
        )

        # (L15)
        m.addConstrs(
            (self.y_wh[w,h] >= gp.quicksum(self.q_scw0[s,c,w] for s in data.S for c in data.C) - (1 - self.z_wh[w,h])*data.U_w[w] for w in data.W for h in data.H),
        name="L15_subsidyCostLinearization_3"
        )
        #endregion

        # ====================================================
        # Follower constraints
        # ====================================================
        # region Follower constraints (dummy vars, for cut generation)
        # (F1-0) # Only one pre- and co-processing capacity per cement facility feasible
        m.addConstrs(
            (gp.quicksum(self.x_ck0[c,k] for k in data.K) <= 1 for c in data.C),
        name="F1-0_capacityChoice"
        )

        # (F2-0) Cement facility budget constraint for investing in pre- & co-processing
        m.addConstr(
            gp.quicksum(self.x_ck0[c,k] * data.c_invest_k[k] for c in data.C for k in data.K) <= data.budget_cem,
        name="F2-0_cementBudget"
        )

        # (F3-0) Energy fulfillment in cement kiln
        m.addConstrs(
            (gp.quicksum(self.q_cf0[c,f] * data.beta_f[f] for f in data.F) + gp.quicksum(self.q_scw0[s,c,w] * data.beta_w[w] for s in data.S for w in data.W) >= data.alpha_c[c] for c in data.C),
        name="F3-0_energyFulfillment"
        )

        # (F4-0) Co-processing capacity limitation
        m.addConstrs(
            (gp.quicksum(self.q_scw0[s,c,w] * data.beta_w[w] for s in data.S for w in data.W) <= data.kappa_coproc * data.alpha_c[c] for c in data.C),
        name="F4-0_coprocCapacityLimit"
        )

        # (F5-0) Pre- & co-processing capacity according to investment decision
        m.addConstrs(
            (gp.quicksum(self.q_scw0[s,c,w] for s in data.S for w in data.W) <= gp.quicksum(self.x_ck0[c,k] * data.Q_k[k] for k in data.K) for c in data.C),
        name="F5-0_investmentCapacity"
        )

        # (F6-0) Waste quota fulfillment at cement facility
        m.addConstr(
            (gp.quicksum(self.q_scw0[s,c,w] for s in data.S for c in data.C for w in data.W) + gp.quicksum(self.r_sw0[s,w] for s in data.S for w in data.W) ==
            self.mu_kiln * data.Q_gen_total),
        name="F6-0_wasteQuotaFulfillment",
        )

        # (F7-0) Waste transport balance
        m.addConstrs(
            (gp.quicksum(self.q_gsw[g,s,w] for g in data.G) ==
            gp.quicksum(self.q_slw[s,l,w] for l in data.L) +
            gp.quicksum(self.q_siw[s,i,w] for i in data.I) +
            gp.quicksum(self.q_scw0[s,c,w] for c in data.C) + self.r_sw0[s,w] for s in data.S for w in data.W),
        name="F7-0_wasteTransportBalance"
        )
        #endregion
    #endregion

    #region Method to set objective function
    def _set_objective(self) -> None:
        data = self.instance
        m = self.model

        # ===== LEADER OBJECTIVE =====
        # 1) Transport emissions
        self.obj_emission_transport = data.epsilon_truck * (
            gp.quicksum(self.q_gsw[g,s,w] * data.TD_gs[g][s] for g in data.G for s in data.S for w in data.W) +
            gp.quicksum(self.q_slw[s,l,w] * data.TD_sl[s][l] for s in data.S for l in data.L for w in data.W) +
            gp.quicksum(self.q_siw[s,i,w] * data.TD_si[s][i] for s in data.S for i in data.I for w in data.W) +
            gp.quicksum(self.q_scw0[s,c,w] * data.TD_sc[s][c] for s in data.S for c in data.C for w in data.W)
        )

        # 2) Treatment emissions
        self.obj_emission_treatment = (
            gp.quicksum(data.epsilon_land[w] * self.q_slw[s,l,w] for s in data.S for l in data.L for w in data.W) +
            gp.quicksum(data.epsilon_inc[w] * self.q_siw[s,i,w] for s in data.S for i in data.I for w in data.W) +
            gp.quicksum(data.epsilon_inc[w] * self.r_sw0[s,w] for s in data.S for w in data.W)
        )

        # 3) Fuel emissions (cement kiln)
        self.obj_emission_fuel = (
            gp.quicksum(data.epsilon_kiln_f[f] * self.q_cf0[c,f] for c in data.C for f in data.F) +
            gp.quicksum(data.epsilon_kiln_w[w] * self.q_scw0[s,c,w] for s in data.S for c in data.C for w in data.W)
        )

        # 4) Transport costs
        self.obj_cost_transport = data.c_truck * (
            gp.quicksum(self.q_gsw[g,s,w] * data.TD_gs[g][s] for g in data.G for s in data.S for w in data.W) +
            gp.quicksum(self.q_slw[s,l,w] * data.TD_sl[s][l] for s in data.S for l in data.L for w in data.W) +
            gp.quicksum(self.q_siw[s,i,w] * data.TD_si[s][i] for s in data.S for i in data.I for w in data.W) +
            gp.quicksum(self.q_scw0[s,c,w] * data.TD_sc[s][c] for s in data.S for c in data.C for w in data.W) +
            gp.quicksum(self.r_sw0[s,w] * data.TD_si_avg for s in data.S for w in data.W)
        )

        # 5) Treatment costs
        self.obj_cost_treatment = (
            data.c_land * gp.quicksum(self.q_slw[s,l,w] for s in data.S for l in data.L for w in data.W) +
            data.c_inc * gp.quicksum(self.q_siw[s,i,w] for s in data.S for i in data.I for w in data.W) +
            # (data.c_inc-data.c_penalty) * gp.quicksum(self.r_sw0[s,w] for s in data.S for w in data.W)
            data.c_inc * gp.quicksum(self.r_sw0[s,w] for s in data.S for w in data.W)
            # (data.c_inc-1) * gp.quicksum(self.r_sw0[s,w] for s in data.S for w in data.W)
        )

        # 6) Subsidy cost
        self.obj_cost_subsidy = gp.quicksum(data.phi_wh[w][h] * self.y_wh[w,h] for w in data.W for h in data.H)
        m.setObjective(
            data.weight_env*(self.obj_emission_transport + self.obj_emission_treatment + self.obj_emission_fuel) +
            data.weight_mon*(self.obj_cost_transport + self.obj_cost_treatment + self.obj_cost_subsidy),
            # data.weight_mon*(self.obj_cost_transport + self.obj_cost_treatment),
            GRB.MINIMIZE)

        # Store objective components for posteriori analysis
        self.obj_total_env = self.obj_emission_transport + self.obj_emission_treatment + self.obj_emission_fuel
        self.obj_total_env_weighted = data.weight_env * self.obj_total_env

        self.obj_total_mon = self.obj_cost_transport + self.obj_cost_treatment + self.obj_cost_subsidy
        self.obj_total_mon_weighted = data.weight_mon * self.obj_total_mon
    #endregion

    #region Method for objective breakdown
    def get_objective_breakdown(self) -> Dict[str, float]:
        """Evaluate objective components at current incumbent."""
        if self.model is None or self.model.SolCount == 0:
            raise RuntimeError("No MP solution available.")

        return {
            "Transport emissions": float(self.obj_emission_transport.getValue()),
            "Treatment emissions": float(self.obj_emission_treatment.getValue()),
            "Fueling emissions": float(self.obj_emission_fuel.getValue()),
            "Total emissions (unweighted)": float(self.obj_total_env.getValue()),
            f"Total emissions (weighted {self.instance.weight_env:.2f})": float(self.obj_total_env_weighted.getValue()),
            "Transport cost": float(self.obj_cost_transport.getValue()),
            "Treatment cost": float(self.obj_cost_treatment.getValue()),
            "Subsidy cost": float(self.obj_cost_subsidy.getValue()),
            "Total costs (unweighted)": float(self.obj_total_mon.getValue()),
            f"Total costs (weighted {self.instance.weight_mon:.3f})": float(self.obj_total_mon_weighted.getValue()),
            "Objective value": float(self.model.ObjVal),
        }
    #endregion

    # (later) Method to add Benders cut (after solving SP2)
    # region Method add optimality KKT-cut (after solving SP2)
    def _add_kkt_oc_block(self, x_ck_fixed: Dict[Tuple[int, int], int]) -> int:
        """
        Method to add one KKT optimality cut block for iteration l with fixed follower pattern x_ck_fixed (from SP1 or SP2)
        - creates variables and constraints for the KKT optimality cut block
        - stores them in a KKTOCBlock dataclass for readability and debugging
        """
        data = self.instance
        m = self.model

        self._kkt_oc_counter += 1
        l = self._kkt_oc_counter
        pfx = f"OC{l}"  # prefix for variable and constraint names for this cut block

        #region Create variables for this KKT optimality cut block
        # 1) Primal follower continuous variables for this cut block (same as in SP, but with suffix for this cut)
        q_cf = m.addVars(data.C, data.F, lb=0.0, vtype=GRB.CONTINUOUS, name=f"{pfx}_q_cf")
        q_scw = m.addVars(data.S, data.C, data.W, lb=0.0, vtype=GRB.CONTINUOUS, name=f"{pfx}_q_scw")
        r_sw = m.addVars(data.S, data.W, lb=0.0, vtype=GRB.CONTINUOUS, name=f"{pfx}_r_sw")
        y_wh_KKT = m.addVars(data.W, data.H, lb=0.0, vtype=GRB.CONTINUOUS, name=f"{pfx}_y_wh_KKT")

        # 2) Dual variables for this cut block
        # duals for inequalities
        lam_F3 = m.addVars(data.C, lb=0.0, vtype=GRB.CONTINUOUS, name=f"{pfx}_lam_F3")
        lam_F4 = m.addVars(data.C, lb=0.0, vtype=GRB.CONTINUOUS, name=f"{pfx}_lam_F4")
        lam_F5 = m.addVars(data.C, lb=0.0, vtype=GRB.CONTINUOUS, name=f"{pfx}_lam_F5")
        # duals for equalities
        nu_F6 = m.addVar(lb=-GRB.INFINITY, vtype=GRB.CONTINUOUS, name=f"{pfx}_nu_F6")
        nu_F7 = m.addVars(data.S, data.W, lb=-GRB.INFINITY, vtype=GRB.CONTINUOUS, name=f"{pfx}_nu_F7")
        # duals for non-negativity constraints of follower variables
        pi_q_cf = m.addVars(data.C, data.F, lb=0.0, vtype=GRB.CONTINUOUS, name=f"{pfx}_pi_q_cf")
        pi_q_scw = m.addVars(data.S, data.C, data.W, lb=0.0, vtype=GRB.CONTINUOUS, name=f"{pfx}_pi_q_scw")
        pi_r_sw = m.addVars(data.S, data.W, lb=0.0, vtype=GRB.CONTINUOUS, name=f"{pfx}_pi_r_sw")

        # 3) Complementarity binaries for this cut block
        bin_F3 = m.addVars(data.C, vtype=GRB.BINARY, name=f"{pfx}_bin_F3")
        bin_F4 = m.addVars(data.C, vtype=GRB.BINARY, name=f"{pfx}_bin_F4")
        bin_F5 = m.addVars(data.C, vtype=GRB.BINARY, name=f"{pfx}_bin_F5")
        bin_q_cf = m.addVars(data.C, data.F, vtype=GRB.BINARY, name=f"{pfx}_bin_q_cf")
        bin_q_scw = m.addVars(data.S, data.C, data.W, vtype=GRB.BINARY, name=f"{pfx}_bin_q_scw")
        bin_r_sw = m.addVars(data.S, data.W, vtype=GRB.BINARY, name=f"{pfx}_bin_r_sw")
        # bin_y_wh_KKT = m.addVars(data.W, data.H, vtype=GRB.BINARY, name=f"{pfx}_bin_y_wh_KKT")
        #endregion

        #region Create constraints for this KKT optimality cut block

        # ======================================================
        # Stationarity constraints
        # ======================================================

        # (S1) Stationarity for q_cf[c,f]
        m.addConstrs(
            (data.price_f[f] - lam_F3[c]*data.beta_f[f] - pi_q_cf[c,f] == 0 for c in data.C for f in data.F),
            name=f"{pfx}_S1_stationarity_q_cf",
        )

        # (S2) Stationarity for q_scw[s,c,w]
        m.addConstrs(
            (data.c_preproc_w[w] + data.tau*data.TD_sc[s][c] - gp.quicksum(data.phi_wh[w][h]*self.z_wh[w,h] for h in data.H) - lam_F3[c]*data.beta_w[w] 
             + lam_F4[c]*data.beta_w[w] + lam_F5[c] + nu_F6 - nu_F7[s,w] - pi_q_scw[s,c,w] == 0 for s in data.S for c in data.C for w in data.W),
            name=f"{pfx}_S2_stationarity_q_scw",
        )

        # (S3) Stationarity for r_sw[s,w]
        m.addConstrs(
            (data.c_penalty + nu_F6 - nu_F7[s,w] - pi_r_sw[s,w] == 0 for s in data.S for w in data.W),
            name=f"{pfx}_S3_stationarity_r_sw",
        )


        # ======================================================
        # Primal feasibility constraints (same as SP, but with suffix for this cut)
        # ======================================================

        # (F1) and (F2) can be skipped because they only involve binary variables x_ck which are fixed in this cut block and do not affect the duals
        
        # (F3) Energy fulfillment in cement kiln
        # (pf1) F3 energy requirement: alpha_c - sum_f q_cf*beta_f - sum_w q_cw*beta_w <= 0
        m.addConstrs(
            (data.alpha_c[c] - gp.quicksum(q_cf[c,f]*data.beta_f[f] for f in data.F) 
             - gp.quicksum(q_scw[s,c,w]*data.beta_w[w] for s in data.S for w in data.W) <= 0 for c in data.C),
            name=f"{pfx}_pf1_F3",
        )

        # (pf2) F4 co-processing share: sum_w q_cw*beta_w - kappa*alpha_c <= 0
        m.addConstrs(
            (gp.quicksum(q_scw[s,c,w]*data.beta_w[w] for s in data.S for w in data.W) - data.kappa_coproc * data.alpha_c[c] <= 0 for c in data.C),
            name=f"{pfx}_pf2_F4",
        )

        # (pf3) F5 capacity with fixed x_ck pattern: sum_w q_cw - sum_k x_ck_fixed*Q_k <= 0
        m.addConstrs(
            (gp.quicksum(q_scw[s,c,w] for s in data.S for w in data.W) - gp.quicksum(x_ck_fixed[(c, k)]*data.Q_k[k] for k in data.K) <= 0 for c in data.C),
            name=f"{pfx}_pf3_F5",
        )

        # (pf4) F6 quota fulfillment (equality): sum_cw q_cw + sum_sw r_sw - mu_kiln*Q_gen_total = 0
        m.addConstr(
            (gp.quicksum(q_scw[s,c,w] for s in data.S for c in data.C for w in data.W) + gp.quicksum(r_sw[s,w] for s in data.S for w in data.W) 
             - self.mu_kiln*data.Q_gen_total == 0),
            name=f"{pfx}_pf4_F6",
        )

        # (pf5) F7 station balance (equality): sum_g q_gsw - sum_l q_slw - sum_i q_siw - sum_c q_scw - r_sw = 0
        m.addConstrs(
            (gp.quicksum(self.q_gsw[g,s,w] for g in data.G) - gp.quicksum(self.q_slw[s,l,w] for l in data.L) 
             - gp.quicksum(self.q_siw[s,i,w] for i in data.I) - gp.quicksum(q_scw[s, c, w] for c in data.C) - r_sw[s, w] 
             == 0 for s in data.S for w in data.W),
            name=f"{pfx}_pf5_F7",
        )
        # non-negativity of primal variables is already defined in variable creation, so no need to add explicitly here

        # ======================================================
        # Complementary slackness constraints (using big-M and binaries)
        # ======================================================
        # (cs1) lam_F3[c] * b_F3[c] = 0, with b_F3[c] = (sum_f q_cf*beta_f + sum_w q_cw*beta_w - alpha_c) >= 0
        m.addConstrs(
            (lam_F3[c] <= data.M_dual["lam_F3"] * bin_F3[c] for c in data.C),
            name=f"{pfx}_CS1_dual",
        )
        m.addConstrs(
            (
                gp.quicksum(q_cf[c, f] * data.beta_f[f] for f in data.F)
                + gp.quicksum(q_scw[s, c, w] * data.beta_w[w] for s in data.S for w in data.W)
                - data.alpha_c[c]
                <= data.M_primal["F3"] * (1 - bin_F3[c])
                for c in data.C
            ),
            name=f"{pfx}_CS1_constr",
        )

        # (cs2) lam_F4[c] * b_F4[c] = 0, with b_F4[c] = (kappa*alpha_c - sum_w q_cw*beta_w) >= 0
        m.addConstrs(
            (lam_F4[c] <= data.M_dual["lam_F4"] * bin_F4[c] for c in data.C),
            name=f"{pfx}_CS2_dual",
        )
        m.addConstrs(
            (
                data.kappa_coproc * data.alpha_c[c]
                - gp.quicksum(q_scw[s, c, w] * data.beta_w[w] for s in data.S for w in data.W)
                <= data.M_primal["F4"] * (1 - bin_F4[c])
                for c in data.C
            ),
            name=f"{pfx}_CS2_constr",
        )

        # (cs3) lam_F5[c] * b_F5[c] = 0, with b_F5[c] = (sum_k x_ck_fixed*Q_k - sum_w q_cw) >= 0
        m.addConstrs(
            (lam_F5[c] <= data.M_dual["lam_F5"] * bin_F5[c] for c in data.C),
            name=f"{pfx}_CS3_dual",
        )
        m.addConstrs(
            (
                gp.quicksum(x_ck_fixed[(c, k)] * data.Q_k[k] for k in data.K)
                - gp.quicksum(q_scw[s, c, w] for s in data.S for w in data.W)
                <= data.M_primal["F5"] * (1 - bin_F5[c])
                for c in data.C
            ),
            name=f"{pfx}_CS3_constr",
        )

        # ---------------------------------------------------------------------
        # Bound complementarity (cs4)-(cs6): pi * q = 0 with pi>=0, q>=0
        # Pattern:
        #   pi <= M_pi * z
        #   q  <= M_q  * (1 - z)
        # ---------------------------------------------------------------------

        # (cs7) pi_q_scw[s,c,w] * q_scw[s,c,w] = 0
        m.addConstrs(
            (pi_q_scw[s, c, w] <= data.M_dual["pi_q_scw"] * bin_q_scw[s, c, w] for s in data.S for c in data.C for w in data.W),
            name=f"{pfx}_CS7_dual",
        )
        m.addConstrs(
            (q_scw[s, c, w] <= data.M_primal["q_scw"] * (1 - bin_q_scw[s, c, w]) for s in data.S for c in data.C for w in data.W),
            name=f"{pfx}_CS7_primal",
        )

        # (cs8) pi_q_cf[c,f] * q_cf[c,f] = 0
        m.addConstrs(
            (pi_q_cf[c, f] <= data.M_dual["pi_q_cf"] * bin_q_cf[c, f] for c in data.C for f in data.F),
            name=f"{pfx}_CS8_dual",
        )
        m.addConstrs(
            (q_cf[c, f] <= data.M_primal["q_cf"] * (1 - bin_q_cf[c, f]) for c in data.C for f in data.F),
            name=f"{pfx}_CS8_primal",
        )

        # (cs10) pi_r_sw[s,w] * r_sw[s,w] = 0
        m.addConstrs(
            (pi_r_sw[s, w] <= data.M_dual["pi_r_sw"] * bin_r_sw[s, w] for s in data.S for w in data.W),
            name=f"{pfx}_CS10_dual",
        )
        m.addConstrs(
            (r_sw[s, w] <= data.M_primal["r_sw"] * (1 - bin_r_sw[s, w]) for s in data.S for w in data.W),
            name=f"{pfx}_CS10_primal",
        )

        # ======================================================
        # Yue Optimality Cut (minimization follower)
        # f(dummy vars) <= f(KKT block vars)
        # ======================================================

        # ----- LEFT HAND SIDE (dummy follower vars in MP) -----

        lhs = (
            # Coal cost
            gp.quicksum(self.q_cf0[c, f]*data.price_f[f] for c in data.C for f in data.F)
            # Investment cost
            + gp.quicksum(data.fixcost_invest_k[k]*self.x_ck0[c, k] for c in data.C for k in data.K)
            # Preprocessing
            + gp.quicksum(self.q_scw0[s, c, w] * data.c_preproc_w[w] for s in data.S for c in data.C for w in data.W)
            # Penalty
            + data.c_penalty * gp.quicksum(self.r_sw0[s, w] for s in data.S for w in data.W)
            # Tie-break
            + data.tau * gp.quicksum(self.q_scw0[s, c, w] * data.TD_sc[s][c] for s in data.S for c in data.C for w in data.W)
            # Subsidy revenue (subtract)
            - gp.quicksum(self.y_wh[w, h] * data.phi_wh[w][h] for w in data.W for h in data.H)
        )

        # ----- RIGHT HAND SIDE (KKT block variables) -----

        # pre-requisit definition of y_wh_KKT for subsidy revenue on RHS: y_wh_KKT[w,h] = z_wh[w,h] * sum_{s,c} q_scw[s,c,w]
        m.addConstrs(
            (y_wh_KKT[w,h] <= self.z_wh[w,h]*data.U_w[w] for w in data.W for h in data.H),
            name=f"{pfx}_y_wh_KKT_def1"
        )
        m.addConstrs(
            (y_wh_KKT[w,h] <= gp.quicksum(q_scw[s,c,w] for s in data.S for c in data.C) for w in data.W for h in data.H),
            name=f"{pfx}_y_wh_KKT_def2"
        )
        m.addConstrs(
            (y_wh_KKT[w,h] >= gp.quicksum(q_scw[s,c,w] for s in data.S for c in data.C) - (1 - self.z_wh[w,h])*data.U_w[w] for w in data.W for h in data.H),
            name=f"{pfx}_y_wh_KKT_def3"
        )

        rhs = (
            # Coal cost
            gp.quicksum(q_cf[c, f] * data.price_f[f] for c in data.C for f in data.F)
            # Investment cost (fixed discrete pattern)
            + gp.quicksum(data.fixcost_invest_k[k] * x_ck_fixed[(c, k)] for c in data.C for k in data.K)
            # Preprocessing
            + gp.quicksum(q_scw[s, c, w] * data.c_preproc_w[w] for s in data.S for c in data.C for w in data.W)
            # Penalty
            + data.c_penalty * gp.quicksum(r_sw[s, w] for s in data.S for w in data.W)
            # Tie-break
            + data.tau * gp.quicksum(q_scw[s, c, w] * data.TD_sc[s][c] for s in data.S for c in data.C for w in data.W)
            # Subsidy revenue (subtract)
            - gp.quicksum(y_wh_KKT[w, h] * data.phi_wh[w][h] for w in data.W for h in data.H)
        )

        # ----- Add Optimality Cut -----

        m.addConstr(lhs <= rhs, name=f"{pfx}_OptimalityCut")
        #endregion

        # create new KKTOCBlock with unique index l and given fixed follower pattern
        kkt_oc_block = KKTOCBlock(
            l=l,
            x_ck_fixed=x_ck_fixed,
            r_sw=r_sw, q_cf=q_cf, y_wh_KKT=y_wh_KKT, q_scw=q_scw,
            lam_F3=lam_F3, lam_F4=lam_F4, lam_F5=lam_F5, nu_F6=nu_F6, nu_F7=nu_F7,
            pi_q_cf=pi_q_cf, pi_q_scw=pi_q_scw, pi_r_sw=pi_r_sw,
            bin_F3=bin_F3, bin_F4=bin_F4, bin_F5=bin_F5,
            bin_q_cf=bin_q_cf, bin_q_scw=bin_q_scw, bin_r_sw=bin_r_sw,
            constr={}
        )
        self.kkt_oc_blocks[kkt_oc_block.l] = kkt_oc_block

        m.update()
        return l
    #endregion

    #region Method for no-good cut to prevent duplicate follower patterns in future iterations
    def _add_no_good_cut(self, x_ck_fixed: Dict[Tuple[int, int], int], name_prefix: str = "NoGoodCut") -> None:
        """
        Method to add a no-good cut to exclude the given fixed follower pattern x_ck_fixed in future iterations
        - creates a no-good cut of the form sum_{c,k} (1 - x_ck_fixed)*x_ck + x_ck_fixed*(1-x_ck) >= 1
        - this ensures that in future iterations, at least one of the x_ck variables must take a different value than in x_ck_fixed
        """
        data = self.instance
        m = self.model

        # Create the no-good cut expression
        expr = gp.LinExpr()
        for c in data.C:
            for k in data.K:
                if int(round(x_ck_fixed[(c, k)])) == 1:
                    expr += (1 - self.x_ck0[c, k])  # If fixed value is 1, we want x_ck to be 0 in future
                else:
                    expr += self.x_ck0[c, k]  # If fixed value is 0, we want x_ck to be 1 in future

        # Add the no-good cut constraint: expr >= 1
        self.no_good_cut_counter += 1
        m.addConstr(expr >= 1, name=f"{name_prefix}_{self.no_good_cut_counter}")
        m.update()
    #endregion