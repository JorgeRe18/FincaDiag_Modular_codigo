from pathlib import Path


# config.py vive en:
# <project_root>/src/fincadiag/config.py
# Por eso el directorio raiz del proyecto es parents[2].
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DATA_FIELD_VALIDATION_DIR = PROJECT_ROOT / "data" / "field_validation"
REPORTS_DIR = PROJECT_ROOT / "reports"

DEFAULT_TARGET_IP = "172.24.29.181"
DEFAULT_TARGET_PORT = 6001
DEFAULT_SIGNATURE = "56 D1 00"
DEFAULT_WINDOW_MS = 250
