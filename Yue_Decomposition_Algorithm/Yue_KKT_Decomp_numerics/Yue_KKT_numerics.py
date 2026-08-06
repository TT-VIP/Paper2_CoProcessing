import numpy as np
import math
import logging
from datetime import datetime
from pathlib import Path
import gurobipy as gp
import time
from enum import Enum, auto         # define a set of named constant values for decomposition status
from dataclasses import dataclass
from typing import Optional

from Instances.instance_generator_normalized import InstanceData
from .MP_numerics import MasterProblem, MasterSolution
from .SP1_numerics import SubProblem1, SubProblem1Solution
from .SP2_numerics import SubProblem2, SubProblem2Solution


class DecompositionStatus(Enum):
    OPTIMAL_PROVEN = auto()
    SUBOPTIMAL_INCUMBENTS_MATCH = auto()
    FEASIBLE_SUBOPTIMAL = auto()
    NO_FEASIBLE_SOLUTION = auto()
    MP_INFEASIBLE_OR_NO_SOLUTION = auto()

@dataclass
class DecompositionSolution:
    status: DecompositionStatus             # Overall status of the decomposition algorithm at termination (e.g., optimality proven, feasible but not proven optimal, no feasible solution found, etc.)

    xi: float                               # Convergence threshold for leader objective improvement (used for termination)
    max_iterations: int                     # Maximum number of iterations allowed for the decomposition algorithm (used for termination)
    iterations: int = 0                     # Actual number of iterations performed
    iteration_best_solution: Optional[int] = None  # Iteration number at which the best solution (lowest feasible UB) was found, if applicable
    total_solution_time: float = 0.0        # Total time taken for the entire decomposition algorithm (from start to termination)

    lower_bound: float = -np.inf            # Best lower bound on the leader's objective value found at termination of decomposition (from MP)
    upper_bound: float = np.inf             # Best upper bound on the leader's objective value found at termination of decomposition (from SP2)
    final_gap_proven: float = np.inf        # Final true optimality gap (UB - LB) at termination, if applicable
    final_gap_incumbents: float = np.inf    # Final gap based on incumbent solutions (SP2 obj - MP obj) at termination, if applicable

    equality_tol: float = 1e-3

    best_bilevel_mp_sol: Optional["MasterSolution"] = None
    best_bilevel_sp2_sol: Optional["SubProblem2Solution"] = None

    termination_reason: Optional[str] = None

    def has_feasible_solution(self) -> bool:
        return self.best_bilevel_sp2_sol is not None

    def incumbents_match(self) -> bool:
        if self.best_bilevel_mp_sol is None or self.best_bilevel_sp2_sol is None:
            return False
        # if self.best_bilevel_mp_sol.mp_obj is None or self.best_bilevel_sp2_sol.sp2_obj is None:
        #     return False
        return abs(self.best_bilevel_mp_sol.mp_obj - self.best_bilevel_sp2_sol.sp2_obj) <= self.equality_tol

    def is_proven_optimal(self) -> bool:
        return (
            math.isfinite(self.lower_bound)
            and math.isfinite(self.upper_bound)
            and (self.upper_bound - self.lower_bound) <= self.xi
        )

    def is_optimal_by_incumbent_match(self) -> bool:
        return self.has_feasible_solution() and self.incumbents_match()

