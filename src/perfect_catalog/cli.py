from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from .config import DatabaseConfig, prompt_password
from .application import apply_approved_plan, approve_plan
from .importer import DEFAULT_MAX_PILOT_ROWS, inspect_plan, run_dry_run
from .publication import (
    archive_release,
    build_release,
    inspect_release,
    publish_release,
)
from .reviews import inspect_review_queue, review_product


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


def _human_evidence_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", required=True)


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

    approve_parser = subparsers.add_parser("approve-plan", help="Aprueba un fingerprint exacto sin aplicar datos.")
    approve_parser.add_argument("plan_id", type=uuid.UUID)
    approve_parser.add_argument("--fingerprint", required=True)
    _human_evidence_arguments(approve_parser)
    _database_arguments(approve_parser)

    apply_parser = subparsers.add_parser("apply-plan", help="Aplica una vez un plan aprobado y verificable.")
    apply_parser.add_argument("plan_id", type=uuid.UUID)
    apply_parser.add_argument("--fingerprint", required=True)
    _human_evidence_arguments(apply_parser)
    _database_arguments(apply_parser)

    inspect_reviews_parser = subparsers.add_parser(
        "inspect-reviews",
        help="Lista las identidades creadas por un plan y su evidencia exacta.",
    )
    inspect_reviews_parser.add_argument("plan_id", type=uuid.UUID)
    inspect_reviews_parser.add_argument("--fingerprint", required=True)
    _database_arguments(inspect_reviews_parser)

    review_product_parser = subparsers.add_parser(
        "review-product",
        help="Aprueba o rechaza una identidad y su referencia primaria.",
    )
    review_product_parser.add_argument("plan_id", type=uuid.UUID)
    review_product_parser.add_argument("product_id", type=uuid.UUID)
    review_product_parser.add_argument("--fingerprint", required=True)
    review_product_parser.add_argument("--review-sha256", required=True)
    review_product_parser.add_argument(
        "--decision", choices=("approve", "reject"), required=True
    )
    _human_evidence_arguments(review_product_parser)
    _database_arguments(review_product_parser)

    build_release_parser = subparsers.add_parser(
        "build-release",
        help="Construye un borrador inmutable desde el catálogo aplicado y revisado.",
    )
    build_release_parser.add_argument("plan_id", type=uuid.UUID)
    build_release_parser.add_argument("--fingerprint", required=True)
    build_release_parser.add_argument("--version", required=True)
    build_release_parser.add_argument("--brand", default="NATSUKI")
    _human_evidence_arguments(build_release_parser)
    _database_arguments(build_release_parser)

    inspect_release_parser = subparsers.add_parser(
        "inspect-release", help="Verifica y muestra un release persistido."
    )
    inspect_release_parser.add_argument("release_id", type=uuid.UUID)
    _database_arguments(inspect_release_parser)

    publish_release_parser = subparsers.add_parser(
        "publish-release", help="Publica un borrador cuyo checksum fue revisado."
    )
    publish_release_parser.add_argument("release_id", type=uuid.UUID)
    publish_release_parser.add_argument("--snapshot-sha256", required=True)
    _human_evidence_arguments(publish_release_parser)
    _database_arguments(publish_release_parser)

    archive_release_parser = subparsers.add_parser(
        "archive-release", help="Archiva un release publicado sin alterar su contenido."
    )
    archive_release_parser.add_argument("release_id", type=uuid.UUID)
    archive_release_parser.add_argument("--snapshot-sha256", required=True)
    _human_evidence_arguments(archive_release_parser)
    _database_arguments(archive_release_parser)
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
        elif args.command == "approve-plan":
            result = approve_plan(
                args.plan_id,
                args.fingerprint,
                args.actor,
                args.reason,
                config,
                password,
            )
        elif args.command == "apply-plan":
            result = apply_approved_plan(
                args.plan_id,
                args.fingerprint,
                args.actor,
                args.reason,
                config,
                password,
            )
        elif args.command == "inspect-reviews":
            result = inspect_review_queue(
                args.plan_id,
                args.fingerprint,
                config,
                password,
            )
        elif args.command == "review-product":
            result = review_product(
                args.plan_id,
                args.product_id,
                args.fingerprint,
                args.review_sha256,
                args.decision,
                args.actor,
                args.reason,
                config,
                password,
            )
        elif args.command == "build-release":
            result = build_release(
                args.plan_id,
                args.fingerprint,
                args.version,
                args.actor,
                args.reason,
                config,
                password,
                brand_name=args.brand,
            )
        elif args.command == "inspect-release":
            result = inspect_release(args.release_id, config, password)
        elif args.command == "publish-release":
            result = publish_release(
                args.release_id,
                args.snapshot_sha256,
                args.actor,
                args.reason,
                config,
                password,
            )
        else:
            result = archive_release(
                args.release_id,
                args.snapshot_sha256,
                args.actor,
                args.reason,
                config,
                password,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (ValueError, RuntimeError, PermissionError, NotImplementedError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
