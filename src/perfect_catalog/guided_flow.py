"""Modo guiado: decide el siguiente paso del flujo Cargar -> Revisar -> Entregar.

Función pura sobre los mismos conteos que ya calcula el panel (sin acceso a base de datos),
para poder explicarle a quien no administra el sistema "qué sigue" en lenguaje llano.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

STEPS = (("cargar", "Cargar"), ("revisar", "Revisar"), ("entregar", "Entregar"))


def _progress(current: str, *, all_done: bool = False) -> list[dict[str, str]]:
    order = [key for key, _ in STEPS]
    current_index = order.index(current)
    steps = []
    for index, (key, label) in enumerate(STEPS):
        if all_done or index < current_index:
            state = "done"
        elif index == current_index:
            state = "current"
        else:
            state = "todo"
        steps.append({"key": key, "label": label, "state": state})
    return steps


def next_step(workflow: Mapping[str, int], plans: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Devuelve el paso actual con texto llano, la acción principal y el progreso."""
    pending = int(workflow.get("pending_review_count", 0))
    images = int(workflow.get("pending_image_count", 0)) + int(workflow.get("materialize_image_count", 0))
    drafts = int(workflow.get("draft_release_count", 0))
    published = int(workflow.get("published_release_count", 0))

    if not plans and published == 0 and drafts == 0:
        return {
            "stage": "cargar",
            "title": "Empieza subiendo tus productos",
            "text": "Sube tu Excel de productos y la carpeta de fotos. El sistema prepara todo; después te pedirá confirmar solo lo dudoso.",
            "action_label": "Subir Excel y fotos",
            "action_href": "/operator/simple",
            "secondary": None,
            "progress": _progress("cargar"),
        }
    if pending > 0:
        first = next((p for p in plans if int(p.get("pending_count", 0)) > 0), None)
        href = f"/operator/plans/{first['import_plan_id']}?state=pending" if first else "/operator/review"
        return {
            "stage": "revisar",
            "title": f"Hay {pending} producto{'s' if pending != 1 else ''} por confirmar",
            "text": "Revisa cada producto nuevo y confirma que los datos están bien. Nada se publica hasta que lo apruebes.",
            "action_label": "Confirmar productos",
            "action_href": href,
            "secondary": {"label": "Subir otro Excel", "href": "/operator/simple"},
            "progress": _progress("revisar"),
        }
    if images > 0:
        return {
            "stage": "revisar",
            "title": f"Hay {images} foto{'s' if images != 1 else ''} por confirmar",
            "text": "Algunas fotos necesitan tu visto bueno para asociarse a su producto.",
            "action_label": "Revisar fotos",
            "action_href": "/operator/images",
            "secondary": {"label": "Subir otro Excel", "href": "/operator/simple"},
            "progress": _progress("revisar"),
        }
    if drafts > 0:
        return {
            "stage": "entregar",
            "title": f"Tienes {drafts} borrador{'es' if drafts != 1 else ''} de catálogo",
            "text": "Ya está todo confirmado. Revisa el borrador, publícalo y descarga el catálogo.",
            "action_label": "Ir a Entregar",
            "action_href": "/operator/catalogs",
            "secondary": {"label": "Subir otro Excel", "href": "/operator/simple"},
            "progress": _progress("entregar"),
        }
    if published > 0:
        return {
            "stage": "listo",
            "title": "Tu catálogo está publicado",
            "text": "Puedes descargarlo en digital, PDF o InDesign, o cargar un Excel nuevo para actualizarlo.",
            "action_label": "Descargar catálogo",
            "action_href": "/operator/catalogs",
            "secondary": {"label": "Subir otro Excel", "href": "/operator/simple"},
            "progress": _progress("entregar", all_done=True),
        }
    return {
        "stage": "entregar",
        "title": "Todo confirmado: crea tu catálogo",
        "text": "Los productos ya están aprobados. El siguiente paso es armar y publicar la versión del catálogo.",
        "action_label": "Crear catálogo",
        "action_href": "/operator/catalogs",
        "secondary": {"label": "Subir otro Excel", "href": "/operator/simple"},
        "progress": _progress("entregar"),
    }
