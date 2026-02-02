# Yue et al. (2017) Decomposition Algorithm - Implementation Guide

## Overview

This project implements the bilevel optimization decomposition algorithm from Yue et al. (2017) for co-processing waste in China's cement industry. The algorithm decomposes a complex bilevel optimization problem into manageable subproblems that are solved iteratively.

## Project Structure

```
Paper2_CoProcessing/
├── test_instance.py              # Instance data and parameters
├── instance_loader.py            # InstanceData class - loads and manages instance data
├── config.py                     # Configuration and algorithm parameters
├── utils.py                      # Utility functions for logging, formatting, etc.
├── master_problem.py             # MasterProblem class - implements the MP
├── subproblem_1.py              # SubProblem1 class - feasibility problem (TO BE CREATED)
├── subproblem_2.py              # SubProblem2 class - optimality problem (TO BE CREATED)
├── Yue_2017_decomposition.py    # YueDecompositionAlgorithm - main orchestration
├── program.py                   # Main entry point (optional - can use Yue_2017_decomposition.py)
└── README.md                    # This file
```

## Architecture & Design Rationale

### 1. **Modular Design Pattern**

The implementation follows a **modular, object-oriented design** for the following reasons:

| Module | Purpose | Rationale |
|--------|---------|-----------|
| `instance_loader.py` | Data centralization | Single source of truth for all parameters |
| `master_problem.py` | MP implementation | Independent class for leader's problem |
| `subproblem_1.py` | SP1 implementation | Independent class for follower feasibility |
| `subproblem_2.py` | SP2 implementation | Independent class for follower optimality |
| `Yue_2017_decomposition.py` | Algorithm orchestration | Coordinates MP and SP solves |
| `config.py` | Parameter management | Easy tuning without code changes |
| `utils.py` | Cross-cutting concerns | Reusable logging, formatting, I/O |

### 2. **Why Separate Classes for MP, SP1, SP2?**

✅ **Advantages:**
- **Maintainability**: Each problem is self-contained and easy to modify
- **Reusability**: Subproblems can be solved independently for debugging
- **Testing**: Unit tests can target individual problems
- **Scalability**: Easy to add new variants or constraints
- **Clarity**: Problem structure is immediately obvious from code

