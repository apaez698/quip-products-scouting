from typing import Callable, Dict
import pandas as pd

ProviderFunction = Callable[[str, str], pd.DataFrame]
REGISTRY: Dict[str, ProviderFunction] = {}


def register(name: str) -> Callable[[ProviderFunction], ProviderFunction]:
    def decorator(func: ProviderFunction) -> ProviderFunction:
        REGISTRY[name] = func
        return func

    return decorator


def get_provider(name: str) -> ProviderFunction:
    if name not in REGISTRY:
        raise ValueError(
            f"Proveedor no registrado: {name}. " f"Disponibles: {list(REGISTRY.keys())}"
        )
    return REGISTRY[name]
