"""Plantilla especializada PROM-9™ para tareas de gestión/operaciones."""

from __future__ import annotations

from typing import Dict

from .prom9_base import render_base


def render_gestion(payload: Dict[str, str]) -> str:
    """Extiende la base con foco en operación y gobierno de procesos."""
    base = render_base(payload)
    extra = f"""\n[Extensión Gestión]
- Área operativa: {payload.get('area_operativa', 'No especificada')}
- Horizonte temporal: {payload.get('horizonte', 'Corto/medio plazo')}
- Consideraciones: eficiencia, coordinación interáreas y control de riesgos.
- Solicitud adicional: plantea plan de acción, hitos y responsables.
"""
    return base + extra
