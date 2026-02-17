"""Utilidades para lectura y preparación de archivos adjuntos."""

from __future__ import annotations

from pathlib import Path

MAX_CHARS_DEFAULT = 15000
TIPOS_SOPORTADOS = {".py", ".json", ".txt", ".md", ".pdf"}


def validar_tipo_archivo(path: Path) -> bool:
    """Valida si la extensión del archivo está soportada."""
    return path.suffix.lower() in TIPOS_SOPORTADOS


def dividir_en_bloques(texto: str, max_chars: int = MAX_CHARS_DEFAULT) -> list[str]:
    """Divide un texto en bloques de tamaño máximo sin cortar silenciosamente."""
    if max_chars <= 0:
        raise ValueError("max_chars debe ser mayor a cero")

    if len(texto) <= max_chars:
        return [texto]

    bloques: list[str] = []
    inicio = 0
    while inicio < len(texto):
        fin = inicio + max_chars
        bloques.append(texto[inicio:fin])
        inicio = fin
    return bloques


def extraer_texto_pdf(path: Path) -> str:
    """Extrae texto de un PDF usando pypdf."""
    try:
        from pypdf import PdfReader
    except Exception as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError("No se pudo importar pypdf para leer archivos PDF.") from exc

    try:
        reader = PdfReader(str(path))
        partes: list[str] = []
        for page in reader.pages:
            partes.append(page.extract_text() or "")
        return "\n".join(partes).strip()
    except Exception as exc:
        raise RuntimeError(f"No se pudo leer el PDF '{path.name}': {exc}") from exc


def _leer_archivo_texto(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return extraer_texto_pdf(path)

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"El archivo '{path.name}' parece binario o no es texto soportado.") from exc


def leer_archivos(paths: list[Path], max_chars: int = MAX_CHARS_DEFAULT) -> str:
    """Lee adjuntos y devuelve una sección lista para incorporar al prompt."""
    if not paths:
        return ""

    secciones: list[str] = ["## Archivos adjuntos para análisis"]

    for path in paths:
        archivo = Path(path)
        if not archivo.exists() or not archivo.is_file():
            raise RuntimeError(f"No existe el archivo adjunto: {archivo}")
        if not validar_tipo_archivo(archivo):
            raise RuntimeError(f"Tipo de archivo no soportado: {archivo.name}")

        contenido = _leer_archivo_texto(archivo)
        bloques = dividir_en_bloques(contenido, max_chars=max_chars)

        if len(bloques) == 1:
            secciones.append(f"\n--- {archivo.name} ---\n{bloques[0]}")
            continue

        secciones.append(
            f"\n--- {archivo.name} ---\n"
            f"[AVISO] Archivo extenso dividido en {len(bloques)} bloques de hasta {max_chars} caracteres."
        )
        for idx, bloque in enumerate(bloques, start=1):
            secciones.append(f"\n[Bloque {idx}/{len(bloques)}]\n{bloque}")

    return "\n".join(secciones).strip()
