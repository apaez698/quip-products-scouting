"""Tests para el parser de PDFs de IDC."""

from __future__ import annotations

from pathlib import Path
from typing import List
from unittest.mock import Mock, patch, MagicMock

import pandas as pd
import pytest

from src.providers.idc_pdf import (
    _parse_price_to_float,
    _parse_stock,
    _cleanup_name,
    _extract_rows_from_text,
    ingest_idc_pdf,
)
from src.core.schema import STANDARD_COLUMNS


class TestParsePriceToFloat:
    """Tests para la función de parseado de precios."""

    def test_parse_price_formato_miles_punto_decimal_coma(self) -> None:
        """Parsea formato 1.398,88 (punto miles, coma decimal)."""
        result = _parse_price_to_float("$1.398,88 + iva")
        assert result == 1398.88

    def test_parse_price_formato_decimal_punto(self) -> None:
        """Parsea formato 138.22 (punto decimal)."""
        result = _parse_price_to_float("$138.22")
        assert result == 138.22

    def test_parse_price_solo_coma_decimal(self) -> None:
        """Parsea formato 1398,88 (solo coma decimal)."""
        result = _parse_price_to_float("1398,88")
        assert result == 1398.88

    def test_parse_price_sin_simbolo_dolar(self) -> None:
        """Parsea precio sin símbolo de dólar."""
        result = _parse_price_to_float("1.234,56")
        assert result == 1234.56

    def test_parse_price_con_espacios(self) -> None:
        """Parsea precio con espacios."""
        result = _parse_price_to_float("$ 1.234,56")
        assert result == 1234.56

    def test_parse_price_texto_vacio(self) -> None:
        """Retorna None para texto vacío."""
        result = _parse_price_to_float("")
        assert result is None

    def test_parse_price_sin_numeros(self) -> None:
        """Retorna None para texto sin números."""
        result = _parse_price_to_float("sin precio")
        assert result is None

    def test_parse_price_formato_invalido(self) -> None:
        """Retorna None para formato inválido."""
        result = _parse_price_to_float("abc.def,ghi")
        assert result is None


class TestParseStock:
    """Tests para la función de parseado de stock."""

    def test_parse_stock_unidades_simple(self) -> None:
        """Parsea '10 UNIDADES'."""
        result = _parse_stock("10 UNIDADES")
        assert result == 10

    def test_parse_stock_con_mas(self) -> None:
        """Parsea '+50 UNIDADES'."""
        result = _parse_stock("+50 UNIDADES")
        assert result == 50

    def test_parse_stock_case_insensitive(self) -> None:
        """Parsea independientemente de mayúsculas/minúsculas."""
        result = _parse_stock("25 unidades")
        assert result == 25

    def test_parse_stock_con_texto_adicional(self) -> None:
        """Parsea con texto adicional."""
        result = _parse_stock("Stock: 100 UNIDADES disponibles")
        assert result == 100

    def test_parse_stock_texto_vacio(self) -> None:
        """Retorna None para texto vacío."""
        result = _parse_stock("")
        assert result is None

    def test_parse_stock_sin_patron(self) -> None:
        """Retorna None si no encuentra el patrón."""
        result = _parse_stock("sin stock")
        assert result is None


class TestCleanupName:
    """Tests para la función de limpieza de nombres."""

    def test_cleanup_name_espacios_multiples(self) -> None:
        """Reemplaza espacios múltiples por uno solo."""
        result = _cleanup_name("Notebook    HP     ProBook")
        assert result == "Notebook HP ProBook"

    def test_cleanup_name_espacios_inicio_fin(self) -> None:
        """Elimina espacios al inicio y final."""
        result = _cleanup_name("  Notebook HP  ")
        assert result == "Notebook HP"

    def test_cleanup_name_saltos_de_linea(self) -> None:
        """Reemplaza saltos de línea por espacios."""
        result = _cleanup_name("Notebook\nHP\nProBook")
        assert result == "Notebook HP ProBook"

    def test_cleanup_name_texto_vacio(self) -> None:
        """Maneja texto vacío."""
        result = _cleanup_name("")
        assert result == ""

    def test_cleanup_name_none(self) -> None:
        """Maneja None."""
        result = _cleanup_name(None)  # type: ignore
        assert result == ""


