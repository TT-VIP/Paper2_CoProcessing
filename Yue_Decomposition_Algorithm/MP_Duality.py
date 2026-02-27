import gurobipy as gp
from gurobipy import GRB

from instance_loader import InstanceData

from typing import Dict, Tuple
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

        # Variable Containers (filled in build())
        # Leader
        self.q_gsw = None
        self.q_slw = None
        self.q_siw = None
        self.mu_land = None
        self.mu_inc = None
        self.mu_kiln = None
        self.z_wh = None

        # Dummy Follower variables
        self.x_ck0 = None
        self.q_cw0 = None
        self.r_sw0 = None
        self.q_cf0 = None
        self.y_cwh0 = None
        self.q_scw0 = None


    # (2) Setup model direcctly when initializing an object of the class
        # in this case, an object represents a model; model is always alive
        # - init creates model object
        # - build() only populates it, i.e. adds variables, constraints, objective, updates it
    '''
    def __init__(self, instance: InstanceData, *, name: str = "MP", output_flag: int = 1):
        self.instance = instance
        self.model = gp.Model(name)
        self.model.setParam('OutputFlag', output_flag)
    '''
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
        
        print("\nMaster Problem model structure:\n")
        print(f"  → Total created variables: {self.model.NumVars}")
        print(f"  → Thereof binary variables: {self.model.NumBinVars}")
        print(f"  → Thereof continuous variables: {self.model.NumVars - self.model.NumBinVars}")

        print(f"  → Total created constraints: {self.model.NumConstrs}")
        
        self._build = True
        # if the model shall be rebuild, set object._build = False before calling build() again
    #endregion


    #region Method to solve the Master problem
    def solve(self):
        # Not necessary to check, if the model is built directly within __init__
        assert self.model is not None, "Model is not built yet. Call build() before solve()."
        
        """Solve the Master Problem"""
        print("\n" + "-"*60)
        print("Solving Master Problem...")
        print("-"*60)
        self.model.optimize()
    #endregion


    #region Method to store solution within a dataclass
    def extract_solution(self) -> MasterSolution:
        """Extract solution from the Master Problem"""
        if self.model.status == GRB.OPTIMAL:
            print('✓ Master Problem solved optimally.')
        elif self.model.status == GRB.SUBOPTIMAL:
            print('⚠ Master Problem solved suboptimally.')
        elif self.model.status == GRB.TIME_LIMIT:
            print('⚠ Master Problem solve reached time limit.')
        else:
            raise RuntimeError("Master Problem is not (sub)optimal; cannot extract solution.")

        data = self.instance

        return MasterSolution(
            mp_obj=self.model.ObjVal,
            q_gsw={
                (g, s, w): self.q_gsw[g, s, w].X
                for g in data.G
                for s in data.S
                for w in data.W
            },
            q_slw={
                (s, l, w): self.q_slw[s, l, w].X
                for s in data.S
                for l in data.L
                for w in data.W
            },
            q_siw={
                (s, i, w): self.q_siw[s, i, w].X
                for s in data.S
                for i in data.I
                for w in data.W
            },
            mu_land=self.mu_land.X,
            mu_inc=self.mu_inc.X,
            mu_kiln=self.mu_kiln.X,
            z_wh={
                (w, h): int(round(self.z_wh[w, h].X))       # rounding because of floating-point relaxation within gurobi (0.9999997 or 1.0000002 possible)
                for w in data.W
                for h in data.H
            }
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

        # ===== DUMMY FOLLOWER VARIABLES (FOR CUT GENERATION) =====
        self.x_ck0 = m.addVars(data.C, data.K, vtype=GRB.BINARY, name="x_ck0")
        self.q_cw0 = m.addVars(data.C, data.W, lb=0.0, vtype=GRB.CONTINUOUS, name="q_cw0")
        self.r_sw0 = m.addVars(data.S, data.W, lb=0.0, vtype=GRB.CONTINUOUS, name="r_sw0")
        self.q_cf0 = m.addVars(data.C, data.F, lb=0.0, vtype=GRB.CONTINUOUS, name="q_cf0")
        self.y_cwh0 = m.addVars(data.C, data.W, data.H, lb=0.0, vtype=GRB.CONTINUOUS, name="y_cwh0")
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
                # superfluous due to F8-0 !
        m.addConstrs(
            (gp.quicksum(self.q_gsw[g,s,w] for g in data.G) >=
            gp.quicksum(self.q_slw[s,l,w] for l in data.L) + gp.quicksum(self.q_siw[s,i,w] for i in data.I)
            for s in data.S for w in data.W),
        name="L2_wasteDispatching"
        )

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
            gp.quicksum(data.phi_wh[w][h] * self.y_cwh0[c,w,h] for c in data.C for w in data.W for h in data.H) <= data.budget_municipality,
        name="L10_municipalityBudget"
        )
        
        # (L11) Quotas must sum to 1
        m.addConstr(
            self.mu_land +self.mu_inc + self.mu_kiln == 1,
        name="L11_quotaBalance"
        )

        # (L12) Landfill quota cannot exceed policy limit
        m.addConstr(
            self.mu_land <= data.kappa_land,
        name="L12_landfillQuotaLimit"
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
            (gp.quicksum(self.q_cf0[c,f] * data.beta_f[f] for f in data.F) + gp.quicksum(self.q_cw0[c,w] * data.beta_w[w] for w in data.W) >= data.alpha_c[c] for c in data.C),
        name="F3-0_energyFulfillment"
        )

        # (F4-0) Co-processing capacity limitation
        m.addConstrs(
            (gp.quicksum(self.q_cw0[c,w] * data.beta_w[w] for w in data.W) <= data.kappa_coproc * data.alpha_c[c] for c in data.C),
        name="F4-0_coprocCapacityLimit"
        )

        # (F5-0) Pre- & co-processing capacity according to investment decision
        m.addConstrs(
            (gp.quicksum(self.q_cw0[c,w] for w in data.W) <= gp.quicksum(self.x_ck0[c,k] * data.Q_k[k] for k in data.K) for c in data.C),
        name="F5-0_investmentCapacity"
        )

        # (F6-0) Waste quota fulfillment at cement facility
        m.addConstr(
            (gp.quicksum(self.q_cw0[c,w] for c in data.C for w in data.W) + gp.quicksum(self.r_sw0[s,w] for s in data.S for w in data.W) ==
            self.mu_kiln * data.Q_gen_total),
        name="F6-0_wasteQuotaFulfillment",
        )

        # (F7-0) Waste transport to cement facility must equal waste used at cement facility
        m.addConstrs(
            (self.q_cw0[c,w] == gp.quicksum(self.q_scw0[s,c,w] for s in data.S) for c in data.C for w in data.W),
        name="F7-0_wasteTransport"
        )

        # (F8-0) Waste transport balance
        m.addConstrs(
            (gp.quicksum(self.q_gsw[g,s,w] for g in data.G) ==
            gp.quicksum(self.q_slw[s,l,w] for l in data.L) +
            gp.quicksum(self.q_siw[s,i,w] for i in data.I) +
            gp.quicksum(self.q_scw0[s,c,w] for c in data.C) + self.r_sw0[s,w] for s in data.S for w in data.W),
        name="F8-0_wasteTransportBalance"
        )

        # (F9-0) Subsidy level selection constraints (linearization)
        m.addConstrs(
            (self.y_cwh0[c,w,h] <= self.z_wh[w,h] * data.Q_k_max for c in data.C for w in data.W for h in data.H),
        name="F9-0_subsidyLevelSelection_1"
        )
        m.addConstrs(
            (self.y_cwh0[c,w,h] <= self.q_cw0[c,w] for c in data.C for w in data.W for h in data.H),
        name="F9-0_subsidyLevelSelection_2"
        )
        m.addConstrs(
            (self.y_cwh0[c,w,h] >= self.q_cw0[c,w] - data.Q_k_max*(1 - self.z_wh[w,h]) for c in data.C for w in data.W for h in data.H),
        name="F9-0_subsidyLevelSelection_3"
        )
        #endregion
    #endregion

    #region Method to set objective function
    def _set_objective(self) -> None:
        data = self.instance
        m = self.model

        # ===== LEADER OBJECTIVE =====
        # 1) Transport emissions
        emission_transport = data.epsilon_truck * (
            gp.quicksum(self.q_gsw[g,s,w] * data.TD_gs[g][s] for g in data.G for s in data.S for w in data.W) +
            gp.quicksum(self.q_slw[s,l,w] * data.TD_sl[s][l] for s in data.S for l in data.L for w in data.W) +
            gp.quicksum(self.q_siw[s,i,w] * data.TD_si[s][i] for s in data.S for i in data.I for w in data.W) +
            gp.quicksum(self.q_scw0[s,c,w] * data.TD_sc[s][c] for s in data.S for c in data.C for w in data.W)
        )

        # 2) Treatment emissions
        emission_treatment = (
            gp.quicksum(data.epsilon_land[w] * self.q_slw[s,l,w] for s in data.S for l in data.L for w in data.W) +
            gp.quicksum(data.epsilon_inc[w] * self.q_siw[s,i,w] for s in data.S for i in data.I for w in data.W) +
            gp.quicksum(data.epsilon_inc[w] * self.r_sw0[s,w] for s in data.S for w in data.W)
        )

        # 3) Fuel emissions (cement kiln)
        emission_fuel = (
            gp.quicksum(data.epsilon_kiln_f[f] * self.q_cf0[c,f] for c in data.C for f in data.F) +
            gp.quicksum(data.epsilon_kiln_w[w] * self.q_cw0[c,w] for c in data.C for w in data.W)
        )

        # 4) Transport costs
        cost_transport = data.c_truck * (
            gp.quicksum(self.q_gsw[g,s,w] * data.TD_gs[g][s] for g in data.G for s in data.S for w in data.W) +
            gp.quicksum(self.q_slw[s,l,w] * data.TD_sl[s][l] for s in data.S for l in data.L for w in data.W) +
            gp.quicksum(self.q_siw[s,i,w] * data.TD_si[s][i] for s in data.S for i in data.I for w in data.W) +
            gp.quicksum(self.q_scw0[s,c,w] * data.TD_sc[s][c] for s in data.S for c in data.C for w in data.W) +
            gp.quicksum(self.r_sw0[s,w] * data.TD_si_avg for s in data.S for w in data.W)
        )

        # 5) Treatment costs
        cost_treatment = (
            data.c_land * gp.quicksum(self.q_slw[s,l,w] for s in data.S for l in data.L for w in data.W) +
            data.c_inc * gp.quicksum(self.q_siw[s,i,w] for s in data.S for i in data.I for w in data.W) +
            (data.c_inc-data.c_penalty) * gp.quicksum(self.r_sw0[s,w] for s in data.S for w in data.W)
            # data.c_inc * gp.quicksum(self.r_sw0[s,w] for s in data.S for w in data.W)
        )

        # 6) Subsidy cost
        cost_subsidy = gp.quicksum(data.phi_wh[w][h] * self.y_cwh0[c,w,h] for c in data.C for w in data.W for h in data.H)

        m.setObjective(
            data.weight_env*(emission_transport + emission_treatment + emission_fuel) +
            data.weight_mon*(cost_transport + cost_treatment + cost_subsidy),
            GRB.MINIMIZE)

    #endregion