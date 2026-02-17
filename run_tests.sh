#!/bin/bash
# Script para ejecutar tests del proyecto

# Activar el entorno virtual
source .venv/bin/activate

# Ejecutar pytest con los argumentos pasados
# Si no se pasan argumentos, ejecuta todos los tests
pytest "$@"
