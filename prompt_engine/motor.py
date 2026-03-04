"""Motor de generación de prompts PROM-9™ por área."""

from __future__ import annotations

from importlib import import_module
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

IT_TEMPLATE_KEYS = [
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
        "titulo": datos_tarea.get("titulo", ""),
        "situacion": datos_tarea.get("situacion", ""),
        "urgencia": datos_tarea.get("urgencia", ""),
        "contexto_detallado": datos_tarea.get("contexto_detallado", ""),
        "objetivo": datos_tarea.get("objetivo", ""),
        "entradas": datos_tarea.get("entradas", ""),
        "restricciones": datos_tarea.get("restricciones", ""),
        "formato_salida": datos_tarea.get("formato_salida", ""),
        "prioridad": datos_tarea.get("prioridad", "Media"),
    }

    extras_filtrados: dict[str, str] = {}
    extras_fields = perfil.get("extras_fields")
    if isinstance(extras_fields, list):
        for field in extras_fields:
            if not isinstance(field, dict):
                continue
            key = str(field.get("key", "")).strip()
            if not key:
                continue
            value = datos_tarea.get(key)
            if value is None:
                continue
            value_text = str(value).strip()
            if value_text:
                extras_filtrados[key] = value_text

    if extras_filtrados:
        payload["_perfil_extras"] = extras_filtrados

    contexto_extras_filtrados: dict[str, str] = {}
    contexto_extras_fields = contexto.get("extras_fields")
    if isinstance(contexto_extras_fields, list):
        for field in contexto_extras_fields:
            if not isinstance(field, dict):
                continue
            key = str(field.get("key", "")).strip()
            if not key:
                continue
            value = datos_tarea.get(key)
            if value is None:
                continue
            value_text = str(value).strip()
            if value_text:
                contexto_extras_filtrados[key] = value_text

    if contexto_extras_filtrados:
        payload["_contexto_extras"] = contexto_extras_filtrados

    for key, value in datos_tarea.items():
        if (
            key in payload
            or key in {"area", "adjuntos"}
            or key.startswith("perfil_")
            or key.startswith("contexto_")
            or value is None
        ):
            continue
        value_text = str(value).strip()
        if value_text:
            payload[key] = value_text

    template_name = _normalizar_area(datos_tarea.get("area", ""))
    if template_name == "it":
        payload.update(
            {
                "stack": datos_tarea.get("stack", "Python 3.9+"),
                "nivel_tecnico": datos_tarea.get("nivel_tecnico", "Senior"),
            }
        )
        for key in IT_TEMPLATE_KEYS:
            value = datos_tarea.get(key)
            if value is not None and str(value).strip():
                payload[key] = str(value).strip()
        prompt = render_it(payload)
    elif template_name == "ventas":
        payload.update(
            {
                "segmento": datos_tarea.get("segmento", "B2B"),
                "propuesta_valor": datos_tarea.get("propuesta_valor", ""),
            }
        )
        prompt = render_ventas(payload)
    elif template_name == "contabilidad":
        payload.update(
            {
                "normativa": datos_tarea.get("normativa", "PGC"),
                "periodo": datos_tarea.get("periodo", ""),
            }
        )
        prompt = render_contabilidad(payload)
    elif template_name == "gestion":
        payload.update(
            {
                "area_operativa": datos_tarea.get("area_operativa", "Operaciones"),
                "horizonte": datos_tarea.get("horizonte", "Trimestral"),
            }
        )
        prompt = render_gestion(payload)
    else:
        try:
            module = import_module(f"{__package__}.plantillas.{template_name}")
            render_fn = getattr(module, "render_custom", None)
            if not callable(render_fn):
                render_fn = getattr(module, f"render_{template_name}", None)
            prompt = render_fn(payload) if callable(render_fn) else render_gestion(payload)
        except Exception:
            prompt = render_gestion(payload)

    secciones_finales = [prompt]

    if adjuntos:
        secciones_finales.append(leer_archivos(adjuntos))

    if template_name == "it":
        secciones_finales.append(DIRECTRICES_TECNICAS_IT)

    return "\n\n".join(seccion for seccion in secciones_finales if seccion.strip())
