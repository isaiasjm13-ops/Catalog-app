"""Perfilador de exportaciones Excel/CSV de Odoo, sin efectos secundarios."""

from .core import profile_file, write_reports

__all__ = ["profile_file", "write_reports"]
__version__ = "0.1.0"
