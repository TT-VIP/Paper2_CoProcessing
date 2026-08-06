from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path 
import math
import random
from typing import List, Dict, Tuple, Any


##########################################
############ Data class ############
###########################################
#region Instance data class
@dataclass(frozen=False)
class InstanceData:
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
    # eta_w: List[float]          # eta[w] Weight reductio after pre-processing for waste type w (0 < eta_w <= 1, where 1 means no reduction)

    c_invest_k: List[float]         # c_invest[k] Investment cost for Pre- & Co-processing facility per capacity (CNY)
    c_preproc_w: List[float]        # c_preproc[w] Pre-processing cost per waste type (CNY/t)
    c_penalty: float                # Penalty cost for denying allocated waste quota (CNY/t)
    budget_cem: float               # Budget of the cement producers (CNY)

    tau: float            # Symmetry breaking parameter for follower problem

    # Fix-cost invest-equivalent per capacity (CNY/period)
    fixcost_invest_k: List[float]

    # Big-M values for primal and dual variables in KKT cuts
    M_primal: Dict[str, float | Dict[int | float, Any]]   # Big-M values for primal variables in KKT cuts (indexed dictionary by s for r_sw)
    M_dual: Dict[str, float]

    U_w: List[int]          # Upper bound on waste flow of type w (can be tightened based on data)

    # multi-objective weights and bounds
    weight_env: float = 0.5               # Weight for environmental objective in leader problem
    weight_mon: float = 0.5               # Weight for monetary objective in leader problem
    Emission_min: float | None = None            # Minimum emissions (single objective for normalization)
    Emission_max: float | None = None            # Maximum emissions (single objective for normalization)
    Cost_min: float | None = None            # Minimum cost (single objective for normalization)
    Cost_max: float | None = None            # Maximum cost (single objective for normalization)
#endregion

##########################################
############ Helper functions ############
##########################################
# region Helper functions

# Capital Recovery Factor for annualizing investment costs: 
# CRF(i,n) = (i*(1+i)^n)/((1+i)^n-1) 
# where i is the interest rate and n is the number of periods
# used to convert an upfront investment cost into an equivalent periodic cost for comparison with operational costs in the objective function
def crf(i: float, n: int) -> float:
    return (i * (1 + i) ** n) / ((1 + i) ** n - 1)

Point = Tuple[float, float]
CoordinateDict = Dict[int, Point]

# Function to generate waste generation points
# Fixed demand grid based on city size and cell size parameters, because waste is generated by all households across the city 
# and thus the generation points are not really random, but rather determined by the urban structure; this also keeps the TD 
# matrices consistent across different runs and allows for more meaningful analysis of the results
def generate_waste_generation_points(
    city_size: float,
    cell_size: float,
    center: Point = (0.0, 0.0),
) -> CoordinateDict:
    """
    Generate deterministic grid-cell centers for the urban demand area.

    Example:
        city_size = 40, cell_size = 10
        -> 4 x 4 = 16 generation spots.
    """
    if city_size <= 0:
        raise ValueError("city_size must be positive.")
    if cell_size <= 0:
        raise ValueError("cell_size must be positive.")
    if not math.isclose(city_size / cell_size, round(city_size / cell_size)):
        raise ValueError("city_size must be divisible by cell_size.")

    n_cells_axis = int(round(city_size / cell_size))
    half = city_size / 2.0
    cx, cy = center

    points: CoordinateDict = {}
    idx = 0

    for ix in range(n_cells_axis):
        for iy in range(n_cells_axis):
            x = cx - half + (ix + 0.5) * cell_size
            y = cy - half + (iy + 0.5) * cell_size
            points[idx] = (x, y)
            idx += 1

    return points

# Function to compute the number of generation points based on city size and cell size parameters
def compute_grid_generation_count(city_size: float, cell_size: float) -> int:
    if city_size <= 0:
        raise ValueError("city_size must be positive.")
    if cell_size <= 0:
        raise ValueError("cell_size must be positive.")
    if not math.isclose(city_size / cell_size, round(city_size / cell_size)):
        raise ValueError("city_size must be divisible by cell_size.")
    
    cells_per_axis = int(round(city_size / cell_size))
    return cells_per_axis ** 2

