from __future__ import annotations

import logging
import re
import warnings
from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd
import pdfplumber

from src.providers.registry import register
from src.core.schema import STANDARD_COLUMNS


_PRICE_RE = re.compile(r"\$?\s*([0-9\.\,]+)")
_SKU_RE = re.compile(r"^\s*(\d{5,6})\s*$")  # IDC suele tener 5-6 dígitos
_SKU_INLINE_RE = re.compile(
    r"^(\d{6})\s+(.+)$"
)  # SKU al inicio de línea seguido de texto
_UNITS_RE = re.compile(r"(\+?\d+)\s*UNIDADES", re.IGNORECASE)


def _parse_price_to_float(text: str) -> Optional[float]:
    """
    Convierte '$1.398,88 + iva' -> 1398.88
    """
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    raw = m.group(1).strip()

    # Formato típico es 1.398,88 (punto miles, coma decimal)
    # también puede venir 138.22 (punto decimal) en otros listados.
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    # else: asume '.' decimal

    try:
        return float(raw)
    except ValueError:
        return None


def _parse_stock(text: str) -> Optional[int]:
    if not text:
        return None
    m = _UNITS_RE.search(text)
    if not m:
        return None
    try:
        return int(m.group(1).replace("+", ""))
    except ValueError:
        return None


def _cleanup_name(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r"\s+", " ", name)
    return name


def _extract_prices_from_line(text: str) -> List[str]:
    """Extrae todos los precios de una línea."""
    prices = []
    for match in re.finditer(r"\$\s*([0-9\.\,]+)\s*\+\s*iva", text, re.IGNORECASE):
        prices.append(f"${match.group(1)}")
    return prices


def _extract_rows_from_text(
    lines: List[str],
) -> List[Tuple[str, str, str, str, str, str, str]]:
    """
    Retorna filas como:
    (sku, name, x1, x3, x6, stock, eta)

    Formato del PDF:
    - Líneas de nombre (sin SKU, sin precios)
    - Línea con: SKU + resto del nombre + $precio1 + $precio2 + $precio3 + STOCK
    - Posibles líneas adicionales de descripción (sin SKU ni precios)
    """
    rows = []
    i = 0
    n = len(lines)

    # Buffer para acumular líneas de nombre antes de encontrar el SKU
    name_buffer = []
    in_continuation = False  # Flag para indicar si estamos en líneas de continuación

    while i < n:
        line = lines[i].strip()

        # saltar headers/footers comunes
        if (
            not line
            or "SKU IDC" in line
            or "NOMBRE DEL PRODUCTO" in line
            or "FORMAS DE PAGO" in line
            or line.startswith("Gratis")
            or line.startswith("💼")
            or line.startswith("•")
        ):
            i += 1
            name_buffer = []  # Reset buffer
            in_continuation = False
            continue

        # Buscar línea con SKU al inicio (6 dígitos) + precios
        sku_match = _SKU_INLINE_RE.match(line)

        if sku_match and "$" in line:  # SKU + precios en la misma línea
            sku = sku_match.group(1)
            rest_of_line = sku_match.group(2)

            # Extraer precios de esta línea
            prices = _extract_prices_from_line(line)

            # Extraer la parte antes del primer precio como resto del nombre
            name_parts = list(name_buffer)  # Líneas anteriores
            if "$" in rest_of_line:
                # Agregar solo la parte antes del primer precio
                before_price = rest_of_line.split("$")[0].strip()
                if before_price:
                    name_parts.append(before_price)
            else:
                name_parts.append(rest_of_line)

            # Unir nombre completo
            name = _cleanup_name(" ".join(name_parts))

            # Asignar precios (esperamos 3)
            x1 = prices[0] if len(prices) > 0 else ""
            x3 = prices[1] if len(prices) > 1 else ""
            x6 = prices[2] if len(prices) > 2 else ""

            # Extraer stock de la misma línea
            stock_text = line

            rows.append((sku, name, x1, x3, x6, stock_text, stock_text))

            # Reset buffer y activar modo continuación
            name_buffer = []
            in_continuation = True
            i += 1

        elif in_continuation:
            # Estamos en líneas de continuación después de un producto
            # Palabras clave que indican inicio de un nuevo producto
            product_keywords = [
                "Laptop",
                "Monitor",
                "Nas",
                "Pc",
                "Aio",
                "Celular",
                "Central",
                "Generador",
                "Impresora",
                "Scanner",
                "Tablet",
                "Desktop",
                "Server",
                "Router",
                "Switch",
                "Firewall",
                "Access",
                "Camera",
                "Webcam",
                "Teclado",
                "Mouse",
                "Audifonos",
                "Parlante",
                "Microfono",
                "Disco",
                "Ssd",
                "Ram",
                "Memoria",
                "Procesador",
                "Tarjeta",
                "Cable",
                "Adaptador",
                "Hub",
                "Dock",
                "Fuente",
                "UPS",
                "Bateria",
                "Pantalla",
                "Proyector",
                "Tv",
                "Smart",
            ]

            # Si la línea empieza con una palabra clave de producto, es un nuevo producto
            if any(line.startswith(keyword) for keyword in product_keywords):
                in_continuation = False
                name_buffer.append(line)
                i += 1
            # Si tiene precio suelto pero no SKU, ignorar
            elif "$" in line:
                i += 1
            # Línea de descripción técnica, ignorar
            else:
                i += 1

        else:
            # No es una línea con SKU+precios y no estamos en continuación
            # Si tiene precio pero no SKU, ignorar
            if "$" in line:
                i += 1
            else:
                # Línea sin precio ni SKU: probablemente es parte del nombre del siguiente
                name_buffer.append(line)
                i += 1

    return rows


