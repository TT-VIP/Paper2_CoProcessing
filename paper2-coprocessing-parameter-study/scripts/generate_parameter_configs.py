import sys
from pathlib import Path
import logging
from datetime import datetime
import numpy as np

# Ensure project root is importable (so "Instances" resolves)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Yue_Decomposition_Algorithm.Yue_KKT_Decomp_New.Yue_KKT_Decomp_ModelReformulation_Multi import main
from Instances.shanghai_instance_effective import make_shanghai_instance_effective

# Define the parameters to vary and their multipliers
params_to_vary = {
    'weight_env': [0.4, 0.6, 0.8, 1.2, 1.4, 1.6],
    'weight_mon': [0.4, 0.6, 0.8, 1.2, 1.4, 1.6],
    'price_f': [0.4, 0.6, 0.8, 1.2, 1.4, 1.6],
    'c_preproc_w': [0.4, 0.6, 0.8, 1.2, 1.4, 1.6],
    'c_penalty': [0.4, 0.6, 0.8, 1.2, 1.4, 1.6],
    'beta_w': [0.4, 0.6, 0.8, 1.2, 1.4, 1.6],
}

# Create a folder for parameter analysis logs
log_dir = Path(__file__).parent / "parameter_analysis"
log_dir.mkdir(exist_ok=True)

def setup_logger(param_name: str, param_value: float) -> Path:
    """Setup logging to file and console for parameter study."""
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
    # Original parameters from the effective instance
    original_instance = make_shanghai_instance_effective()
    
    # Iterate over each parameter and its values
    for param_name, multipliers in params_to_vary.items():
        for multiplier in multipliers:
            # Create a modified instance based on the parameter being varied
            modified_instance = original_instance
            
            if param_name == 'weight_env':
                modified_instance.weight_env *= multiplier
            elif param_name == 'weight_mon':
                modified_instance.weight_mon *= multiplier
            elif param_name == 'price_f':
                modified_instance.price_f = [price * multiplier for price in original_instance.price_f]
            elif param_name == 'c_preproc_w':
                modified_instance.c_preproc_w = [cost * multiplier for cost in original_instance.c_preproc_w]
            elif param_name == 'c_penalty':
                modified_instance.c_penalty *= multiplier
            elif param_name == 'beta_w':
                modified_instance.beta_w = [beta * multiplier for beta in original_instance.beta_w]

            # Setup logger for this specific run
            log_path = setup_logger(param_name, multiplier)
            logging.info(f"Running Yue-KKT Decomposition Algorithm with {param_name} = {multiplier}")
            
            # Run the main decomposition algorithm
            main(Verbose=True)

if __name__ == "__main__":
    run_parameter_study()