class TestExtractRowsFromText:
    """Tests para la función de extracción de filas del texto."""

    def test_extract_simple_row(self) -> None:
        """Extrae una fila simple con todos los campos."""
        lines = [
            "Notebook HP ProBook 450 G8",
            "Core i5 8GB RAM",
            "123456 Descripción Adicional $1.200,00 + iva $1.150,00 + iva $1.100,00 + iva 50 UNIDADES",
        ]

        rows = _extract_rows_from_text(lines)

        assert len(rows) == 1
        sku, name, x1, x3, x6, stock_txt, eta_txt = rows[0]
        assert sku == "123456"
        assert "Notebook HP ProBook" in name
        assert "Core i5 8GB RAM" in name
        assert "$1.200,00" in x1 or "1.200,00" in x1
        assert "$1.150,00" in x3 or "1.150,00" in x3
        assert "$1.100,00" in x6 or "1.100,00" in x6
        assert "50 UNIDADES" in stock_txt

    def test_extract_multiple_rows(self) -> None:
        """Extrae múltiples filas."""
        lines = [
            "Laptop Producto A",
            "123456 Extra $100,00 + iva $95,00 + iva $90,00 + iva 10 UNIDADES",
            "Descripción técnica del producto A",
            "Monitor Producto B",
            "678901 Extra $200,00 + iva $190,00 + iva $180,00 + iva 20 UNIDADES",
        ]

        rows = _extract_rows_from_text(lines)

        assert len(rows) == 2
        assert rows[0][0] == "123456"
        assert rows[1][0] == "678901"

    def test_extract_skips_headers(self) -> None:
        """Omite líneas de encabezado."""
        lines = [
            "SKU IDC",
            "NOMBRE DEL PRODUCTO",
            "Laptop Producto A",
            "123456 Extra $100,00 + iva $95,00 + iva $90,00 + iva 10 UNIDADES",
        ]

        rows = _extract_rows_from_text(lines)

        assert len(rows) == 1
        assert rows[0][0] == "123456"

    def test_extract_skips_empty_lines(self) -> None:
        """Omite líneas vacías."""
        lines = [
            "",
            "Laptop Producto A",
            "",
            "123456 Extra $100,00 + iva $95,00 + iva $90,00 + iva 10 UNIDADES",
            "",
        ]

        rows = _extract_rows_from_text(lines)

        assert len(rows) == 1
        assert rows[0][0] == "123456"

    def test_extract_multiline_name(self) -> None:
        """Maneja nombres de productos en múltiples líneas."""
        lines = [
            "Laptop Notebook HP",
            "ProBook 450 G8",
            "Core i5 8GB",
            "123456 Extra $1.200,00 + iva $1.150,00 + iva $1.100,00 + iva 50 UNIDADES",
        ]

        rows = _extract_rows_from_text(lines)

        assert len(rows) == 1
        name = rows[0][1]
        assert "Notebook HP" in name or "Laptop Notebook HP" in name
        assert "ProBook 450 G8" in name
        assert "Core i5 8GB" in name

    def test_extract_sku_5_digitos(self) -> None:
        """El parser ahora solo acepta SKU de 6 dígitos (formato real IDC)."""
        lines = [
            "Laptop Producto Test",
            "098765 Extra $100,00 + iva $95,00 + iva $90,00 + iva 10 UNIDADES",
        ]

        rows = _extract_rows_from_text(lines)

        assert len(rows) == 1
        assert rows[0][0] == "098765"  # SKU de 6 dígitos con cero a la izquierda

    def test_extract_sku_6_digitos(self) -> None:
        """Reconoce SKU de 6 dígitos."""
        lines = [
            "Laptop Producto Test",
            "123456 Extra $100,00 + iva $95,00 + iva $90,00 + iva 10 UNIDADES",
        ]

        rows = _extract_rows_from_text(lines)

        assert len(rows) == 1
        assert rows[0][0] == "123456"

    def test_extract_ignores_invalid_sku(self) -> None:
        """Ignora SKUs inválidos (no son de 6 dígitos)."""
        lines = [
            "Laptop Producto A",
            "12345 Extra $100,00 + iva $95,00 + iva $90,00 + iva 10 UNIDADES",  # 5 dígitos, ignorar
            "Monitor Producto B",
            "123456 Extra $100,00 + iva $95,00 + iva $90,00 + iva 10 UNIDADES",  # 6 dígitos, válido
        ]

        rows = _extract_rows_from_text(lines)

        assert len(rows) == 1
        assert rows[0][0] == "123456"

    def test_extract_skips_footer_text(self) -> None:
        """Omite texto de pie de página."""
        lines = [
            "Laptop Producto A",
            "123456 Extra $100,00 + iva $95,00 + iva $90,00 + iva 10 UNIDADES",
            "FORMAS DE PAGO: Efectivo, Tarjeta",
        ]

        rows = _extract_rows_from_text(lines)

        assert len(rows) == 1


