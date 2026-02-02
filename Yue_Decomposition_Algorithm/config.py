"""
Configuration and Constants Module
Centralized configuration for the decomposition algorithm
"""

# ===== ALGORITHM PARAMETERS =====
# Benders Decomposition / Yue et al. parameters

ITERATION_LIMIT = 100  # Maximum number of decomposition iterations
OPTIMALITY_GAP_TOLERANCE = 5e-4  # Optimality gap tolerance (0.05%)
TIME_LIMIT = 3600  # Time limit in seconds (1 hour)

# Feasibility and optimality cut generation parameters
FEASIBILITY_CUT_RHS_TOLERANCE = 1e-5  # Tolerance for feasibility cut RHS
OPTIMALITY_CUT_RHS_TOLERANCE = 1e-5  # Tolerance for optimality cut RHS

# ===== SOLVER PARAMETERS =====
# Gurobi solver settings

SOLVER_TIMEOUT = 60  # Timeout per subproblem solve (seconds)
SOLVER_MIP_GAP = 1e-4  # MIP gap tolerance
SOLVER_LOG_LEVEL = 1  # 0 = silent, 1 = normal, 2 = verbose

# ===== OUTPUT AND REPORTING =====

VERBOSE = True  # Enable detailed output
WRITE_MODELS = False  # Write .lp files for inspection
WRITE_SOLUTIONS = False  # Write solution files

# Output file names
OUTPUT_MP = "master_problem.lp"
OUTPUT_SP1 = "subproblem1.lp"
OUTPUT_SP2 = "subproblem2.lp"

# ===== NUMERICAL TOLERANCES =====

EPSILON = 1e-6  # General small number for zero comparisons
CONSTRAINT_TOLERANCE = 1e-5  # Constraint violation tolerance

if __name__ == "__main__":
    print("Configuration loaded successfully")
    print(f"  Iteration limit: {ITERATION_LIMIT}")
    print(f"  Optimality gap: {OPTIMALITY_GAP_TOLERANCE:.2e}")
    print(f"  Time limit: {TIME_LIMIT} seconds")
