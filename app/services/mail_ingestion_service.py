"""Servicio de ingesta y clasificación de emails."""

from __future__ import annotations

from dataclasses import dataclass

from app.persistence.email_repository import EmailRepository


@dataclass
class IngestedEmail:
    gmail_id: str
    thread_id: str | None
    sender: str | None
    recipient: str | None
    subject: str | None
    body_text: str | None
    body_html: str | None
    received_at: str | None


class MailIngestionService:
    """Ingesta emails y les asigna una categoría inicial."""

    MARKETING_KEYWORDS = (
        "oferta",
        "descuento",
        "promo",
        "publicidad",
        "newsletter",
    )

    def __init__(self, repository: EmailRepository) -> None:
        self._repository = repository
        self._repository.ensure_schema()

    def classify_email(self, subject: str | None, body_text: str | None) -> str:
        """Clasificación base preparada para reemplazarse por AIClassifierService."""
        blob = f"{subject or ''} {body_text or ''}".lower()
        if any(keyword in blob for keyword in self.MARKETING_KEYWORDS):
            return "marketing"
        return "priority"

    def ingest_email(self, email: IngestedEmail) -> None:
        """Ejemplo de ingesta con clasificación y persistencia."""
        category = self.classify_email(email.subject, email.body_text)
        self._repository.upsert_email(
            {
                "gmail_id": email.gmail_id,
                "thread_id": email.thread_id,
                "sender": email.sender,
                "recipient": email.recipient,
                "subject": email.subject,
                "body_text": email.body_text,
                "body_html": email.body_html,
                "received_at": email.received_at,
                "status": "new",
                "category": category,
            }
        )