class TestIngestIdcPdf:
    """Tests de integración para la función principal."""

    @patch("src.providers.idc_pdf.pdfplumber")
    def test_ingest_pdf_completo(self, mock_pdfplumber: Mock) -> None:
        """Procesa un PDF completo con múltiples productos."""
        # Mock del PDF
        mock_page = MagicMock()
        mock_page.extract_text.return_value = """SKU IDC
NOMBRE DEL PRODUCTO
Laptop Notebook HP ProBook 450 G8
Core i5 8GB RAM 256GB SSD
123456 Extra Specs $1.200,00 + iva $1.150,00 + iva $1.100,00 + iva 50 UNIDADES En stock
Tecnical details line
Monitor Mouse Logitech MX Master 3
678901 Wireless $150,50 + iva $145,00 + iva $140,00 + iva +100 UNIDADES
"""

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        # Ejecutar
        result = ingest_idc_pdf("test.pdf", "IDC")

        # Verificar
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert list(result.columns) == STANDARD_COLUMNS

        # Verificar primer producto
        row1 = result.iloc[0]
        assert row1["supplier"] == "IDC"
        assert row1["supplier_sku"] == "123456"
        assert "Notebook HP" in row1["title"] or "Laptop Notebook HP" in row1["title"]
        assert row1["cost_x1_usd"] == 1200.00
        assert row1["cost_x3_usd"] == 1150.00
        assert row1["cost_x6_usd"] == 1100.00
        assert row1["stock"] == 50
        assert row1["tax_included"] == "no"
        assert row1["source_file"] == "test.pdf"

        # Verificar segundo producto
        row2 = result.iloc[1]
        assert row2["supplier_sku"] == "678901"
        assert "Mouse Logitech" in row2["title"]
        assert row2["stock"] == 100

    @patch("src.providers.idc_pdf.pdfplumber")
    def test_ingest_pdf_vacio(self, mock_pdfplumber: Mock) -> None:
        """Retorna DataFrame vacío con columnas correctas si no hay datos."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Sin datos válidos"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        result = ingest_idc_pdf("empty.pdf", "IDC")

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        assert list(result.columns) == STANDARD_COLUMNS

    @patch("src.providers.idc_pdf.pdfplumber")
    def test_ingest_pdf_multiples_paginas(self, mock_pdfplumber: Mock) -> None:
        """Procesa PDFs con múltiples páginas."""
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = """Laptop Producto Página 1
123456 Extra $100,00 + iva $95,00 + iva $90,00 + iva 10 UNIDADES
"""

        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = """Monitor Producto Página 2
