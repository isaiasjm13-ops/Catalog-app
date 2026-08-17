from __future__ import annotations

import argparse
from pathlib import Path

from .core import profile_file, write_reports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="odoo-profiler",
        description=(
            "Analiza exportaciones XLSX/CSV de Odoo sin modificar el archivo "
            "ni importar datos a una base de datos."
        ),
    )
    parser.add_argument("source", type=Path, help="Archivo .xlsx o .csv de Odoo")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/exports/profiles"),
        help="Carpeta de reportes (predeterminado: data/exports/profiles)",
    )
    parser.add_argument(
        "--format",
        choices=("both", "json", "markdown"),
        default="both",
        help="Formato de salida (predeterminado: both)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        profile = profile_file(args.source)
        outputs = write_reports(profile, args.output_dir, args.format)
    except (FileNotFoundError, PermissionError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2

    print("Perfil completado. El archivo fuente no fue modificado.")
    print(f"SHA-256: {profile['source']['sha256']}")
    for output in outputs:
        print(output.resolve())
    return 0
