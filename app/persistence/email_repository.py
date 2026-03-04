"""Repositorio de persistencia para emails."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable


class EmailRepository:
    """Encapsula todas las operaciones SQLite de emails."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self.ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gmail_id TEXT UNIQUE,
                    thread_id TEXT,
                    sender TEXT,
                    recipient TEXT,
                    subject TEXT,
                    body_text TEXT,
                    body_html TEXT,
                    received_at TEXT,
                    status TEXT DEFAULT 'new',
                    category TEXT DEFAULT 'pending'
                )
                """
            )
            cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(emails)").fetchall()
            }
            if "category" not in cols:
                conn.execute(
                    "ALTER TABLE emails ADD COLUMN category TEXT DEFAULT 'pending'"
                )

    def get_emails_by_category(self, category: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    gmail_id,
                    sender,
                    recipient,
                    subject,
                    body_text,
                    body_html,
                    received_at,
                    status,
                    category
                FROM emails
                WHERE category = ?
                ORDER BY datetime(received_at) DESC, id DESC
                """,
                (category,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_emails_by_ids(self, ids: Iterable[int]) -> list[dict[str, Any]]:
        ids = list(ids)
        if not ids:
            return []

        placeholders = ",".join("?" for _ in ids)
        query = f"""
            SELECT
                id,
                gmail_id,
                sender,
                recipient,
                subject,
                body_text,
                body_html,
                received_at,
                status,
                category
            FROM emails
            WHERE id IN ({placeholders})
        """

        with self._connect() as conn:
            rows = conn.execute(query, ids).fetchall()
        return [dict(row) for row in rows]


    def upsert_email(self, email: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO emails (
                    gmail_id,
                    thread_id,
                    sender,
                    recipient,
                    subject,
                    body_text,
                    body_html,
                    received_at,
                    status,
                    category
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(gmail_id) DO UPDATE SET
                    thread_id=excluded.thread_id,
                    sender=excluded.sender,
                    recipient=excluded.recipient,
                    subject=excluded.subject,
                    body_text=excluded.body_text,
                    body_html=excluded.body_html,
                    received_at=excluded.received_at,
                    category=excluded.category
                """,
                (
                    email["gmail_id"],
                    email.get("thread_id"),
                    email.get("sender"),
                    email.get("recipient"),
                    email.get("subject"),
                    email.get("body_text"),
                    email.get("body_html"),
                    email.get("received_at"),
                    email.get("status", "new"),
                    email.get("category", "pending"),
                ),
            )

    def update_status(self, gmail_id: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE emails SET status = ? WHERE gmail_id = ?",
                (status, gmail_id),
            )

    def delete_emails(self, ids: Iterable[int]) -> None:
        ids = list(ids)
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self._connect() as conn:
            conn.execute(f"DELETE FROM emails WHERE id IN ({placeholders})", ids)

    def bulk_update_status(self, ids: Iterable[int], status: str) -> None:
        ids = list(ids)
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE emails SET status = ? WHERE id IN ({placeholders})",
                [status, *ids],
            )
