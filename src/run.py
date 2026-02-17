import argparse
from pathlib import Path

from src.core.exporter import export_excel
from src.providers.registry import get_provider

import src.providers.idc_pdf  # registra provider


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True)  # idc_pdf
    ap.add_argument("--input", required=True)  # pdf
    ap.add_argument("--supplier", default="IDC")  # nombre proveedor
    ap.add_argument("--out", default="out/idc.xlsx")  # salida
    args = ap.parse_args()

    fn = get_provider(args.provider)
    df = fn(args.input, args.supplier)

    out_path = Path(args.out)
    export_excel(df, out_path)
    print(f"Exportado {out_path} | filas={len(df)}")


if __name__ == "__main__":
    main()