# Transfer-station placement
# Random, but spatially disperesed. Divide the city into coarse blocks and place transfer stations approximately evenly across the area.
# For example, if S_max=8, place transfer stations in 8 randomly selected grid cells or in a roughly balanced layout.
def generate_transfer_stations(
    n_points: int,
    rng: random.Random,
    city_size: float,
    center: Point = (0.0, 0.0),
) -> CoordinateDict:
    """
    Generate random points in a city box, but distribute them more evenly
    than independent uniform sampling.

    The method creates a coarse grid with at least n_points cells, randomly
    selects n_points cells, and places one point randomly inside each selected cell.
    """
    if n_points <= 0:
        raise ValueError("n_points must be positive.")

    cx, cy = center
    half = city_size / 2.0

    n_axis = math.ceil(math.sqrt(n_points))
    coarse_cell_size = city_size / n_axis

    candidate_cells = [
        (ix, iy)
        for ix in range(n_axis)
        for iy in range(n_axis)
    ]

    selected_cells = rng.sample(candidate_cells, n_points)

    points: CoordinateDict = {}

    for idx, (ix, iy) in enumerate(selected_cells):
        xmin = cx - half + ix * coarse_cell_size
        xmax = xmin + coarse_cell_size
        ymin = cy - half + iy * coarse_cell_size
        ymax = ymin + coarse_cell_size

        points[idx] = (
            rng.uniform(xmin, xmax),
            rng.uniform(ymin, ymax),
        )

    return points

# Function to place Incinerators, landfills, and cement plants
def place_points_in_ring(
    indices: range,
    rng: random.Random,
    radius_min: float,
    radius_max: float,
    radius_center: float | None = None,   # optional argument for triangular distribution to place more points around a certain radius (e.g., for landfills around 50 km and cement plants around 200 km)
    center: Point = (0.0, 0.0),
    angle_min: float = 0.0,
    angle_max: float = 2.0 * math.pi,
) -> CoordinateDict:
    """
    Place points randomly in a circular ring around a center.

    If radius_center is None, radial distances are sampled uniformly.
    If radius_center is provided, radial distances are sampled from a
    triangular distribution with mode radius_center.

    Notes
    -----
    - The radius distribution controls distance from the city center.
    - The angle interval controls geographical direction.
    """
    if radius_min < 0:
        raise ValueError("radius_min must be non-negative.")

    if radius_min > radius_max:
        raise ValueError("radius_min must be smaller than or equal to radius_max.")

    if radius_center is not None:
        if not radius_min <= radius_center <= radius_max:
            raise ValueError("radius_center must lie between radius_min and radius_max.")

    if angle_min > angle_max:
        raise ValueError("angle_min must be smaller than or equal to angle_max.")
    
    cx, cy = center
    coordinates: CoordinateDict = {}

    for idx in indices:
        if radius_center is None:
            radius = rng.uniform(radius_min, radius_max)
        else:
            radius = rng.triangular(radius_min, radius_max, radius_center)

        angle = rng.uniform(angle_min, angle_max)

        coordinates[idx] = (
            cx + radius * math.cos(angle),
            cy + radius * math.sin(angle),
        )

    return coordinates

