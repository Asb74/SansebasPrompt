"""Exportación de prompts a PDF con ReportLab."""

from __future__ import annotations

from pathlib import Path


def export_prompt_to_pdf(titulo: str, metadata: dict, prompt: str, output_path: str) -> str:
    """Genera un PDF legible con metadatos y contenido del prompt.

    Lanza RuntimeError si ReportLab no está instalado.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise RuntimeError(
            "ReportLab no está instalado. Ejecuta: pip install reportlab"
        ) from exc

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(str(destination), pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph(titulo, styles["Title"]), Spacer(1, 12)]

    for key, value in metadata.items():
        story.append(Paragraph(f"<b>{key}:</b> {value}", styles["BodyText"]))
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 12))
    for line in prompt.splitlines():
        safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(safe_line if safe_line else " ", styles["Code"]))

    doc.build(story)
    return str(destination)
