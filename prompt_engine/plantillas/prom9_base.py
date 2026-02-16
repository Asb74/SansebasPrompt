"""Plantilla base para prompts con estructura PROM-9™."""

from __future__ import annotations

from typing import Any, Dict


def _formatear_especializacion_agricola(payload: Dict[str, Any]) -> str:
    especializaciones = payload.get("especializacion_agricola", [])
    if not especializaciones:
        return ""
    if isinstance(especializaciones, str):
        especializaciones = [item.strip() for item in especializaciones.split(",") if item.strip()]
    return (
        "10) Este perfil está especializado en los siguientes cultivos agrícolas: "
        f"{', '.join(str(item) for item in especializaciones)}.\n"
    )


def render_base(payload: Dict[str, Any]) -> str:
    """Construye la estructura base PROM-9™ con los campos generales."""
    perfil_especializacion = _formatear_especializacion_agricola(payload)
    return f"""PROM-9™ | Base
1) Perfil: {payload['perfil_nombre']} ({payload['perfil_rol']})
2) Contexto: {payload['contexto_nombre']} - Rol contextual: {payload['contexto_rol']}
3) Objetivo: {payload['objetivo']}
4) Entradas clave: {payload['entradas']}
5) Restricciones: {payload['restricciones']}
6) Formato de salida: {payload['formato_salida']}
7) Prioridad: {payload['prioridad']}
8) Criterios de calidad: Claridad, precisión y accionabilidad.
9) Instrucción final: Entrega una respuesta profesional y estructurada en español.
{perfil_especializacion}"""