# Function to generate synthetic network locations for all facility types
def generate_grid_based_network_locations(
    G: range,
    S: range,
    I: range,
    L: range,
    C: range,
    rng: random.Random,
    city_size: float = 30.0,
    grid_cell_size: float = 10.0,
    incinerator_radius_min: float = 10.0,
    incinerator_radius_max: float = 60.0,
    incinerator_radius_center: float = 35.0,   # place more incinerators around 35 km from city center
    landfill_radius_min: float = 40.0,
    landfill_radius_max: float = 120.0,
    landfill_radius_center: float = 75.0,   # place more landfills around 75 km from city center
    cement_radius_min: float = 80.0,
    cement_radius_max: float = 320.0,
    cement_radius_center: float = 200.0,    # place more cement plants around 200 km from city center
    incinerator_colocation_probability: float = 0.025,
    center: Point = (0.0, 0.0),
) -> Dict[str, CoordinateDict]:
    """
    Generate synthetic network locations with fixed grid-based generation spots.

    Generation spots are deterministic cell centers in a city grid.
    Transfer stations are placed randomly but evenly across the city.
    Incinerators, landfills, and cement plants are placed in rings around the city center, with some probability of co-location for incinerators at transfer stations.
    """

    waste_generation_points = generate_waste_generation_points(
        city_size=city_size,
        cell_size=grid_cell_size,
        center=center,
    )

    if len(G) > len(waste_generation_points):
        raise ValueError(
            f"len(G)={len(G)} exceeds available grid cells={len(waste_generation_points)}."
        )
    else:
        print(f"Generated {len(waste_generation_points)} waste generation points based on city size and grid cell size, with {len(G)} used for the instance.")

    G_coords = {
        g: waste_generation_points[g]
        for g in G
    }

    S_coords = generate_transfer_stations(
        n_points=len(S),
        rng=rng,
        city_size=city_size,
        center=center,
    )

    I_coords: CoordinateDict = {}

    for i in I:
        if rng.random() < incinerator_colocation_probability:       # co-locate some incinerators at transfer stations for realism
            assigned_s = rng.choice(list(S))
            I_coords[i] = S_coords[assigned_s]
        else:
            radius = rng.triangular(incinerator_radius_min, incinerator_radius_max, incinerator_radius_center)
            angle = rng.uniform(0.0, 2.0 * math.pi)
            I_coords[i] = (
                center[0] + radius * math.cos(angle),
                center[1] + radius * math.sin(angle),
            )

    L_coords = place_points_in_ring(
        indices=L,
        rng=rng,
        radius_min=landfill_radius_min,
        radius_max=landfill_radius_max,
        radius_center=landfill_radius_center,
        center=center,
    )

    C_coords = place_points_in_ring(
        indices=C,
        rng=rng,
        radius_min=cement_radius_min,
        radius_max=cement_radius_max,
        radius_center=cement_radius_center,
        center=center,
    )

    return {
        "G": G_coords,
        "S": S_coords,
        "I": I_coords,
        "L": L_coords,
        "C": C_coords,
    }

def euclidean_distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])

#region Road distance
# Function to compute road distance based on network structure
def road_distance(
    origin: Point,
    destination: Point,
    rng: random.Random,
    detour_min: float,
    detour_max: float,
    noise_share: float,
) -> int:
    """
    Compute synthetic road distance between two coordinates.

    Coordinates are interpreted as kilometres. The distance is computed as
    Euclidean distance multiplied by a random road-detour factor and perturbed
    by small relative noise.

    No clipping is applied. Therefore, all distance realism should be induced
    by the coordinate-generation procedure.
    """
    euclidean = euclidean_distance(origin, destination)

    # Only exact or numerical co-location should yield distance zero.
    if math.isclose(euclidean, 0.0, abs_tol=1e-9):
        return 0

    detour_factor = rng.uniform(detour_min, detour_max)
    noise = rng.uniform(-noise_share, noise_share) * euclidean

    distance = detour_factor * euclidean + noise
    rounded_distance = int(round(distance))

    # Prevent non-co-located but very close facilities from becoming zero.
    return max(1, rounded_distance)
# Function to compute road distance with clipping (i.e. enforce transport distance bounds) and noise
def clipped_road_distance(
    origin: Point,
    destination: Point,
    rng: random.Random,
    min_distance: float,
    max_distance: float,
    detour_min: float,
    detour_max: float,
    noise_share: float,
) -> int:
    euclidean = euclidean_distance(origin, destination)

    if math.isclose(euclidean, 0.0, abs_tol=1e-1):
        return 0

    detour_factor = rng.uniform(detour_min, detour_max)
    noise = rng.uniform(-noise_share, noise_share) * euclidean

    distance = detour_factor * euclidean + noise
    distance = max(min_distance, min(max_distance, distance))

    rounded_distance = int(round(distance))

    if min_distance == 0.0 and rounded_distance == 0:
        return 1

    return rounded_distance
