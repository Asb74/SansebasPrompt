"""Plantilla especializada PROM-9™ para tareas de ventas."""

from __future__ import annotations

from typing import Dict

from .prom9_base import render_base


def render_ventas(payload: Dict[str, str]) -> str:
    """Extiende la base con enfoque comercial y de conversión."""
    base = render_base(payload)
    extra = f"""\n[Extensión Ventas]
- Segmento objetivo: {payload.get('segmento', 'General')}
- Propuesta de valor: {payload.get('propuesta_valor', 'No especificada')}
- KPIs sugeridos: ratio de conversión, ticket medio, tiempo de cierre.
- Solicitud adicional: redacta argumentos y objeciones con cierre persuasivo.
"""
    return base + extra
