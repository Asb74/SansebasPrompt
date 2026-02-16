"""Plantilla especializada PROM-9™ para tareas de gestión/operaciones."""

from __future__ import annotations

from typing import Any, Dict

from .prom9_base import render_base


def _contexto_agricola_negocio(payload: Dict[str, Any]) -> str:
    especializaciones = payload.get("especializacion_agricola", [])
    if not especializaciones:
        return ""
    cultivos = ", ".join(str(item) for item in especializaciones)
    return (
        "- Contexto de negocio agrícola: prioriza recomendaciones operativas y ejemplos alineados con "
        f"la gestión de {cultivos}.\n"
    )


def render_gestion(payload: Dict[str, Any]) -> str:
    """Extiende la base con foco en operación y gobierno de procesos."""
    base = render_base(payload)
    contexto_agricola = _contexto_agricola_negocio(payload)
    extra = f"""\n[Extensión Gestión]
- Área operativa: {payload.get('area_operativa', 'No especificada')}
- Horizonte temporal: {payload.get('horizonte', 'Corto/medio plazo')}
{contexto_agricola}- Consideraciones: eficiencia, coordinación interáreas y control de riesgos.
- Solicitud adicional: plantea plan de acción, hitos y responsables.
"""
    return base + extra
