from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import List, Dict, Tuple


##########################################
############ Data class ############
###########################################
@dataclass(frozen=False)
class ShanghaiInstance:
    # Sets (sizes)
    G_max: int      # Number of Generation spots
    S_max: int      # Number of Transfer stations
    W_max: int      # Number of Waste types
    I_max: int      # Number of Incinerators
    L_max: int      # Number of Landfills
    C_max: int      # Number of Cement facilities
    K_max: int      # Number of available Pre- and Co-processing capacities
    F_max: int      # Number of Coal types as conservative fuel
    H_max: int      # Number of Subsidy levels

    # Index sets
    G: range        # Set of Generation spots
    S: range        # Set of Transfer stations
    W: range        # Set of Waste types
    I: range        # Set of Incinerators
    L: range        # Set of Landfills
    C: range        # Set of Cement facilities
    K: range        # Set of available Pre- and Co-processing capacities
    F: range        # Set of Coal types as conservative fuel
    H: range        # Set of Subsidy levels 

    # Names (optional)
    cement_names: List[str]

    # Distances (km)
    TD_gs: List[List[int]]      # TD[g][s] Transportation distance from Generation to Transfer
    TD_sl: List[List[int]]      # TD[s][l] Transportation distance from Transfer to Landfill
    TD_si: List[List[int]]      # TD[s][i] Transportation distance from Transfer to Incinerator
    TD_si_avg: float            # Average transportation distance to incinerator
    TD_sc: List[List[int]]      # TD[s][c] Transportation distance from Transfer to Cement facility

    # Leader parameters
    epsilon_truck: float            # Emission factor for trucks (ton CO2 per ton-km)
    epsilon_land: List[float]       # Emission factors for landfills (ton CO2e per ton)
    epsilon_inc: List[float]        # Emission factors for incinerators (ton CO2e per ton)
    epsilon_kiln_w: List[float]     # Emission factors for kiln waste (ton CO2 per ton)
    epsilon_kiln_f: List[float]     # Emission factors for kiln fuel (ton CO2 per ton)  
    c_truck: float          # Transportation cost (CNY/ton-km)
    c_land: float           # Landfill cost (CNY/ton)
    c_inc: float            # Incineration cost (CNY/ton)

    # Waste quantities (t/day)
    Q_gw: List[List[int]]       # Q[g][w] Waste quantity at Generation spots
    Q_gen_total: int                  # Total generated waste (t/day)
    Q_s: List[int]              # Q[s] Capacity at Transfer stations
    Q_l: List[int]              # Q[l] Capacity at Landfills
    Q_i: List[int]              # Q[i] Capacity at Incinerators

    # Co-processing capacity options (t/day)
    Q_k: List[int]              # Q[k] Available Pre- & Co-processing capacities or investment at Cement facilities
    Q_k_max: int                # Max cement kiln capacity for co-procesing (tons)

    # Objective weights & policy
    weight_env: float               # Weight for environmental objective in leader problem
    weight_mon: float               # Weight for monetary objective in leader problem
    kappa_land: float               # Maximum allowed landfill quota/capacity
    kappa_coproc: float             # Maximum co-processing quota/capacity
    budget_municipality: float      # Budget for the municipality
    phi_max: List[float]            # Maximum subsidy levels for waste types (CNY/ton)
    phi_wh: List[List[float]]   # phi[w][h] Subsidy levels for waste types
    
    # Follower parameters
    price_f: List[float]        # p[f] Price of coal types (CNY/t)
    beta_f: List[float]         # beta[f] Calorific value of coal types (GJ/t)
    alpha_c: List[float]        # alpha[c] Energy requirement of cement kiln (GJ/period) (or consistent with your model)
    beta_w: List[float]         # beta[w] Calorific value of waste types (GJ/t)

    c_invest_k: List[float]         # c_invest[k] Investment cost for Pre- & Co-processing facility per capacity (CNY)
    c_preproc_w: List[float]        # c_preproc[w] Pre-processing cost per waste type (CNY/t)
    c_penalty: float                # Penalty cost for denying allocated waste quota (CNY/t)
    budget_cem: float               # Budget of the cement producers (CNY)

    tau: float            # Symmetry breaking parameter for follower problem

    # Fix-cost invest-equivalent per capacity (CNY/period)
    fixcost_invest_k: List[float]

    # Big-M values for primal and dual variables in KKT cuts
    M_primal: Dict[str, float]
    M_dual: Dict[str, float]

##########################################
############ Data definition ############
##########################################
def crf(i: float, n: int) -> float:
    return (i * (1 + i) ** n) / ((1 + i) ** n - 1)


