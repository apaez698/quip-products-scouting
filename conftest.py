"""
Configuración global de pytest.

Este archivo se ejecuta automáticamente antes de los tests
y permite configurar fixtures globales y otros ajustes.
"""
import sys
from pathlib import Path

# Agregar el directorio raíz al path si no está ya
root_dir = Path(__file__).parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
