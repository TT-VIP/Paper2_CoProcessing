##########################################
############ Data preparation ############
##########################################

############ Sets ############
G_max = 3        # Number of Generation spots
S_max = 2        # Number of Transfer stations
W_max = 2        # Number of Waste types
I_max = 1        # Number of Incinerators
L_max = 1        # Number of Landfills
C_max = 2        # Number of Cement facilities
K_max = 2        # Number of Pre and Co-processing capacities
F_max = 1        # Number of Coal types as conservative fuel
H_max = 5        # Number of Subsidy levels

G = range(G_max) # Set of Generation spots
S = range(S_max) # Set of Transfer stations
W = range(W_max) # Set of Waste types
I = range(I_max) # Set of Incinerators
L = range(L_max) # Set of Landfills
C = range(C_max) # Set of Cement facilities
K = range(K_max) # Set of Pre and Co-processing capacities
F = range(F_max) # Set of Coal types as conservative fuel
H = range(H_max) # Set of Subsidy levels

############ Parameters ############
#### Leader - Municipality ####
# (Values are illustrative; replace with actual data as needed)
TD_gs = [[50,100],[60,120],[110,40]]     # TD[g,s] Transportation distance from Generation to Transfer
TD_sl = [[200],[180]]                       # TD[s,l] Transportation distance from Transfer to Landfill
TD_si = [[150],[100]]                        # TD[s,i] Transportation distance from Transfer to Incinerator
TD_si_avg = sum(TD_si[s][i] for s in S for i in I) / (S_max * I_max)  # Average transportation distance to incinerator
TD_sc = [[120,200],[250,80]]              # TD[s,c] Transportation distance from Transfer to Cement facility
epsilon_truck = 0.0002          # Emission factor for trucks (ton CO2 per ton-km)
epsilon_land = [0.75,0.64]      # Emission factors for landfills (ton CO2 per ton of waste - high moisture/low moisture)
epsilon_inc = [0.06,0.42]       # Emission factors for incinerators (ton CO2 per ton of waste - high moisture/low moisture)
epsilon_kiln_w = [0.05,0.4]     # Emission factors for waste in cement kilns (ton CO2 per ton of waste - high moisture/low moisture)
epsilon_kiln_f = [2.54]         # Emission factors for coal in cement kilns (ton CO2 per ton of coal)

c_truck = 0.45                   # Transportation cost CNY/ton-km
c_land = 55                      # Landfill cost CNY/ton
c_inc = 120                      # Incineration cost CNY/ton

Q_gw = [[240,110],[180,70],[210,90]]   # Q[g,w] Waste quantity at Generation spots (tons)
Q_gen_total = sum(Q_gw[g][w] for g in G for w in W)  # Total waste generated (tons)
Q_s = [550,550]                     # Q[s] Waste capacity at Transfer stations (tons)
Q_l = [500]                          # Q[l] Waste capacity at Landfills (tons)
Q_i = [450]                           # Q[i] Waste capacity at Incinerators (tons)
Q_k = [200,400]                 # Q[k] Pre-processing capacity at Cement facilities (tons)
Q_k_max = max(Q_k)           # Max cement kiln capacity for co-procesing (tons)

weight_env = 1          # Weight for environmental objective in leader problem
weight_mon = 0.004      # Weight for monetary objective in leader problem
kappa_land = 0.35       # Maximum landfill quota (35% of total waste)
kappa_coproc = 0.4      # Maximum co-processing quota (40% of energy content needed at kiln)
budget_municipality = 800000  # Municipality budget for subsidies (CNY)
phi_max = [150,200]     # Maximum subsidy levels for waste types (CNY/ton) - high moisture/low moisture
phi_wh = [[(h / (H_max-1)) * phi_max[w] for h in range(H_max)] for w in range(W_max)]   # Subsidy levels for waste types phi[w,h] derived from set H and max subsidy values

#### Follower - Cement Facility ####
price_f = [650]              # Price of coal (CNY/ton)
c_invest_k = [70000000,125000000] # Investment cost for pre- & co-processing capacity expansion at Cement facilities depending on size k (CNY)
c_preproc_w = [150.0, 110.0]    # Pre-processing cost (CNY/ton)
c_penalty = 100                 # Penalty cost for denying allocated waste quota (CNY/ton)
budget_cem = 150000000          # Cement facility budget for investing in pre- & co-processing (CNY)
alpha_c = [10000,8000]       # Energy content needed in cement kiln (GJ/ton)
beta_f = [25]                # Energy content of coal (GJ/ton)
beta_w = [8,16]             # Energy content of waste types (GJ/ton) - high moisture/low moisture
eta_w = [0.65, 0.2]          # Weight reduction after pre-processing for waste types (0 < eta_w <= 1, where 1 means no reduction)

tau = 10e-4                     # Small positive value for follower objective to account for leader cost (avoids symmetries)

# Levelized daily fixed cost per option k
i_rate = 0.0325
lifetime_years = 15

def crf(i: float, n: int) -> float:
    return (i * (1 + i) ** n) / ((1 + i) ** n - 1)
CRF = crf(i_rate, lifetime_years)
capex_ann = [c_invest_k[k] * CRF for k in K]
opex_fix_ann = [c_invest_k[k] * 0.06 for k in K]
fixcost_invest_k = [(capex_ann[k] + opex_fix_ann[k]) / 1000 for k in K]

# Big-M value for cut generation
M_primal = {
    'F3': 10,
    'F4': max(alpha_c)*kappa_coproc,     # Maximmum energy content in co-processing
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
    'lam_F5': 10**6,     # Big-M for dual variable of constraint F5 (co-process capacity limited by investment decision)
    'lam_F9_1': 10**6,   # Big-M for dual variable of constraint F9_1 (linking co-processing quantity to subsidy level h)
    'lam_F9_2': 10**6,   # Big-M for dual variable of constraint F9_2 (linking co-processing quantity to subsidy level h)
    'lam_F9_3': 10**6,   # Big-M for dual variable of constraint F9_3 (linking co-processing quantity to subsidy level h)
    'pi_q_cw': 10**6,    # Big-M for dual variable of constraint limiting quantity of waste processed at cement plant
    'pi_q_cf': 10**6,    # Big-M for dual variable of constraint limiting quantity of coal processed at cement plant
    'pi_q_scw': 10**6,   # Big-M for dual variable of constraint limiting quantity of waste allocated from transfer station to cement plant
    'pi_r_sw': 10**6,    # Big-M for dual variable of constraint limiting residual waste at transfer station after allocation
    'pi_y_cwh': 10**6    # Big-M for dual variable of constraint linking subsidy level to co-processing quantity
}

U_w = [min(sum(Q_gw[g][w] for g in G), Q_k_max*len(C)) for w in W]  # Upper bound on waste flow of type w (can be tightened based on data)