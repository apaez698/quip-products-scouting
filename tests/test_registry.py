import pytest
import pandas as pd
from src.providers.registry import register, get_provider, REGISTRY


# Simulamos proveedores reales que usarías en tu aplicación
@register("idc")
def get_idc_data(ticker: str, period: str) -> pd.DataFrame:
    """Simula obtener datos del proveedor IDC."""
    return pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02"],
            "price": [100.0, 101.5],
            "volume": [1000, 1200],
            "provider": ["idc", "idc"],
        }
    )


@register("tecnomega")
def get_tecnomega_data(ticker: str, period: str) -> pd.DataFrame:
    """Simula obtener datos del proveedor Tecnomega."""
    return pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02"],
            "price": [99.8, 101.2],
            "volume": [950, 1100],
            "provider": ["tecnomega", "tecnomega"],
        }
    )


class TestProviderRegistry:
    """Tests para entender cómo funciona el registry pattern."""

    def test_decorator_registra_funciones(self):
        """El decorador @register debe agregar las funciones al REGISTRY."""
        # Verificar que ambos proveedores están registrados
        assert "idc" in REGISTRY
        assert "tecnomega" in REGISTRY

    def test_get_provider_retorna_funcion_correcta(self):
        """get_provider debe retornar la función registrada."""
        # Obtener la función del proveedor
        idc_provider = get_provider("idc")

        # Verificar que es callable (se puede llamar)
        assert callable(idc_provider)

        # Verificar que es la función correcta
        assert idc_provider.__name__ == "get_idc_data"

    def test_llamar_proveedor_directamente(self):
        """Demostrar cómo usar un proveedor después de obtenerlo."""
        # Opción 1: Usar la función directamente (ya está registrada)
        resultado = get_idc_data("AAPL", "1mo")

        assert isinstance(resultado, pd.DataFrame)
        assert len(resultado) == 2
        assert "price" in resultado.columns
        assert resultado["provider"].iloc[0] == "idc"

    def test_llamar_proveedor_desde_registry(self):
        """Demostrar cómo usar un proveedor dinámicamente desde el registry."""
        # Opción 2: Obtener desde registry y usar (más dinámico)
        proveedor = get_provider("tecnomega")
        resultado = proveedor("MSFT", "1y")

        assert isinstance(resultado, pd.DataFrame)
        assert len(resultado) == 2
        assert resultado["provider"].iloc[0] == "tecnomega"

    def test_uso_dinamico_con_nombre_variable(self):
        """Caso de uso real: elegir proveedor dinámicamente."""
        # Esto es útil cuando el usuario selecciona el proveedor
        nombre_proveedor = "idc"  # Podría venir de input del usuario

        # Obtener y usar el proveedor dinámicamente
        proveedor = get_provider(nombre_proveedor)
        datos = proveedor("TSLA", "6mo")

        assert isinstance(datos, pd.DataFrame)
        assert datos["provider"].iloc[0] == nombre_proveedor

    def test_cambiar_entre_proveedores(self):
        """Demostrar cómo cambiar fácilmente entre proveedores."""
        ticker = "GOOGL"
        period = "1mo"

        # Obtener datos de ambos proveedores
        datos_idc = get_provider("idc")(ticker, period)
        datos_tecnomega = get_provider("tecnomega")(ticker, period)

        # Verificar que ambos retornan DataFrames válidos
        assert isinstance(datos_idc, pd.DataFrame)
        assert isinstance(datos_tecnomega, pd.DataFrame)

        # Pero con diferentes proveedores
        assert datos_idc["provider"].iloc[0] == "idc"
        assert datos_tecnomega["provider"].iloc[0] == "tecnomega"

    def test_listar_proveedores_disponibles(self):
        """Ver todos los proveedores registrados."""
        proveedores_disponibles = list(REGISTRY.keys())

        assert "idc" in proveedores_disponibles
        assert "tecnomega" in proveedores_disponibles
        assert len(proveedores_disponibles) >= 2

    def test_proveedor_no_existente_lanza_error(self):
        """Intentar obtener un proveedor no registrado debe lanzar ValueError."""
        with pytest.raises(ValueError) as excinfo:
            get_provider("proveedor_inexistente")

        # Verificar que el mensaje de error es útil
        assert "Proveedor no registrado: proveedor_inexistente" in str(excinfo.value)
        assert "Disponibles:" in str(excinfo.value)

    def test_multiples_proveedores_mismo_tipo(self):
        """Demostrar que puedes registrar múltiples proveedores."""

        # Registrar un tercer proveedor temporalmente
        @register("yahoo")
        def get_yahoo_data(ticker: str, period: str) -> pd.DataFrame:
            return pd.DataFrame({"price": [100], "provider": ["yahoo"]})

        # Ahora hay al menos 3 proveedores
        assert len(REGISTRY) >= 3
        assert "yahoo" in REGISTRY


class TestUsoCasoReal:
    """Ejemplo de cómo usarías esto en tu aplicación real."""

    def test_flujo_completo_obtencion_datos(self):
        """Simula el flujo completo de obtener datos de un proveedor."""
        # 1. Usuario/config selecciona el proveedor
        proveedor_seleccionado = "tecnomega"

        # 2. Usuario ingresa ticker y período
        ticker = "AAPL"
        period = "1y"

        # 3. Obtener la función del proveedor
        obtener_datos = get_provider(proveedor_seleccionado)

        # 4. Llamar la función con los parámetros
        datos = obtener_datos(ticker, period)

        # 5. Procesar los datos
        assert isinstance(datos, pd.DataFrame)
        assert not datos.empty
        assert "price" in datos.columns

    def test_fallback_entre_proveedores(self):
        """Intentar múltiples proveedores si uno falla."""
        ticker = "AAPL"
        period = "1mo"
        proveedores_a_intentar = ["proveedor_inexistente", "idc", "tecnomega"]

        datos = None
        for nombre_proveedor in proveedores_a_intentar:
            try:
                proveedor = get_provider(nombre_proveedor)
                datos = proveedor(ticker, period)
                break  # Si funciona, salir del loop
            except ValueError:
                continue  # Intentar el siguiente proveedor

        # Debe haber obtenido datos de "idc" (el primero disponible)
        assert datos is not None
        assert isinstance(datos, pd.DataFrame)
        assert datos["provider"].iloc[0] == "idc"
