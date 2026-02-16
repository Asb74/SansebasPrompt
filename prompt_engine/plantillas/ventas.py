"""Plantilla especializada PROM-9™ para tareas de ventas."""

from __future__ import annotations

from typing import Any, Dict

from .prom9_base import render_base


def _contexto_agricola_ventas(payload: Dict[str, Any]) -> str:
    especializaciones = payload.get("especializacion_agricola", [])
    if not especializaciones:
        return ""
    cultivos = ", ".join(str(item) for item in especializaciones)
    return (
        "- Contexto agrícola aplicado: adapta los argumentos comerciales, ejemplos de oferta y objeciones "
        f"al mercado de {cultivos}.\n"
    )


def render_ventas(payload: Dict[str, Any]) -> str:
    """Extiende la base con enfoque comercial y de conversión."""
    base = render_base(payload)
    contexto_agricola = _contexto_agricola_ventas(payload)
    extra = f"""\n[Extensión Ventas]
- Segmento objetivo: {payload.get('segmento', 'General')}
- Propuesta de valor: {payload.get('propuesta_valor', 'No especificada')}
{contexto_agricola}- KPIs sugeridos: ratio de conversión, ticket medio, tiempo de cierre.
- Solicitud adicional: redacta argumentos y objeciones con cierre persuasivo.
"""
    return base + extra
