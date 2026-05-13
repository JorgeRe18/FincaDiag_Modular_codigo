import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
# Permite ejecutar el proyecto desde la raiz sin instalar el paquete en modo editable.
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fincadiag.cli import main


if __name__ == "__main__":
    # Todo el flujo del motor arranca desde el CLI central.
    main()
