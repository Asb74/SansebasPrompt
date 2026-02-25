"""Asistente IA para generar maestros PROM-9™."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any


_ALLOWED_KINDS = {"perfil", "contexto", "plantilla"}


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
        f"El tipo de maestro es: {kind}. Nombre esperado: {name}.\n\n{schemas[kind]}"
    )


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

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("OpenAI no instalado. Instala el paquete 'openai' para usar el Asistente IA.") from exc

    api_key = _load_api_key()

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": _system_prompt(normalized_kind, normalized_name)},
            {
                "role": "user",
                "content": (
                    f"Genera el maestro tipo {normalized_kind} con nombre '{normalized_name}'. "
                    f"Descripción funcional: {normalized_description}"
                ),
            },
        ],
    )

    raw_content = ""
    if response.choices:
        raw_content = _strip_text(response.choices[0].message.content)
    if not raw_content:
        raise RuntimeError("OpenAI no devolvió contenido para generar el maestro.")

    payload = _extract_json(raw_content)
    return _normalize(normalized_kind, payload, normalized_name)
