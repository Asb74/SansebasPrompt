"""Motor de generación de prompts PROM-9™ por área."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from .attachments import leer_archivos
from .plantillas.contabilidad import render_contabilidad
from .plantillas.gestion import render_gestion
from .plantillas.it import render_it
from .plantillas.ventas import render_ventas

DIRECTRICES_TECNICAS_IT = """### Directrices obligatorias de análisis técnico

- No asumir comportamiento de código no mostrado.
- Señalar debilidades técnicas detectadas.
- Indicar riesgos y problemas potenciales.
- Si faltan archivos o funciones para análisis completo,
  solicitarlos explícitamente antes de proponer solución final.
- No validar decisiones por cortesía.
- Mantener tono profesional, crítico y técnico.
- No incluir elogios ni frases motivacionales.
"""


def _normalizar_area(area: str) -> str:
    """Normaliza el área para facilitar el enrutamiento de plantilla."""
    return area.strip().lower()


def generar_prompt(
    datos_tarea: Dict[str, str],
    perfil: Dict[str, str],
    contexto: Dict[str, str],
    adjuntos: list[Path] | None = None,
) -> str:
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
        prompt = render_it(payload)
    elif area == "ventas":
        payload.update(
            {
                "segmento": datos_tarea.get("segmento", "B2B"),
                "propuesta_valor": datos_tarea.get("propuesta_valor", ""),
            }
        )
        prompt = render_ventas(payload)
    elif area == "contabilidad":
        payload.update(
            {
                "normativa": datos_tarea.get("normativa", "PGC"),
                "periodo": datos_tarea.get("periodo", ""),
            }
        )
        prompt = render_contabilidad(payload)
    else:
        payload.update(
            {
                "area_operativa": datos_tarea.get("area_operativa", "Operaciones"),
                "horizonte": datos_tarea.get("horizonte", "Trimestral"),
            }
        )
        prompt = render_gestion(payload)

    secciones_finales = [prompt]

    if adjuntos:
        secciones_finales.append(leer_archivos(adjuntos))

    if area == "it":
        secciones_finales.append(DIRECTRICES_TECNICAS_IT)

    return "\n\n".join(seccion for seccion in secciones_finales if seccion.strip())
