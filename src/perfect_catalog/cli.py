from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from .config import DatabaseConfig, prompt_password
from .application import apply_approved_plan, approve_plan
from .importer import DEFAULT_MAX_PILOT_ROWS, inspect_plan, run_dry_run
from .intake_promotion import promote_intake_to_dry_run
from .image_archive_index import build_image_archive_index
from .catalog_export_job import (
    CATALOG_THEMES,
    CATALOG_FILTER_FIELDS,
    CATALOG_GROUP_FIELDS,
    DEFAULT_FORMATS,
    INDESIGN_TEMPLATE_PROFILES,
    SUPPORTED_FORMATS,
    export_catalog_release,
    verify_catalog_bundle,
)
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
        "--company-id", type=uuid.UUID, required=True,
        help="Company exacta que será propietaria del plan; la consola web la completa automáticamente.",
    )
    import_parser.add_argument(
        "--max-rows",
        type=int,
        default=DEFAULT_MAX_PILOT_ROWS,
        help="Límite de seguridad del piloto; amplíelo solo después de validar una muestra.",
    )
    _database_arguments(import_parser)

    promotion_parser = subparsers.add_parser(
        "promote-intake",
        help="Promueve explícitamente un ingreso Odoo en cuarentena hacia perfilado y dry-run.",
    )
    promotion_parser.add_argument("submission_id", type=uuid.UUID)
    promotion_parser.add_argument("--intake-root", type=Path, default=Path("data/intake"))
    promotion_parser.add_argument("--output-dir", type=Path, default=Path("data/exports/imports"))
    promotion_parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_PILOT_ROWS)
    _human_evidence_arguments(promotion_parser)
    _database_arguments(promotion_parser)

    image_index_parser = subparsers.add_parser(
        "index-images", help="Indexa sin extraer un ZIP de imágenes aceptado en cuarentena."
    )
    image_index_parser.add_argument("submission_id", type=uuid.UUID)
    image_index_parser.add_argument("--intake-root", type=Path, default=Path("data/intake"))
    _human_evidence_arguments(image_index_parser)
    _database_arguments(image_index_parser)

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

    export_parser = subparsers.add_parser(
        "export-catalog",
        help="Exporta PDF, PPTX y snapshot InDesign desde un release publicado.",
    )
    export_parser.add_argument("release_id", type=uuid.UUID)
    export_parser.add_argument("--output-dir", type=Path, required=True)
    export_parser.add_argument("--image-root", type=Path, default=Path("data/images"))
    export_parser.add_argument(
        "--format", dest="formats", action="append", choices=SUPPORTED_FORMATS,
        help="Puede repetirse; por defecto genera los tres formatos.",
    )
    export_parser.add_argument("--title", default="Catálogo de productos")
    export_parser.add_argument("--subtitle", default="")
    export_parser.add_argument("--group-by", choices=CATALOG_GROUP_FIELDS, default="category_path")
    export_parser.add_argument("--group-by-secondary", choices=("", *CATALOG_GROUP_FIELDS), default="")
    export_parser.add_argument("--filter-field", choices=CATALOG_FILTER_FIELDS, default="all")
    export_parser.add_argument("--filter-query", default="")
    export_parser.add_argument(
        "--reference", dest="selected_references", action="append", default=[],
        help="Referencia exacta a incluir; puede repetirse.",
    )
    export_parser.add_argument("--columns", type=int, choices=(1, 2, 3), default=2)
    export_parser.add_argument("--theme", choices=CATALOG_THEMES, default="forest")
    export_parser.add_argument(
        "--indesign-template", choices=INDESIGN_TEMPLATE_PROFILES, default="T4"
    )
    _database_arguments(export_parser)

    verify_export_parser = subparsers.add_parser(
        "verify-catalog-export",
        help="Verifica offline manifiesto, entregables y paquetes ZIP de una exportación.",
    )
    verify_export_parser.add_argument("manifest", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "verify-catalog-export":
            result = verify_catalog_bundle(args.manifest)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        config = DatabaseConfig.from_args(args)
        password = prompt_password(args.prompt_password)
        if args.command == "import-odoo":
            result = run_dry_run(
                args.source, config, password, args.output_dir, args.max_rows,
                company_id=args.company_id,
            )
        elif args.command == "promote-intake":
            result = promote_intake_to_dry_run(
                args.submission_id, args.intake_root, config, password, args.output_dir,
                actor=args.actor, reason=args.reason, max_rows=args.max_rows,
            )
        elif args.command == "index-images":
            result = build_image_archive_index(
                args.submission_id, args.intake_root, config, password,
                actor=args.actor, reason=args.reason,
            )
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
        elif args.command == "archive-release":
            result = archive_release(
                args.release_id,
                args.snapshot_sha256,
                args.actor,
                args.reason,
                config,
                password,
            )
        else:
            result = export_catalog_release(
                args.release_id,
                config,
                password,
                args.output_dir,
                formats=args.formats or DEFAULT_FORMATS,
                config={
                    "title": args.title,
                    "subtitle": args.subtitle,
                    "group_by": args.group_by,
                    "group_by_secondary": args.group_by_secondary,
                    "filter_field": args.filter_field,
                    "filter_query": args.filter_query,
                    "selected_references": args.selected_references,
                    "columns_per_row": args.columns,
                    "theme": args.theme,
                    "template_profile": args.indesign_template,
                },
                image_root=args.image_root,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (ValueError, RuntimeError, PermissionError, FileNotFoundError, NotImplementedError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
