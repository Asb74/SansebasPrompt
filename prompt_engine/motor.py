"""Motor de generación de prompts PROM-9™ por área."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .attachments import leer_archivos
from .plantillas.prom9_base import render_base
from .storage_sqlite import get_plantillas

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


def _incluir_valor_campo(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def _render_template_fields_block(payload: Dict[str, Any], template_name: str) -> str:
    try:
        plantillas = get_plantillas()
    except Exception:
        return ""

    plantilla = next(
        (
            item
            for item in plantillas
            if isinstance(item, dict)
            and _normalizar_area(str(item.get("nombre", ""))) == template_name
        ),
        None,
    )
    if not isinstance(plantilla, dict):
        return ""

    fields = plantilla.get("fields")
    if not isinstance(fields, list):
        return ""

    lineas: list[str] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        key = str(field.get("key") or "").strip()
        if not key:
            continue
        value = payload.get(key)
        if not _incluir_valor_campo(value):
            continue
        value_text = value.strip() if isinstance(value, str) else str(value)
        label = str(field.get("label") or key)
        lineas.append(f"- {label}: {value_text}")

    if not lineas:
        return ""

    return f"\n[Campos de plantilla: {template_name}]\n" + "\n".join(lineas) + "\n"


def _render_extension_block(payload: Dict[str, Any], template_name: str) -> str:
    if template_name == "it":
        extra = f"""\n[Extensión IT]
- Stack/entorno: {payload.get('stack', 'No especificado')}
- Nivel técnico esperado: {payload.get('nivel_tecnico', 'Senior')}
- Consideraciones: seguridad, escalabilidad, mantenibilidad y pruebas.
- Solicitud adicional: propone pasos de implementación y riesgos técnicos.
"""

        lineas_it = []
        for key in IT_TEMPLATE_KEYS:
            value = payload.get(key)
            if value is not None and str(value).strip() != "":
                label = key.replace("_", " ").capitalize()
                if key == "tipo_sistema":
                    label = "Tipo de sistema"
                elif key == "entorno_ejecucion":
                    label = "Entorno de ejecución"
                elif key == "datos_persistencia":
                    label = "Datos y persistencia"
                elif key == "requisitos_funcionales":
                    label = "Requisitos funcionales"
                elif key == "requisitos_no_funcionales":
                    label = "Requisitos no funcionales"
                elif key == "criterios_aceptacion":
                    label = "Criterios de aceptación"
                elif key == "entregables":
                    label = "Entregables"
                elif key == "riesgos_y_mitigacion":
                    label = "Riesgos y mitigación"
                elif key == "plan_pruebas":
                    label = "Plan de pruebas"
                lineas_it.append(f"- {label}: {value}")

        if lineas_it:
            extra += "\n[Parámetros IT de la tarea]\n" + "\n".join(lineas_it) + "\n"

        return extra

    if template_name == "ventas":
        return f"""\n[Extensión Ventas]
- Segmento objetivo: {payload.get('segmento', 'General')}
- Propuesta de valor: {payload.get('propuesta_valor', 'No especificada')}
- KPIs sugeridos: ratio de conversión, ticket medio, tiempo de cierre.
- Solicitud adicional: redacta argumentos y objeciones con cierre persuasivo.
"""

    if template_name == "contabilidad":
        return f"""\n[Extensión Contabilidad]
- Marco normativo: {payload.get('normativa', 'PGC/NIIF según aplique')}
- Periodo de análisis: {payload.get('periodo', 'No especificado')}
- Consideraciones: trazabilidad, conciliación y cumplimiento fiscal.
- Solicitud adicional: incluye asientos sugeridos y validaciones clave.
"""

    if template_name == "gestion":
        return f"""\n[Extensión Gestión]
- Área operativa: {payload.get('area_operativa', 'No especificada')}
- Horizonte temporal: {payload.get('horizonte', 'Corto/medio plazo')}
- Consideraciones: eficiencia, coordinación interáreas y control de riesgos.
- Solicitud adicional: plantea plan de acción, hitos y responsables.
"""

    return ""


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

    template_name = _normalizar_area(str(datos_tarea.get("area", ""))) or "gestion"
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
    elif template_name == "ventas":
        payload.update(
            {
                "segmento": datos_tarea.get("segmento", "B2B"),
                "propuesta_valor": datos_tarea.get("propuesta_valor", ""),
            }
        )
    elif template_name == "contabilidad":
        payload.update(
            {
                "normativa": datos_tarea.get("normativa", "PGC"),
                "periodo": datos_tarea.get("periodo", ""),
            }
        )
    elif template_name == "gestion":
        payload.update(
            {
                "area_operativa": datos_tarea.get("area_operativa", "Operaciones"),
                "horizonte": datos_tarea.get("horizonte", "Trimestral"),
            }
        )
    base_prompt = render_base(payload)
    template_fields_block = _render_template_fields_block(payload, template_name)
    extension_block = _render_extension_block(payload, template_name)
    prompt = base_prompt + template_fields_block + extension_block

    secciones_finales = [prompt]

    if adjuntos:
        secciones_finales.append(leer_archivos(adjuntos))

    if template_name == "it":
        secciones_finales.append(DIRECTRICES_TECNICAS_IT)

    return "\n\n".join(seccion for seccion in secciones_finales if seccion.strip())
