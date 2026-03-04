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
1) Perfil: {payload.get('perfil_nombre', 'Usuario')} ({payload.get('perfil_rol', 'Profesional')})
2) Contexto: {payload.get('contexto_nombre', 'General')} - Rol contextual: {payload.get('contexto_rol', 'Asistente')}
{extras_block}{contexto_extras_block}3) Título: {payload.get('titulo', '')}
4) Objetivo: {payload.get('objetivo', '')}
5) Tipo de situación: {payload.get('situacion', '')}
6) Urgencia: {payload.get('urgencia', '')}
7) Contexto detallado: {payload.get('contexto_detallado', '')}
8) Restricciones: {payload.get('restricciones', '')}
9) Formato de salida: {payload.get('formato_salida', 'Respuesta estructurada')}
10) Prioridad: {payload.get('prioridad', 'Media')}
11) Criterios de calidad: Claridad, precisión y accionabilidad.
12) Instrucción final: Entrega una respuesta profesional y estructurada en español.
"""