❌ **Alternatives (and why we don't use them):**
- **Monolithic function**: Hard to maintain, difficult to test, tightly coupled
- **Nested functions**: Same issues as monolithic approach
- **Dictionary-based approach**: Less structure, harder to enforce consistency

### 3. **Algorithm Flow**

```
┌─────────────────────────────────────────────────────────────────┐
│                  Main Algorithm (Yue_2017_decomposition.py)    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ↓
                    ┌─────────────────────┐
                    │  MasterProblem(MP)  │
                    │  - Leadership decision│
                    │  - Sets θ (cuts)    │
                    └─────────────────────┘
                              │
                              ↓
                    ┌─────────────────────┐
                    │ SubProblem_1 (SP1) │
                    │ - Follower feasibility│
                    │ - Detects infeasibility│
                    └─────────────────────┘
                              │
                              ↓
                    ┌─────────────────────┐
                    │ SubProblem_2 (SP2)  │
                    │ - Follower optimality│
                    │ - Maximizes profit  │
                    └─────────────────────┘
                              │
                              ↓
                    ┌─────────────────────┐
                    │  Generate Cuts      │
                    │  (Feasibility/Opt)  │
                    └─────────────────────┘
                              │
                              ↓
                    ┌─────────────────────┐
                    │ Check Convergence?  │
                    └─────────────────────┘
                         Yes │    No
                             │     │
                             ↓     └────→ [Add cuts to MP, next iteration]
                        OPTIMAL
```

## File Descriptions

### `test_instance.py`
Contains all data: sets, parameters, and coefficients for the problem instance.
- **Sets**: G (generation spots), S (transfer stations), W (waste types), etc.
- **Parameters**: Transportation distances, costs, capacities, subsidies, etc.

### `instance_loader.py`
**Class: `InstanceData`**
- Loads all data from `test_instance.py`
- Centralizes access to parameters throughout the codebase
- Includes validation method to check data consistency

**Usage:**
```python
from instance_loader import InstanceData
instance = InstanceData()
instance.validate()
```

### `master_problem.py`
**Class: `MasterProblem`**

**Methods:**
- `__init__(instance)`: Initialize with instance data
- `build()`: Create the Gurobi model and add variables/constraints
- `optimize()`: Solve the MP
- `get_solution()`: Extract variable values from the solution
- `write_model(filename)`: Export model to .lp file for inspection

**Decision Variables:**
- `x_gsl[g,s,l]`: Waste to landfill
- `x_gsi[g,s,i]`: Waste to incinerator
- `x_gsc[g,s,c]`: Waste to cement facility
- `y_gsh[g,s,h]`: Waste at subsidy level h
- `y_scw[s,c,w]`: Waste type w to cement facility
- `z_ck[c,k]`: Investment indicator
- `theta`: Auxiliary variable for lower-level objective approximation

**Constraints:**
1. Demand satisfaction (all waste must be routed)
2. Transfer station capacity
3. Landfill, incinerator capacity
4. Landfill quota (35% of total waste)
5. Subsidy budget constraint
6. Investment constraints (≤1 per facility)

**Usage:**
```python
mp = MasterProblem(instance)
mp.build()
obj_value = mp.optimize()
solution = mp.get_solution()
```

### `subproblem_1.py` (TO BE CREATED)
**Class: `SubProblem1`**

This will implement the follower's feasibility problem:
- Given decisions from MP (subsidies, allocations)
- Determine if follower can process the allocated waste
- Generate feasibility cuts if infeasible

### `subproblem_2.py` (TO BE CREATED)
**Class: `SubProblem2`**

This will implement the follower's optimality problem:
- Given decisions from MP
- Maximize follower's (cement facility) profit
- Generate optimality cuts to improve lower bound

### `config.py`
Global configuration for the algorithm:
```python
ITERATION_LIMIT = 100           # Max iterations
OPTIMALITY_GAP_TOLERANCE = 1e-4 # Convergence criterion
TIME_LIMIT = 3600               # Time limit in seconds
SOLVER_TIMEOUT = 60             # Per-problem timeout
```

**Why separate?**
- Easy to tune algorithm without modifying core code
- Reproducible parameter documentation
- Different configs for testing vs. production

### `utils.py`
Reusable utility functions:
- `setup_logger()`: Configure logging for algorithm
- `print_section()`, `print_subsection()`: Formatted output
- `format_number()`: Thousand separators for readability
- `compute_optimality_gap()`: Gap calculation
- `save_results()`: Export results to file

### `Yue_2017_decomposition.py`
**Class: `YueDecompositionAlgorithm`**

Main orchestration logic:
- `__init__(instance)`: Initialize
- `initialize()`: Set up all problems
- `solve_master_problem()`: Call MP.optimize()
- `solve_subproblem_1()`: Call SP1.optimize()
- `solve_subproblem_2()`: Call SP2.optimize()
- `generate_cuts()`: Create and add cuts to MP
- `check_convergence()`: Test termination criteria
- `run()`: Main loop executing all iterations

**Usage:**
```python
instance = InstanceData()
instance.validate()

algorithm = YueDecompositionAlgorithm(instance)
results = algorithm.run()

print(f"Converged: {results['converged']}")
print(f"Optimal value: {results['upper_bound']}")
```

## Step-by-Step Implementation Plan

### ✅ **Step 1: Foundation (COMPLETED)**
- [x] Load packages and instance data
- [x] Define Master Problem (MP) class with full model
- [x] Set up configuration and utilities

### 📋 **Step 2: Subproblem 1 (NEXT)**
- [ ] Create `subproblem_1.py` with `SubProblem1` class
- [ ] Implement follower feasibility problem
- [ ] Add method to generate feasibility cuts

### 📋 **Step 3: Subproblem 2 (NEXT)**
- [ ] Create `subproblem_2.py` with `SubProblem2` class
- [ ] Implement follower optimality problem
- [ ] Add method to generate optimality cuts

### 📋 **Step 4: Cut Generation (NEXT)**
- [ ] Implement feasibility cut generation logic
- [ ] Implement optimality cut generation logic
- [ ] Integrate into main algorithm

### 📋 **Step 5: Integration & Testing (NEXT)**
- [ ] Connect all problems in main algorithm
- [ ] Test with `test_instance.py` data
- [ ] Verify convergence behavior

## How to Run (Current State)

```bash
# Run master problem setup only
python Yue_2017_decomposition.py
```

This will:
1. Load instance data
2. Build the Master Problem
3. Show the algorithm structure (SP1 and SP2 placeholders)

## Next Steps

After this foundation, we'll implement:

1. **SubProblem 1 (Follower Feasibility)**: 
   - Check if cement facility can accept allocated waste
   - Generate feasibility cuts for infeasible scenarios

2. **SubProblem 2 (Follower Optimality)**:
   - Maximize cement facility profit given allocations
   - Generate optimality cuts to improve solution

3. **Cut Management**:
   - Add generated cuts to Master Problem
   - Manage warm start for faster solving

4. **Convergence Testing**:
   - Run full algorithm with test data
   - Verify theoretical convergence properties

## Best Practices in This Implementation

1. **Class-based organization** for clarity and maintainability
2. **Comprehensive logging** for debugging and monitoring
3. **Separation of concerns** (data, models, algorithm)
4. **Configuration externalization** for easy tuning
5. **Type hints and docstrings** for code understanding
6. **Modular utilities** for reusability

This structure makes it easy to:
- Debug individual components
- Extend with new constraints or features
- Write unit tests
- Switch solvers (e.g., CPLEX instead of Gurobi)
- Parallelize subproblem solves

---

**Ready for Step 2?** Let me know when to implement SubProblem 1!
