"""
Yue et al. (2017) Decomposition Algorithm
Implementation of bilevel optimization decomposition for co-processing waste in cement industry

Paper: Yue et al. (2017) - Bilevel Supply Chain Network Design and Co-processing Waste

Algorithm Overview:
- Master Problem (MP): Leader (Municipality) problem
- Subproblem 1 (SP1): Follower feasibility problem (Cement facility)
- Subproblem 2 (SP2): Follower optimality problem (Cement facility profit maximization)

The algorithm iteratively solves these problems with cut generation until convergence.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import gurobipy as gp
from gurobipy import GRB

# Import local modules
from instance_loader import InstanceData
from Yue_Decomposition_Algorithm.gptSolution.master_problem import MasterProblem
from config import (
    ITERATION_LIMIT, OPTIMALITY_GAP_TOLERANCE, TIME_LIMIT,
    VERBOSE, WRITE_MODELS, OUTPUT_MP
)
from utils import (
    setup_logger, print_section, print_subsection, 
    format_number, compute_optimality_gap, save_results
)


class YueDecompositionAlgorithm:
    """
    Yue et al. (2017) Decomposition Algorithm Implementation
    
    This class orchestrates the bilevel optimization decomposition:
    1. Initialize the Master Problem (MP)
    2. Solve the Master Problem to obtain decisions for upper level
    3. Solve Subproblem 1 (SP1) - Feasibility problem for lower level
    4. Solve Subproblem 2 (SP2) - Optimality problem for lower level
    5. Generate cuts and add to MP
    6. Repeat until convergence
    """
    
    def __init__(self, instance: InstanceData, verbose: bool = VERBOSE):
        """
        Initialize the decomposition algorithm
        
        Parameters
        ----------
        instance : InstanceData
            Instance data containing all sets and parameters
        verbose : bool
            Enable verbose output
        """
        self.instance = instance
        self.verbose = verbose
        self.logger = setup_logger("YueDecomposition")
        
        # Algorithm state
        self.iteration = 0
        self.upper_bound = float('inf')  # Best feasible solution found
        self.lower_bound = -float('inf')  # Best LP relaxation
        self.optimality_gap = float('inf')
        self.converged = False
        
        # Problems
        self.mp = None  # Master Problem instance
        self.sp1 = None  # Subproblem 1 (will be created later)
        self.sp2 = None  # Subproblem 2 (will be created later)
        
        # Solutions and cuts
        self.mp_solutions = []
        self.sp1_solutions = []
        self.sp2_solutions = []
        self.cuts_generated = 0
        
        # Results
        self.results = {}
        
    def initialize(self):
        """Initialize all problems"""
        print_section("YÜNE ET AL. (2017) DECOMPOSITION ALGORITHM")
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        self.logger.info("="*70)
        self.logger.info("Initializing Yue et al. Decomposition Algorithm")
        self.logger.info("="*70)
        
        # Initialize Master Problem
        print_subsection("Step 1: Initialize Master Problem (MP)")
        self.mp = MasterProblem(self.instance)
        self.mp.build()
        
        if WRITE_MODELS:
            self.mp.write_model(OUTPUT_MP)
        
        self.logger.info("Master Problem initialized successfully")
        
        print("\n✓ Algorithm initialization complete!")
        print(f"  Ready to start {ITERATION_LIMIT} iterations")
        
    def solve_master_problem(self):
        """Solve the Master Problem"""
        print_subsection(f"Iteration {self.iteration}: Solve Master Problem")
        
        self.logger.info(f"Solving Master Problem - Iteration {self.iteration}")
        
        obj_value = self.mp.optimize()
        
        if obj_value is not None:
            self.logger.info(f"MP solved with objective: {format_number(obj_value)}")
            return self.mp.get_solution()
        else:
            self.logger.error("Master Problem solve failed")
            return None
    
    def solve_subproblem_1(self, mp_solution: dict):
        """
        Solve Subproblem 1 (Feasibility Problem)
        
        This will be implemented in the next step.
        For now, we create a placeholder.
        
        Parameters
        ----------
        mp_solution : dict
            Solution from the Master Problem
        """
        print_subsection(f"Iteration {self.iteration}: Solve Subproblem 1 (Feasibility)")
        print("  [SP1 will be implemented in the next step]")
        self.logger.info("SP1 solve placeholder (to be implemented)")
    
    def solve_subproblem_2(self, mp_solution: dict):
        """
        Solve Subproblem 2 (Optimality Problem)
        
        This will be implemented in the next step.
        For now, we create a placeholder.
        
        Parameters
        ----------
        mp_solution : dict
            Solution from the Master Problem
        """
        print_subsection(f"Iteration {self.iteration}: Solve Subproblem 2 (Optimality)")
        print("  [SP2 will be implemented in the next step]")
        self.logger.info("SP2 solve placeholder (to be implemented)")
    
    def generate_cuts(self, sp_solution: dict):
        """
        Generate optimality or feasibility cuts
        
        This will be implemented when SP1 and SP2 are ready.
        
        Parameters
        ----------
        sp_solution : dict
            Solution from subproblems
        """
        print_subsection(f"Iteration {self.iteration}: Generate Cuts")
        print("  [Cut generation will be implemented after SP1 and SP2]")
        self.logger.info("Cut generation placeholder (to be implemented)")
    
    def check_convergence(self) -> bool:
        """
        Check convergence criteria
        
        Returns
        -------
        bool
            True if algorithm has converged
        """
        self.optimality_gap = compute_optimality_gap(self.upper_bound, self.lower_bound)
        
        converged = self.optimality_gap <= OPTIMALITY_GAP_TOLERANCE
        
        if self.verbose:
            print(f"\n  Upper bound (UB): {format_number(self.upper_bound)}")
            print(f"  Lower bound (LB): {format_number(self.lower_bound)}")
            print(f"  Optimality gap:  {self.optimality_gap:.4%}")
            print(f"  Converged:       {'Yes' if converged else 'No'}")
        
        return converged
    
    def run(self) -> dict:
        """
        Run the complete decomposition algorithm
        
        Returns
        -------
        dict
            Results dictionary containing:
            - iterations: number of iterations
            - upper_bound: best feasible solution value
            - lower_bound: best lower bound
            - optimality_gap: final optimality gap
            - converged: whether algorithm converged
            - time_elapsed: computation time
        """
        import time
        start_time = time.time()
        
        try:
            self.initialize()
            
            for iteration in range(ITERATION_LIMIT):
                self.iteration = iteration
                
                print_section(f"ITERATION {iteration + 1}/{ITERATION_LIMIT}")
                
                # Step 1: Solve Master Problem
                mp_solution = self.solve_master_problem()
                if mp_solution is None:
                    self.logger.error("Algorithm terminated: MP solve failed")
                    break
                
                # Step 2: Solve Subproblem 1
                self.solve_subproblem_1(mp_solution)
                
                # Step 3: Solve Subproblem 2
                self.solve_subproblem_2(mp_solution)
                
                # Step 4: Generate Cuts
                self.generate_cuts(mp_solution)
                
                # Step 5: Check Convergence
                if self.check_convergence():
                    self.logger.info(f"Algorithm converged at iteration {iteration + 1}")
                    print("\n✓ CONVERGENCE ACHIEVED!")
                    self.converged = True
                    break
                
                print()  # Spacing
            
            # Finalize results
            elapsed_time = time.time() - start_time
            
            self.results = {
                'algorithm': 'Yue et al. (2017) Decomposition',
                'iterations': self.iteration + 1,
                'converged': self.converged,
                'upper_bound': self.upper_bound,
                'lower_bound': self.lower_bound,
                'optimality_gap': self.optimality_gap,
                'elapsed_time_seconds': elapsed_time,
                'cuts_generated': self.cuts_generated,
            }
            
            print_section("ALGORITHM SUMMARY")
            print(f"Total iterations: {self.results['iterations']}")
            print(f"Converged: {'Yes' if self.results['converged'] else 'No'}")
            print(f"Upper bound: {format_number(self.results['upper_bound'])}")
            print(f"Lower bound: {format_number(self.results['lower_bound'])}")
            print(f"Optimality gap: {self.results['optimality_gap']:.4%}")
            print(f"Elapsed time: {elapsed_time:.2f} seconds")
            print(f"Cuts generated: {self.cuts_generated}")
            
            return self.results
            
        except Exception as e:
            self.logger.error(f"Algorithm failed with error: {str(e)}")
            raise


def main():
    """Main entry point for the decomposition algorithm"""
    
    # Load instance data
    print_section("LOADING INSTANCE DATA")
    instance = InstanceData()
    instance.validate()
    print("✓ Instance data loaded successfully")
    
    # Run algorithm
    algorithm = YueDecompositionAlgorithm(instance, verbose=VERBOSE)
    results = algorithm.run()
    
    # Save results
    print_section("SAVING RESULTS")
    # save_results(results, filename="decomposition_results.txt")
    
    return results


if __name__ == "__main__":
    results = main()