@register("idc_pdf")
def ingest_idc_pdf(input_path: str, supplier_name: str) -> pd.DataFrame:
    """
    Lee un PDF estilo IDC y devuelve columnas estándar.
    """
    p = Path(input_path)
    all_lines: List[str] = []

    # Suprimir logs de pdfminer que genera warnings sobre FontBBox
    pdfminer_logger = logging.getLogger("pdfminer")
    original_level = pdfminer_logger.level
    pdfminer_logger.setLevel(logging.ERROR)

    try:
        # Suprimir warnings de FontBBox y otros errores comunes de PDF
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*FontBBox.*")
            warnings.filterwarnings("ignore", message=".*font descriptor.*")

            with pdfplumber.open(str(p)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    # split conservador
                    all_lines.extend(
                        [ln.strip() for ln in text.splitlines() if ln.strip()]
                    )
    finally:
        # Restaurar nivel de logging original
        pdfminer_logger.setLevel(original_level)

    raw_rows = _extract_rows_from_text(all_lines)

    out = []
    for sku, name, x1, x3, x6, stock_txt, eta_txt in raw_rows:
        out.append(
            {
                "supplier": supplier_name,
                "supplier_sku": sku,
                "title": name,
                "brand": None,
                "model": None,
                "ean_upc": None,
                "category": None,
                "condition": None,
                "cost_x1_usd": _parse_price_to_float(x1),
                "cost_x3_usd": _parse_price_to_float(x3),
                "cost_x6_usd": _parse_price_to_float(x6),
                "tax_included": "no",  # IDC muestra + iva
                "stock": _parse_stock(stock_txt),
                "eta_text": eta_txt.strip() if eta_txt else None,
                "source_file": p.name,
            }
        )

    df = pd.DataFrame(out)
    if df.empty:
        # para que no “reviente” el Excel aunque no detecte filas
        df = pd.DataFrame(columns=STANDARD_COLUMNS)

    # asegurar columnas en orden
    for c in STANDARD_COLUMNS:
        if c not in df.columns:
            df[c] = None
    return df[STANDARD_COLUMNS]
