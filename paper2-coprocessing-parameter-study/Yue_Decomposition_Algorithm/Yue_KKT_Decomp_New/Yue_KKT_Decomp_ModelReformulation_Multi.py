import sys
from pathlib import Path
import logging
from datetime import datetime
import numpy as np

# Ensure project root is importable (so "Instances" resolves)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# from Yue_KKT_Decomp_New.Yue_KKT_Decomp_ModelReformulation_Multi import main
from Instances.shanghai_instance_effective import make_shanghai_instance_effective

# Define the parameters to vary and their multipliers
parameters_to_vary = {
    'weight_env': (1.0, [0.4, 0.6, 0.8, 1.2, 1.4, 1.6]),
    'weight_mon': (0.004, [0.4, 0.6, 0.8, 1.2, 1.4, 1.6]),
    'price_f': ([420.0, 520.0], [0.4, 0.6, 0.8, 1.2, 1.4, 1.6]),
    'c_preproc_w': ([150.0, 125.0], [0.4, 0.6, 0.8, 1.2, 1.4, 1.6]),
    'c_penalty': (100.0, [0.4, 0.6, 0.8, 1.2, 1.4, 1.6]),
    'beta_w': ([12.0 * 0.3, 16.0 * 0.6], [0.4, 0.6, 0.8, 1.2, 1.4, 1.6]),
}

def setup_logger(param_name: str, param_value: str) -> Path:
    """Setup logging to file and console for parameter study"""
    # Create parameter analysis folder if it doesn't exist
    log_dir = Path(__file__).parent / "parameter_analysis"
    log_dir.mkdir(exist_ok=True)
    
    # Create log filename with date, time, and parameter values
    now = datetime.now()
    log_filename = f"Yue_KKT_Decomp_{now.strftime('%Y%m%d_%H%M')}_{param_name}_{param_value}.log"
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
    for param_name, (original_value, multipliers) in parameters_to_vary.items():
        for multiplier in multipliers:
            # Create a modified instance with varied parameters
            if isinstance(original_value, list):
                modified_value = [v * multiplier for v in original_value]
            else:
                modified_value = original_value * multiplier
            
            # Log the current parameter configuration
            log_path = setup_logger(param_name, multiplier)
            logging.info(f"Running parameter study with {param_name} = {modified_value}")

            # Create the instance with modified parameters
            shanghai_data = make_shanghai_instance_effective()
            if param_name == 'weight_env':
                shanghai_data.weight_env = modified_value
            elif param_name == 'weight_mon':
                shanghai_data.weight_mon = modified_value
            elif param_name == 'price_f':
                shanghai_data.price_f = modified_value
            elif param_name == 'c_preproc_w':
                shanghai_data.c_preproc_w = modified_value
            elif param_name == 'c_penalty':
                shanghai_data.c_penalty = modified_value
            elif param_name == 'beta_w':
                shanghai_data.beta_w = modified_value
            
            # Run the main decomposition algorithm
            main(Verbose=True)

if __name__ == "__main__":
    run_parameter_study()