# endregion

# Function to build transport distance matrix from origins to destinations based on their coordinates and the road distance function
def build_transport_distance_matrix(
    origins: CoordinateDict,
    destinations: CoordinateDict,
    rng: random.Random,
    min_distance: float,
    max_distance: float,
    detour_min: float,
    detour_max: float,
    noise_share: float,
    clipping: bool = False,
) -> List[List[int]]:
    origin_ids = sorted(origins)
    destination_ids = sorted(destinations)

    if clipping:
        return [
            [
                clipped_road_distance(
                    origin=origins[o],
                    destination=destinations[d],
                    rng=rng,
                    min_distance=min_distance,
                    max_distance=max_distance,
                    detour_min=detour_min,
                    detour_max=detour_max,
                    noise_share=noise_share,
                )
                for d in destination_ids
            ]
            for o in origin_ids
        ]
    else:
        return [
            [
                road_distance(
                    origin=origins[o],
                    destination=destinations[d],
                    rng=rng,
                    detour_min=detour_min,
                    detour_max=detour_max,
                    noise_share=noise_share,
                )
                for d in destination_ids
            ]
            for o in origin_ids
        ]

#endregion

##########################################
############ Data definition #############
##########################################

#region Instance generation
def generate_instance(seed: int = 7) -> InstanceData:
    rng = random.Random(seed)

    # -----------------------------
    # SETS
    # -----------------------------
    # This keeps your TD_trans meaningful without exploding size too much.
    # G_max = 8
    S_max = 8
    W_max = 2
    I_max = 6
    L_max = 3
    C_max = 6
    K_max = 3
    F_max = 2
    H_max = 5

    # G = range(G_max)
    S = range(S_max)
    W = range(W_max)
    I = range(I_max)
    L = range(L_max)
    C = range(C_max)
    K = range(K_max)
    F = range(F_max)
    H = range(H_max)

    # "Anhui Conch Cement (cluster)", "Suzhou Dahua Marine", "Jiangsu Pengfei (Haian)", "Zhejiang Producer A", "Jiangsu Producer A","Anhui Producer A"
    cement_names = [f"Cement Plant {i+1}" for i in C]  # Placeholder names; replace with actual names if desired

    city_size = 40.0
    grid_cell_size = 10.0

    G_max = compute_grid_generation_count(city_size, grid_cell_size)
    G = range(G_max)

    # -----------------------------
    # DISTANCES (km) - synthetic but plausible
    # Shanghai districts -> local transfer: 5..30 km
    # transfer -> incinerator: 10..60 km
    # transfer -> landfill (neighbour districts): 30..120 km
    # transfer -> cement (Jiangsu/Anhui/Zhejiang): 80..320 km
    # -----------------------------
    network_locations = generate_grid_based_network_locations(
        G=G,
        S=S,
        I=I,
        L=L,
        C=C,
        rng=rng,
        city_size=city_size,
        grid_cell_size=grid_cell_size,
        incinerator_radius_min=10.0,
        incinerator_radius_max=60.0,
        incinerator_radius_center=35.0,   # place more incinerators around 35 km from city center
        landfill_radius_min=40.0,
        landfill_radius_max=120.0,
        landfill_radius_center=75.0,   # place more landfills around 75 km from city center
        cement_radius_min=80.0,
        cement_radius_max=320.0,
        cement_radius_center=200.0,    # place more cement plants around 200 km from city center
        incinerator_colocation_probability=0.025,
        center=(0.0, 0.0),
    )

    G_coords = network_locations["G"]
    S_coords = network_locations["S"]
    I_coords = network_locations["I"]
    L_coords = network_locations["L"]
    C_coords = network_locations["C"]

    TD_gs = build_transport_distance_matrix(
        origins=G_coords,
        destinations=S_coords,
        rng=rng,
        min_distance=2.0,
        max_distance=50.0,
        detour_min=1.05,
        detour_max=1.20,
        noise_share=0.02,
        clipping=False,
    )

    TD_si = build_transport_distance_matrix(
        origins=S_coords,
        destinations=I_coords,
        rng=rng,
        min_distance=0.0,
        max_distance=60.0,
        detour_min=1.05,
        detour_max=1.30,
        noise_share=0.04,
        clipping=False,
    )

    TD_si_avg = sum(TD_si[s][i] for s in S for i in I) / (S_max * I_max)
    
    TD_sl = build_transport_distance_matrix(
        origins=S_coords,
        destinations=L_coords,
        rng=rng,
        min_distance=30.0,
        max_distance=120.0,
        detour_min=1.10,
        detour_max=1.40,
        noise_share=0.04,
        clipping=False,
    )

    TD_sc = build_transport_distance_matrix(
        origins=S_coords,
        destinations=C_coords,
        rng=rng,
        min_distance=80.0,
        max_distance=320.0,
        detour_min=1.10,
        detour_max=1.40,
        noise_share=0.04,
        clipping=False,
    )

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
    # WASTE GENERATION (t/year): Shanghai-sized synthetic
    # Total MSW in Shanghai is very large; for computational tests keep totals moderate first
    # Generate around 6,000–9,000 t/year in total (~0.1%, normally 9,000,000 per year)
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
    total_Q_gen_per_w = [sum(Q_gw[g][w] for g in G) for w in W]

    # Transfer capacity: ensure > inbound per station; keep loose
    # If each district maps mostly to one transfer, set capacity around 700..1100 t/day
    # Q_trans = [rng.randint(700, 1100) for _ in S]
    Q_s = [int(round(rng.triangular(900, 1400, 1200) / 10) * 10) for _ in S]

    # Incineration and landfill capacities:
    # Set so that inc+land can cover all waste (to avoid forced investment),
    # but landfill quota still restricts landfill share.
    Q_i = [int(round(rng.triangular(700, 1200, 950))) for _ in I]  # 6 plants
    Q_l = [int(round(rng.triangular(1000, 1300, 1200))) for _ in L]  # 3 sites

    # -----------------------------
    # CO-PROCESSING OPTIONS (t/day)
    # -----------------------------
    Q_k = [200, 350, 500]
    Q_k_max = max(Q_k)

    # -----------------------------
    # POLICY / WEIGHTS
    # -----------------------------
    kappa_land = 0.35
    kappa_coproc = 0.40

    phi_max = [220.0, 175.0]  # [high moisture, medium moisture]
    phi_wh = [[(h / (H_max - 1)) * phi_max[w] for h in H] for w in W]

    # U_w = [min(sum(Q_gw[g][w] for g in G), Q_k_max*len(C)) for w in W]  # Upper bound on waste flow of type w (can be tightened based on data)
    # A waste type w cannot flow trough network in an amount larger than: (i) total generated amount, (ii) total transfer-station capacity, (iii) total co-processing capacity
    U_w = [min(total_Q_gen_per_w[w], sum(Q_s), Q_k_max*len(C)) for w in W]  # Upper bound on waste flow of type w (can be tightened based on data)
    budget_municipality = 800_000_000.0  # scale up vs small toy
    # budget_availability = 0.9   # Only 90% of the maximum total potential waste flow to kilns can be subsidized supposing maximum subsidy levels, 
    #                             # to create a more realistic budget constraint that requires trade-offs in subsidy allocation
    # budget_municipality = budget_availability * sum(phi_max[w] * U_w[w] for w in W)  # Set municipal budget based on maximum potential subsidy payout with some availability factor

    # -----------------------------
    # FOLLOWER: coal types, costs, kiln demands
    # -----------------------------
    # Coal mixtures: e.g., standard and higher-quality
    price_f = [420.0, 520.0]   # CNY/t
    beta_f = [24.0, 27.0]      # GJ/t (two mixes)

    # Kiln daily energy requirement: scale with 6 cement plants
    alpha_c = [rng.randint(7000, 12000) for _ in C]

    beta_w = [12.0*0.3, 16.0*0.6]   # GJ/t for waste types, adjusted by moisture content (high moisture reduced by 70%, medium moisture reduced by 30%)

    # Investment CAPEX by option size (CNY) – extend to K=3
    c_invest_k = [70_000_000.0, 110_000_000.0, 150_000_000.0]

    # Preprocessing cost by waste type
    c_preproc_w = [150.0, 125.0]

    c_penalty = 100.0
    budget_cem = 600_000_000.0  # bigger portfolio-level budget for 6 plants

    tau = 1e-3

    # Levelized daily fixed cost per option k
    i_rate = 0.0325
    lifetime_years = 15
    CRF = crf(i_rate, lifetime_years)
    capex_ann = [c_invest_k[k] * CRF for k in K]
    opex_fix_ann = [c_invest_k[k] * 0.06 for k in K]
    fixcost_invest_unscaled_k = [capex_ann[k] + opex_fix_ann[k] for k in K]
    fixcost_invest_k = [cost/1000 for cost in fixcost_invest_unscaled_k]     # divide by 1000 to scale down to daily cost, because only 0.1% of annual waste is modeled in this instance

    # Big-M value for cut generation
    M_primal = {
        'F3': 1,
        # 'F4': max(alpha_c)*kappa_coproc+10,     # Maximmum energy content in co-processing
        'F4': {c: (alpha_c[c]*kappa_coproc) + 1 for c in C},     # Maximmum energy content in co-processing
        'F5': Q_k_max+1,                        # Maximum co-processing quantity (not really needed, because x_ck_fixed is already fixed in the OC block, thus the maximal capacity is deterministic based on the fixed investment decision; keep it for fallback)
        # 'q_cf': max(alpha_c)+1,                 # Maximum quantity of coal processed at cement plant (based on maximum energy content needed)
        # since alpha_c is in GJ and beta_f is in GJ/t, a physically meaningful coal bound is closer to alpha_c[c] / beta_f[f] + 1.0
        'q_cf': {c: {f: alpha_c[c] / beta_f[f] + 1 for f in F} for c in C},   # Maximum quantity of coal processed at cement plant (based on maximum energy content needed)
        # 'q_scw': Q_k_max+1,                     # Maximum quantity of waste allocated from transfer station to cement plant
        'q_scw': {s: {c: {w: float(min(Q_s[s], Q_k_max, total_Q_gen_per_w[w]))+1 for w in W} for c in C} for s in S},  # Maximum quantity of waste allocated from transfer station to cement plant
        # 'r_sw': max(Q_s)+1,                   # Maximum residual waste at transfer station after allocation
        # 'r_sw': {s: int(Q_s[s])+1 for s in S},  # Maximum residual waste at transfer station after allocation, capcitated by individual capacities of transfer stations
        'r_sw': {s: {w: float(min(Q_s[s], total_Q_gen_per_w[w]))+1 for w in W} for s in S},  # Maximum residual waste at transfer station after allocation, capcitated by individual capacities of transfer stations
    }

    M_dual = {
        # 'lam_F3': 1e3,     # Big-M for dual variable of constraint F3 (energy fulfillment constraint)
        # p_{f}-\lambda^{F3}_c\beta_f-\pi^{1}_{cf} = 0 with \lambda^{F3}_c >= 0 and \pi^{1}_{cf} >= 0; rearrange to \pi^{1}_{cf} = p_{f}-\lambda^{F3}_c\beta_f; it follows p_{f}-\lambda^{F3}_c\beta_f >= 0 and thus \lambda^{F3}_c <= p_{f}/\beta_f for all f; so a reasonable Big-M for \lambda^{F3}_c is max(p_{f}/\beta_f) + 1 to allow for some numerical tolerance
        'lam_F3': min(price_f[f] / beta_f[f] for f in F) + 1,     # Big-M for dual variable of constraint F3 (energy fulfillment constraint)
        'lam_F4': 1e4,     # Big-M for dual variable of constraint F4 (maximum co-processing quantity)
        'lam_F5': 1e4,     # Big-M for dual variable of constraint F5 (co-process capacity limited by investment decision)
        # derived from stationarity for q_cf: data.price_f[f] - lam_F3[c]*data.beta_f[f] - pi_q_cf[c,f] == 0 with lam_F3 >= 0 and beta_f >= 8, so price_f is a reasonable upper bound for pi_q_cf
        'pi_q_cf': max(price_f)+1,    # Big-M for dual variable of constraint limiting quantity of coal processed at cement plant
        'pi_q_scw': 1e4,   # Big-M for dual variable of constraint limiting quantity of waste allocated from transfer station to cement plant
        'pi_r_sw': 1e4,    # Big-M for dual variable of constraint limiting residual waste at transfer station after allocation
    }

    return InstanceData(
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
        M_primal=M_primal, M_dual=M_dual,
        U_w=U_w
    )
