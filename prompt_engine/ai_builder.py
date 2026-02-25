"""Asistente IA para generar maestros PROM-9™."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


_ALLOWED_KINDS = {"perfil", "contexto", "plantilla"}
MODEL_DEFAULT = "gpt-4o-mini"


def resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base_path / relative_path


def _strip_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_strip_text(item) for item in value if _strip_text(item)]


def _normalize_field_item(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None
    normalized = {
        "key": _strip_text(item.get("key")),
        "label": _strip_text(item.get("label")),
        "help": _strip_text(item.get("help")),
        "example": _strip_text(item.get("example")),
        "default": _strip_text(item.get("default")),
    }
    if not normalized["key"]:
        return None
    return normalized


def _as_fields_list(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    cleaned: list[dict[str, str]] = []
    for item in value:
        normalized = _normalize_field_item(item)
        if normalized is not None:
            cleaned.append(normalized)
    return cleaned


def _extract_json(raw: str) -> dict[str, Any]:
    content = raw.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "La respuesta del modelo no es JSON válido. Intenta reformular la descripción."
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError("La respuesta del modelo debe ser un objeto JSON.")
    return payload


def _normalize_perfil(payload: dict[str, Any], name: str) -> dict[str, Any]:
    normalized = {
        "nombre": _strip_text(payload.get("nombre")) or name,
        "rol": _strip_text(payload.get("rol")),
        "rol_base": _strip_text(payload.get("rol_base")),
        "empresa": _strip_text(payload.get("empresa")),
        "ubicacion": _strip_text(payload.get("ubicacion")),
        "herramientas": _as_string_list(payload.get("herramientas")),
        "estilo": _strip_text(payload.get("estilo")),
        "nivel_tecnico": _strip_text(payload.get("nivel_tecnico")),
        "prioridades": _as_string_list(payload.get("prioridades")),
        "extras_fields": _as_fields_list(payload.get("extras_fields")),
    }

    if not normalized["rol"] and normalized["rol_base"]:
        normalized["rol"] = normalized["rol_base"]
    if not normalized["rol_base"] and normalized["rol"]:
        normalized["rol_base"] = normalized["rol"]

    if not normalized["nombre"]:
        raise RuntimeError("El JSON generado no contiene un 'nombre' válido para el perfil.")
    if not normalized["rol_base"]:
        raise RuntimeError("El JSON generado debe incluir 'rol_base' para el perfil.")

    return normalized


def _normalize_contexto(payload: dict[str, Any], name: str) -> dict[str, Any]:
    normalized = {
        "nombre": _strip_text(payload.get("nombre")) or name,
        "rol_contextual": _strip_text(payload.get("rol_contextual")),
        "enfoque": _as_string_list(payload.get("enfoque")),
        "no_hacer": _as_string_list(payload.get("no_hacer")),
        "extras_fields": _as_fields_list(payload.get("extras_fields")),
    }

    if not normalized["nombre"]:
        raise RuntimeError("El JSON generado no contiene un 'nombre' válido para el contexto.")
    if not normalized["rol_contextual"]:
        raise RuntimeError("El JSON generado debe incluir 'rol_contextual' para el contexto.")

    return normalized


def _normalize_plantilla(payload: dict[str, Any], name: str) -> dict[str, Any]:
    normalized = {
        "nombre": _strip_text(payload.get("nombre")) or name,
        "label": _strip_text(payload.get("label")),
        "fields": _as_fields_list(payload.get("fields")),
        "ejemplos": _as_string_list(payload.get("ejemplos")),
    }

    if not normalized["nombre"]:
        raise RuntimeError("El JSON generado no contiene un 'nombre' válido para la plantilla.")
    if not normalized["label"]:
        raise RuntimeError("El JSON generado debe incluir 'label' para la plantilla.")

    return normalized


def _normalize(kind: str, payload: dict[str, Any], name: str) -> dict[str, Any]:
    if kind == "perfil":
        return _normalize_perfil(payload, name)
    if kind == "contexto":
        return _normalize_contexto(payload, name)
    return _normalize_plantilla(payload, name)


def _normalize_draft_lenient(kind: str, draft: dict[str, Any], name: str) -> dict[str, Any]:
    if kind == "perfil":
        normalized = {
            "nombre": _strip_text(draft.get("nombre")) or name,
            "rol": _strip_text(draft.get("rol")),
            "rol_base": _strip_text(draft.get("rol_base")),
            "empresa": _strip_text(draft.get("empresa")),
            "ubicacion": _strip_text(draft.get("ubicacion")),
            "herramientas": _as_string_list(draft.get("herramientas")),
            "estilo": _strip_text(draft.get("estilo")),
            "nivel_tecnico": _strip_text(draft.get("nivel_tecnico")),
            "prioridades": _as_string_list(draft.get("prioridades")),
            "extras_fields": _as_fields_list(draft.get("extras_fields")),
        }
        if not normalized["rol"] and normalized["rol_base"]:
            normalized["rol"] = normalized["rol_base"]
        if not normalized["rol_base"] and normalized["rol"]:
            normalized["rol_base"] = normalized["rol"]
        return normalized

    if kind == "contexto":
        return {
            "nombre": _strip_text(draft.get("nombre")) or name,
            "rol_contextual": _strip_text(draft.get("rol_contextual")),
            "enfoque": _as_string_list(draft.get("enfoque")),
            "no_hacer": _as_string_list(draft.get("no_hacer")),
            "extras_fields": _as_fields_list(draft.get("extras_fields")),
        }

    return {
        "nombre": _strip_text(draft.get("nombre")) or name,
        "label": _strip_text(draft.get("label")),
        "fields": _as_fields_list(draft.get("fields")),
        "ejemplos": _as_string_list(draft.get("ejemplos")),
    }


def _normalize_slots(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    valid_states = {"known", "missing", "unclear"}
    normalized: dict[str, str] = {}
    for key, state in value.items():
        clean_key = _strip_text(key)
        clean_state = _strip_text(state).lower()
        if clean_key and clean_state in valid_states:
            normalized[clean_key] = clean_state
    return normalized


_DOMAIN_EXTRA_KEYS = {
    "agro": [
        "cultivo_objetivo",
        "campana_actual",
        "zona_productiva",
        "tipo_suelo",
        "riesgos_climaticos",
        "ventana_aplicacion",
    ],
    "it": [
        "stack_principal",
        "entorno_despliegue",
        "nivel_seguridad",
        "sla_objetivo",
        "metrica_exito",
        "restricciones_tecnicas",
    ],
    "ventas": [
        "segmento_cliente",
        "ticket_promedio",
        "canal_principal",
        "objeciones_frecuentes",
        "ciclo_venta",
        "kpi_comercial",
    ],
    "contabilidad": [
        "regimen_fiscal",
        "periodicidad_reporte",
        "plan_cuentas",
        "politica_gastos",
        "riesgo_auditoria",
        "nivel_detalle_informe",
    ],
}


def _detect_domain_family(description: str) -> str:
    text = _strip_text(description).lower()
    heuristics = {
        "agro": ("agro", "cultivo", "siembra", "fertil", "riego", "cosecha"),
        "it": ("software", "it", "dev", "api", "backend", "frontend", "infra", "cloud"),
        "ventas": ("ventas", "comercial", "lead", "pipeline", "prospect", "crm"),
        "contabilidad": ("contable", "contabilidad", "fiscal", "balance", "tribut", "auditor"),
    }
    for family, words in heuristics.items():
        if any(word in text for word in words):
            return family
    return ""


def _normalize_diagnosis_questions(raw: Any, max_questions: int) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            key = _strip_text(item.get("key"))
            question = _strip_text(item.get("question"))
            if not key or not question:
                continue
            required = bool(item.get("required", False))
            why = _strip_text(item.get("why"))
            questions.append({"key": key, "question": question, "required": required, "why": why})
    return questions[:max(1, min(max_questions, 20))]


def _normalize_diagnosis(kind: str, payload: dict[str, Any], name: str, max_questions: int) -> dict[str, Any]:
    base_questions = _normalize_diagnosis_questions(payload.get("base_questions"), max_questions)
    extras_questions = _normalize_diagnosis_questions(payload.get("extras_questions"), max_questions)
    if not base_questions:
        base_questions = _normalize_diagnosis_questions(payload.get("preguntas"), max_questions)

    normalized = {
        "nombre": _strip_text(payload.get("nombre")) or name,
        "kind": kind,
        "base_questions": base_questions,
        "extras_fields_sugeridos": _as_fields_list(payload.get("extras_fields_sugeridos")),
        "extras_questions": extras_questions,
        "draft": _normalize_draft_lenient(
            kind,
            payload.get("draft") if isinstance(payload.get("draft"), dict) else {},
            name,
        ),
    }
    return normalized


def _load_api_key() -> str:
    env_key = _strip_text(os.getenv("OPENAI_API_KEY"))
    if env_key:
        return env_key

    key_file = resource_path("prompt_engine/KeySecret.txt")
    if key_file.exists():
        file_key = key_file.read_text(encoding="utf-8").strip()
        if file_key:
            return file_key

    raise RuntimeError(
        "Falta API key de OpenAI. Define OPENAI_API_KEY o crea prompt_engine/KeySecret.txt con la clave."
    )


def _system_prompt(kind: str, name: str) -> str:
    schemas = {
        "perfil": """Devuelve SOLO un JSON con este esquema exacto:
{
  \"nombre\": \"...\",
  \"rol\": \"...\",
  \"rol_base\": \"...\",
  \"empresa\": \"...\",
  \"ubicacion\": \"...\",
  \"herramientas\": [\"...\"],
  \"estilo\": \"...\",
  \"nivel_tecnico\": \"...\",
  \"prioridades\": [\"...\"],
  \"extras_fields\": [
    {\"key\":\"...\",\"label\":\"...\",\"help\":\"...\",\"example\":\"...\",\"default\":\"\"}
  ]
}""",
        "contexto": """Devuelve SOLO un JSON con este esquema exacto:
{
  \"nombre\":\"...\",
  \"rol_contextual\":\"...\",
  \"enfoque\":[\"...\"],
  \"no_hacer\":[\"...\"],
  \"extras_fields\":[
    {\"key\":\"...\",\"label\":\"...\",\"help\":\"...\",\"example\":\"...\",\"default\":\"\"}
  ]
}""",
        "plantilla": """Devuelve SOLO un JSON con este esquema exacto:
{
  \"nombre\":\"...\",
  \"label\":\"...\",
  \"fields\":[
    {\"key\":\"...\",\"label\":\"...\",\"help\":\"...\",\"example\":\"...\",\"default\":\"\"}
  ],
  \"ejemplos\":[\"...\"]
}""",
    }
    return (
        "Eres un asistente experto en diseño de maestros para PROM-9. "
        "Responde únicamente JSON válido, sin markdown, sin comentarios, sin texto adicional. "
        "No inventes datos de identidad (por ejemplo empresa, ubicación, nombres de clientes, país o ciudad). "
        "Si la descripción no aporta explícitamente un dato, devuelve \"\" en ese campo. "
        f"El tipo de maestro es: {kind}. Nombre esperado: {name}.\n\n{schemas[kind]}"
    )


def _diagnosis_system_prompt(
    kind: str,
    name: str,
    max_questions: int,
    domain_family: str,
    exclude_keys: list[str],
) -> str:
    domain_keys = _DOMAIN_EXTRA_KEYS.get(domain_family, [])
    return (
        "Eres un asistente experto en diseño de maestros para PROM-9. "
        "Devuelve SOLO JSON del esquema diagnosis; no markdown; no texto; no inventes; si falta info, pregunta. "
        "No inventes datos de identidad (empresa, ubicación, personas, clientes). "
        f"Genera como máximo {max_questions} preguntas en base_questions y 6 en extras_questions. "
        "base_questions: para campos base críticos del maestro (rol_base/rol_contextual/label, etc). "
        "extras_fields_sugeridos: entre 6 y 12 campos extra reutilizables y útiles. "
        "extras_questions: entre 3 y 6 preguntas para afinar esos extras. "
        "No preguntes por keys presentes en exclude_keys. "
        "base_questions = solo campos base críticos aún no cubiertos. "
        "extras_questions = solo extras útiles que NO estén ya cubiertos. "
        "Usa keys simples y estables en snake_case. "
        f"Tipo: {kind}. Nombre esperado: {name}. "
        f"Familia de dominio detectada: {domain_family or 'general'}. "
        f"Keys recomendadas por familia (sin forzar valores): {json.dumps(domain_keys, ensure_ascii=False)}. "
        f"exclude_keys ya resueltas: {json.dumps(exclude_keys, ensure_ascii=False)}. "
        "Esquema exacto: "
        "{"
        '"nombre":"...",'
        '"kind":"perfil|contexto|plantilla",'
        '"base_questions":[{"key":"...","question":"...","required":false,"why":"..."}],'
        '"extras_fields_sugeridos":[{"key":"...","label":"...","help":"...","example":"...","default":""}],'
        '"extras_questions":[{"key":"...","question":"...","required":false,"why":"..."}],'
        '"draft":{...}'
        "}. "
        "En draft deja cadenas vacías o listas vacías cuando falte información."
    )


def _clean_non_empty_map(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        clean_key = _strip_text(key)
        if not clean_key or value in (None, "", [], {}):
            continue
        cleaned[clean_key] = value
    return cleaned


def _final_system_prompt(kind: str, name: str) -> str:
    return (
        "Eres un asistente experto en diseño de maestros para PROM-9. "
        "Devuelve SOLO JSON maestro; usa answers; no inventes; "
        "rellena primero campos base críticos, luego extras_fields útiles y luego el resto. "
        "Prioriza memoria+answers del usuario por encima de masters_activos si hay conflicto. "
        "No clones el maestro activo: genera uno actualizado a partir de la conversación. "
        "lo que no se indique queda en '' o listas vacías; "
        "extras_fields incluir sugerencias útiles si el usuario no las definió. "
        "No markdown, no texto adicional. "
        "No inventes datos personales/empresa/ubicación. "
        f"Tipo: {kind}. Nombre esperado: {name}.\n\n{_system_prompt(kind, name)}"
    )


def _create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI no instalado. Instala el paquete 'openai' para usar el Asistente IA.") from exc
    return OpenAI(api_key=_load_api_key())


def _request_json(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    client = _create_client()
    response = client.chat.completions.create(
        model=MODEL_DEFAULT,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw_content = ""
    if response.choices:
        raw_content = _strip_text(response.choices[0].message.content)
    if not raw_content:
        raise RuntimeError("OpenAI no devolvió contenido para generar el maestro.")
    return _extract_json(raw_content)


def generate_master_diagnosis(
    kind: str,
    name: str,
    description: str,
    memory: dict[str, Any] | None = None,
    max_questions: int = 8,
    masters_activos: dict[str, Any] | None = None,
    exclude_keys: list[str] | None = None,
    focus: str = "balanced",
) -> dict[str, Any]:
    normalized_kind = _strip_text(kind).lower()
    normalized_name = _strip_text(name)
    normalized_description = _strip_text(description)

    if normalized_kind not in _ALLOWED_KINDS:
        raise RuntimeError("Tipo de maestro inválido. Usa Perfil, Contexto o Plantilla.")
    if not normalized_name:
        raise RuntimeError("El nombre del maestro es obligatorio.")
    if not normalized_description:
        raise RuntimeError("La descripción es obligatoria para diagnosticar con IA.")

    clean_memory = _clean_non_empty_map(memory)
    clean_ui_context = masters_activos if isinstance(masters_activos, dict) else {}
    safe_max_questions = max(1, min(int(max_questions), 20))
    domain_family = _detect_domain_family(normalized_description)
    normalized_focus = _strip_text(focus).lower()
    if normalized_focus not in {"base", "extras", "balanced"}:
        normalized_focus = "balanced"

    clean_exclude_keys: list[str] = []
    for key in (exclude_keys or []):
        clean_key = _strip_text(key)
        if clean_key:
            clean_exclude_keys.append(clean_key)

    payload = _request_json(
        _diagnosis_system_prompt(
            normalized_kind,
            normalized_name,
            safe_max_questions,
            domain_family,
            clean_exclude_keys,
        ),
        (
            f"Diagnostica el maestro tipo {normalized_kind} con nombre '{normalized_name}'. "
            f"Descripción funcional: {normalized_description}. "
            f"En esta iteración prioriza: {normalized_focus}. "
            "Memoria confirmada (respuestas acumuladas): "
            f"{json.dumps(clean_memory, ensure_ascii=False)}. "
            "No preguntes por keys presentes en exclude_keys. "
            f"exclude_keys: {json.dumps(clean_exclude_keys, ensure_ascii=False)}. "
            "Maestros activos de la UI (perfil/contexto/plantilla seleccionada), para no reinventar datos: "
            f"{json.dumps(clean_ui_context, ensure_ascii=False)}"
        ),
    )
    return _normalize_diagnosis(normalized_kind, payload, normalized_name, safe_max_questions)


def generate_master_with_answers(
    kind: str,
    name: str,
    description: str,
    memory: dict[str, Any] | None = None,
    answers: dict[str, Any] | None = None,
    masters_activos: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_kind = _strip_text(kind).lower()
    normalized_name = _strip_text(name)
    normalized_description = _strip_text(description)

    if normalized_kind not in _ALLOWED_KINDS:
        raise RuntimeError("Tipo de maestro inválido. Usa Perfil, Contexto o Plantilla.")
    if not normalized_name:
        raise RuntimeError("El nombre del maestro es obligatorio.")
    if not normalized_description:
        raise RuntimeError("La descripción es obligatoria para generar con IA.")

    if answers is None:
        answers = memory if isinstance(memory, dict) else {}
        memory = {}

    clean_answers = _clean_non_empty_map(answers)
    clean_memory = _clean_non_empty_map(memory)

    clean_ui_context = masters_activos if isinstance(masters_activos, dict) else {}

    payload = _request_json(
        _final_system_prompt(normalized_kind, normalized_name),
        (
            f"Genera el maestro tipo {normalized_kind} con nombre '{normalized_name}'. "
            f"Descripción funcional: {normalized_description}. "
            "Usa memoria confirmada previa: "
            f"{json.dumps(clean_memory, ensure_ascii=False)}. "
            "Usa estas respuestas del usuario para completar faltantes: "
            f"{json.dumps(clean_answers, ensure_ascii=False)}. "
            "Maestros activos de la UI (perfil/contexto/plantilla seleccionada), úsalo para completar sin inventar "
            "priorizando campos base y extras_fields y luego listas: "
            f"{json.dumps(clean_ui_context, ensure_ascii=False)}"
        ),
    )
    normalized = _normalize(normalized_kind, payload, normalized_name)

    missing_required: list[str] = []
    if normalized_kind == "perfil" and not _strip_text(normalized.get("rol_base")):
        missing_required.append("rol_base")
    if normalized_kind == "contexto" and not _strip_text(normalized.get("rol_contextual")):
        missing_required.append("rol_contextual")
    if normalized_kind == "plantilla" and not _strip_text(normalized.get("label")):
        missing_required.append("label")

    if missing_required:
        raise RuntimeError(
            "Faltan campos críticos requeridos para generar el maestro: " + ", ".join(missing_required)
        )
    return normalized


def generate_master(kind: str, name: str, description: str) -> dict[str, Any]:
    """Genera un maestro normalizado usando OpenAI Chat Completions."""
    normalized_kind = _strip_text(kind).lower()
    normalized_name = _strip_text(name)
    normalized_description = _strip_text(description)

    if normalized_kind not in _ALLOWED_KINDS:
        raise RuntimeError("Tipo de maestro inválido. Usa Perfil, Contexto o Plantilla.")
    if not normalized_name:
        raise RuntimeError("El nombre del maestro es obligatorio.")
    if not normalized_description:
        raise RuntimeError("La descripción es obligatoria para generar con IA.")

    payload = _request_json(
        _system_prompt(normalized_kind, normalized_name),
        (
            f"Genera el maestro tipo {normalized_kind} con nombre '{normalized_name}'. "
            f"Descripción funcional: {normalized_description}"
        ),
    )
    return _normalize(normalized_kind, payload, normalized_name)


# Mini smoke test manual:
# 1) Abrir Asistente IA, elegir Perfil, escribir nombre y descripción breve.
# 2) Pulsar "Usar datos del maestro seleccionado" y verificar memoria confirmada.
# 3) Pulsar Diagnosticar en profundidad Rápido/Normal/Profundo y validar bloques Base/Extras.
# 4) Añadir respuestas clave:valor (incluyendo listas con ; y JSON en extras) y Generar maestro.
# 5) Confirmar que el draft final reutiliza memoria+maestros activos sin inventar identidad.
