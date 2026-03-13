import os
import logging
from datetime import datetime
from pathlib import Path
from Yue_KKT_Decomp_New.Yue_KKT_Decomp_ModelReformulation_Multi import main
from Instances.shanghai_instance_effective import make_shanghai_instance_effective

# Define the parameter multipliers
multipliers = [0.4, 0.6, 0.8, 1.2, 1.4, 1.6]

# Create a directory for parameter analysis logs
param_analysis_dir = Path(__file__).parent / "parameter_analysis"
param_analysis_dir.mkdir(exist_ok=True)

# Function to set up logging
def setup_logger(param_values) -> Path:
    """Setup logging to file and console"""
    # Create log filename with date, time, and parameter values
    now = datetime.now()
    param_str = "_".join(f"{v:.1f}" for v in param_values)
    log_filename = f"Yue_KKT_Decomp_{now.strftime('%Y%m%d_%H%M')}_params_{param_str}.log"
    log_path = param_analysis_dir / log_filename
    
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

# Function to run the parameter study
def run_parameter_study():
    # Original parameters from the effective instance
    original_instance = make_shanghai_instance_effective()
    
    # Parameters to vary
    parameters_to_vary = [
        ("weight_env", original_instance.weight_env),
        ("weight_mon", original_instance.weight_mon),
        ("price_f", original_instance.price_f),
        ("c_preproc_w", original_instance.c_preproc_w),
        ("c_penalty", original_instance.c_penalty),
        ("beta_w", original_instance.beta_w)
    ]
    
    for param_name, original_value in parameters_to_vary:
        for multiplier in multipliers:
            # Create a modified instance with varied parameters
            modified_instance = make_shanghai_instance_effective()
            
            if param_name == "weight_env":
                modified_instance.weight_env = original_value * multiplier
            elif param_name == "weight_mon":
                modified_instance.weight_mon = original_value * multiplier
            elif param_name == "price_f":
                modified_instance.price_f = [p * multiplier for p in original_value]
            elif param_name == "c_preproc_w":
                modified_instance.c_preproc_w = [c * multiplier for c in original_value]
            elif param_name == "c_penalty":
                modified_instance.c_penalty = original_value * multiplier
            elif param_name == "beta_w":
                modified_instance.beta_w = [b * multiplier for b in original_value]
            
            # Set up logging for this parameter configuration
            log_path = setup_logger([modified_instance.weight_env, modified_instance.weight_mon] + 
                                    modified_instance.price_f + modified_instance.c_preproc_w + 
                                    [modified_instance.c_penalty] + modified_instance.beta_w)
            
            logging.info(f"Running decomposition algorithm with {param_name} set to {original_value * multiplier:.2f}")
            main(Verbose=True)  # Run the main function of the decomposition algorithm

if __name__ == "__main__":
    run_parameter_study()