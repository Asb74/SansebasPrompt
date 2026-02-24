"""Plantilla especializada PROM-9™ para tareas de IT."""

from __future__ import annotations

from typing import Dict

from .prom9_base import render_base


LABELS = {
    "tipo_sistema": "Tipo de sistema",
    "entorno_ejecucion": "Entorno de ejecución",
    "datos_persistencia": "Datos y persistencia",
    "requisitos_funcionales": "Requisitos funcionales",
    "requisitos_no_funcionales": "Requisitos no funcionales",
    "criterios_aceptacion": "Criterios de aceptación",
    "entregables": "Entregables",
    "riesgos_y_mitigacion": "Riesgos y mitigación",
    "plan_pruebas": "Plan de pruebas",
}

ORDER = [
    "tipo_sistema",
    "entorno_ejecucion",
    "datos_persistencia",
    "requisitos_funcionales",
    "requisitos_no_funcionales",
    "criterios_aceptacion",
    "entregables",
    "riesgos_y_mitigacion",
    "plan_pruebas",
]


def render_it(payload: Dict[str, str]) -> str:
    """Extiende la base con lineamientos técnicos para informática."""
    base = render_base(payload)
    extra = f"""\n[Extensión IT]
- Stack/entorno: {payload.get('stack', 'No especificado')}
- Nivel técnico esperado: {payload.get('nivel_tecnico', 'Senior')}
- Consideraciones: seguridad, escalabilidad, mantenibilidad y pruebas.
- Solicitud adicional: propone pasos de implementación y riesgos técnicos.
"""

    lineas_it = []
    for key in ORDER:
        value = payload.get(key)
        if value is not None and str(value).strip() != "":
            lineas_it.append(f"- {LABELS[key]}: {value}")

    if lineas_it:
        extra += "\n[Parámetros IT de la tarea]\n" + "\n".join(lineas_it) + "\n"

    return base + extra
