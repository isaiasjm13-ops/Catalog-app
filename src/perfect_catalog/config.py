from __future__ import annotations

import getpass
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "perfect_catalog_dev"
    user: str = "perfect_catalog_app"

    @classmethod
    def from_args(cls, args: object) -> "DatabaseConfig":
        return cls(
            host=getattr(args, "host", None) or os.getenv("PGHOST", "localhost"),
            port=int(getattr(args, "port", None) or os.getenv("PGPORT", "5432")),
            database=getattr(args, "database", None) or os.getenv("PGDATABASE", "perfect_catalog_dev"),
            user=getattr(args, "user", None) or os.getenv("PGUSER", "perfect_catalog_app"),
        )

    def connection_kwargs(self, password: str) -> dict[str, object]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "password": password,
            "connect_timeout": 10,
        }


def prompt_password(enabled: bool) -> str:
    if not enabled:
        raise ValueError("Se requiere --prompt-password; no se aceptan contraseñas en argumentos ni archivos.")
    return getpass.getpass("Contraseña de PostgreSQL (entrada oculta): ")
