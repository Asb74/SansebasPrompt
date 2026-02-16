"""Plantilla especializada PROM-9™ para tareas de IT."""

from __future__ import annotations

from typing import Dict

from .prom9_base import render_base


def render_it(payload: Dict[str, str]) -> str:
    """Extiende la base con lineamientos técnicos para informática."""
    base = render_base(payload)
    extra = f"""\n[Extensión IT]
- Stack/entorno: {payload.get('stack', 'No especificado')}
- Nivel técnico esperado: {payload.get('nivel_tecnico', 'Senior')}
- Consideraciones: seguridad, escalabilidad, mantenibilidad y pruebas.
- Solicitud adicional: propone pasos de implementación y riesgos técnicos.
"""
    return base + extra
