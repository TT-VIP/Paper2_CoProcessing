import numpy as np
import logging
from datetime import datetime
from pathlib import Path
import math
import gurobipy as gp

from Instances.instance_loader import InstanceData
from .MP_KKT_ModelReformulation_Multi import MasterProblem
from .SP1_ModelReformulation import SubProblem1
from .SP2_ModelReformulation import SubProblem2
# from shanghai_instance import make_shanghai_instance
# from Instances.shanghai_instance_scaled import make_shanghai_instance_scaled
from Instances.shanghai_instance_effective import make_shanghai_instance_effective


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

        # -------- helper: check b_expr <= M_primal*(1-bin)
        def check_primal_cap(name: str, b_expr: float, bin_var, M_key: str):
            nonlocal total_primal_hits
            M = float(data.M_primal[M_key])
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
            check_primal_cap(f"OC{l}.F4[c={c}]", bF4, oc.bin_F4[c], "F4")

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
                check_primal_cap(f"OC{l}.q_cf[{c},{f}]", q, oc.bin_q_cf[c, f], "q_cf")

        for s in data.S:
            for c in data.C:
                for w in data.W:
                    check_dual_cap(f"OC{l}.pi_q_scw[{s},{c},{w}]", oc.pi_q_scw[s, c, w], oc.bin_q_scw[s, c, w], "pi_q_scw")
                    q = float(oc.q_scw[s, c, w].X)
                    check_primal_cap(f"OC{l}.q_scw[{s},{c},{w}]", q, oc.bin_q_scw[s, c, w], "q_scw")
        
        for s in data.S:
            for w in data.W:
                check_dual_cap(f"OC{l}.pi_r_sw[{s},{w}]", oc.pi_r_sw[s, w], oc.bin_r_sw[s, w], "pi_r_sw")
                r = float(oc.r_sw[s, w].X)
                check_primal_cap(f"OC{l}.r_sw[{s},{w}]", r, oc.bin_r_sw[s, w], "r_sw")


        if dual_hits or primal_hits:
            logging.info(f"[BigM] OC block l={l}: dual_hits={len(dual_hits)}, primal_hits={len(primal_hits)}")
            for s in dual_hits:
                logging.info(f"  - {s}")
            for s in primal_hits:
                logging.info(f"  - {s}")
    if total_dual_hits == 0 and total_primal_hits == 0:
        logging.info("[BigM] No big-M caps appear binding at the chosen tolerance.")

# convert x_ck_fixed dict to a sorted tuple for consistent pattern keys in logging and cut management
def pattern_key(x_ck_fixed: dict) -> tuple:
    # sort to be deterministic
    return tuple(sorted((c, k, int(round(v))) for (c, k), v in x_ck_fixed.items()))

def log_nonzero_gurobi_vars(model: gp.Model, model_name: str, tol: float = 1e-4, var_names_to_log: list = None) -> None:
    """Log all nonzero variable values of a solved Gurobi model."""
    logging.info(f"Objective value: {model.ObjVal:.4f}")

    logging.info(f"\nNonzero variables in {model_name} (|x| > {tol}):")
    count = 0
    for v in model.getVars():
        val = v.X
        if abs(val) > tol:
            # If filter list provided, only log if variable name starts with one of the filters
            if var_names_to_log is not None and not any(v.VarName.startswith(name) for name in var_names_to_log):
                    continue
            logging.info(f"  {v.VarName} = {val:.10g}")
            count += 1

