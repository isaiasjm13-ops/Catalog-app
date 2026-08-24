from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from .config import DatabaseConfig, prompt_password
from .importer import DEFAULT_MAX_PILOT_ROWS, assert_apply_allowed, inspect_plan, run_dry_run


def _database_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--database", default=None)
    parser.add_argument("--user", default=None)
    parser.add_argument(
        "--prompt-password",
        action="store_true",
        help="Solicita la contraseña mediante getpass; nunca la muestra ni la conserva.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="perfect-catalog")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import-odoo", help="Genera un dry-run persistente sin aplicar productos.")
    import_parser.add_argument("source", type=Path)
    import_parser.add_argument("--output-dir", type=Path, default=Path("data/exports/imports"))
    import_parser.add_argument(
        "--max-rows",
        type=int,
        default=DEFAULT_MAX_PILOT_ROWS,
        help="Límite de seguridad del piloto; amplíelo solo después de validar una muestra.",
    )
    _database_arguments(import_parser)

    inspect_parser = subparsers.add_parser("inspect-plan", help="Inspecciona un plan persistido.")
    inspect_parser.add_argument("plan_id", type=uuid.UUID)
    _database_arguments(inspect_parser)

    apply_parser = subparsers.add_parser("apply-plan", help="Valida la compuerta de aprobación; no aplica en este bloque.")
    apply_parser.add_argument("plan_id", type=uuid.UUID)
    _database_arguments(apply_parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = DatabaseConfig.from_args(args)
        password = prompt_password(args.prompt_password)
        if args.command == "import-odoo":
            result = run_dry_run(args.source, config, password, args.output_dir, args.max_rows)
        elif args.command == "inspect-plan":
            result = inspect_plan(args.plan_id, config, password)
        else:
            assert_apply_allowed(args.plan_id, config, password)
            return 0
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (ValueError, RuntimeError, PermissionError, NotImplementedError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