#endregion


#region JSON serialization
def _make_json_serializable(obj: Any) -> Any:
    if isinstance(obj, range):
        return list(obj)
    elif isinstance(obj, dict):
        return {key: _make_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_json_serializable(value) for value in obj]
    return obj
#endregion

#region JSON writer
def write_instance_to_json(
        output_dir: Path,
        instance_id: str,
        size_class: str,
        structural_regime: str,
        seed: int,
        distribution_settings: Dict[str, Any] | None = None,
        generator_version: str = "V1.0"
) -> Path:
    '''
    Generate an instance and write it to a JSON file with separated metadata and data:
    {
    "metadata": {
        "instance_id": "instance_001",
        "size_class": "small",
        "structural_regime": "balanced",
        "seed": 7,
        "distribution_settings": {...}
    },
    "data": {
        ... instance data fields ...
    }
    }
    '''
    instance_data = generate_instance(seed=seed)

    if distribution_settings is None:
        distribution_settings = {
            "TD_gs (uniform int, diagonal bias)": [10, 50],  # diagonal bias with local transfer distances around 2-10 km and others up to 50 km
            "TD_si (uniform int)": [0, 60],
            "TD_sl (triangular)": [60, 150, 110],
            "TD_sc (triangular)": [80, 360, 220],
            "total_waste (uniform, int)": [6000, 9000],
            "waste_split (uniform, float)": [0.4, 0.7],  # range for high moisture split
            "Q_s (triangular)": [900, 1400, 1200],
            "Q_i (triangular)": [700, 1200, 950],
            "Q_l (triangular)": [1000, 1300, 1200],
            "alpha_c (uniform, int)": [7000, 12000]
        }

    metadata = {
        "instance_id": instance_id,
        "size_class": size_class,
        "structural_regime": structural_regime,
        "seed": seed,
        "dimensions": {
            "G_max": instance_data.G_max,
            "S_max": instance_data.S_max,
            "I_max": instance_data.I_max,
            "L_max": instance_data.L_max,
            "C_max": instance_data.C_max
        },
        "distribution_settings": distribution_settings,
        "generator_version": generator_version
    }

    payload = {
        "metadata": metadata,
        "data": _make_json_serializable(asdict(instance_data))
    }

    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with output_dir.open('w', encoding='utf-8') as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
    
    return output_dir
