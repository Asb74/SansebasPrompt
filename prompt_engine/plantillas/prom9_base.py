"""Plantilla base para prompts con estructura PROM-9™."""

from __future__ import annotations

from typing import Dict


def render_base(payload: Dict[str, str]) -> str:
    """Construye la estructura base PROM-9™ con los campos generales."""
    extras = payload.get("_perfil_extras") if isinstance(payload.get("_perfil_extras"), dict) else {}
    extras_block = ""
    if extras:
        extras_lines = "\n".join(f"- {key}: {value}" for key, value in extras.items())
        extras_block = f"[Datos adicionales del perfil]\n{extras_lines}\n"

    contexto_extras = payload.get("_contexto_extras") if isinstance(payload.get("_contexto_extras"), dict) else {}
    contexto_extras_block = ""
    if contexto_extras:
        contexto_extras_lines = "\n".join(f"- {key}: {value}" for key, value in contexto_extras.items())
        contexto_extras_block = f"[Datos adicionales del contexto]\n{contexto_extras_lines}\n"

    return f"""PROM-9™ | Base
1) Perfil: {payload['perfil_nombre']} ({payload['perfil_rol']})
2) Contexto: {payload['contexto_nombre']} - Rol contextual: {payload['contexto_rol']}
{extras_block}{contexto_extras_block}3) Objetivo: {payload['objetivo']}
4) Entradas clave: {payload['entradas']}
5) Restricciones: {payload['restricciones']}
6) Formato de salida: {payload['formato_salida']}
7) Prioridad: {payload['prioridad']}
8) Criterios de calidad: Claridad, precisión y accionabilidad.
9) Instrucción final: Entrega una respuesta profesional y estructurada en español.
"""
