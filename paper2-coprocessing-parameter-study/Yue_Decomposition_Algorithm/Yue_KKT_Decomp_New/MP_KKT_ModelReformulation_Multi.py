import sys
from pathlib import Path
import logging
from datetime import datetime
# from Yue_KKT_Decomp_New.Yue_KKT_Decomp_ModelReformulation_Multi import main
from Instances.shanghai_instance_effective import make_shanghai_instance_effective

# Ensure project root is importable (so "Instances" resolves)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Create a new directory for parameter analysis
param_analysis_dir = Path(__file__).parent / "parameter_analysis"
param_analysis_dir.mkdir(exist_ok=True)

# Define the parameter variations
multipliers = [0.4, 0.6, 0.8, 1.2, 1.4, 1.6]

# Original parameters from the instance
original_instance = make_shanghai_instance_effective()

# Parameters to vary
params_to_vary = {
    'weight_env': original_instance.weight_env,
    'weight_mon': original_instance.weight_mon,
    'price_f': original_instance.price_f,
    'c_preproc_w': original_instance.c_preproc_w,
    'c_penalty': original_instance.c_penalty,
    'beta_w': original_instance.beta_w,
}

# Run the parameter study
for param_name, original_value in params_to_vary.items():
    for multiplier in multipliers:
        # Create a modified instance with varied parameters
        modified_instance = make_shanghai_instance_effective()
        
        # Update the parameter based on the multiplier
        if param_name in ['price_f', 'c_preproc_w', 'beta_w']:
            # For lists, multiply each element
            setattr(modified_instance, param_name, [v * multiplier for v in original_value])
        else:
            # For single float values
            setattr(modified_instance, param_name, original_value * multiplier)

        # Setup logging for this specific run
        now = datetime.now()
        log_filename = f"Yue_KKT_Decomp_{now.strftime('%Y%m%d_%H%M')}_{param_name}_{multiplier:.1f}.log"
        log_path = param_analysis_dir / log_filename
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(message)s',
            handlers=[
                logging.FileHandler(log_path, encoding='utf-8'),
                logging.StreamHandler()  # Also print to console
            ]
        )
        
        logging.info(f"Running parameter study with {param_name} = {original_value * multiplier:.2f}")

        # Run the main decomposition algorithm
        main(Verbose=True)

if __name__ == "__main__":
    logging.info("Parameter study completed.")