def build_decomposition_solution(
    *,
    iterations: int,
    max_iterations: int,
    iteration_best_solution: Optional[int],
    total_solution_time: float,
    LB: float,
    UB: float,
    Xi: float,
    best_bilevel_mp_sol,
    best_bilevel_sp2_sol,
    termination_reason: str,
    equality_tol: float = 1e-3,
):
    best_bilevel_mp_obj = None if best_bilevel_mp_sol is None else float(best_bilevel_mp_sol.mp_obj)
    best_bilevel_sp2_obj = None if best_bilevel_sp2_sol is None else float(best_bilevel_sp2_sol.sp2_obj)

    final_gap_proven = None
    if math.isfinite(LB) and math.isfinite(UB):
        final_gap_proven = UB - LB
    
    final_gap_incumbents = None
    if best_bilevel_mp_obj is not None and best_bilevel_sp2_obj is not None:
        final_gap_incumbents = abs(best_bilevel_sp2_obj - best_bilevel_mp_obj)

    if math.isfinite(LB) and math.isfinite(UB) and (UB - LB <= Xi):
        status = DecompositionStatus.OPTIMAL_PROVEN
    elif (
        best_bilevel_mp_obj is not None
        and best_bilevel_sp2_obj is not None
        and final_gap_incumbents <= equality_tol
    ):
        status = DecompositionStatus.SUBOPTIMAL_INCUMBENTS_MATCH
    elif best_bilevel_sp2_sol is not None:
        status = DecompositionStatus.FEASIBLE_SUBOPTIMAL
    elif termination_reason == "MP solution run returned no feasible solution":
        status = DecompositionStatus.MP_INFEASIBLE_OR_NO_SOLUTION
    else:
        status = DecompositionStatus.NO_FEASIBLE_SOLUTION

    return DecompositionSolution(
        status=status,
        xi=Xi,
        max_iterations=max_iterations,
        iterations=iterations,
        iteration_best_solution=iteration_best_solution,
        total_solution_time=total_solution_time,
        lower_bound=LB,
        upper_bound=UB,
        final_gap_proven=final_gap_proven,
        final_gap_incumbents=final_gap_incumbents,
        equality_tol=equality_tol,
        best_bilevel_mp_sol=best_bilevel_mp_sol,
        best_bilevel_sp2_sol=best_bilevel_sp2_sol,
        termination_reason=termination_reason
    )


#region Setup Logger
def setup_logger() -> None:
    """Setup logging to file and console"""
    # Create solutions folder if it doesn't exist
    log_dir = Path(__file__).parent / "solutions"
    log_dir.mkdir(exist_ok=True)
    
    # Create log filename with date and time
    now = datetime.now()
    log_filename = f"Yue_KKT_Decomp_{now.strftime('%Y%m%d_%H%M')}.log"
    log_path = log_dir / log_filename
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler()  # Also print to console
        ]
    )
    
    return log_path
#endregion