#endregion

#region JSON reader
# JSON turns dict keys into strings, so it is necessary to convert them back to ints for indexed Big-M values
def _keys_to_int(d: dict) -> dict:
    return {int(k): v for k, v in d.items()}

def _keys_to_int_recursive(obj):
    if isinstance(obj, dict):
        return {int(k): _keys_to_int_recursive(v) for k, v in obj.items()}
    return obj

# JSON to InstanceData object
def read_instanceData_from_json(json_path: Path) -> InstanceData:
    with json_path.open('r', encoding='utf-8') as file:
        payload = json.load(file)

    data = payload["data"]

    # Convert lists back to ranges for index sets
    data['G'] = range(data['G_max'])
    data['S'] = range(data['S_max'])
    data['W'] = range(data['W_max'])
    data['I'] = range(data['I_max'])
    data['L'] = range(data['L_max'])
    data['C'] = range(data['C_max'])
    data['K'] = range(data['K_max'])
    data['F'] = range(data['F_max'])
    data['H'] = range(data['H_max'])

    # Convert JSON string keys back to ints for indexed Big-M values
    data['M_primal']['F4'] = _keys_to_int(data['M_primal']['F4'])
    data['M_primal']['r_sw'] = _keys_to_int_recursive(data['M_primal']['r_sw'])
    data['M_primal']['q_cf'] = _keys_to_int_recursive(data['M_primal']['q_cf'])
    data['M_primal']['q_scw'] = _keys_to_int_recursive(data['M_primal']['q_scw'])

    instance = InstanceData(
        G_max=data['G_max'], S_max=data['S_max'], W_max=data['W_max'], 
        I_max=data['I_max'], L_max=data['L_max'], C_max=data['C_max'],
        K_max=data['K_max'], F_max=data['F_max'], H_max=data['H_max'],

        G=data['G'], S=data['S'], W=data['W'], I=data['I'], L=data['L'], 
        C=data['C'], K=data['K'], F=data['F'], H=data['H'],
        
        cement_names=data['cement_names'],
        
        TD_gs=data['TD_gs'], TD_sl=data['TD_sl'], 
        TD_sc=data['TD_sc'], TD_si=data['TD_si'], 
        TD_si_avg=data['TD_si_avg'],
        
        epsilon_truck=data['epsilon_truck'],
        epsilon_land=data['epsilon_land'], epsilon_inc=data['epsilon_inc'], 
        epsilon_kiln_w=data['epsilon_kiln_w'], epsilon_kiln_f=data['epsilon_kiln_f'],

        c_truck=data['c_truck'], c_land=data['c_land'], c_inc=data['c_inc'],

        Q_gw=data['Q_gw'], Q_gen_total=data['Q_gen_total'],
        Q_s=data['Q_s'], Q_l=data['Q_l'], Q_i=data['Q_i'],
        Q_k=data['Q_k'], Q_k_max=data['Q_k_max'],

        weight_env=data['weight_env'], weight_mon=data['weight_mon'],

        kappa_land=data['kappa_land'], kappa_coproc=data['kappa_coproc'],

        budget_municipality=data['budget_municipality'],
        budget_cem=data['budget_cem'],

        phi_max=data['phi_max'],
        phi_wh=data['phi_wh'],

        price_f=data['price_f'], 
        beta_f=data['beta_f'], beta_w=data['beta_w'],

        alpha_c=data['alpha_c'], 

        c_invest_k=data['c_invest_k'], 
        c_preproc_w=data['c_preproc_w'],
        c_penalty=data['c_penalty'], 

        tau = data["tau"],
        fixcost_invest_k = data["fixcost_invest_k"],

        M_primal=data['M_primal'], M_dual=data['M_dual'],
        U_w=data['U_w']
    )

    return instance
#endregion

def read_instance_metadata_from_json(json_path: Path) -> Dict[str, Any]:
    with json_path.open('r', encoding='utf-8') as file:
        payload = json.load(file)
    return payload["metadata"]

#region Run instance generator
# call the script to generate an instance and save to JSON within the python environment (can be adapted to command-line arguments if needed)
if __name__ == "__main__":
    instance_name = "instance_m_base_normal_001.json"
    output_path = write_instance_to_json(
        output_dir=Path(__file__).parent / "generated_instances" / instance_name,
        instance_id=instance_name[:-5],  # Remove ".json" extension
        size_class="medium",
        structural_regime="baseline",
        seed=7
    )
    print(f"Instance generated and saved to {output_path}")
