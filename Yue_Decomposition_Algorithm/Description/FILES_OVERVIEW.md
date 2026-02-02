# 📁 Project Files Overview

## Complete File Listing - Step 1

Below is a complete description of every file created and used in this project.

---

## 🔵 Core Implementation Files

### 1. `instance_loader.py` (75 lines)
**Purpose**: Centralized instance data management  
**Author**: Generated  
**Status**: ✅ Complete & Tested  

**Key Class**: `InstanceData`
- **Responsibility**: Load all parameters from test_instance.py
- **Methods**: 
  - `__init__()`: Load all sets and parameters
  - `validate()`: Check data consistency
- **Usage**: 
  ```python
  from instance_loader import InstanceData
  instance = InstanceData()
  instance.validate()
  print(instance.G_max)  # Access parameters
  ```

**Dependencies**: 
- `test_instance.py` (imports data from here)

**Should Modify When**:
- Adding new parameter types
- Validating additional constraints
- Changing data loading mechanism

---

### 2. `master_problem.py` (380 lines)
**Purpose**: Implement the Master Problem (Leader's optimization)  
**Author**: Generated  
**Status**: ✅ Complete & Tested  

**Key Class**: `MasterProblem`
- **Responsibility**: Build and solve the leader's (municipality) problem
- **Decision Variables** (67 total):
  - `x_gsl`: Waste to landfills (6 variables)
  - `x_gsi`: Waste to incinerators (6 variables)
  - `x_gsc`: Waste to cement facilities (12 variables)
  - `y_gsh`: Subsidy allocation (30 variables)
  - `y_scw`: Waste type to cement (8 variables)
  - `z_ck`: Investment choices (4 binary variables)
  - `theta`: Auxiliary for cuts (1 variable)

- **Constraints** (14 total):
  - Demand satisfaction (2)
  - Capacity constraints (4)
  - Landfill quota (1)
  - Budget constraints (1)
  - Investment constraints (2)
  - Supporting constraints (4)

- **Objective Function**:
  - Minimize: weighted(environmental impact) + weighted(monetary cost) - theta
  - theta is auxiliary for lower-level approximation via cuts

- **Methods**:
  - `build()`: Create the Gurobi model
  - `optimize()`: Solve the model
  - `get_solution()`: Extract variable values
  - `write_model(filename)`: Export to .lp file

- **Usage**:
  ```python
  from master_problem import MasterProblem
  from instance_loader import InstanceData
  
  instance = InstanceData()
  mp = MasterProblem(instance)
  mp.build()
  obj = mp.optimize()
  solution = mp.get_solution()
  ```

**Dependencies**:
- `gurobipy` (Gurobi Python API)
- `instance_loader.py` (InstanceData class)

**Should Modify When**:
- Adding new constraints
- Changing objective function
- Adding new decision variables
- Adjusting cost parameters

---

### 3. `config.py` (40 lines)
**Purpose**: Global configuration and algorithm parameters  
**Author**: Generated  
**Status**: ✅ Complete  

**Key Parameters**:
- `ITERATION_LIMIT = 100`: Maximum decomposition iterations
- `OPTIMALITY_GAP_TOLERANCE = 1e-4`: Convergence criterion
- `TIME_LIMIT = 3600`: Total time limit (seconds)
- `SOLVER_TIMEOUT = 60`: Per-problem timeout (seconds)
- `SOLVER_LOG_LEVEL = 1`: Verbosity (0=silent, 1=normal, 2=verbose)
- `VERBOSE = True`: Enable detailed output

**Usage**:
```python
from config import ITERATION_LIMIT, OPTIMALITY_GAP_TOLERANCE

for i in range(ITERATION_LIMIT):
    if gap <= OPTIMALITY_GAP_TOLERANCE:
        break
```

**Should Modify When**:
- Tuning algorithm behavior
- Testing with different tolerances
- Production vs. testing modes
- Performance optimization

---

### 4. `utils.py` (140 lines)
**Purpose**: Shared utility functions  
**Author**: Generated  
**Status**: ✅ Complete  

**Key Functions**:
- `setup_logger(name, log_file=None)`: Configure logging
- `print_section(title, width=70)`: Print formatted headers
- `print_subsection(title, width=70)`: Print subheaders
- `format_number(value, decimals=2)`: Format with thousand separators
- `check_feasibility(model)`: Verify model solution status
- `extract_nonzero_solution(solution_dict, tolerance=1e-6)`: Filter nonzero vars
- `compute_optimality_gap(upper_bound, lower_bound)`: Calculate gap
- `save_results(results, filename="results.txt")`: Export results

**Usage**:
```python
from utils import setup_logger, format_number, compute_optimality_gap

logger = setup_logger("MyAlgorithm")
logger.info(f"Objective: {format_number(12345.67)}")
gap = compute_optimality_gap(ub=100, lb=95)
```

**Should Modify When**:
- Adding new output formats
- Adding new utility functions
- Changing logging configuration

---

### 5. `Yue_2017_decomposition.py` (310 lines)
**Purpose**: Main algorithm orchestration  
**Author**: Generated  
**Status**: ✅ Complete (with placeholders for SP1/SP2)  

**Key Class**: `YueDecompositionAlgorithm`
- **Responsibility**: Orchestrate the complete decomposition algorithm
- **Main Methods**:
  - `__init__(instance, verbose=True)`: Initialize algorithm
  - `initialize()`: Set up all problems
  - `solve_master_problem()`: Solve MP
  - `solve_subproblem_1(mp_solution)`: Solve SP1 (placeholder)
  - `solve_subproblem_2(mp_solution)`: Solve SP2 (placeholder)
  - `generate_cuts(sp_solution)`: Generate cuts (placeholder)
  - `check_convergence()`: Check stopping criteria
  - `run()`: Main iteration loop

- **Attributes**:
  - `iteration`: Current iteration number
  - `upper_bound`: Best feasible solution found
  - `lower_bound`: Best lower bound
  - `optimality_gap`: Current optimality gap
  - `converged`: Whether algorithm converged
  - `cuts_generated`: Total cuts added

- **Main Flow**:
  1. Load instance data
  2. For each iteration:
     - Solve MP
     - Solve SP1, SP2
     - Generate cuts
     - Check convergence

**Usage**:
```python
from Yue_2017_decomposition import YueDecompositionAlgorithm
from instance_loader import InstanceData

instance = InstanceData()
algorithm = YueDecompositionAlgorithm(instance, verbose=True)
results = algorithm.run()

print(f"Converged: {results['converged']}")
print(f"Optimal value: {results['upper_bound']}")
print(f"Gap: {results['optimality_gap']:.2%}")
```

**Dependencies**:
- `gurobipy` (Gurobi)
- `instance_loader.py` (InstanceData)
- `master_problem.py` (MasterProblem)
- `config.py` (algorithm parameters)
- `utils.py` (utilities)

**Should Modify When**:
- Changing algorithm flow
- Adding convergence criteria
- Implementing cut generation
- Adding new subproblems

---

## 🟡 To Be Implemented

### 6. `subproblem_1.py` (to be created in Step 2)
**Purpose**: Implement the Follower's Feasibility Problem  
**Status**: 📋 Pending (Step 2)  

**What it will do**:
- Check if cement facility can accept allocated waste
- Verify operational feasibility
- Generate feasibility cuts if infeasible

**Expected Structure**:
```python
class SubProblem1:
    def __init__(self, instance, mp_solution)
    def build()
    def optimize()
    def get_solution()
    def generate_feasibility_cuts()
```

---

### 7. `subproblem_2.py` (to be created in Step 3)
**Purpose**: Implement the Follower's Optimality Problem  
**Status**: 📋 Pending (Step 3)  

**What it will do**:
- Maximize cement facility profit given allocations
- Extract dual information for optimality cuts
- Generate Benders optimality cuts

**Expected Structure**:
```python
class SubProblem2:
    def __init__(self, instance, mp_solution)
    def build()
    def optimize()
    def get_solution()
    def generate_optimality_cuts()
```

---

## 📘 Documentation Files

### 8. `README.md` (500+ lines)
**Purpose**: Comprehensive architecture and design documentation  
**Status**: ✅ Complete  
**Contents**:
- Project overview
- Complete project structure
- Architecture rationale
- File descriptions
- Design patterns used
- Implementation plan (all 5 steps)
- Usage examples
- Best practices

**Read This When**:
- Understanding overall structure
- Learning about design decisions
- Finding detailed file descriptions
- Looking for implementation plan

---

### 9. `IMPLEMENTATION_GUIDE.md` (400+ lines)
**Purpose**: Quick reference and step-by-step guide  
**Status**: ✅ Complete  
**Contents**:
- Summary of what was created
- Architecture details
- How to use (current state)
- Next steps planning
- Model statistics
- FAQ
- Learning path
- Code quality features

**Read This When**:
- Quick reference needed
- Looking for next steps
- Want to understand how to use the code
- Need implementation templates

---

### 10. `STEP1_SUMMARY.py` (250+ lines)
**Purpose**: Step 1 checklist and summary  
**Status**: ✅ Complete  
**Contents**:
- What has been created
- What was verified
- How to use now
- Next steps
- Implementation templates
- Quality assurance details

**Read This When**:
- Reviewing what was done in Step 1
- Looking for implementation templates
- Checking the checklist

---

### 11. `STEP1_VISUAL_SUMMARY.md` (300+ lines)
**Purpose**: Visual representation of project status  
**Status**: ✅ Complete  
**Contents**:
- Project structure diagram
- Algorithm flowchart
- Component status matrix
- Master Problem details
- Performance expectations
- Code quality metrics
- What you can do now
- Architecture comparison

**Read This When**:
- Need visual overview
- Want to understand algorithm flow
- Checking what components are done
- Planning next steps

---

### 12. `this file - FILES_OVERVIEW.md`
**Purpose**: This reference document  
**Status**: ✅ Complete  
**Contents**:
- Description of every file
- Purpose and status
- Key classes and functions
- Dependencies
- When to modify

**Read This When**:
- Don't know where something is
- Need to understand file relationships
- Planning modifications

---

## 🟢 Data Files

### 13. `test_instance.py` (Pre-existing - 90 lines)
**Purpose**: Instance data and problem parameters  
**Status**: ✅ Existing  

**Contains**:
- **Sets**: G, S, W, I, L, C, K, F, H (with cardinalities)
- **Transportation Data**: TD_gs, TD_sl, TD_si, TD_sc
- **Emission Factors**: epsilon_truck, epsilon_land, epsilon_inc, epsilon_kiln_w, epsilon_kiln_f
- **Costs**: c_truck, c_land, c_inc, c_invest_k, c_preproc_w, c_penalty, price_f
- **Capacities**: Q_gw, Q_s, Q_l, Q_i, Q_k
- **Budget Parameters**: budget_municipality, budget_cem
- **Subsidy Parameters**: phi_max, phi_wh
- **Energy Content**: alpha_c, beta_f, beta_w
- **Computed Parameters**: fixcost_invest, CRF

**Should Modify When**:
- Testing with different instance sizes
- Changing problem parameters
- Trying different scenarios

---

## 📊 File Dependencies

```
test_instance.py
    ↓
instance_loader.py ←────────────────┐
    ↓                               │
┌───┴────────┬──────────────────┐   │
│            │                  │   │
│            ↓                  ↓   │
│      master_problem.py   utils.py │
│            ↑               ↑      │
│            └───────┬───────┘      │
│                    │              │
│                    ↓              │
│      Yue_2017_decomposition.py    │
│      (main orchestration)         │
│                    ↑              │
│                    └──────────────┘
│
└──── config.py
```

**Dependency Rules**:
1. No file imports from files below it
2. No circular imports
3. Leaf files (utils.py, config.py) have no internal dependencies
4. Top-level (Yue_2017_decomposition.py) coordinates everything

---

## 📈 File Statistics

| File | Lines | Status | Comments |
|------|-------|--------|----------|
| instance_loader.py | 75 | ✅ | Concise, focused |
| master_problem.py | 380 | ✅ | Comprehensive MP |
| config.py | 40 | ✅ | Simple, well-organized |
| utils.py | 140 | ✅ | Reusable utilities |
| Yue_2017_decomposition.py | 310 | ✅ | Well-structured orchestration |
| README.md | 500+ | ✅ | Comprehensive docs |
| IMPLEMENTATION_GUIDE.md | 400+ | ✅ | Quick reference |
| STEP1_SUMMARY.py | 250+ | ✅ | Checklist & templates |
| STEP1_VISUAL_SUMMARY.md | 300+ | ✅ | Visual overview |
| FILES_OVERVIEW.md | 350+ | ✅ | This file |
| **TOTAL** | **3,200+** | ✅ | Complete foundation |

---

## 🚀 Quick Start

### To get started immediately:
```bash
# Navigate to project directory
cd "h:\Dissertation\Shanghai\Paper\Co-Processing waste in cement industry\Paper2_CoProcessing"

# Test instance loading
python instance_loader.py

# Test Master Problem
python master_problem.py

# Run main algorithm (with SP1/SP2 placeholders)
python Yue_2017_decomposition.py
```

### To understand the architecture:
1. Read: `README.md` (overall structure)
2. Read: `STEP1_VISUAL_SUMMARY.md` (algorithm flow)
3. Read: `IMPLEMENTATION_GUIDE.md` (how to use)
4. Read: `FILES_OVERVIEW.md` (this file - detailed descriptions)

### To modify or extend:
1. Identify which file needs modification
2. Check its section in this document
3. Look at dependencies
4. Make changes
5. Test with `python filename.py`

---

## 🔍 Finding Things

### By File Type

**Configuration**:
- `config.py` - Algorithm parameters

**Core Implementation**:
- `instance_loader.py` - Data loading
- `master_problem.py` - MP implementation
- `Yue_2017_decomposition.py` - Algorithm orchestration

**Utilities**:
- `utils.py` - Helper functions

**Documentation**:
- `README.md` - Architecture
- `IMPLEMENTATION_GUIDE.md` - Usage guide
- `STEP1_SUMMARY.py` - Checklist
- `STEP1_VISUAL_SUMMARY.md` - Visual overview
- `FILES_OVERVIEW.md` - This file

### By Concept

**Where is the Master Problem?** → `master_problem.py`

**Where are the parameters?** → `test_instance.py` (data), `instance_loader.py` (loaded)

**Where is the main algorithm?** → `Yue_2017_decomposition.py`

**Where are the configuration settings?** → `config.py`

**Where should I add SP1?** → Create `subproblem_1.py`

**Where should I add SP2?** → Create `subproblem_2.py`

**How do I understand the architecture?** → Read `README.md`, then `STEP1_VISUAL_SUMMARY.md`

---

## 📝 Modification Checklist

**Adding a new parameter to the model?**
- [ ] Add to `test_instance.py`
- [ ] Add to `InstanceData.__init__()` in `instance_loader.py`
- [ ] Use in appropriate class (MP, SP1, SP2)

**Adding a new constraint?**
- [ ] Identify which problem (MP, SP1, SP2)
- [ ] Add to that class's `build()` method
- [ ] Test the model

**Changing algorithm behavior?**
- [ ] Modify `config.py` for parameters
- [ ] Modify `Yue_2017_decomposition.py` for logic
- [ ] Test with `python Yue_2017_decomposition.py`

**Debugging issues?**
- [ ] Check individual files with `python filename.py`
- [ ] Export model with `write_model()`
- [ ] Check logs with verbose=True

---

## ✅ Verification Checklist

After Step 1, verify:
- [ ] `python instance_loader.py` runs without errors
- [ ] `python master_problem.py` builds MP successfully
- [ ] `python Yue_2017_decomposition.py` shows algorithm structure
- [ ] All 9 documentation files are present
- [ ] No import errors when running code
- [ ] Model statistics match expectations (67 variables, 14 constraints)

---

## 🎯 Next Steps

After understanding these files:

1. **Step 2**: Create `subproblem_1.py` using template from `STEP1_SUMMARY.py`
2. **Step 3**: Create `subproblem_2.py` using same template pattern
3. **Step 4**: Implement cut generation in both SP1 and SP2
4. **Step 5**: Integrate everything and test convergence

Each step should take 45-60 minutes.

---

## 📞 Questions?

**What does this class do?** → Check "Key Class" section for the file

**How do I use this?** → Check "Usage" section for the file

**What depends on this?** → Check "Dependencies" section for the file

**When should I modify this?** → Check "Should Modify When" section for the file

---

*Last Updated: February 2, 2026*  
*Status: ✅ STEP 1 COMPLETE*  
*Ready for: STEP 2 (SubProblem 1 Implementation)*
