import sys
from pathlib import Path
import logging
from datetime import datetime
from Yue_KKT_Decomp_New.Yue_KKT_Decomp_ModelReformulation_Multi import main
from Instances.shanghai_instance_effective import make_shanghai_instance_effective

# Ensure project root is importable (so "Instances" resolves)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Define the parameters to vary and their multipliers
parameters_to_vary = {
    'weight_env': [0.4, 0.6, 0.8, 1.2, 1.4, 1.6],
    'weight_mon': [0.4, 0.6, 0.8, 1.2, 1.4, 1.6],
    'price_f': [0.4, 0.6, 0.8, 1.2, 1.4, 1.6],
    'c_preproc_w': [0.4, 0.6, 0.8, 1.2, 1.4, 1.6],
    'c_penalty': [0.4, 0.6, 0.8, 1.2, 1.4, 1.6],
    'beta_w': [0.4, 0.6, 0.8, 1.2, 1.4, 1.6],
}

# Create a folder for parameter analysis
param_analysis_dir = Path(__file__).parent / "parameter_analysis"
param_analysis_dir.mkdir(exist_ok=True)

def run_parameter_study():
    # Original instance data
    original_instance = make_shanghai_instance_effective()

    # Iterate over each parameter and its multipliers
    for param_name, multipliers in parameters_to_vary.items():
        for multiplier in multipliers:
            # Create a modified instance based on the parameter being varied
            modified_instance = create_modified_instance(original_instance, param_name, multiplier)

            # Setup logging for this specific run
            log_filename = f"Yue_KKT_Decomp_{datetime.now().strftime('%Y%m%d_%H%M')}_{param_name}_{multiplier:.1f}.log"
            log_path = param_analysis_dir / log_filename
            logging.basicConfig(
                level=logging.INFO,
                format='%(message)s',
                handlers=[
                    logging.FileHandler(log_path, encoding='utf-8'),
                    logging.StreamHandler()  # Also print to console
                ]
            )
            logging.info(f"Running parameter study with {param_name} = {original_instance.__dict__[param_name] * multiplier:.2f}")

            # Run the main decomposition algorithm
            main(Verbose=True, instance_data=modified_instance)

def create_modified_instance(original_instance, param_name, multiplier):
    # Create a copy of the original instance
    modified_instance = original_instance

    # Modify the specified parameter
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

    return modified_instance

if __name__ == "__main__":
    run_parameter_study()