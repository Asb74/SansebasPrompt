"""Motor de generación de prompts PROM-9™ por área."""

from __future__ import annotations

from typing import Dict

from .plantillas.contabilidad import render_contabilidad
from .plantillas.gestion import render_gestion
from .plantillas.it import render_it
from .plantillas.ventas import render_ventas


def _normalizar_area(area: str) -> str:
    """Normaliza el área para facilitar el enrutamiento de plantilla."""
    return area.strip().lower()


def generar_prompt(datos_tarea: Dict[str, str], perfil: Dict[str, str], contexto: Dict[str, str]) -> str:
    """Selecciona plantilla por área y construye el prompt final."""
    payload = {
        "perfil_nombre": perfil.get("nombre", "Usuario"),
        "perfil_rol": perfil.get("rol", "Profesional"),
        "contexto_nombre": contexto.get("nombre", "General"),
        "contexto_rol": contexto.get("rol_contextual", "Asistente"),
        "objetivo": datos_tarea.get("objetivo", ""),
        "entradas": datos_tarea.get("entradas", ""),
        "restricciones": datos_tarea.get("restricciones", ""),
        "formato_salida": datos_tarea.get("formato_salida", ""),
        "prioridad": datos_tarea.get("prioridad", "Media"),
    }

    area = _normalizar_area(datos_tarea.get("area", ""))
    if area == "it":
        payload.update(
            {
                "stack": datos_tarea.get("stack", "Python 3.9+"),
                "nivel_tecnico": datos_tarea.get("nivel_tecnico", "Senior"),
            }
        )
        return render_it(payload)
    if area == "ventas":
        payload.update(
            {
                "segmento": datos_tarea.get("segmento", "B2B"),
                "propuesta_valor": datos_tarea.get("propuesta_valor", ""),
            }
        )
        return render_ventas(payload)
    if area == "contabilidad":
        payload.update(
            {
                "normativa": datos_tarea.get("normativa", "PGC"),
                "periodo": datos_tarea.get("periodo", ""),
            }
        )
        return render_contabilidad(payload)

    payload.update(
        {
            "area_operativa": datos_tarea.get("area_operativa", "Operaciones"),
            "horizonte": datos_tarea.get("horizonte", "Trimestral"),
        }
    )
    return render_gestion(payload)
