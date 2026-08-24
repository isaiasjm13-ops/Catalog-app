from __future__ import annotations

import argparse
from pathlib import Path

from perfect_catalog.web import ExcelCatalogRepository, serve


parser = argparse.ArgumentParser(description="Inicia el catálogo local de solo lectura")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8080)
parser.add_argument(
	"--source",
	type=Path,
	default=Path("data/imports/NATSUKI_EMPAQUES_MAESTRO.xlsx"),
)
args = parser.parse_args()

repository = ExcelCatalogRepository(str(args.source))
serve(repository, args.host, args.port)
