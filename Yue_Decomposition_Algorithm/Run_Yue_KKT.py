import sys
from pathlib import Path
import logging
from datetime import datetime

# Ensure project root is importable (so "Instances" resolves)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# from Yue_KKT_Decomp_New.Yue_KKT_Decomp_ModelReformulation_Multi import main
from Yue_KKT_Decomp_New.Yue_KKT_Decomp_ModelReformulation import main


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

if __name__ == "__main__":
    log_path = setup_logger()
    logging.info(f"Yue-KKT Decomposition Algorithm started. Logs will be saved to {log_path}")
    main(Verbose=True)