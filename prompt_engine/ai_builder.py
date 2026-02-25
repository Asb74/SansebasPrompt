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


def _normalize_diagnosis(kind: str, payload: dict[str, Any], name: str, max_questions: int) -> dict[str, Any]:
    preguntas_raw = payload.get("preguntas")
    preguntas: list[dict[str, Any]] = []
    if isinstance(preguntas_raw, list):
        for item in preguntas_raw:
            if not isinstance(item, dict):
                continue
            key = _strip_text(item.get("key"))
            question = _strip_text(item.get("question"))
            if not key or not question:
                continue
            required = bool(item.get("required", False))
            why = _strip_text(item.get("why"))
            preguntas.append({"key": key, "question": question, "required": required, "why": why})
    preguntas = preguntas[:max(1, min(max_questions, 20))]

    normalized = {
        "nombre": _strip_text(payload.get("nombre")) or name,
        "kind": kind,
        "slots": _normalize_slots(payload.get("slots")),
        "preguntas": preguntas,
        "extras_fields_sugeridos": _as_fields_list(payload.get("extras_fields_sugeridos")),
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


def _diagnosis_system_prompt(kind: str, name: str, depth: int, max_questions: int) -> str:
    return (
        "Eres un asistente experto en diseño de maestros para PROM-9. "
        "Devuelve SOLO JSON del esquema diagnosis; no markdown; no texto; no inventes; si falta info, pregunta. "
        "No inventes datos de identidad (empresa, ubicación, personas, clientes). "
        f"Genera como máximo {max_questions} preguntas, priorizando calidad del maestro. "
        f"Profundidad solicitada: {depth} (1=rápido, 2=normal, 3=profundo). "
        "Usa keys simples y estables en snake_case. "
        f"Tipo: {kind}. Nombre esperado: {name}. "
        "Esquema exacto: "
        "{"
        '"nombre":"...",'
        '"kind":"perfil|contexto|plantilla",'
        '"slots":{"campo":"known|missing|unclear"},'
        '"preguntas":[{"key":"...","question":"...","required":false,"why":"..."}],'
        '"extras_fields_sugeridos":[{"key":"...","label":"...","help":"...","example":"...","default":""}],'
        '"draft":{...}'
        "}. "
        "En draft deja cadenas vacías o listas vacías cuando falte información."
    )


def _final_system_prompt(kind: str, name: str) -> str:
    return (
        "Eres un asistente experto en diseño de maestros para PROM-9. "
        "Devuelve SOLO JSON maestro; usa answers; no inventes; "
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
    depth: int = 2,
    max_questions: int = 8,
    ui_context: dict[str, Any] | None = None,
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

    clean_memory = memory if isinstance(memory, dict) else {}
    clean_ui_context = ui_context if isinstance(ui_context, dict) else {}
    safe_depth = max(1, min(int(depth), 3))
    safe_max_questions = max(1, min(int(max_questions), 20))

    payload = _request_json(
        _diagnosis_system_prompt(normalized_kind, normalized_name, safe_depth, safe_max_questions),
        (
            f"Diagnostica el maestro tipo {normalized_kind} con nombre '{normalized_name}'. "
            f"Descripción funcional: {normalized_description}. "
            "Memoria confirmada (respuestas acumuladas): "
            f"{json.dumps(clean_memory, ensure_ascii=False)}. "
            "Contexto activo de la UI (perfil/contexto/plantilla): "
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
    ui_context: dict[str, Any] | None = None,
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

    clean_answers: dict[str, Any] = {}
    for key, value in (answers or {}).items():
        clean_key = _strip_text(key)
        if clean_key:
            clean_answers[clean_key] = value

    clean_memory: dict[str, Any] = {}
    for key, value in (memory or {}).items():
        clean_key = _strip_text(key)
        if clean_key:
            clean_memory[clean_key] = value

    clean_ui_context = ui_context if isinstance(ui_context, dict) else {}

    payload = _request_json(
        _final_system_prompt(normalized_kind, normalized_name),
        (
            f"Genera el maestro tipo {normalized_kind} con nombre '{normalized_name}'. "
            f"Descripción funcional: {normalized_description}. "
            "Usa memoria confirmada previa: "
            f"{json.dumps(clean_memory, ensure_ascii=False)}. "
            "Usa estas respuestas del usuario para completar faltantes: "
            f"{json.dumps(clean_answers, ensure_ascii=False)}. "
            "Contexto activo de la UI (perfil/contexto/plantilla): "
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
# - Diagnosticar Perfil con descripción mínima debería devolver preguntas + draft
#   sin romper aunque falten rol_base/empresa/ubicacion.
