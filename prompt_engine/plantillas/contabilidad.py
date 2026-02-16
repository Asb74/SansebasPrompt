"""Plantilla especializada PROM-9™ para tareas de contabilidad."""

from __future__ import annotations

from typing import Dict

from .prom9_base import render_base


def render_contabilidad(payload: Dict[str, str]) -> str:
    """Extiende la base con criterios contables y normativos."""
    base = render_base(payload)
    extra = f"""\n[Extensión Contabilidad]
- Marco normativo: {payload.get('normativa', 'PGC/NIIF según aplique')}
- Periodo de análisis: {payload.get('periodo', 'No especificado')}
- Consideraciones: trazabilidad, conciliación y cumplimiento fiscal.
- Solicitud adicional: incluye asientos sugeridos y validaciones clave.
"""
    return base + extra