#region Helper functions for logging and big-M analysis in OC blocks
def log_bigM_binding(mp: MasterProblem, data: InstanceData, *, tol_ratio: float = 1e-3) -> None:
    """
    Logs if any big-M caps appear binding in any OC block.
    tol_ratio: flag as binding if value >= (1 - tol_ratio) * M
    """
    if not hasattr(mp, "kkt_oc_blocks") or not mp.kkt_oc_blocks:
        return

    def is_one(x: float) -> bool:
        return x >= 0.5  # binary; tolerate numerics

    def near_cap(val: float, M: float) -> bool:
        if M is None or M <= 0 or val is None:
            return False
        return val >= (1.0 - tol_ratio) * M

    # Pull leader z-values once (used in F9 b-terms)
    z_val = {(w, h): float(mp.z_wh[w, h].X) for w in data.W for h in data.H}

    total_dual_hits = 0
    total_primal_hits = 0

    for l, oc in mp.kkt_oc_blocks.items():
        dual_hits = []
        primal_hits = []

        # -------- helper: check lam <= M_dual * bin
        def check_dual_cap(name: str, lam_var, bin_var, M_key: str):
            nonlocal total_dual_hits
            M = float(data.M_dual[M_key])
            lam = float(lam_var.X)
            b = float(bin_var.X)
            if is_one(b) and near_cap(lam, M):
                dual_hits.append(f"{name}: dual={lam:.3g} hits M={M:.3g}")
                total_dual_hits += 1

        def _get_primal_M(data: InstanceData, M_key: str, *idx) -> float:
            M = data.M_primal[M_key]
            for i in idx:
                M = M[i]
            return float(M)

        # -------- helper: check b_expr <= M_primal*(1-bin)
        def check_primal_cap(name: str, b_expr: float, bin_var, M_key: str, *idx):
            nonlocal total_primal_hits
            # M = float(data.M_primal[M_key])
            M = _get_primal_M(data, M_key, *idx)
            b = float(bin_var.X)
            if (not is_one(b)) and near_cap(b_expr, M):
                primal_hits.append(f"{name}: primal={b_expr:.3g} hits M={M:.3g}")
                total_primal_hits += 1

        # === F3 (b = sum q_cf*beta_f + sum q_cw*beta_w - alpha) >= 0
        for c in data.C:
            bF3 = sum(float(oc.q_cf[c, f].X) * data.beta_f[f] for f in data.F) + sum(float(oc.q_scw[s, c, w].X) * data.beta_w[w] for s in data.S for w in data.W) - data.alpha_c[c]
            check_dual_cap(f"OC{l}.F3[c={c}]", oc.lam_F3[c], oc.bin_F3[c], "lam_F3")
            check_primal_cap(f"OC{l}.F3[c={c}]", bF3, oc.bin_F3[c], "F3")

        # === F4 (b = kappa*alpha - sum q_cw*beta_w) >= 0
        for c in data.C:
            bF4 = data.kappa_coproc * data.alpha_c[c] - sum(float(oc.q_scw[s, c, w].X) * data.beta_w[w] for s in data.S for w in data.W)
            check_dual_cap(f"OC{l}.F4[c={c}]", oc.lam_F4[c], oc.bin_F4[c], "lam_F4")
            check_primal_cap(f"OC{l}.F4[c={c}]", bF4, oc.bin_F4[c], "F4", c)

        # === F5 (b = cap - sum q_cw) >= 0
        for c in data.C:
            cap = sum(oc.x_ck_fixed[(c, k)] * data.Q_k[k] for k in data.K)
            bF5 = cap - sum(float(oc.q_scw[s, c, w].X) for s in data.S for w in data.W)
            check_dual_cap(f"OC{l}.F5[c={c}]", oc.lam_F5[c], oc.bin_F5[c], "lam_F5")
            check_primal_cap(f"OC{l}.F5[c={c}]", bF5, oc.bin_F5[c], "F5")

        # === Bound complementarity examples: pi_q_cw <= M*pi * bin, and q_cw <= M*q * (1-bin)
        # Here b = q itself (>=0)
        for c in data.C:
            for f in data.F:
                check_dual_cap(f"OC{l}.pi_q_cf[{c},{f}]", oc.pi_q_cf[c, f], oc.bin_q_cf[c, f], "pi_q_cf")
                q = float(oc.q_cf[c, f].X)
                check_primal_cap(f"OC{l}.q_cf[{c},{f}]", q, oc.bin_q_cf[c, f], "q_cf", c, f)

        for s in data.S:
            for c in data.C:
                for w in data.W:
                    check_dual_cap(f"OC{l}.pi_q_scw[{s},{c},{w}]", oc.pi_q_scw[s, c, w], oc.bin_q_scw[s, c, w], "pi_q_scw")
                    q = float(oc.q_scw[s, c, w].X)
                    check_primal_cap(f"OC{l}.q_scw[{s},{c},{w}]", q, oc.bin_q_scw[s, c, w], "q_scw", s, c, w)
        
        for s in data.S:
            for w in data.W:
                check_dual_cap(f"OC{l}.pi_r_sw[{s},{w}]", oc.pi_r_sw[s, w], oc.bin_r_sw[s, w], "pi_r_sw")
                r = float(oc.r_sw[s, w].X)
                check_primal_cap(f"OC{l}.r_sw[{s},{w}]", r, oc.bin_r_sw[s, w], "r_sw", s, w)


        if dual_hits or primal_hits:
            logging.info(f"[BigM] OC block l={l}: dual_hits={len(dual_hits)}, primal_hits={len(primal_hits)}")
            for s in dual_hits:
                logging.info(f"  - {s}")
            for s in primal_hits:
                logging.info(f"  - {s}")
    if total_dual_hits == 0 and total_primal_hits == 0:
        logging.info("[BigM] No big-M caps appear binding at the chosen tolerance.")
#endregion

#region Helper functions for pattern keys and solution logging
# convert x_ck_fixed dict to a sorted tuple for consistent pattern keys in logging and cut management
def pattern_key(x_ck_fixed: dict) -> tuple:
    # sort to be deterministic
    return tuple(sorted((c, k, int(round(v))) for (c, k), v in x_ck_fixed.items()))

def format_pattern_dict(x_ck: dict) -> str:
    items = ", ".join(f"({c}, {k}): {int(round(v))}" for (c, k), v in sorted(x_ck.items()))
    return items

def log_nonzero_gurobi_vars(model: gp.Model, model_name: str, tol: float = 1e-4, var_names_to_log: list = None) -> None:
    """Log all nonzero variable values of a solved Gurobi model."""
    # logging.info(f"Objective value: {model.ObjVal:.4f}")

    logging.info(f"\nNonzero variables in {model_name} (|x| > {tol}):")
    count = 0
    for v in model.getVars():
        val = v.X
        if abs(val) > tol:
            # If filter list provided, only log if variable name starts with one of the filters
            if var_names_to_log is not None:
                if not any(v.VarName.startswith(name) for name in var_names_to_log):
                    continue
            logging.info(f"  {v.VarName} = {val:.10g}")
            count += 1
    logging.info(f"Total nonzero vars in {model_name}: {count}")
