import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

"""
Instance Loader Module
Loads and manages instance data for the bilevel optimization model
"""

class InstanceData:
    """
    Container class for all instance data (sets, parameters)
    Loads from test_instance.py or external files
    """
    
    def __init__(self):
        """Initialize instance data from test_instance module"""
        from test_instance import (
            # Sets
            G_max, S_max, W_max, I_max, L_max, C_max, K_max, F_max, H_max,
            G, S, W, I, L, C, K, F, H, J,
            # Leader parameters
            TD_gs, TD_sl, TD_si, TD_si_avg, TD_sc,
            epsilon_truck, epsilon_land, epsilon_inc, epsilon_kiln_w, epsilon_kiln_f,
            c_truck, c_land, c_inc,
            Q_gw, Q_gen_total,Q_s, Q_l, Q_i, Q_k, Q_k_max,
            weight_env, weight_mon, kappa_land, kappa_coproc,
            budget_municipality, phi_max, phi_wh,
            # Follower parameters
            price_f, c_invest_k, c_preproc_w, c_penalty, budget_cem,
            alpha_c, beta_f, beta_w, eta_w, tau,
            fixcost_invest_k, CRF,
            M_primal, M_dual, U_w
        )
        
        # ===== SETS =====
        self.G_max = G_max
        self.S_max = S_max
        self.W_max = W_max
        self.I_max = I_max
        self.L_max = L_max
        self.C_max = C_max
        self.K_max = K_max
        self.F_max = F_max
        self.H_max = H_max
        
        self.G = G
        self.S = S
        self.W = W
        self.I = I
        self.L = L
        self.C = C
        self.K = K
        self.F = F
        self.H = H
        
        # ===== LEADER (MUNICIPALITY) PARAMETERS =====
        self.TD_gs = TD_gs
        self.TD_sl = TD_sl
        self.TD_si = TD_si
        self.TD_si_avg = TD_si_avg
        self.TD_sc = TD_sc
        
        self.epsilon_truck = epsilon_truck
        self.epsilon_land = epsilon_land
        self.epsilon_inc = epsilon_inc
        self.epsilon_kiln_w = epsilon_kiln_w
        self.epsilon_kiln_f = epsilon_kiln_f
        
        self.c_truck = c_truck
        self.c_land = c_land
        self.c_inc = c_inc
        
        self.Q_gw = Q_gw
        self.Q_gen_total = Q_gen_total
        self.Q_s = Q_s
        self.Q_l = Q_l
        self.Q_i = Q_i
        self.Q_k = Q_k
        self.Q_k_max = Q_k_max
        
        self.weight_env = weight_env
        self.weight_mon = weight_mon
        self.kappa_land = kappa_land
        self.kappa_coproc = kappa_coproc
        self.budget_municipality = budget_municipality
        self.phi_max = phi_max
        self.phi_wh = phi_wh
        
        # ===== FOLLOWER (CEMENT FACILITY) PARAMETERS =====
        self.price_f = price_f
        self.c_invest_k = c_invest_k
        self.c_preproc_w = c_preproc_w
        self.c_penalty = c_penalty
        self.budget_cem = budget_cem
        
        self.alpha_c = alpha_c
        self.beta_f = beta_f
        self.beta_w = beta_w
        self.eta_w = eta_w
        
        self.tau = tau
        self.fixcost_invest_k = fixcost_invest_k
        self.CRF = CRF

        self.M_primal = M_primal
        self.M_dual = M_dual

        self.U_w = U_w
    
    def validate(self):
        """Validate instance data for consistency and feasibility"""
        # Example validations
        assert self.G_max > 0, "Number of generation spots must be positive"
        assert self.C_max > 0, "Number of cement facilities must be positive"
        assert self.budget_municipality > 0, "Municipality budget must be positive"
        assert self.budget_cem > 0, "Cement facility budget must be positive"
        print("✓ Instance data validated successfully")


# Determine the file both as a importable module (via from instance_loader import InstanceData) and as a standalone script
# If run as a standalone script, the name is automatically set to "__main__", thus a simple instance is created, validated and a few prints are performed
if __name__ == "__main__":
    # Test instance loader
    instance = InstanceData()
    instance.validate()
    print("\nInstance Data Loaded:")
    print(f"  - Generation spots: {instance.G_max}")
    print(f"  - Transfer stations: {instance.S_max}")
    print(f"  - Waste types: {instance.W_max}")
    print(f"  - Cement facilities: {instance.C_max}")
    print(f"  - Municipality budget: {instance.budget_municipality:,.0f} CNY")
    print(f"  - Cement facility budget: {instance.budget_cem:,.0f} CNY")
