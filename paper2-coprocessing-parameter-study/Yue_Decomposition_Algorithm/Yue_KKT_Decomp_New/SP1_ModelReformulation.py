import sys
from pathlib import Path
import logging
from datetime import datetime
import numpy as np
from Instances.shanghai_instance_effective import make_shanghai_instance_effective
from Yue_KKT_Decomp_New.Yue_KKT_Decomp_ModelReformulation_Multi import main

# Ensure project root is importable (so "Instances" resolves)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def setup_logger(param_name: str, param_value: float) -> Path:
    """Setup logging to file and console for parameter analysis."""
    # Create parameter analysis folder if it doesn't exist
    log_dir = Path(__file__).parent / "parameter_analysis"
    log_dir.mkdir(exist_ok=True)
    
    # Create log filename with date, time, and parameter value
    now = datetime.now()
    log_filename = f"Yue_KKT_Decomp_{now.strftime('%Y%m%d_%H%M')}_param_{param_name}_{param_value:.2f}.log"
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

def run_parameter_study():
    # Original parameters from the effective instance
    original_instance = make_shanghai_instance_effective()
    
    # Parameters to vary
    parameters_to_vary = {
        'weight_env': original_instance.weight_env,
        'weight_mon': original_instance.weight_mon,
        'price_f': original_instance.price_f,
        'c_preproc_w': original_instance.c_preproc_w,
        'c_penalty': original_instance.c_penalty,
        'beta_w': original_instance.beta_w,
    }
    
    # Multipliers for the parameters
    multipliers = [0.4, 0.6, 0.8, 1.2, 1.4, 1.6]
    
    # Iterate over each parameter
    for param_name, original_value in parameters_to_vary.items():
        for multiplier in multipliers:
            # Create a modified instance based on the parameter being varied
            modified_instance = make_shanghai_instance_effective()
            
            # Update the parameter based on the multiplier
            if param_name in ['price_f', 'beta_w']:
                # For lists, multiply each element
                setattr(modified_instance, param_name, [v * multiplier for v in original_value])
            else:
                # For single float values
                setattr(modified_instance, param_name, original_value * multiplier)
            
            # Setup logger for this parameter configuration
            log_path = setup_logger(param_name, multiplier)
            logging.info(f"Running parameter study with {param_name} = {original_value * multiplier:.2f}")

            # Run the decomposition algorithm with the modified instance
            main(Verbose=True)

if __name__ == "__main__":
    run_parameter_study()