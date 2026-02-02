"""
Utilities Module
Helper functions for the decomposition algorithm
"""

import logging
from datetime import datetime
from pathlib import Path


def setup_logger(name: str, log_file: str = None) -> logging.Logger:
    """
    Setup a logger for the decomposition algorithm
    
    Parameters
    ----------
    name : str
        Logger name
    log_file : str, optional
        File to write logs to. If None, only console logging.
    
    Returns
    -------
    logging.Logger
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger


def print_section(title: str, width: int = 70):
    """Print a formatted section header"""
    print("\n" + "="*width)
    print(f" {title}")
    print("="*width)


def print_subsection(title: str, width: int = 70):
    """Print a formatted subsection header"""
    print("\n" + "-"*width)
    print(f" {title}")
    print("-"*width)


def format_number(value: float, decimals: int = 2) -> str:
    """Format a number with thousand separators"""
    return f"{value:,.{decimals}f}"


def check_feasibility(model) -> bool:
    """
    Check if a Gurobi model is feasible
    
    Parameters
    ----------
    model : gurobipy.Model
        Gurobi model to check
    
    Returns
    -------
    bool
        True if model is optimal, False otherwise
    """
    from gurobipy import GRB
    return model.status == GRB.OPTIMAL or model.status == GRB.SUBOPTIMAL


def extract_nonzero_solution(solution_dict: dict, tolerance: float = 1e-6) -> dict:
    """
    Filter solution to include only non-zero variables
    
    Parameters
    ----------
    solution_dict : dict
        Dictionary of variable values
    tolerance : float
        Threshold below which values are considered zero
    
    Returns
    -------
    dict
        Filtered dictionary with only non-zero entries
    """
    return {k: v for k, v in solution_dict.items() if abs(v) > tolerance}


def compute_optimality_gap(upper_bound: float, lower_bound: float) -> float:
    """
    Compute the optimality gap
    
    Parameters
    ----------
    upper_bound : float
        Upper bound (best feasible solution)
    lower_bound : float
        Lower bound (best relaxation)
    
    Returns
    -------
    float
        Relative optimality gap
    """
    if abs(lower_bound) < 1e-10:
        return float('inf')
    
    gap = abs(upper_bound - lower_bound) / abs(lower_bound)
    return gap


def save_results(results: dict, filename: str = "results.txt"):
    """
    Save optimization results to a file
    
    Parameters
    ----------
    results : dict
        Dictionary containing optimization results
    filename : str
        Output filename
    """
    with open(filename, 'w') as f:
        f.write("="*70 + "\n")
        f.write("DECOMPOSITION ALGORITHM RESULTS\n")
        f.write("="*70 + "\n")
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for key, value in results.items():
            if isinstance(value, dict):
                f.write(f"\n{key}:\n")
                for k, v in value.items():
                    f.write(f"  {k}: {v}\n")
            else:
                f.write(f"{key}: {value}\n")
    
    print(f"\n✓ Results saved to {filename}")


if __name__ == "__main__":
    logger = setup_logger("test")
    logger.info("Logger test message")
    print_section("Test Section")
    print(format_number(1234567.89, decimals=2))
    print(f"Gap: {compute_optimality_gap(100, 95):.4f}")