678901 Extra $200,00 + iva $190,00 + iva $180,00 + iva 20 UNIDADES
"""

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page1, mock_page2]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        result = ingest_idc_pdf("multi.pdf", "IDC")

        assert len(result) == 2
        assert result.iloc[0]["supplier_sku"] == "123456"
        assert result.iloc[1]["supplier_sku"] == "678901"

    @patch("src.providers.idc_pdf.pdfplumber")
    def test_ingest_pdf_campos_opcionales_none(self, mock_pdfplumber: Mock) -> None:
        """Los campos opcionales quedan como None."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = """Laptop Producto Test
123456 Extra $100,00 + iva $95,00 + iva $90,00 + iva 10 UNIDADES
"""

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        result = ingest_idc_pdf("test.pdf", "IDC")

        row = result.iloc[0]
        assert pd.isna(row["brand"]) or row["brand"] is None
        assert pd.isna(row["model"]) or row["model"] is None
        assert pd.isna(row["ean_upc"]) or row["ean_upc"] is None
        assert pd.isna(row["category"]) or row["category"] is None
        assert pd.isna(row["condition"]) or row["condition"] is None

    @patch("src.providers.idc_pdf.pdfplumber")
    def test_ingest_pdf_precios_invalidos(self, mock_pdfplumber: Mock) -> None:
        """Maneja precios inválidos como None."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = """Laptop Producto Sin Precio
123456 texto sin precio
"""

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        result = ingest_idc_pdf("test.pdf", "IDC")

        # Si no hay precios válidos, puede no extraer ningún producto
        # o extraerlo con precios None
        if len(result) > 0:
            row = result.iloc[0]
            assert pd.isna(row["cost_x1_usd"]) or row["cost_x1_usd"] is None

    @patch("src.providers.idc_pdf.pdfplumber")
    def test_ingest_pdf_nombre_archivo_correcto(self, mock_pdfplumber: Mock) -> None:
        """Guarda el nombre del archivo fuente correctamente."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = """Laptop Producto Test
123456 Extra $100,00 + iva $95,00 + iva $90,00 + iva 10 UNIDADES
"""

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        result = ingest_idc_pdf("/ruta/completa/archivo.pdf", "IDC")

        assert result.iloc[0]["source_file"] == "archivo.pdf"

    @patch("src.providers.idc_pdf.pdfplumber")
    def test_ingest_pdf_stock_sin_unidades(self, mock_pdfplumber: Mock) -> None:
        """Maneja casos donde no se encuentra el patrón de stock."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = """Laptop Producto Test
123456 Extra $100,00 + iva $95,00 + iva $90,00 + iva Consultar disponibilidad
"""

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        result = ingest_idc_pdf("test.pdf", "IDC")

        if len(result) > 0:
            row = result.iloc[0]
            assert pd.isna(row["stock"]) or row["stock"] is None
            assert "Consultar disponibilidad" in row["eta_text"]


class TestIntegrationWithRegistry:
    """Tests de integración con el registro de proveedores."""

    def test_idc_pdf_registered(self) -> None:
        """Verifica que ingest_idc_pdf está registrado."""
        from src.providers.registry import get_provider

        provider = get_provider("idc_pdf")
        assert provider is not None
        assert callable(provider)

    @patch("src.providers.idc_pdf.pdfplumber")
    def test_idc_pdf_through_registry(self, mock_pdfplumber: Mock) -> None:
        """Puede invocar la función a través del registro."""
        from src.providers.registry import get_provider

        mock_page = MagicMock()
        mock_page.extract_text.return_value = """Laptop Producto Test
123456 Extra $100,00 + iva $95,00 + iva $90,00 + iva 10 UNIDADES
"""

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdfplumber.open.return_value.__enter__.return_value = mock_pdf

        provider = get_provider("idc_pdf")
        result = provider("test.pdf", "IDC")

        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