def make_shanghai_instance_scaled(seed: int = 7) -> ShanghaiInstance:
    rng = random.Random(seed)

    # -----------------------------
    # SETS
    # -----------------------------
    # This keeps your TD_trans meaningful without exploding size too much.
    G_max = 8
    S_max = 8
    W_max = 2
    I_max = 6
    L_max = 3
    C_max = 6
    K_max = 3
    F_max = 2
    H_max = 5

    G = range(G_max)
    S = range(S_max)
    W = range(W_max)
    I = range(I_max)
    L = range(L_max)
    C = range(C_max)
    K = range(K_max)
    F = range(F_max)
    H = range(H_max)

    cement_names = [
        "Anhui Conch Cement (cluster)",
        "Suzhou Dahua Marine",
        "Jiangsu Pengfei (Haian)",
        "Zhejiang Producer A",
        "Jiangsu Producer A",
        "Anhui Producer A",
    ]

    # -----------------------------
    # DISTANCES (km) - synthetic but plausible
    # Shanghai districts -> local transfer: 5..30 km
    # transfer -> incinerator: 10..60 km
    # transfer -> landfill (neighbour districts): 30..120 km
    # transfer -> cement (Jiangsu/Anhui/Zhejiang): 80..320 km
    # -----------------------------
    TD_gs = [[rng.randint(10, 50) for s in S] for g in G]
    # Each district mainly to the local transfer station via bias diagonals:
    for g in G:
        for s in S:
            if g == s:
                TD_gs[g][s] = rng.randint(2, 10)

    TD_si = [[rng.randint(0, 60) for i in I] for s in S]
    TD_si_avg = sum(TD_si[s][i] for s in S for i in I) / (S_max * I_max)
    TD_sl = [[rng.triangular(60, 150, 110) for l in L] for s in S]
    TD_sc = [[rng.triangular(80, 360, 220) for c in C] for s in S]

    # -----------------------------
    # EMISSIONS / COSTS
    # w=0: high moisture/chlorine (worse), w=1: medium moisture/chlorine (better)
    # -----------------------------
    epsilon_truck = 0.0002  # tCO2 per t-km (your value)
    epsilon_land = [1.7, 1.0]
    epsilon_inc = [0.54, 0.42]
    epsilon_kiln_w = [0.30, 0.15]
    epsilon_kiln_f = [2.54, 2.22]  # same factor, two coal types

    c_truck = 0.45
    c_land = 55.0
    c_inc = 120.0

    # -----------------------------
    # WASTE GENERATION (t/day): Shanghai-sized synthetic
    # Total MSW in Shanghai is very large; for computational tests keep totals moderate first
    # Generate around 6,000–9,000 t/day in total (~0.1%, normally 9,000,000 per year)
    # Split by type: 55% high moisture, 45% medium moisture.
    # -----------------------------
    total_target = rng.randint(6000, 9000)
    # split = [0.55, 0.45]      # fixed split
    # distribute by district (G) using a Dirichlet-like random split
    weights = [rng.random() for _ in G]
    sw = sum(weights)
    weights = [w / sw for w in weights]

    Q_gw = []
    for g in G:
        g_total = int(round(total_target * weights[g]))
        split_w0 = rng.uniform(0.4, 0.7)
        split = [split_w0, 1 - split_w0]
        
        q0 = int(round(g_total * split[0]))
        q1 = max(0, g_total - q0)
        Q_gw.append([q0, q1])

    Q_gen_total = sum(Q_gw[g][w] for g in G for w in W)

    # Transfer capacity: ensure > inbound per station; keep loose
    # If each district maps mostly to one transfer, set capacity around 700..1100 t/day
    # Q_trans = [rng.randint(700, 1100) for _ in S]
    Q_s = [int(round(rng.triangular(900, 1400, 1200) / 10) * 10) for _ in S]

    # Incineration and landfill capacities:
    # Set so that inc+land can cover all waste (to avoid forced investment),
    # but landfill quota still restricts landfill share.
    Q_i = [rng.triangular(700, 1200, 950) for _ in I]  # 6 plants
    Q_l = [rng.triangular(1000, 1300, 1200) for _ in L]  # 3 sites

    # -----------------------------
    # CO-PROCESSING OPTIONS (t/day)
    # -----------------------------
    Q_k = [200, 350, 500]
    Q_k_max = max(Q_k)

    # -----------------------------
    # POLICY / WEIGHTS
    # -----------------------------
    weight_env = 1.0
    weight_mon = 0.004
    kappa_land = 0.35
    kappa_coproc = 0.40

    budget_municipality = 1_800_000.0  # scale up vs small toy
    phi_max = [220.0, 175.0]  # [high moisture, medium moisture]
    phi_wh = [[(h / (H_max - 1)) * phi_max[w] for h in H] for w in W]

    # -----------------------------
    # FOLLOWER: coal types, costs, kiln demands
    # -----------------------------
    # Coal mixtures: e.g., standard and higher-quality
    price_f = [420.0, 520.0]   # CNY/t
    beta_f = [24.0, 27.0]      # GJ/t (two mixes)

    # Kiln daily energy requirement: scale with 6 cement plants
    alpha_c = [rng.randint(7000, 12000) for _ in C]

    beta_w = [8.0, 16.0]

    # Investment CAPEX by option size (CNY) – extend to K=3
    c_invest_k = [70_000.0, 110_000.0, 150_000.0]

    # Preprocessing cost by waste type
    c_preproc_w = [150.0, 110.0]

    c_penalty = 160.0
    budget_cem = 350_000.0  # bigger portfolio-level budget for 6 plants

    tau = 1e-3

    # Levelized daily fixed cost per option k
    i_rate = 0.0325
    lifetime_years = 15
    CRF = crf(i_rate, lifetime_years)
    capex_ann = [c_invest_k[k] * CRF for k in K]
    opex_fix_ann = [c_invest_k[k] * 0.06 for k in K]
    fixcost_invest_k = [(capex_ann[k] + opex_fix_ann[k]) / 1000 for k in K]

    # Big-M value for cut generation
    M_primal = {
        'F3': 10,
        'F4': max(alpha_c)*kappa_coproc+10,     # Maximmum energy content in co-processing
        'F5': Q_k_max+1,                       # Maximum co-processing quantity
        'F9_1': Q_k_max+1,                      # Maximum co-processing quantity
        'F9_2': Q_k_max+1,                       # Maximum co-processing quantity
        'F9_3': Q_k_max+1,                       # Maximum co-processing quantity
        'q_cw': Q_k_max+1,                       # Maximum quantity of waste processed at cement plant
        'q_cf': max(alpha_c)+10,                   # Maximum quantity of coal processed at cement plant (based on maximum energy content needed)
        'q_scw': Q_k_max+1,                      # Maximum quantity of waste allocated from transfer station to cement plant
        'r_sw': max(Q_s)+1,                       # Maximum residual waste at transfer station after allocation
        'y_cwh': Q_k_max+1                       # Maximum quantity of waste allocated to subsidy level h at cement plant c
    }

    M_dual = {
        'lam_F3': 10**6,     # Big-M for dual variable of constraint F3 (energy fulfillment constraint)
        'lam_F4': 10**6,     # Big-M for dual variable of constraint F4 (maximum co-processing quantity)
        'lam_F5': 10**10,     # Big-M for dual variable of constraint F5 (co-process capacity limited by investment decision)
        'lam_F9_1': 10**20,   # Big-M for dual variable of constraint F9_1 (linking co-processing quantity to subsidy level h)
        'lam_F9_2': 10**10,   # Big-M for dual variable of constraint F9_2 (linking co-processing quantity to subsidy level h)
        'lam_F9_3': 10**6,   # Big-M for dual variable of constraint F9_3 (linking co-processing quantity to subsidy level h)
        'pi_q_cw': 10**8,    # Big-M for dual variable of constraint limiting quantity of waste processed at cement plant
        'pi_q_cf': 10**6,    # Big-M for dual variable of constraint limiting quantity of coal processed at cement plant
        'pi_q_scw': 10**10,   # Big-M for dual variable of constraint limiting quantity of waste allocated from transfer station to cement plant
        'pi_r_sw': 10**10,    # Big-M for dual variable of constraint limiting residual waste at transfer station after allocation
        'pi_y_cwh': 10**20    # Big-M for dual variable of constraint linking subsidy level to co-processing quantity
    }

    return ShanghaiInstance(
        G_max=G_max, S_max=S_max, W_max=W_max, I_max=I_max, L_max=L_max, C_max=C_max,
        K_max=K_max, F_max=F_max, H_max=H_max,
        G=G, S=S, W=W, I=I, L=L, C=C, K=K, F=F, H=H,
        cement_names=cement_names,
        TD_gs=TD_gs, TD_sl=TD_sl, TD_si=TD_si, TD_si_avg=TD_si_avg, TD_sc=TD_sc,
        epsilon_truck=epsilon_truck,
        epsilon_land=epsilon_land, epsilon_inc=epsilon_inc, epsilon_kiln_w=epsilon_kiln_w, epsilon_kiln_f=epsilon_kiln_f,
        c_truck=c_truck, c_land=c_land, c_inc=c_inc,
        Q_gw=Q_gw, Q_gen_total=Q_gen_total,
        Q_s=Q_s, Q_l=Q_l, Q_i=Q_i,
        Q_k=Q_k, Q_k_max=Q_k_max,
        weight_env=weight_env, weight_mon=weight_mon,
        kappa_land=kappa_land, kappa_coproc=kappa_coproc,
        budget_municipality=budget_municipality,
        phi_max=phi_max,
        phi_wh=phi_wh,
        price_f=price_f, beta_f=beta_f,
        alpha_c=alpha_c, beta_w=beta_w,
        c_invest_k=c_invest_k, c_preproc_w=c_preproc_w,
        c_penalty=c_penalty, budget_cem=budget_cem,
        tau=tau,
        fixcost_invest_k=fixcost_invest_k,
        M_primal=M_primal, M_dual=M_dual
    )