#endregion

#region Main function for decomposition algorithm
def run_yue_decomposition(
        Verbose: bool = True,
        solver_time_limit: int = 500,
        mip_gap: float = 1e-4,
        Xi: float = 1e-1,
        max_iterations: int = 5,
        instance: InstanceData = None,
        weight_env: float = 0.5,
        weight_mon: float = 0.5,
        total_time_limit: float = 3630.0,
        shutdown_buffer: float = 30.0,
) -> None:

    # Load instance data
    # shanghai_data = make_shanghai_instance_effective()
    if instance is None:
        raise RuntimeError("Instance data must be provided to run the Decomposition Algorithm.")
    instance_data = instance

    instance_data.weight_env = weight_env
    instance_data.weight_mon = weight_mon

    # Starting Configuration
    LB = -np.inf
    UB = np.inf
    iteration = 0
    oc_blocks_added = 0
    duplicate_oc_blocks_skipped = 0

    # start timer for overall algorithm
    start_total = time.perf_counter()
    # internal wall-clock budget for solver calls
    def elapsed() -> float:
        return time.perf_counter() - start_total

    def remaining() -> float:
        return max(0.0, total_time_limit - elapsed())

    def time_left_for_solve() -> float:
        return max(1.0, remaining() - shutdown_buffer)

    # Initialize Master Problem - L=empty set is implicit: MP starts without any OC blocks
    mp = MasterProblem(instance_data)
    mp.build(output_flag=1)

    best_bilevel_mp_sol = None
    best_bilevel_sp2_sol = None
    termination_reason = None
    iteration_best_solution = None

    # Track if we've printed quality for each model after first solve
    mp_quality_printed = False
    sp1_quality_printed = False
    sp2_quality_printed = False

    generated_patterns_kkt_blocks = set()   # book-keeping: to track which patterns have had KKT OC blocks added, to avoid duplicates
    generated_patterns = []                 # list of dictionaries of all patterns in the order the cuts were added

    # Decomposition Algorithm with KKT OC Cuts
    while iteration < max_iterations and (UB - LB > Xi) and remaining() > shutdown_buffer:
        iteration += 1
        terminate = False
        starttime_iteration = time.perf_counter()

        if Verbose:
            logging.info("\n" + "="*150)
            logging.info(f"Iteration {iteration}")
            logging.info(f"Current bounds: LB = {LB:.5f}, UB = {UB:.5f}, Gap = {(UB - LB):.5f}")
            logging.info("="*150)

        if iteration <= 8:
            base_mp_limit = 180
        elif iteration <= 10:
            base_mp_limit = 300
        else:
            base_mp_limit = 600

        mp_time_limit = min(base_mp_limit, time_left_for_solve())
        
        if mp_time_limit <= 5.5:
            termination_reason = "Global time limit reached (before next MP solve, time left <= 5 seconds)"
            break

        # Solve Master Problem
        if iteration % 5 == 0:
            mp.model.Params.MIPFocus = 3  # Focus on best objective bound if bound is moving very slowly (or not at all)
            # mp.model.Params.ScaleFlag = 2  # Enable aggressive scaling to help with numerical issues and potentially improve bounds
            solver_time = min(solver_time_limit, time_left_for_solve())
            mp.solve(time_limit=solver_time)  # Longer time limit for MP every 5 iterations to improve LB
        else:
            mp.model.Params.MIPFocus = 0  # Default focus - balance between finding good solutions and proving optimality
            # mp.model.Params.MIPFocus = 2  # solver is having no trouble finding good quality solutions, and wish to focus more attention on proving optimality
            # mp.model.Params.ScaleFlag = 2   # Already default in MP.py
            mp.model.Params.Seed = 1
            mp.solve(time_limit=mp_time_limit, mip_gap=mip_gap)
        if mp.model.SolCount == 0:
            logging.info("No solution found for Master Problem. Terminating.")
            termination_reason = "MP solution run returned no feasible solution"
            break

        # Print MP quality after first solve (happens after first OC block is added in iteration 2)
        if not mp_quality_printed and mp.model.SolCount > 0 and iteration >= 2:
            logging.info("\n" + "="*70)
            logging.info("Master Problem Solution Quality (after first OC block added):")
            logging.info("="*70)
            mp.model.printQuality()
            logging.info("="*70 + "\n")
            mp_quality_printed = True
        
        # LB update
        prev_LB = LB
        try:
            new_LB = mp.model.ObjBound  # Update LB with the best bound from MP
        except Exception:
            new_LB = mp.model.ObjVal  # Fallback to MP solution objective if bound is not available
        LB = max(LB, new_LB)  # Ensure LB does not decrease
        
        # solution logging
        logging.info(f"\nBest Master Problem Solution: Objective = {mp.model.ObjVal:.5f}, Bound = {mp.model.ObjBound:.5f}, Gap = {mp.model.MIPGap*100:.2f}%")
        if new_LB > prev_LB:
            logging.info(f"New LB found. LB updated from {prev_LB:.5f} to {new_LB:.5f}")
        else:
            logging.info(f"LB remains unchanged: LB = {LB:.5f}")

        mp_sol = mp.extract_solution()
        # Log the objective components for the MP solution
        logging.info("\nObjective breakdown MP:\n")
        logging.info(f"Weights: Environment ={instance_data.weight_env:.2f}, Monetary={instance_data.weight_mon:.2f}\n")
        for index, (component, value) in enumerate(mp_sol.objective_components.items(), start=1):
                logging.info(f"{component:<30} {float(value):>14.6f}")
                if index in (5,10):  # Add extra spacing after transport and treatment costs for readability
                    logging.info("")

        logging.info(f"\nCheck big-M bindings in MP solution:")
        log_bigM_binding(mp, instance_data)        # Log any big-M bindings in the current MP solution
        
        if remaining() <= shutdown_buffer:
            termination_reason = "Global time limit reached (after MP solve and before SP solves staerted)"
            break

        sp1_time_limit = min(60.0, time_left_for_solve())
        # Solve Subproblem 1 at leader solution (Follower Optimality)
        sp1 = SubProblem1(instance_data)
        sp1.build(mp_sol, name=f"Subproblem 1 - Iteration {iteration}", output_flag=1)
        
        # Print SP1 statistics after first build
        if not sp1_quality_printed:
            logging.info("\n" + "="*70)
            logging.info("Subproblem 1 Statistics:")
            logging.info("="*70)
            sp1.model.printStats()
            logging.info("="*70 + "\n")

        # sp1.solve(time_limit=solver_time_limit)
        sp1.solve(time_limit=sp1_time_limit)

        # Print SP1 quality after first solve
        if not sp1_quality_printed and sp1.model.SolCount > 0:
            logging.info("\n" + "="*70)
            logging.info("Subproblem 1 Solution Quality (after first solve):")
            logging.info("="*70)
            sp1.model.printQuality()
            logging.info("="*70 + "\n")
            sp1_quality_printed = True

        sp1_sol = sp1.extract_solution()
        logging.info(f"Subproblem 1 Solution: {sp1_sol.sp1_obj:.5f}")
        logging.info(f'Binary combination in SP1: x_ck = {sp1_sol.x_ck}')

        sp2_time_limit = min(60, time_left_for_solve())
        # Solve Subproblem 2 (Bilevel Feasibility) at leader solution and SP1 follower solution
        sp2 = SubProblem2(instance_data)
        sp2.build(mp_sol, sp1_sol, name=f"Subproblem 2 - Iteration {iteration}", output_flag=1)

        # Print SP2 statistics after first build
        if not sp2_quality_printed:
            logging.info("\n" + "="*70)
            logging.info("Subproblem 2 Statistics:")
            logging.info("="*70)
            sp2.model.printStats()
            logging.info("="*70 + "\n")

        # sp2.solve(time_limit=solver_time_limit)
        sp2.solve(time_limit=sp2_time_limit)

        # Print SP2 quality after first solve
        if not sp2_quality_printed and sp2.model.SolCount > 0:
            logging.info("\n" + "="*70)
            logging.info("Subproblem 2 Solution Quality (after first solve):")
            logging.info("="*70)
            sp2.model.printQuality()
            logging.info("="*70 + "\n")
            sp2_quality_printed = True

        sp2_sol = sp2.extract_solution()

        if sp2_sol.feasible:
            # Update upper bound and best solutions if better
            if float(sp2_sol.sp2_obj) < UB:
                UB = float(sp2_sol.sp2_obj)
                best_bilevel_mp_sol = mp_sol
                best_bilevel_sp2_sol = sp2_sol
                iteration_best_solution = iteration
                logging.info(f"Subproblem 2 feasible. Updated Upper Bound: UB = {UB:.5f}")
                logging.info(f'Binary combination in SP2: x_ck = {sp2_sol.x_ck}')
            else:
                logging.info(f"Subproblem 2 feasible but no improvement. Upper Bound remains unchanged: UB = {UB:.5f}")
                logging.info(f'Binary combination in SP2: x_ck = {sp2_sol.x_ck}')
            
            # Check convergence or finish before adding cut
            if UB - LB <= Xi:
                logging.info(f"Convergence achieved: UB - LB <= Xi: {UB - LB:.5f} <= {Xi}")
                logging.info("Terminating decomposition algorithm.")
                termination_reason = "Convergence achieved based on bounds and Gap tolerance (UB - LB <= Xi)"
                terminate = True
            elif iteration == max_iterations:
                logging.info(f"Maximum iterations reached: {iteration}. Terminating decomposition algorithm.")
                termination_reason = "Maximum iterations reached without convergence."
                terminate = True
            
            # check if x_ck KKT pattern has already had a KKT OC block added; if so, skip adding another to force diversification in future iterations
            if not terminate:
                key = pattern_key(sp2_sol.x_ck)
                if key in generated_patterns_kkt_blocks:
                    logging.info("ATTENTION: Duplicate x_ck pattern from SP2 encountered. OC block will NOT be duplicated because of no improvement.")
                    # mp._add_kkt_oc_block(sp2_sol.x_ck)  # Still add the OC block to cut off current solution, but log the duplication
                    duplicate_oc_blocks_skipped += 1
                    # logging.info("Duplicate x_ck pattern from SP2 encountered. Skipping OC block and forcing diversification.")
                    # mp._add_no_good_cut(sp2_sol.x_ck)  # Add no-good cut to forbid this exact x_ck pattern in future iterations
                else:
                    generated_patterns_kkt_blocks.add(key)
                    generated_patterns.append(sp2_sol.x_ck)  # Store the pattern for logging and analysis
                    # Add KKT Optimality Cut to MP based on SP2 solution
                    logging.info("Adding KKT-OC block based on x_ck of SP2 solution to cut off current leader solution.")
                    mp._add_kkt_oc_block(sp2_sol.x_ck)
                    oc_blocks_added += 1
                    # mp._add_kkt_oc_block_sos1(sp2_sol.x_ck)

                    # Print MP stats after first OC block is added
                    if not mp_quality_printed:
                        logging.info("\n" + "="*70)
                        logging.info("Master Problem Statistics (after first OC block added):")
                        logging.info("="*70)
                        mp.model.printStats()
                        logging.info("="*70 + "\n")
        
        else:
            if iteration == max_iterations:
                logging.info(f"Maximum iterations reached: {iteration}. Terminating decomposition algorithm.")
                termination_reason = "Maximum iterations reached without convergence."
                terminate = True

            else:
                logging.info("Subproblem 2 is infeasible -> Upper bound remains unchanged.")
                key = pattern_key(sp1_sol.x_ck)
                if key in generated_patterns_kkt_blocks:
                    logging.info("ATTENTION: Duplicate x_ck pattern from SP1 encountered. OC block will NOT be duplicated because of no improvement.")
                    # mp._add_kkt_oc_block(sp1_sol.x_ck)  # Still add the OC block to cut off current solution, but log the duplication
                    duplicate_oc_blocks_skipped += 1
                    # logging.info("Duplicate x_ck pattern from SP1 encountered. Skipping OC block and forcing diversification.")
                    # mp._add_no_good_cut(sp1_sol.x_ck)  # Add no-good cut to forbid this exact x_ck pattern in future iterations
                else:
                    generated_patterns_kkt_blocks.add(key)
                    generated_patterns.append(sp1_sol.x_ck)  # Store the pattern for logging and analysis
                    # Add KKT Optimality Cut to MP based on SP1 solution
                    logging.info("Adding KKT-OC block based on x_ck of SP1 solution to cut off current leader solution.")
                    mp._add_kkt_oc_block(sp1_sol.x_ck)
                    oc_blocks_added += 1
                    # mp._add_kkt_oc_block_sos1(sp1_sol.x_ck)

                    # Print MP stats after first OC block is added
                    if not mp_quality_printed:
                        logging.info("\n" + "="*70)
                        logging.info("Master Problem Statistics (after first OC block added):")
                        logging.info("="*70)
                        mp.model.printStats()
                        logging.info("="*70 + "\n")

        # Iteration summary
        if Verbose:
            endtime_iteration = time.perf_counter()
            iteration_time = endtime_iteration - starttime_iteration
            total_time = endtime_iteration - start_total

            logging.info("\n" + "-"*70)
            logging.info(f"End of Iteration {iteration} Summary:")
            logging.info(f"Best Incumbent MP Objective: {mp_sol.mp_obj:.5f}, MP Bound: {mp_sol.mp_bound:.5f}")
            rel_gap_str = (f"{(UB - LB) / abs(UB) * 100:.2f} %" if math.isfinite(LB) and math.isfinite(UB) and UB != 0 else 'N/A')
            logging.info(f"LB = {LB:.5f}, UB = {UB:.5f}, Gap (abs) = {(UB - LB):.5f}, Gap (relative) = {rel_gap_str}")
            logging.info(f"The KKT-OC block was added based on x_ck pattern: {sp2_sol.x_ck if sp2_sol.feasible else sp1_sol.x_ck}")
            logging.info(f"Total OC blocks added so far: {oc_blocks_added} (Duplicate patterns skipped: {duplicate_oc_blocks_skipped})")
            logging.info(f"Iteration time: {iteration_time:.2f} s | Total time so far: {total_time:.2f} s")
            logging.info("-"*70)

        if terminate:
            break

    # End timer for overall algorithm
    end_total = time.perf_counter()
    decomp_solution_time = end_total - start_total

    # Build DecompositionSolution object to summarize results
    decomp_sol = build_decomposition_solution(
        iterations=iteration,
        max_iterations=max_iterations,
        iteration_best_solution=iteration_best_solution,
        total_solution_time=decomp_solution_time,
        LB=LB,
        UB=UB,
        Xi=Xi,
        best_bilevel_mp_sol=best_bilevel_mp_sol,
        best_bilevel_sp2_sol=best_bilevel_sp2_sol,
        termination_reason=termination_reason,
        equality_tol=1e-3
    )
    
    #region Final Solution Summary
    def _nonzero_items(d: dict, tol: float = 1e-6):
        return [(k, v) for k, v in d.items() if abs(float(v)) > tol]

    def _log_dict(name: str, d: dict, tol: float = 1e-6) -> None:
        def _fmt_index(idx) -> str:
            if isinstance(idx, tuple):
                return "[" + ",".join(str(x) for x in idx) + "]"
            return f"({idx})"
        
        nz = _nonzero_items(d, tol)
        logging.info(f"• {name}: {len(nz)} nonzero")
        for k, v in sorted(nz):
            logging.info(f"  {name}{_fmt_index(k)} = {float(v):.10g}")

    def solution_summary(decomp_sol: DecompositionSolution, tol: float = 1e-6) -> None:
        logging.info("\n" + "#"*70)
        logging.info("Decomposition Algorithm - Solution Summary:")
        logging.info("#"*70)
        logging.info(f"Status: {decomp_sol.status.name}")
        logging.info(f"Termination Reason: {decomp_sol.termination_reason}")
        logging.info(f"Iterations: {decomp_sol.iterations}/{decomp_sol.max_iterations} (OC blocks added: {oc_blocks_added}, Duplicate patterns skipped: {duplicate_oc_blocks_skipped})")
        if decomp_sol.iteration_best_solution is not None:
            logging.info(f"Best solution found in iteration: {decomp_sol.iteration_best_solution}")
        logging.info(f"Total Solution Time: {decomp_sol.total_solution_time:.2f} seconds")
        logging.info(f"Final incumbent MP Objective: {decomp_sol.best_bilevel_mp_sol.mp_obj:.5f}" if decomp_sol.best_bilevel_mp_sol is not None else "No incumbent MP solution")
        logging.info(f"Final LB (best Master): {decomp_sol.lower_bound:.5f}")
        logging.info(f"Final UB (best SP2): {decomp_sol.upper_bound:.5f}")
        logging.info(f"Final Gap (abs): {decomp_sol.final_gap_proven:.5f}" if decomp_sol.final_gap_proven is not None else "Final Gap (proven): N/A")
        logging.info(f"Final Gap (incumbent abs): {decomp_sol.final_gap_incumbents:.5f}" if decomp_sol.final_gap_incumbents is not None else "Final Gap (incumbents): N/A")
        logging.info(f"Final Gap (realtive): {((decomp_sol.upper_bound - decomp_sol.lower_bound) / abs(decomp_sol.upper_bound)) * 100:.2f}%" if math.isfinite(decomp_sol.lower_bound) and math.isfinite(decomp_sol.upper_bound) and decomp_sol.upper_bound != 0 else "Final Gap (relative): N/A")
        logging.info(f"Final Gap (incumbent realtive): {((decomp_sol.upper_bound - decomp_sol.best_bilevel_mp_sol.mp_obj) / abs(decomp_sol.upper_bound)) * 100:.2f}%" if decomp_sol.best_bilevel_mp_sol is not None and math.isfinite(decomp_sol.best_bilevel_mp_sol.mp_obj) and math.isfinite(decomp_sol.upper_bound) and decomp_sol.upper_bound != 0 else "Final Gap (incumbent relative): N/A")

        logging.info(f"\nCutted patterns (x_ck fixed patterns with KKT-OC blocks added):")
        for i, pattern in enumerate(generated_patterns, start=1):
            logging.info(f" Configuration {i}: {format_pattern_dict(pattern)}")

        if decomp_sol.status is DecompositionStatus.OPTIMAL_PROVEN and decomp_sol.final_gap_proven is not None:
            logging.info(f"Final Gap (proven): {decomp_sol.final_gap_proven:.5f}")
        if decomp_sol.status is DecompositionStatus.SUBOPTIMAL_INCUMBENTS_MATCH and decomp_sol.final_gap_incumbents is not None:
            logging.info(f"Final Gap (incumbent solutions): {decomp_sol.final_gap_incumbents:.5f}")

        if decomp_sol.status is DecompositionStatus.MP_INFEASIBLE_OR_NO_SOLUTION:
            logging.info("No feasible solution found for Master Problem during decomposition.")
        elif decomp_sol.status is DecompositionStatus.NO_FEASIBLE_SOLUTION:
            logging.info("No feasible bilevel solution found during decomposition.")
        else:
            logging.info("\n" + "#"*70)
            logging.info(f"Best bilevel solution found")
            logging.info("#"*70)

            logging.info("\nMunicipality [Leader]")
            logging.info("" + "-"*70)

            logging.info("\nObjective breakdown:\n")
            logging.info(f"Weights: Environment ={instance_data.weight_env:.2f}, Monetary={instance_data.weight_mon:.2f}")
            for index, (component, value) in enumerate(decomp_sol.best_bilevel_mp_sol.objective_components.items(), start=1):
                logging.info(f"{component:<30} {float(value):>14.6f}")
                if index in (5,10):  # Add extra spacing after transport and treatment costs for readability
                    logging.info("")
            
            leader_dict_vars = ["q_gsw", "q_slw", "q_siw", "d_siw", "z_wh", "y_wh"]
            leader_scalar_vars = ["mu_land", "mu_inc", "mu_kiln"]

            logging.info(f"\nNonzero variables in Leader Problem (|x| > {tol}):")
            for name in leader_dict_vars:
                _log_dict(name, getattr(decomp_sol.best_bilevel_mp_sol, name), tol)
            for name in leader_scalar_vars:
                val = float(getattr(decomp_sol.best_bilevel_mp_sol, name))
                if abs(val) > tol:
                    logging.info(f"{name} = {val:.10g}")

            logging.info("\nCement Producer [Follower]")
            logging.info("" + "-"*70)

            logging.info("\nObjective breakdown:\n")
            for index, (component, value) in enumerate(decomp_sol.best_bilevel_sp2_sol.objective_components.items(), start=1):
                logging.info(f"{component:<30} {float(value):>14.6f}")
                if index == 6:
                    logging.info("")
            
            follower_dict_vars = ["x_ck", "q_cf", "r_sw", "q_scw"]
            logging.info(f"\nNonzero variables in Follower Problem (|x| > {tol}):")
            for name in follower_dict_vars:
                _log_dict(name, getattr(decomp_sol.best_bilevel_sp2_sol, name), tol)

    solution_summary(decomp_sol)
    #endregion
#endregion

if __name__ == "__main__":
    log_path = setup_logger()
    logging.info(f"Yue-KKT Decomposition Algorithm started. Logs will be saved to {log_path}")
    run_yue_decomposition(Verbose=True)