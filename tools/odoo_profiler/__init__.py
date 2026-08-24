"""Perfilador de exportaciones Excel/CSV de Odoo, sin efectos secundarios."""

from .core import SheetData, profile_file, read_tabular_source, sha256_file, write_reports

__all__ = [
    "SheetData",
    "profile_file",
    "read_tabular_source",
    "sha256_file",
    "write_reports",
]
__version__ = "0.1.0"