def main(Verbose: bool = True) -> None:
    solver_time_limit = 300     # seconds per solve (MP, SP1, SP2)
    solver_time_limit_sp2 = 1800  # longer time limit for SP2 due to feasibility check necessity
    Xi = 10                     # termination tolerance (UB - LB <= Xi)
    max_iterations = 3         # maximum number of iterations
    # Verbose = True              # enable detailed output

    # Load instance data
    shanghai_data = make_shanghai_instance_effective()

    # Starting Configuration
    LB = -np.inf
    UB = np.inf
    iteration = 0

    # Initialize Master Problem - L=empty set is implicit: MP starts without any OC blocks
    mp = MasterProblem(shanghai_data)
    mp.build(output_flag=1)

    best_mp_sol = None
    best_sp2_sol = None
    last_sp2_model = None  # to store the last SP2 model for potential post-analysis

    generated_patterns_kkt_blocks = set()  # to track which patterns have had KKT OC blocks added, to avoid duplicates

    # Decomposition Algorithm with KKT OC Cuts
    while iteration < max_iterations and (UB - LB > Xi):
        iteration += 1
        if Verbose:
            logging.info("\n" + "="*70)
            logging.info(f"Iteration {iteration}")
            logging.info(f"Current bounds: LB = {LB:.2f}, UB = {UB:.2f}, Gap = {(UB - LB):.2f}")
            logging.info("="*70)

        # Solve Master Problem
        if iteration % 5 == 0:
            mp.model.Params.MIPFocus = 3  # Focus on bound improvement every 5 iterations
            mp.solve(time_limit=1800)  # Longer time limit for MP every 5 iterations to improve LB
        else:
            mp.model.Params.MIPFocus = 0  # Default focus
            # mp.solve(time_limit=solver_time_limit)
            # mp.model.Params.MIPGap = 0.02
            mp.solve(time_limit=solver_time_limit)
        if mp.model.SolCount == 0:
            logging.info("No solution found for Master Problem. Terminating.")
            break
        
        # LB update
        prev_LB = LB
        if mp.model.NumObj > 1:
            mp.model.params.ObjNumber = 0  # If a second objective exists (e.g. for stabilization), switch to it for bound
            try:
                new_LB = mp.model.ObjPassNObjBound  # Update LB with the best bound from MP
                logging.info(f"Best Master Problem Solution: Objective = {mp.model.ObjPassNObjVal:.2f}, Bound = {mp.model.ObjPassNObjBound:.2f}")
            except Exception:
                new_LB = mp.model.ObjPassNObjVal  # Fallback to MP solution objective if bound is not available
                logging.info(f"Best Master Problem Solution: Objective = {mp.model.ObjPassNObjVal:.2f} (bound not available)")
        else:
            try:
                new_LB = mp.model.ObjBound  # Update LB with the best bound from MP
                logging.info(f"Best Master Problem Solution: Objective = {mp.model.ObjVal:.2f}, Bound = {mp.model.ObjBound:.2f}")
            except Exception:
                new_LB = mp.model.ObjVal  # Fallback to MP solution objective if bound is not available
                logging.info(f"Best Master Problem Solution: Objective = {mp.model.ObjVal:.2f} (bound not available)")
        LB = max(LB, new_LB)  # Ensure LB does not decrease
        
        # solution logging
        if new_LB > prev_LB:
            logging.info(f"New LB found. LB updated from {prev_LB:.2f} to {new_LB:.2f}")
        else:
            logging.info(f"LB remains unchanged: LB = {LB:.2f}")

        log_bigM_binding(mp, shanghai_data)        # Log any big-M bindings in the current MP solution
        mp_sol = mp.extract_solution()


        # Solve Subproblem 1 at leader solution (Follower Optimality)
        sp1 = SubProblem1(shanghai_data)
        sp1.build(mp_sol, name=f"Subproblem 1 - Iteration {iteration}", output_flag=1)
        sp1.solve(time_limit=solver_time_limit)
        sp1_sol = sp1.extract_solution()
        logging.info(f"Subproblem 1 Solution: {sp1_sol.sp1_obj:.2f}")
        logging.info(f'Binary combination in SP1: x_ck = {sp1_sol.x_ck}')


        # Solve Subproblem 2 (Bilevel Feasibility) at leader solution and SP1 follower solution
        sp2 = SubProblem2(shanghai_data)
        sp2.build(mp_sol, sp1_sol, name=f"Subproblem 2 - Iteration {iteration}", output_flag=1)
        sp2.solve(time_limit=solver_time_limit_sp2)
        sp2_sol = sp2.extract_solution()
        last_sp2_model = sp2.model  # Store the last SP2 model for potential post-analysis

        if sp2_sol.feasible:
            # Update upper bound and best solutions if better
            if float(sp2_sol.sp2_obj) < UB:
                UB = float(sp2_sol.sp2_obj)
                best_mp_sol = mp_sol
                best_sp2_sol = sp2_sol
                logging.info(f"Subproblem 2 feasible. Updated Upper Bound: UB = {UB:.2f}")
                logging.info(f'Binary combination in SP2: x_ck = {sp2_sol.x_ck}')
            else:
                logging.info(f"Subproblem 2 feasible but no improvement. Upper Bound remains unchanged: UB = {UB:.2f}")
                logging.info(f'Binary combination in SP2: x_ck = {sp2_sol.x_ck}')
            
            # Check convergence before adding cut
            if UB - LB <= Xi:
                logging.info(f"Convergence achieved: UB - LB = {UB - LB:.2f} <= Xi = {Xi}")
                logging.info("Terminating decomposition loop without adding new OC block.")
                break
            
            # check if x_ck KKT pattern has already had a KKT OC block added; if so, skip adding another to force diversification in future iterations
            key = pattern_key(sp2_sol.x_ck)
            if key in generated_patterns_kkt_blocks:
                logging.info("ATTENTION: Duplicate x_ck pattern from SP2 encountered. OC block will be duplicated without improvement.")
                mp._add_kkt_oc_block(sp2_sol.x_ck)  # Still add the OC block to cut off current solution, but log the duplication
                # logging.info("Duplicate x_ck pattern from SP2 encountered. Skipping OC block and forcing diversification.")
                # mp._add_no_good_cut(sp2_sol.x_ck)  # Add no-good cut to forbid this exact x_ck pattern in future iterations
            else:
                generated_patterns_kkt_blocks.add(key)
                # Add KKT Optimality Cut to MP based on SP2 solution
                logging.info("Adding KKT OC block based on x_ck of SP2 solution to cut off current leader solution.")
                mp._add_kkt_oc_block(sp2_sol.x_ck)
                # mp._add_kkt_oc_block_sos1(sp2_sol.x_ck)
        else:
            logging.info("Subproblem 2 is infeasible -> Upper bound remains unchanged.")
            key = pattern_key(sp1_sol.x_ck)
            if key in generated_patterns_kkt_blocks:
                logging.info("ATTENTION: Duplicate x_ck pattern from SP1 encountered. OC block will be duplicated without improvement.")
                mp._add_kkt_oc_block(sp1_sol.x_ck)  # Still add the OC block to cut off current solution, but log the duplication
                # logging.info("Duplicate x_ck pattern from SP1 encountered. Skipping OC block and forcing diversification.")
                # mp._add_no_good_cut(sp1_sol.x_ck)  # Add no-good cut to forbid this exact x_ck pattern in future iterations
            else:
                generated_patterns_kkt_blocks.add(key)
                # Add KKT Optimality Cut to MP based on SP1 solution
                logging.info("Adding KKT OC block based on x_ck of SP1 solution to cut off current leader solution.")
                mp._add_kkt_oc_block(sp1_sol.x_ck)
                # mp._add_kkt_oc_block_sos1(sp1_sol.x_ck)

        # Iteration summary
        if Verbose:
            logging.info("\n" + "-"*70)
            logging.info(f"End of Iteration {iteration} Summary:")
            logging.info(f"  LB = {LB:.2f}, UB = {UB:.2f}, Gap = {(UB - LB):.2f}, Cut added from {'SP2' if sp2_sol.feasible else 'SP1'}")
            logging.info(f"The KKT OC block was added based on x_ck pattern: {sp2_sol.x_ck if sp2_sol.feasible else sp1_sol.x_ck}")
            # logging.info(f"The KKT OC block was added based on x_ck pattern: {key}")
            logging.info("-"*70)
    
    # Final Solution Summary
    def _nonzero_items(d: dict, tol: float = 1e-6):
        return [(k, v) for k, v in d.items() if abs(float(v)) > tol]

    def _log_dict(name: str, d: dict, tol: float = 1e-6) -> None:
        nz = _nonzero_items(d, tol)
        logging.info(f"• {name}: {len(nz)} nonzero")
        for k, v in sorted(nz):
            logging.info(f"    {name}{k} = {float(v):.10g}")

    def log_compact_best_solution(best_mp_sol, best_sp2_sol, tol: float = 1e-6) -> None:
        logging.info("\n" + "#"*70)
        logging.info("Best Solution found (nonzero relevant vars only, no duals):")
        logging.info("" + "#"*70)

        logging.info("\nMunicipality [Leader]")
        logging.info("" + "-"*70)
        logging.info(f"Objective value: {best_mp_sol.mp_obj:.2f}")
        leader_dict_vars = ["q_gsw", "q_slw", "q_siw", "z_wh", "y_wh"]
        leader_scalar_vars = ["mu_land", "mu_inc", "mu_kiln"]

        logging.info(f"\nNonzero variables in Leader Problem (|x| > {tol}):")

        for name in leader_dict_vars:
            _log_dict(name, getattr(best_mp_sol, name))

        for name in leader_scalar_vars:
            val = float(getattr(best_mp_sol, name))
            if abs(val) > tol:
                logging.info(f"{name} = {val:.10g}")

        logging.info("\nCement Producer [Follower]")
        logging.info("" + "-"*70)
        logging.info(f"Objective value: {last_sp2_model.ObjVal:.2f}")
        follower_dict_vars = ["x_ck", "q_cf", "r_sw", "q_scw"]
        logging.info(f"\nNonzero variables in Follower Problem (|x| > {tol}):")
        for name in follower_dict_vars:
            _log_dict(name, getattr(best_sp2_sol, name))
    
    logging.info("\n" + "#"*70)
    logging.info("Finished Yue-KKT Decomposition run.")
    logging.info(f"Iterations {iteration}")
    logging.info(f"Final LB = {LB:.2f}")
    logging.info(f"Final UB = {UB:.2f}")
    logging.info(f"Final Gap = {(UB - LB):.2f} (tolerance Xi = {Xi})")
    logging.info(f"Cutted patterns: {generated_patterns_kkt_blocks}")
    if best_mp_sol is not None and best_sp2_sol is not None:
        # logging.info("\nBest Solution found:")
        # logging.info("Master Problem Solution (Leader Decisions):")
        # logging.info(best_mp_sol)
        # logging.info("\nSubproblem 2 Solution (Follower Reaction):")
        # logging.info(best_sp2_sol)

        log_compact_best_solution(best_mp_sol, best_sp2_sol)
    else:
        logging.info("No feasible solution found during the decomposition process.")
    
    # Print all nonzero decision variables from final solved models
    leader_vars = ["q_gsw", "q_slw", "q_siw", "mu_land", "mu_inc", "mu_kiln", "z_wh", "y_wh"]
    follower_vars = ["x_ck", "q_cf", "r_sw", "q_scw"]
    if mp.model.SolCount > 0:
        logging.info("\n" + "#"*70)
        logging.info("Best Solution found (nonzero relevant vars only, no duals):")
        logging.info("" + "#"*70)

        logging.info("\nMunicipality [Leader]")
        logging.info("" + "-"*70)

        leader_obj_values = mp.get_objective_breakdown()
        logging.info("\nObjective breakdown:\n")
        # key column width for alignment
        key_width_leader=max(len(k) for k in leader_obj_values.keys()) + 2
        for index, (k, v) in enumerate(leader_obj_values.items(), start=1):
            logging.info(f"{k:<{key_width_leader}} {v:>14.6f}")
            if index in (5,10):  # Add extra spacing after transport and treatment costs for readability
                logging.info("")

        log_nonzero_gurobi_vars(mp.model, "Leader Problem [Municipality]", var_names_to_log=leader_vars)
    
    if last_sp2_model is not None and last_sp2_model.SolCount > 0:
        logging.info("\n\nCement Producer [Follower]")
        logging.info("" + "-"*70)

        follower_obj_values = sp2.get_objective_components()
        logging.info("\nObjective breakdown:\n")
        key_width_follower = max(len(k) for k in follower_obj_values.keys()) + 2
        for index, (k, v) in enumerate(follower_obj_values.items(), start=1):
            logging.info(f"{k:<{key_width_follower}} {v:>14.6f}")
            if index == 6:
                logging.info("")

        log_nonzero_gurobi_vars(last_sp2_model, "Follower Problem [Cement Producer]", var_names_to_log=follower_vars)


if __name__ == "__main__":
    log_path = setup_logger()
    logging.info(f"Yue-KKT Decomposition Algorithm started. Logs will be saved to {log_path}")
    main(Verbose=True)