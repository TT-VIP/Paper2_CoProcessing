# Ensure project root is importable (so "Instances" resolves)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Create a new folder for parameter analysis
PARAM_ANALYSIS_DIR = Path(__file__).parent / "parameter_analysis"
PARAM_ANALYSIS_DIR.mkdir(exist_ok=True)

# Parameter variations
variations = [0.4, 0.6, 0.8, 1.2, 1.4, 1.6]

# Original parameters from the effective instance
original_instance = make_shanghai_instance_effective()

# Function to run the parameter study
def run_parameter_study():
    for weight_env_factor in variations:
        for weight_mon_factor in variations:
            for price_f_factor in variations:
                for c_preproc_w_factor in variations:
                    for c_penalty_factor in variations:
                        for beta_w_factor in variations:
                            # Create a modified instance with varied parameters
                            modified_instance = original_instance

                            # Update parameters
                            modified_instance.weight_env = original_instance.weight_env * weight_env_factor
                            modified_instance.weight_mon = original_instance.weight_mon * weight_mon_factor
                            modified_instance.price_f = [p * price_f_factor for p in original_instance.price_f]
                            modified_instance.c_preproc_w = [c * c_preproc_w_factor for c in original_instance.c_preproc_w]
                            modified_instance.c_penalty = original_instance.c_penalty * c_penalty_factor
                            modified_instance.beta_w = [b * beta_w_factor for b in original_instance.beta_w]

                            # Create a unique log filename
                            now = datetime.now()
                            log_filename = (
                                f"Yue_KKT_Decomp_{now.strftime('%Y%m%d_%H%M')}_"
                                f"weight_env_{weight_env_factor}_"
                                f"weight_mon_{weight_mon_factor}_"
                                f"price_f_{price_f_factor}_"
                                f"c_preproc_w_{c_preproc_w_factor}_"
                                f"c_penalty_{c_penalty_factor}_"
                                f"beta_w_{beta_w_factor}.log"
                            )
                            log_path = PARAM_ANALYSIS_DIR / log_filename

                            # Setup logging for this run
                            logging.basicConfig(
                                level=logging.INFO,
                                format='%(message)s',
                                handlers=[
                                    logging.FileHandler(log_path, encoding='utf-8'),
                                    logging.StreamHandler()  # Also print to console
                                ]
                            )

                            logging.info(f"Running parameter study with:")
                            logging.info(f"  weight_env: {modified_instance.weight_env}")
                            logging.info(f"  weight_mon: {modified_instance.weight_mon}")
                            logging.info(f"  price_f: {modified_instance.price_f}")
                            logging.info(f"  c_preproc_w: {modified_instance.c_preproc_w}")
                            logging.info(f"  c_penalty: {modified_instance.c_penalty}")
                            logging.info(f"  beta_w: {modified_instance.beta_w}")

                            # Run the main decomposition algorithm
                            main(Verbose=True)

if __name__ == "__main__":
    run_parameter_study()
```

### Explanation of the Code:
- **Parameter Variations**: The script defines a list of factors to multiply the original parameters.
- **Instance Modification**: For each combination of parameter variations, it creates a modified instance of `ShanghaiInstance` by multiplying the original parameters by the specified factors.
- **Logging**: It sets up logging to a unique file for each run, including the varied parameter values in the filename.
- **Decomposition Algorithm Execution**: The `main` function from the decomposition algorithm is called with the modified instance.

### Running the Script:
- Save the script in the same directory as your other scripts.
- Run the script, and it will generate logs for each configuration in the `parameter_analysis` folder.

### Note:
- Ensure that the `main` function in the `Yue_KKT_Decomp_ModelReformulation_Multi` module can accept the modified instance directly or adjust the function call accordingly.
- Depending on the number of parameters and variations, this could result in a large number of runs, so consider limiting the combinations if necessary.