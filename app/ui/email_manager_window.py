"""Ventana avanzada de gestión de emails."""

from __future__ import annotations

from datetime import datetime
import re
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from app.persistence.email_repository import EmailRepository

try:
    from app.ui.excel_tree_filter import ExcelTreeFilter
except ImportError:  # pragma: no cover
    ExcelTreeFilter = None  # type: ignore[assignment]


class EmailManagerWindow(tk.Toplevel):
    """Gestor de emails con tabs, filtro Excel y vista previa contextual."""

    COLUMNS = (
        "id",
        "subject",
        "sender",
        "received_at",
        "status",
    )

    def __init__(
        self,
        master: tk.Misc,
        email_repository: EmailRepository,
        create_note_from_email: Callable[[dict], None],
        download_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Email Manager")
        self.geometry("1200x760")

        self._repo = email_repository
        self._create_note_from_email = create_note_from_email
        self._download_callback = download_callback

        self._category_var = tk.StringVar(value="priority")
        self._rows_by_item: dict[str, dict] = {}

        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        self.rowconfigure(4, weight=1)

        top_actions = ttk.Frame(self)
        top_actions.grid(row=0, column=0, sticky="ew", padx=8, pady=8)

        ttk.Button(top_actions, text="Descargar", command=self._download_emails).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(
            top_actions,
            text="Crear Nota seleccionadas",
            command=self._create_notes_selected,
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            top_actions,
            text="Eliminar seleccionadas",
            command=self._delete_selected,
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            top_actions,
            text="Marcar como ignoradas",
            command=self._mark_selected_ignored,
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_actions, text="Seleccionar todo", command=self._select_all).pack(
            side=tk.LEFT, padx=10
        )
        ttk.Button(
            top_actions, text="Deseleccionar todo", command=self._clear_selection
        ).pack(side=tk.LEFT)

        tabs = ttk.Notebook(self)
        tabs.grid(row=1, column=0, sticky="ew", padx=8)
        tab_priority = ttk.Frame(tabs)
        tab_marketing = ttk.Frame(tabs)
        tabs.add(tab_priority, text="Prioritarios")
        tabs.add(tab_marketing, text="Publicidad")

        tabs.bind("<<NotebookTabChanged>>", self._on_tab_change)

        if ExcelTreeFilter:
            filter_host = ttk.Frame(self)
            filter_host.grid(row=2, column=0, sticky="ew", padx=8, pady=(6, 0))
            self._filter_engine = ExcelTreeFilter(filter_host)
        else:
            self._filter_engine = None

        table_frame = ttk.Frame(self)
        table_frame.grid(row=3, column=0, sticky="nsew", padx=8, pady=8)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_frame,
            columns=self.COLUMNS,
            show="headings",
            selectmode="extended",
        )
        headers = {
            "id": "ID",
            "subject": "Asunto",
            "sender": "Remitente",
            "received_at": "Fecha",
            "status": "Estado",
        }
        widths = {
            "id": 70,
            "subject": 500,
            "sender": 250,
            "received_at": 170,
            "status": 150,
        }
        for col in self.COLUMNS:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=widths[col], anchor="w")

        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=y_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")

        self.tree.bind("<<TreeviewSelect>>", self._update_preview)

        preview_frame = ttk.LabelFrame(self, text="Vista previa")
        preview_frame.grid(row=4, column=0, sticky="nsew", padx=8, pady=(0, 8))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(1, weight=1)

        self.preview_meta = tk.StringVar(value="Selecciona un email para ver detalle")
        ttk.Label(preview_frame, textvariable=self.preview_meta).grid(
            row=0, column=0, sticky="ew", padx=8, pady=(8, 4)
        )

        self.preview_text = tk.Text(preview_frame, wrap="word", height=9)
        self.preview_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.preview_text.configure(state=tk.DISABLED)

    def _on_tab_change(self, event: tk.Event) -> None:
        notebook = event.widget
        tab_text = notebook.tab(notebook.select(), "text")
        self._category_var.set("priority" if tab_text == "Prioritarios" else "marketing")
        self.refresh_data()

    def refresh_data(self) -> None:
        category = self._category_var.get()
        rows = self._repo.get_emails_by_category(category)

        for item_id in self.tree.get_children():
            self.tree.delete(item_id)

        self._rows_by_item.clear()

        for row in rows:
            values = (
                row["id"],
                row.get("subject") or "(sin asunto)",
                row.get("sender") or "",
                self._format_received_at(row.get("received_at")),
                row.get("status") or "new",
            )
            item_id = self.tree.insert("", tk.END, values=values)
            self._rows_by_item[item_id] = row

        if self._filter_engine:
            self._attach_filter(rows)

        self._clear_preview()

    def _attach_filter(self, rows: list[dict]) -> None:
        """Conecta el motor ExcelTreeFilter reutilizable sin duplicar lógica."""
        if hasattr(self._filter_engine, "bind_tree"):
            self._filter_engine.bind_tree(self.tree, rows=rows, columns=self.COLUMNS)
        elif hasattr(self._filter_engine, "attach"):
            self._filter_engine.attach(self.tree, rows=rows, columns=self.COLUMNS)

    def _selected_ids(self) -> list[int]:
        ids: list[int] = []
        for item in self.tree.selection():
            row = self._rows_by_item.get(item)
            if row:
                ids.append(int(row["id"]))
        return ids

    def _create_notes_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Email Manager", "No hay emails seleccionados.")
            return

        emails = self._repo.get_emails_by_ids(ids)
        for email in emails:
            self._create_note_from_email(email)

        self._repo.bulk_update_status(ids, "converted_to_note")
        self.refresh_data()

    def _delete_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        if not messagebox.askyesno(
            "Confirmar",
            "Se eliminarán los emails de SQLite (no de Gmail). ¿Continuar?",
        ):
            return

        self._repo.delete_emails(ids)
        self.refresh_data()

    def _mark_selected_ignored(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        self._repo.bulk_update_status(ids, "ignored")
        self.refresh_data()

    def _select_all(self) -> None:
        self.tree.selection_set(self.tree.get_children())
        self._update_preview(None)

    def _clear_selection(self) -> None:
        self.tree.selection_remove(self.tree.selection())
        self._clear_preview()

    def _update_preview(self, _event: tk.Event | None) -> None:
        selection = self.tree.selection()
        if len(selection) != 1:
            self._clear_preview()
            return

        row = self._rows_by_item.get(selection[0])
        if not row:
            self._clear_preview()
            return

        subject = row.get("subject") or "(sin asunto)"
        sender = row.get("sender") or "(desconocido)"
        received = self._format_received_at(row.get("received_at"))
        body_text = (row.get("body_text") or "").strip()
        if not body_text and row.get("body_html"):
            body_text = self._strip_html(row["body_html"])

        self.preview_meta.set(f"Asunto: {subject} | Remitente: {sender} | Fecha: {received}")
        self.preview_text.configure(state=tk.NORMAL)
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", body_text or "(sin contenido)")
        self.preview_text.configure(state=tk.DISABLED)

    def _clear_preview(self) -> None:
        self.preview_meta.set("Selecciona un email para ver detalle")
        self.preview_text.configure(state=tk.NORMAL)
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.configure(state=tk.DISABLED)

    def _download_emails(self) -> None:
        if self._download_callback:
            self._download_callback()
            self.refresh_data()

    @staticmethod
    def _strip_html(html: str) -> str:
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _format_received_at(value: str | None) -> str:
        if not value:
            return ""
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
            try:
                dt = datetime.strptime(value, fmt)
                return dt.strftime("%d/%m/%Y %H:%M")
            except ValueError:
                continue
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return value
