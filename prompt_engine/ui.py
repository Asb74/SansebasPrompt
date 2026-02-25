"""Interfaz gráfica Tkinter para PROM-9™ Prompt Engine."""

from __future__ import annotations

import json
import csv
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

from .widgets import DictationField

from .app_paths import ensure_user_dirs, get_db_path, get_templates_dir
from .ai_builder import generate_master_diagnosis, generate_master_with_answers
from .attachments import validar_tipo_archivo
from .database import init_db
from .motor import generar_prompt
from .pdf_export import export_prompt_to_pdf
from .schemas import Tarea, generate_task_id, task_id_to_human
from .storage_sqlite import (
    insert_perfil,
    delete_contexto,
    delete_perfil,
    delete_plantilla,
    eliminar_tarea,
    get_contextos,
    get_perfiles,
    get_plantillas,
    guardar_perfiles,
    guardar_tarea,
    insert_contexto,
    listar_tareas,
    update_plantilla,
    update_perfil,
    update_contexto,
    upsert_plantilla,
)
from .voice_input import VoiceInput

BASE_FIELDS = [
    ("titulo", "Título"),
    ("objetivo", "Objetivo"),
    ("situacion", "Tipo de situación"),
    ("urgencia", "Urgencia"),
    ("contexto_detallado", "Contexto detallado"),
    ("restricciones", "Restricciones"),
]

BASE_HELP = {
    "titulo": ("Nombre breve de la tarea.", "Plan comercial Q4 para clientes B2B"),
    "objetivo": ("Resultado concreto esperado.", "Diseñar una propuesta de upselling en 30 días"),
    "situacion": ("Problema o caso a resolver.", "Incidencia técnica en sistema de pedidos"),
    "urgencia": ("Prioridad temporal.", "Alta: debe resolverse hoy"),
    "contexto_detallado": ("Contexto operativo adicional.", "2 centros logísticos y 40 usuarios"),
    "restricciones": ("Límites de la solución.", "No usar herramientas de pago"),
}

def resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base_path / relative_path


def ensure_bootstrap_assets() -> None:
    """Prepara DB y plantillas per-user en primer arranque."""
    ensure_user_dirs()

    db_path = get_db_path()
    if not db_path.exists():
        seed_db_path = resource_path("seed/prom9_seed.sqlite")
        if seed_db_path.exists():
            shutil.copy2(seed_db_path, db_path)

    templates_dir = get_templates_dir()
    has_user_templates = any(templates_dir.glob("*.py"))
    if not has_user_templates:
        bundled_templates_dir = resource_path("prompt_engine/plantillas")
        if bundled_templates_dir.exists():
            for source_tpl in bundled_templates_dir.glob("*.py"):
                shutil.copy2(source_tpl, templates_dir / source_tpl.name)

    init_db()


def _set_app_icon(window: tk.Tk | tk.Toplevel) -> None:
    icon_path = resource_path("icono_app.ico")
    if not icon_path.exists():
        return
    try:
        window.iconbitmap(default=str(icon_path))
    except tk.TclError:
        pass


class JsonRecordDialog(tk.Toplevel):
    """Modal para crear/editar registros tipo JSON (clave-valor)."""

    def __init__(self, master: tk.Widget, title: str, initial: dict | None = None) -> None:
        super().__init__(master)
        _set_app_icon(self)
        self.title(title)
        self.transient(master)
        self.grab_set()
        self.result: dict | None = None
        self.rows: list[tuple[ttk.Entry, ttk.Entry]] = []

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Clave").grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="Valor").grid(row=0, column=1, sticky="w")

        for idx, (key, value) in enumerate((initial or {"nombre": ""}).items(), start=1):
            self._add_row(frame, idx, str(key), str(value))

        controls = ttk.Frame(frame)
        controls.grid(row=999, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(controls, text="+ Campo", command=lambda: self._add_row(frame, len(self.rows) + 1, "", "")).pack(
            side="left"
        )
        ttk.Button(controls, text="Cancelar", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(controls, text="Guardar", command=self._save).pack(side="right")

    def _add_row(self, parent: ttk.Frame, row: int, key: str, value: str) -> None:
        key_entry = ttk.Entry(parent)
        key_entry.insert(0, key)
        key_entry.grid(row=row, column=0, sticky="ew", pady=4, padx=(0, 6))

        value_entry = ttk.Entry(parent)
        value_entry.insert(0, value)
        value_entry.grid(row=row, column=1, sticky="ew", pady=4)

        self.rows.append((key_entry, value_entry))

    def _save(self) -> None:
        payload: dict[str, str] = {}
        for key_entry, value_entry in self.rows:
            key = key_entry.get().strip()
            if key:
                payload[key] = value_entry.get().strip()

        if not payload.get("nombre"):
            messagebox.showwarning("Validación", "El campo 'nombre' es obligatorio.", parent=self)
            return
        self.result = payload
        self.destroy()


class JsonListManagerDialog(tk.Toplevel):
    """Gestor genérico para listas de registros JSON."""

    def __init__(self, master: tk.Widget, title: str, records: list[dict]) -> None:
        super().__init__(master)
        _set_app_icon(self)
        self.title(title)
        self.geometry("900x520")
        self.transient(master)
        self.grab_set()
        self.saved = False
        self.records = [dict(item) for item in records]

        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ttk.Label(left, text="Listado").pack(anchor="w")
        self.listbox = tk.Listbox(left, exportselection=False)
        self.listbox.pack(fill="both", expand=True, pady=(6, 8))
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        buttons = ttk.Frame(left)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Nuevo", command=self._new).pack(side="left")
        ttk.Button(buttons, text="Editar", command=self._edit).pack(side="left", padx=6)

        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        ttk.Label(right, text="Detalle JSON").pack(anchor="w")
        self.detail = ScrolledText(right, wrap="word")
        self.detail.pack(fill="both", expand=True, pady=(6, 8))
        self.detail.configure(state="disabled")

        footer = ttk.Frame(main)
        footer.grid(row=1, column=0, columnspan=2, sticky="ew")
        ttk.Button(footer, text="Cancelar", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Guardar cambios", command=self._save_and_close).pack(side="right")

        self._refresh()

    def _refresh(self) -> None:
        self.listbox.delete(0, "end")
        for item in self.records:
            self.listbox.insert("end", item.get("nombre", "(sin nombre)"))
        if self.records:
            self.listbox.selection_set(0)
            self._on_select(None)

    def _on_select(self, _event) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        record = self.records[selection[0]]
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", json.dumps(record, ensure_ascii=False, indent=2))
        self.detail.configure(state="disabled")

    def _new(self) -> None:
        modal = JsonRecordDialog(self, "Nuevo registro")
        self.wait_window(modal)
        if modal.result:
            self.records.append(modal.result)
            self._refresh()

    def _edit(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        modal = JsonRecordDialog(self, "Editar registro", initial=self.records[idx])
        self.wait_window(modal)
        if modal.result:
            self.records[idx] = modal.result
            self._refresh()
            self.listbox.selection_set(idx)
            self._on_select(None)

    def _save_and_close(self) -> None:
        self.saved = True
        self.destroy()


class ProfileEditorDialog(tk.Toplevel):
    def __init__(self, master: tk.Widget, profile: dict | None = None) -> None:
        super().__init__(master)
        _set_app_icon(self)
        self.title("Perfil")
        self.geometry("560x620")
        self.transient(master)
        self.grab_set()
        self.result: dict | None = None
        initial = dict(profile or {})
        extras_fields = initial.get("extras_fields")
        if isinstance(extras_fields, list):
            self.extras_fields: list[dict[str, str]] = [
                {
                    "key": str(item.get("key", "")).strip(),
                    "label": str(item.get("label", "")).strip(),
                    "help": str(item.get("help", "")).strip(),
                    "example": str(item.get("example", "")).strip(),
                    "default": str(item.get("default", "")).strip(),
                }
                for item in extras_fields
                if isinstance(item, dict) and str(item.get("key", "")).strip()
            ]
        else:
            self.extras_fields = []

        self.fields: dict[str, tk.Widget] = {}
        form = ttk.Frame(self, padding=12)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        field_defs = [
            ("nombre", "Nombre", False),
            ("rol_base", "Rol base", False),
            ("empresa", "Empresa", False),
            ("ubicacion", "Ubicación", False),
            ("herramientas", "Herramientas (una por línea)", True),
            ("estilo", "Estilo", False),
            ("nivel_tecnico", "Nivel técnico", False),
            ("prioridades", "Prioridades", True),
        ]

        if "rol_base" not in initial and "rol" in initial:
            initial["rol_base"] = initial.get("rol", "")

        for idx, (key, label, multiline) in enumerate(field_defs):
            ttk.Label(form, text=label).grid(row=idx, column=0, sticky="nw", pady=4, padx=(0, 8))
            if multiline:
                widget: tk.Widget = ScrolledText(form, height=4, wrap="word")
                value = initial.get(key, [])
                if isinstance(value, list):
                    widget.insert("1.0", "\n".join(str(item) for item in value))
                else:
                    widget.insert("1.0", str(value))
            else:
                widget = ttk.Entry(form)
                widget.insert(0, str(initial.get(key, "")))
            widget.grid(row=idx, column=1, sticky="ew", pady=4)
            self.fields[key] = widget

        extras_row = len(field_defs)
        extras_frame = ttk.LabelFrame(form, text="Campos personalizados")
        extras_frame.grid(row=extras_row, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        extras_frame.columnconfigure(0, weight=1)
        extras_frame.rowconfigure(0, weight=1)
        form.rowconfigure(extras_row, weight=1)

        self.extras_listbox = tk.Listbox(extras_frame, height=7)
        self.extras_listbox.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)

        extras_buttons = ttk.Frame(extras_frame)
        extras_buttons.grid(row=0, column=1, sticky="ns", padx=(4, 8), pady=8)
        ttk.Button(extras_buttons, text="Añadir", command=self._add_extra).pack(fill="x", pady=(0, 6))
        ttk.Button(extras_buttons, text="Editar", command=self._edit_extra).pack(fill="x", pady=6)
        ttk.Button(extras_buttons, text="Eliminar", command=self._delete_extra).pack(fill="x", pady=(6, 0))
        self._refresh_extras()

        actions = ttk.Frame(form)
        actions.grid(row=extras_row + 1, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(actions, text="Cancelar", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(actions, text="Guardar", command=self._save).pack(side="right")

    def _refresh_extras(self) -> None:
        self.extras_listbox.delete(0, tk.END)
        for item in self.extras_fields:
            label = item.get("label") or item.get("key", "")
            self.extras_listbox.insert(tk.END, f"{label} ({item.get('key', '')})")

    def _selected_extra_index(self) -> int | None:
        selection = self.extras_listbox.curselection()
        if not selection:
            return None
        return int(selection[0])

    def _extra_editor(self, title: str, initial: dict[str, str] | None = None) -> dict[str, str] | None:
        initial = initial or {}
        dialog = tk.Toplevel(self)
        _set_app_icon(dialog)
        dialog.title(title)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        vars_map = {
            "key": tk.StringVar(value=initial.get("key", "")),
            "label": tk.StringVar(value=initial.get("label", "")),
            "help": tk.StringVar(value=initial.get("help", "")),
            "example": tk.StringVar(value=initial.get("example", "")),
            "default": tk.StringVar(value=initial.get("default", "")),
        }
        labels = {
            "key": "Clave técnica",
            "label": "Etiqueta visible",
            "help": "Descripción",
            "example": "Ejemplo",
            "default": "Valor por defecto (opcional)",
        }

        for row, key in enumerate(["key", "label", "help", "example", "default"]):
            ttk.Label(frame, text=labels[key]).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
            ttk.Entry(frame, textvariable=vars_map[key]).grid(row=row, column=1, sticky="ew", pady=4)

        result: dict[str, str] | None = None

        def save_and_close() -> None:
            nonlocal result
            final_key = vars_map["key"].get().strip()
            if not final_key:
                messagebox.showwarning("Validación", "La clave técnica es obligatoria.", parent=dialog)
                return
            result = {name: var.get().strip() for name, var in vars_map.items()}
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Cancelar", command=dialog.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Guardar", command=save_and_close).pack(side="right")

        dialog.wait_window()
        return result

    def _add_extra(self) -> None:
        edited = self._extra_editor("Añadir campo")
        if not edited:
            return
        self.extras_fields.append(edited)
        self._refresh_extras()

    def _edit_extra(self) -> None:
        idx = self._selected_extra_index()
        if idx is None:
            messagebox.showinfo("Campos personalizados", "Selecciona un campo para editar.", parent=self)
            return
        edited = self._extra_editor("Editar campo", initial=self.extras_fields[idx])
        if not edited:
            return
        self.extras_fields[idx] = edited
        self._refresh_extras()

    def _delete_extra(self) -> None:
        idx = self._selected_extra_index()
        if idx is None:
            messagebox.showinfo("Campos personalizados", "Selecciona un campo para eliminar.", parent=self)
            return
        self.extras_fields.pop(idx)
        self._refresh_extras()

    @staticmethod
    def _read(widget: tk.Widget) -> str:
        if isinstance(widget, tk.Text):
            return widget.get("1.0", "end").strip()
        return widget.get().strip()

    @staticmethod
    def _split_lines(raw: str) -> list[str]:
        return [line.strip() for line in raw.replace(",", "\n").splitlines() if line.strip()]

    def _save(self) -> None:
        payload = {key: self._read(widget) for key, widget in self.fields.items()}
        if not payload["nombre"]:
            messagebox.showwarning("Validación", "El nombre es obligatorio.", parent=self)
            return
        payload["herramientas"] = self._split_lines(payload.get("herramientas", ""))
        payload["prioridades"] = self._split_lines(payload.get("prioridades", ""))
        payload["rol"] = payload.get("rol_base", "")
        payload["extras_fields"] = list(self.extras_fields)
        payload.setdefault("extras", {})
        self.result = payload
        self.destroy()


class ContextEditorDialog(tk.Toplevel):
    def __init__(self, master: tk.Widget, context: dict | None = None) -> None:
        super().__init__(master)
        _set_app_icon(self)
        self.title("Contexto")
        self.geometry("560x560")
        self.transient(master)
        self.grab_set()
        self.result: dict | None = None
        initial = dict(context or {})
        extras_fields = initial.get("extras_fields")
        if isinstance(extras_fields, list):
            self.extras_fields: list[dict[str, str]] = [
                {
                    "key": str(item.get("key", "")).strip(),
                    "label": str(item.get("label", "")).strip(),
                    "help": str(item.get("help", "")).strip(),
                    "example": str(item.get("example", "")).strip(),
                    "default": str(item.get("default", "")).strip(),
                }
                for item in extras_fields
                if isinstance(item, dict) and str(item.get("key", "")).strip()
            ]
        else:
            self.extras_fields = []

        self.fields: dict[str, tk.Widget] = {}
        form = ttk.Frame(self, padding=12)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        field_defs = [
            ("nombre", "Nombre", False),
            ("rol_contextual", "Rol contextual", False),
            ("enfoque", "Enfoque (una por línea)", True),
            ("no_hacer", "No hacer (una por línea)", True),
        ]

        for idx, (key, label, multiline) in enumerate(field_defs):
            ttk.Label(form, text=label).grid(row=idx, column=0, sticky="nw", pady=4, padx=(0, 8))
            if multiline:
                widget: tk.Widget = ScrolledText(form, height=4, wrap="word")
                value = initial.get(key, [])
                if isinstance(value, list):
                    widget.insert("1.0", "\n".join(str(item) for item in value))
                else:
                    widget.insert("1.0", str(value))
            else:
                widget = ttk.Entry(form)
                widget.insert(0, str(initial.get(key, "")))
            widget.grid(row=idx, column=1, sticky="ew", pady=4)
            self.fields[key] = widget

        extras_row = len(field_defs)
        extras_frame = ttk.LabelFrame(form, text="Campos personalizados")
        extras_frame.grid(row=extras_row, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        extras_frame.columnconfigure(0, weight=1)
        extras_frame.rowconfigure(0, weight=1)
        form.rowconfigure(extras_row, weight=1)

        self.extras_listbox = tk.Listbox(extras_frame, height=7)
        self.extras_listbox.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)

        extras_buttons = ttk.Frame(extras_frame)
        extras_buttons.grid(row=0, column=1, sticky="ns", padx=(4, 8), pady=8)
        ttk.Button(extras_buttons, text="Añadir", command=self._add_extra).pack(fill="x", pady=(0, 6))
        ttk.Button(extras_buttons, text="Editar", command=self._edit_extra).pack(fill="x", pady=6)
        ttk.Button(extras_buttons, text="Eliminar", command=self._delete_extra).pack(fill="x", pady=(6, 0))
        self._refresh_extras()

        actions = ttk.Frame(form)
        actions.grid(row=extras_row + 1, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(actions, text="Cancelar", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(actions, text="Guardar", command=self._save).pack(side="right")

    def _refresh_extras(self) -> None:
        self.extras_listbox.delete(0, tk.END)
        for item in self.extras_fields:
            label = item.get("label") or item.get("key", "")
            self.extras_listbox.insert(tk.END, f"{label} ({item.get('key', '')})")

    def _selected_extra_index(self) -> int | None:
        selection = self.extras_listbox.curselection()
        if not selection:
            return None
        return int(selection[0])

    def _extra_editor(self, title: str, initial: dict[str, str] | None = None) -> dict[str, str] | None:
        initial = initial or {}
        dialog = tk.Toplevel(self)
        _set_app_icon(dialog)
        dialog.title(title)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        vars_map = {
            "key": tk.StringVar(value=initial.get("key", "")),
            "label": tk.StringVar(value=initial.get("label", "")),
            "help": tk.StringVar(value=initial.get("help", "")),
            "example": tk.StringVar(value=initial.get("example", "")),
            "default": tk.StringVar(value=initial.get("default", "")),
        }

        rows = [
            ("key", "Clave técnica"),
            ("label", "Etiqueta"),
            ("help", "Descripción"),
            ("example", "Ejemplo"),
            ("default", "Valor por defecto"),
        ]

        for row, (key, label) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
            ttk.Entry(frame, textvariable=vars_map[key]).grid(row=row, column=1, sticky="ew", pady=4)

        result: dict[str, str] = {}

        def _confirm() -> None:
            key = vars_map["key"].get().strip()
            if not key:
                messagebox.showwarning("Campos personalizados", "La clave técnica es obligatoria.", parent=dialog)
                return
            result.update({name: var.get().strip() for name, var in vars_map.items()})
            dialog.destroy()

        actions = ttk.Frame(frame)
        actions.grid(row=len(rows), column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(actions, text="Cancelar", command=dialog.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(actions, text="Guardar", command=_confirm).pack(side="right")

        dialog.wait_window()
        return result or None

    def _add_extra(self) -> None:
        edited = self._extra_editor("Añadir campo")
        if not edited:
            return
        key = edited.get("key", "")
        if any(item.get("key") == key for item in self.extras_fields):
            messagebox.showwarning("Campos personalizados", "La clave ya existe.", parent=self)
            return
        self.extras_fields.append(edited)
        self._refresh_extras()

    def _edit_extra(self) -> None:
        idx = self._selected_extra_index()
        if idx is None:
            messagebox.showinfo("Campos personalizados", "Selecciona un campo para editar.", parent=self)
            return
        edited = self._extra_editor("Editar campo", initial=self.extras_fields[idx])
        if not edited:
            return
        new_key = edited.get("key", "")
        if any(i != idx and item.get("key") == new_key for i, item in enumerate(self.extras_fields)):
            messagebox.showwarning("Campos personalizados", "La clave ya existe.", parent=self)
            return
        self.extras_fields[idx] = edited
        self._refresh_extras()

    def _delete_extra(self) -> None:
        idx = self._selected_extra_index()
        if idx is None:
            messagebox.showinfo("Campos personalizados", "Selecciona un campo para eliminar.", parent=self)
            return
        self.extras_fields.pop(idx)
        self._refresh_extras()

    @staticmethod
    def _read(widget: tk.Widget) -> str:
        if isinstance(widget, tk.Text):
            return widget.get("1.0", "end").strip()
        return widget.get().strip()

    @staticmethod
    def _split_lines(raw: str) -> list[str]:
        return [line.strip() for line in raw.replace(",", "\n").splitlines() if line.strip()]

    def _save(self) -> None:
        payload = {key: self._read(widget) for key, widget in self.fields.items()}
        if not payload["nombre"]:
            messagebox.showwarning("Validación", "El nombre es obligatorio.", parent=self)
            return
        payload["enfoque"] = self._split_lines(payload.get("enfoque", ""))
        payload["no_hacer"] = self._split_lines(payload.get("no_hacer", ""))
        payload["extras_fields"] = list(self.extras_fields)
        self.result = payload
        self.destroy()


class TemplateEditorDialog(tk.Toplevel):
    def __init__(self, master: tk.Widget, template_data: dict[str, object], content: str) -> None:
        super().__init__(master)
        _set_app_icon(self)
        self.template_name = str(template_data.get("nombre", ""))
        self.title(f"Plantilla: {self.template_name}")
        self.geometry("920x680")
        self.transient(master)
        self.grab_set()
        self.result: dict[str, object] | None = None
        self.template_fields: list[dict[str, str]] = [
            {
                "key": str(item.get("key", "")).strip(),
                "label": str(item.get("label", "")).strip(),
                "help": str(item.get("help", "")).strip(),
                "example": str(item.get("example", "")).strip(),
                "default": str(item.get("default", "")).strip(),
            }
            for item in (template_data.get("fields") if isinstance(template_data.get("fields"), list) else [])
            if isinstance(item, dict)
        ]

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(frame)
        notebook.grid(row=0, column=0, sticky="nsew")

        definition_tab = ttk.Frame(notebook, padding=12)
        definition_tab.columnconfigure(0, weight=1)
        definition_tab.rowconfigure(1, weight=1)
        definition_tab.rowconfigure(2, weight=1)
        notebook.add(definition_tab, text="Definición (sin código)")

        label_frame = ttk.Frame(definition_tab)
        label_frame.grid(row=0, column=0, sticky="ew")
        label_frame.columnconfigure(1, weight=1)
        ttk.Label(label_frame, text="Label de plantilla").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.template_label_var = tk.StringVar(value=str(template_data.get("label", "")))
        ttk.Entry(label_frame, textvariable=self.template_label_var).grid(row=0, column=1, sticky="ew")

        fields_frame = ttk.LabelFrame(definition_tab, text="Campos de plantilla")
        fields_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        fields_frame.columnconfigure(0, weight=1)
        fields_frame.rowconfigure(0, weight=1)
        self.fields_listbox = tk.Listbox(fields_frame, exportselection=False, height=8)
        self.fields_listbox.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        fields_buttons = ttk.Frame(fields_frame)
        fields_buttons.grid(row=0, column=1, sticky="ns", padx=(4, 8), pady=8)
        ttk.Button(fields_buttons, text="Añadir", command=self._add_field).pack(fill="x", pady=(0, 6))
        ttk.Button(fields_buttons, text="Editar", command=self._edit_field).pack(fill="x", pady=6)
        ttk.Button(fields_buttons, text="Eliminar", command=self._delete_field).pack(fill="x", pady=(6, 0))
        self._refresh_template_fields()

        examples_frame = ttk.LabelFrame(definition_tab, text="Ejemplos de uso (uno por línea)")
        examples_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        examples_frame.columnconfigure(0, weight=1)
        examples_frame.rowconfigure(0, weight=1)
        self.examples_text = ScrolledText(examples_frame, wrap="word", height=7)
        self.examples_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        examples = template_data.get("ejemplos") if isinstance(template_data.get("ejemplos"), list) else []
        self.examples_text.insert("1.0", "\n".join(str(item) for item in examples if str(item).strip()))

        advanced_tab = ttk.Frame(notebook, padding=12)
        advanced_tab.columnconfigure(0, weight=1)
        advanced_tab.rowconfigure(0, weight=1)
        notebook.add(advanced_tab, text="Código (Avanzado)")

        self.editor = ScrolledText(advanced_tab, wrap="word")
        self.editor.grid(row=0, column=0, sticky="nsew")
        self.editor.insert("1.0", content)

        actions = ttk.Frame(frame)
        actions.grid(row=1, column=0, sticky="e", pady=(12, 0))
        ttk.Button(actions, text="Cancelar", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(actions, text="Guardar", command=self._save).pack(side="right")

    def _save(self) -> None:
        label = self.template_label_var.get().strip()
        if not label:
            messagebox.showwarning("Validación", "El label de plantilla es obligatorio.", parent=self)
            return
        self.result = {
            "label": label,
            "fields": list(self.template_fields),
            "ejemplos": self._split_lines(self.examples_text.get("1.0", "end")),
            "content": self.editor.get("1.0", "end"),
        }
        self.destroy()

    def _refresh_template_fields(self) -> None:
        self.fields_listbox.delete(0, tk.END)
        for item in self.template_fields:
            label = item.get("label") or item.get("key", "")
            self.fields_listbox.insert(tk.END, f"{label} ({item.get('key', '')})")

    def _selected_field_index(self) -> int | None:
        selection = self.fields_listbox.curselection()
        if not selection:
            return None
        return int(selection[0])

    def _field_editor(self, title: str, initial: dict[str, str] | None = None) -> dict[str, str] | None:
        initial = initial or {}
        dialog = tk.Toplevel(self)
        _set_app_icon(dialog)
        dialog.title(title)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        vars_map = {
            "key": tk.StringVar(value=initial.get("key", "")),
            "label": tk.StringVar(value=initial.get("label", "")),
            "help": tk.StringVar(value=initial.get("help", "")),
            "example": tk.StringVar(value=initial.get("example", "")),
            "default": tk.StringVar(value=initial.get("default", "")),
        }
        labels = {
            "key": "Clave (obligatoria)",
            "label": "Nombre visible",
            "help": "Descripción",
            "example": "Ejemplo de campo",
            "default": "Valor por defecto (opcional)",
        }

        for row, key in enumerate(["key", "label", "help", "example", "default"]):
            ttk.Label(frame, text=labels[key]).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
            ttk.Entry(frame, textvariable=vars_map[key]).grid(row=row, column=1, sticky="ew", pady=4)

        result: dict[str, str] | None = None

        def save_and_close() -> None:
            nonlocal result
            final_key = vars_map["key"].get().strip()
            if not final_key:
                messagebox.showwarning("Validación", "La key del campo es obligatoria.", parent=dialog)
                return
            result = {name: var.get().strip() for name, var in vars_map.items()}
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Cancelar", command=dialog.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Guardar", command=save_and_close).pack(side="right")

        dialog.wait_window()
        return result

    def _add_field(self) -> None:
        edited = self._field_editor("Añadir campo")
        if not edited:
            return
        key = edited.get("key", "")
        if any(item.get("key") == key for item in self.template_fields):
            messagebox.showwarning("Campos de plantilla", "La key ya existe.", parent=self)
            return
        self.template_fields.append(edited)
        self._refresh_template_fields()

    def _edit_field(self) -> None:
        idx = self._selected_field_index()
        if idx is None:
            messagebox.showinfo("Campos de plantilla", "Selecciona un campo para editar.", parent=self)
            return
        edited = self._field_editor("Editar campo", initial=self.template_fields[idx])
        if not edited:
            return
        new_key = edited.get("key", "")
        if any(i != idx and item.get("key") == new_key for i, item in enumerate(self.template_fields)):
            messagebox.showwarning("Campos de plantilla", "La key ya existe.", parent=self)
            return
        self.template_fields[idx] = edited
        self._refresh_template_fields()

    def _delete_field(self) -> None:
        idx = self._selected_field_index()
        if idx is None:
            messagebox.showinfo("Campos de plantilla", "Selecciona un campo para eliminar.", parent=self)
            return
        self.template_fields.pop(idx)
        self._refresh_template_fields()

    @staticmethod
    def _split_lines(raw: str) -> list[str]:
        return [line.strip() for line in raw.splitlines() if line.strip()]


class AsistenteIADialog(tk.Toplevel):
    _LIST_KEYS = {"herramientas", "prioridades", "enfoque", "no_hacer", "ejemplos"}
    _DEPTH_CONFIG = {
        "Rápido": {"depth": 1, "max_questions": 5},
        "Normal": {"depth": 2, "max_questions": 8},
        "Profundo": {"depth": 3, "max_questions": 12},
    }

    def __init__(self, ui: "PromptEngineUI") -> None:
        super().__init__(ui.root)
        _set_app_icon(self)
        self.ui = ui
        self.title("Asistente IA")
        self.geometry("760x640")
        self.transient(ui.root)
        self.grab_set()

        self.generated_data: dict[str, object] | None = None
        self.diagnosis_data: dict[str, object] | None = None
        self._future = None

        self.kind_var = tk.StringVar(value="Perfil")
        self.name_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Listo")
        self.depth_var = tk.StringVar(value="Normal")
        self.memory: dict[str, object] = {}

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(5, weight=1)

        ttk.Label(frame, text="Tipo de maestro").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.kind_combo = ttk.Combobox(
            frame,
            values=["Perfil", "Contexto", "Plantilla"],
            textvariable=self.kind_var,
            state="readonly",
        )
        self.kind_combo.grid(row=0, column=1, sticky="ew", pady=4)
        self.kind_combo.bind("<<ComboboxSelected>>", self._on_kind_changed)

        ttk.Label(frame, text="Nombre").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(frame, textvariable=self.name_var).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="Descripción").grid(row=2, column=0, sticky="nw", padx=(0, 8), pady=4)
        self.description_text = DictationField(frame, voice_input=ui.voice_input, multiline=True, height=9)
        self.description_text.grid(row=2, column=1, sticky="nsew", pady=4)

        ttk.Label(frame, text="Profundidad").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        self.depth_combo = ttk.Combobox(
            frame,
            values=list(self._DEPTH_CONFIG.keys()),
            textvariable=self.depth_var,
            state="readonly",
        )
        self.depth_combo.grid(row=3, column=1, sticky="ew", pady=4)

        source_button = ttk.Button(
            frame,
            text="Usar datos del maestro seleccionado",
            command=self._use_selected_master_data,
        )
        source_button.grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 4))

        qa_frame = ttk.LabelFrame(frame, text="Preguntas (rellena respuestas y vuelve a generar)")
        qa_frame.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        qa_frame.columnconfigure(0, weight=1)
        qa_frame.columnconfigure(1, weight=1)
        qa_frame.rowconfigure(1, weight=1)

        ttk.Label(qa_frame, text="Preguntas").grid(row=0, column=0, sticky="w", padx=(8, 4), pady=(8, 4))
        ttk.Label(qa_frame, text="Respuestas (clave: valor)").grid(row=0, column=1, sticky="w", padx=(4, 8), pady=(8, 4))

        self.questions_text = ScrolledText(qa_frame, wrap="word", height=6)
        self.questions_text.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(0, 8))
        self.questions_text.configure(state="disabled")

        self.answers_text = DictationField(qa_frame, voice_input=ui.voice_input, multiline=True, height=6)
        self.answers_text.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=(0, 8))

        memory_frame = ttk.LabelFrame(frame, text="Memoria confirmada")
        memory_frame.grid(row=6, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        memory_frame.columnconfigure(0, weight=1)
        memory_frame.rowconfigure(0, weight=1)

        self.memory_text = ScrolledText(memory_frame, wrap="word", height=5)
        self.memory_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.memory_text.configure(state="disabled")

        preview_frame = ttk.LabelFrame(frame, text="Vista previa JSON")
        preview_frame.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.preview_text = ScrolledText(preview_frame, wrap="word", height=12)
        self.preview_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.preview_text.configure(state="disabled")

        footer = ttk.Frame(frame)
        footer.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Label(footer, textvariable=self.status_var).pack(side="left")
        self.generate_master_button = ttk.Button(footer, text="Generar maestro", command=self._on_generate_master)
        self.generate_master_button.pack(side="right", padx=(6, 0))
        self.generate_master_button.configure(state="disabled")
        self.diagnose_button = ttk.Button(footer, text="Diagnosticar", command=self._on_diagnose)
        self.diagnose_button.pack(side="right", padx=(6, 0))
        self.refine_button = ttk.Button(footer, text="Refinar", command=self._on_refine)
        self.refine_button.pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Aplicar al formulario", command=self._on_apply).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Guardar en maestros", command=self._on_save).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Cerrar", command=self.destroy).pack(side="right", padx=(6, 0))

    @staticmethod
    def _clear_text_widget(widget: ScrolledText | DictationField, readonly: bool = False) -> None:
        if isinstance(widget, DictationField):
            widget.clear()
            return
        if readonly:
            widget.configure(state="normal")
        widget.delete("1.0", "end")
        if readonly:
            widget.configure(state="disabled")

    @staticmethod
    def _read_text_widget(widget: ScrolledText | DictationField) -> str:
        if isinstance(widget, DictationField):
            return widget.get_text()
        return widget.get("1.0", "end").strip()

    def _render_memory(self) -> None:
        self.memory_text.configure(state="normal")
        self.memory_text.delete("1.0", "end")
        if self.memory:
            self.memory_text.insert("1.0", json.dumps(self.memory, ensure_ascii=False, indent=2))
        self.memory_text.configure(state="disabled")

    def _answered_keys(self) -> set[str]:
        answered: set[str] = set()
        for key, value in self.memory.items():
            clean_key = str(key).strip()
            if clean_key and value not in (None, "", [], {}):
                answered.add(clean_key)
        return answered

    @staticmethod
    def _parse_answer_lines(raw: str) -> dict[str, str]:
        parsed: dict[str, str] = {}
        for line in raw.splitlines():
            clean = line.strip()
            if not clean or ":" not in clean:
                continue
            key, value = clean.split(":", 1)
            clean_key = key.strip()
            if clean_key:
                parsed[clean_key] = value.strip()
        return parsed

    def _merge_answers_into_memory(self) -> None:
        answers = self._parse_answers(self._read_text_widget(self.answers_text))
        for key, value in answers.items():
            if value in (None, "", [], {}):
                continue
            self.memory[key] = value
        self._render_memory()

    def _prefill_answers_from_questions(
        self,
        base_questions: list[dict[str, object]],
        extras_questions: list[dict[str, object]],
    ) -> None:
        current_raw = self._read_text_widget(self.answers_text)
        existing_pairs = self._parse_answer_lines(current_raw)
        answered_keys = self._answered_keys()
        ordered_pending_keys: list[str] = []

        for question in [*base_questions, *extras_questions]:
            key = str(question.get("key", "")).strip()
            if not key or key in answered_keys or key in ordered_pending_keys:
                continue
            ordered_pending_keys.append(key)

        prefilled_lines = [f"{key}: {existing_pairs.get(key, '').strip()}" for key in ordered_pending_keys]

        for line in current_raw.splitlines():
            clean_line = line.strip()
            if not clean_line:
                continue
            if ":" in clean_line:
                key, _value = clean_line.split(":", 1)
                if key.strip() in ordered_pending_keys:
                    continue
            prefilled_lines.append(clean_line)

        self.answers_text.set_text("\n".join(prefilled_lines))

    def _depth_settings(self) -> dict[str, int]:
        return self._DEPTH_CONFIG.get(self.depth_var.get(), self._DEPTH_CONFIG["Normal"])

    def _active_ai_context(self) -> dict[str, object]:
        perfil = self.ui._selected_item(self.ui.perfiles, self.ui.perfil_var.get())
        contexto = self.ui._selected_item(self.ui.contextos, self.ui.contexto_var.get())
        plantilla = self.ui._selected_item(self.ui.plantillas, self.ui.template_var.get())
        return {
            "perfil_activo": perfil if isinstance(perfil, dict) else {},
            "contexto_activo": contexto if isinstance(contexto, dict) else {},
            "plantilla_seleccionada": plantilla if isinstance(plantilla, dict) else {},
        }

    def _use_selected_master_data(self) -> None:
        context = self._active_ai_context()
        kind = self._kind_key()
        if kind == "perfil":
            perfil = context.get("perfil_activo") if isinstance(context.get("perfil_activo"), dict) else {}
            for key in ("empresa", "ubicacion", "rol_base", "rol", "nivel_tecnico", "herramientas", "prioridades"):
                value = perfil.get(key) if isinstance(perfil, dict) else None
                if value not in (None, "", []):
                    self.memory[key] = value
        elif kind == "contexto":
            contexto = context.get("contexto_activo") if isinstance(context.get("contexto_activo"), dict) else {}
            for key in ("rol_contextual", "enfoque", "no_hacer"):
                value = contexto.get(key) if isinstance(contexto, dict) else None
                if value not in (None, "", []):
                    self.memory[key] = value
        elif kind == "plantilla":
            plantilla = (
                context.get("plantilla_seleccionada")
                if isinstance(context.get("plantilla_seleccionada"), dict)
                else {}
            )
            label = plantilla.get("label") if isinstance(plantilla, dict) else None
            if label:
                self.memory["label"] = label
        self._render_memory()

    def _on_kind_changed(self, _event: tk.Event | None = None) -> None:
        self._clear_text_widget(self.questions_text, readonly=True)
        self._clear_text_widget(self.answers_text)
        self._set_preview(None)
        self.generated_data = None
        self.diagnosis_data = None
        self.status_var.set("Listo")
        self.generate_master_button.configure(state="disabled")

    def _set_questions(
        self,
        base_questions: list[dict[str, object]],
        extras_questions: list[dict[str, object]],
    ) -> None:
        self.questions_text.configure(state="normal")
        self.questions_text.delete("1.0", "end")

        def _format_block(title: str, questions: list[dict[str, object]]) -> list[str]:
            lines = [title]
            for idx, question in enumerate(questions, start=1):
                key = str(question.get("key", "")).strip()
                text = str(question.get("question", "")).strip()
                required = bool(question.get("required", False))
                suffix = " [requerida]" if required else ""
                if key and text:
                    lines.append(f"{idx}. ({key}) {text}{suffix}")
            if len(lines) == 1:
                lines.append("- Sin preguntas en este bloque")
            return lines

        lines = _format_block("Base (obligatorio)", base_questions)
        lines.append("")
        lines.extend(_format_block("Extras (para afinar)", extras_questions))
        if lines:
            self.questions_text.insert("1.0", "\n".join(lines))
        self.questions_text.configure(state="disabled")

    @classmethod
    def _parse_answers(cls, raw: str) -> dict[str, object]:
        parsed: dict[str, object] = {}
        for line in raw.splitlines():
            clean = line.strip()
            if not clean or ":" not in clean:
                continue
            key, value = clean.split(":", 1)
            clean_key = key.strip()
            if clean_key:
                clean_value = value.strip()
                if clean_value.startswith("[") or clean_value.startswith("{"):
                    try:
                        parsed[clean_key] = json.loads(clean_value)
                        continue
                    except json.JSONDecodeError:
                        pass
                if clean_key in cls._LIST_KEYS:
                    separator = ";" if ";" in clean_value else ","
                    parsed[clean_key] = [item.strip() for item in clean_value.split(separator) if item.strip()]
                    continue
                parsed[clean_key] = clean_value
        return parsed

    def _set_preview(self, payload: dict[str, object] | None) -> None:
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        if payload is not None:
            self.preview_text.insert("1.0", json.dumps(payload, ensure_ascii=False, indent=2))
        self.preview_text.configure(state="disabled")

    def _kind_key(self) -> str:
        return self.kind_var.get().strip().lower()

    def _request_diagnosis(self, focus: str, reset_questions: bool) -> None:
        name = self.name_var.get().strip()
        description = self._read_text_widget(self.description_text)
        if not name:
            messagebox.showwarning("Asistente IA", "El nombre es obligatorio.", parent=self)
            return
        if not description:
            messagebox.showwarning("Asistente IA", "La descripción es obligatoria.", parent=self)
            return

        self._merge_answers_into_memory()
        exclude_keys = sorted(self._answered_keys())
        self.diagnosis_data = None
        if reset_questions:
            self._clear_text_widget(self.questions_text, readonly=True)
        self._set_preview(None)
        self.diagnose_button.configure(state="disabled")
        self.generate_master_button.configure(state="disabled")
        self.refine_button.configure(state="disabled")
        self.status_var.set("Diagnosticando…")
        depth_settings = self._depth_settings()
        self._future = self.ui.executor.submit(
            generate_master_diagnosis,
            self._kind_key(),
            name,
            description,
            dict(self.memory),
            depth_settings["max_questions"],
            self._active_ai_context(),
            exclude_keys,
            focus,
        )
        self.after(80, self._poll_diagnosis)

    def _on_diagnose(self) -> None:
        self._request_diagnosis(focus="base", reset_questions=True)

    def _on_refine(self) -> None:
        self._request_diagnosis(focus="balanced", reset_questions=False)

    def _on_generate_master(self) -> None:
        name = self.name_var.get().strip()
        description = self._read_text_widget(self.description_text)

        if not name:
            messagebox.showwarning("Asistente IA", "El nombre es obligatorio.", parent=self)
            return
        if not description:
            messagebox.showwarning("Asistente IA", "La descripción es obligatoria.", parent=self)
            return

        self._merge_answers_into_memory()
        answers = self._parse_answers(self._read_text_widget(self.answers_text))

        self.diagnose_button.configure(state="disabled")
        self.refine_button.configure(state="disabled")
        self.generate_master_button.configure(state="disabled")
        self.status_var.set("Generando maestro…")
        self._future = self.ui.executor.submit(
            generate_master_with_answers,
            self._kind_key(),
            name,
            description,
            dict(self.memory),
            answers,
            self._active_ai_context(),
        )
        self.after(80, self._poll_generation)

    def _poll_diagnosis(self) -> None:
        if self._future is None:
            return
        if not self._future.done():
            self.after(80, self._poll_diagnosis)
            return

        try:
            result = self._future.result()
            if not isinstance(result, dict):
                raise RuntimeError("El diagnóstico devolvió un formato inválido.")
            self.diagnosis_data = result
            base_questions = result.get("base_questions") if isinstance(result.get("base_questions"), list) else []
            extras_questions = result.get("extras_questions") if isinstance(result.get("extras_questions"), list) else []
            answered_keys = self._answered_keys()
            base_questions = [
                question
                for question in base_questions
                if str(question.get("key", "")).strip() and str(question.get("key", "")).strip() not in answered_keys
            ]
            extras_questions = [
                question
                for question in extras_questions
                if str(question.get("key", "")).strip() and str(question.get("key", "")).strip() not in answered_keys
            ]
            self._set_questions(base_questions, extras_questions)
            self._prefill_answers_from_questions(base_questions, extras_questions)

            draft = result.get("draft")
            if isinstance(draft, dict):
                self.generated_data = draft
                self.name_var.set(str(draft.get("nombre", self.name_var.get())).strip())
                self._set_preview(draft)

            self.generate_master_button.configure(state="normal")
            self.refine_button.configure(state="normal")
            self.status_var.set("Diagnóstico completado")
        except RuntimeError as exc:
            self.status_var.set("Error")
            self.generate_master_button.configure(state="normal" if isinstance(self.diagnosis_data, dict) else "disabled")
            messagebox.showerror("Asistente IA", str(exc), parent=self)
        except Exception as exc:
            self.status_var.set("Error")
            self.generate_master_button.configure(state="normal" if isinstance(self.diagnosis_data, dict) else "disabled")
            messagebox.showerror("Asistente IA", f"Error inesperado al diagnosticar: {exc}", parent=self)
        finally:
            self.diagnose_button.configure(state="normal")
            self.refine_button.configure(state="normal")
            self._future = None

    def _poll_generation(self) -> None:
        if self._future is None:
            return
        if not self._future.done():
            self.after(80, self._poll_generation)
            return

        try:
            result = self._future.result()
            if not isinstance(result, dict):
                raise RuntimeError("La generación devolvió un formato inválido.")
            self.generated_data = result
            self.name_var.set(str(result.get("nombre", self.name_var.get())).strip())
            self._set_preview(self.generated_data)
            self.status_var.set("Generación completada")
        except RuntimeError as exc:
            self.status_var.set("Error")
            messagebox.showerror("Asistente IA", str(exc), parent=self)
        except Exception as exc:
            self.status_var.set("Error")
            messagebox.showerror("Asistente IA", f"Error inesperado al generar: {exc}", parent=self)
        finally:
            self.diagnose_button.configure(state="normal")
            self.refine_button.configure(state="normal")
            self.generate_master_button.configure(state="normal")
            self._future = None

    def _on_apply(self) -> None:
        if not self.generated_data:
            messagebox.showinfo("Asistente IA", "Primero debes generar un JSON.", parent=self)
            return
        applied = self.ui._apply_ai_master_to_form(self._kind_key(), dict(self.generated_data))
        if applied:
            self.generated_data = applied
            self.name_var.set(str(applied.get("nombre", self.name_var.get())).strip())
            self._set_preview(self.generated_data)

    def _on_save(self) -> None:
        if not self.generated_data:
            messagebox.showinfo("Asistente IA", "Primero debes generar un JSON.", parent=self)
            return
        saved = self.ui._save_ai_master(self._kind_key(), dict(self.generated_data), parent=self)
        if saved:
            self.status_var.set("Guardado")


class HistoryWindow(tk.Toplevel):
    """Ventana de historial de tareas con acciones."""

    def __init__(self, master: tk.Widget, tasks: list[Tarea], callbacks: dict[str, callable]) -> None:
        super().__init__(master)
        _set_app_icon(self)
        self.title("Historial de tareas")
        self.geometry("1020x520")
        self.transient(master)
        self.tasks = tasks
        self.callbacks = callbacks

        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        columns = ("id", "fecha", "titulo", "plantilla", "usuario")
        self.tree = ttk.Treeview(container, columns=columns, show="headings")
        for col, width in zip(columns, (170, 160, 320, 120, 180)):
            self.tree.heading(col, text=col.upper())
            self.tree.column(col, width=width, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")

        actions = ttk.Frame(container)
        actions.grid(row=1, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(actions, text="Ver prompt", command=self._view).pack(side="left", padx=4)
        ttk.Button(actions, text="Clonar tarea", command=self._clone).pack(side="left", padx=4)
        ttk.Button(actions, text="Exportar PDF", command=self._export).pack(side="left", padx=4)
        ttk.Button(actions, text="Eliminar tarea", command=self._delete).pack(side="left", padx=4)

        self._populate()

    def _populate(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for task in self.tasks:
            title = task.objetivo or "(sin título)"
            self.tree.insert(
                "",
                "end",
                iid=task.id,
                values=(task.id, task_id_to_human(task.id), title, task.area, task.usuario),
            )

    def _selected_id(self) -> str | None:
        selected = self.tree.selection()
        return selected[0] if selected else None

    def _view(self) -> None:
        task_id = self._selected_id()
        if task_id:
            self.callbacks["view"](task_id)

    def _clone(self) -> None:
        task_id = self._selected_id()
        if task_id:
            self.callbacks["clone"](task_id)

    def _export(self) -> None:
        task_id = self._selected_id()
        if task_id:
            self.callbacks["export"](task_id)

    def _delete(self) -> None:
        task_id = self._selected_id()
        if not task_id:
            return
        self.callbacks["delete"](task_id)
        self.tasks = listar_tareas()
        self._populate()


class PromptEngineUI:
    """Ventana principal de PROM-9™."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Prompt Engine PROM-9™")
        self.root.geometry("1280x860")
        _set_app_icon(self.root)
        ensure_bootstrap_assets()

        self.executor = ThreadPoolExecutor(max_workers=2)
        self.voice_input: VoiceInput | None = None
        self.voice_error_message = ""
        if VoiceInput.is_supported():
            try:
                self.voice_input = VoiceInput()
            except RuntimeError as exc:
                self.voice_error_message = str(exc)
        else:
            self.voice_error_message = (
                "Dictado deshabilitado: faltan dependencias opcionales "
                "(sounddevice, numpy u openai)."
            )

        self.perfiles = get_perfiles()
        self.contextos = get_contextos()
        self.plantillas = get_plantillas()
        self.history_cache: list[Tarea] = []
        self.current_task: Tarea | None = None
        self.is_dirty = False
        self.last_saved_prompt = ""
        self.pending_reset_after_save = False

        self.perfil_var = tk.StringVar()
        self.contexto_var = tk.StringVar()
        self.template_var = tk.StringVar()
        self.perfil_activo: dict | None = None
        self.contexto_activo: dict | None = None

        self.base_widgets: dict[str, tk.Widget | DictationField] = {}
        self.profile_extra_widgets: dict[str, ttk.Entry] = {}
        self.profile_extra_meta: dict[str, dict[str, str]] = {}
        self.context_extra_widgets: dict[str, ttk.Entry] = {}
        self.context_extra_meta: dict[str, dict[str, str]] = {}
        self.template_widgets: dict[str, ttk.Entry] = {}
        self.attachment_paths: list[Path] = []

        self._build_menu()
        self._build_ui()
        self._reload_selectors()
        self._refresh_history()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        archivo = tk.Menu(menubar, tearoff=False)
        archivo.add_command(label="Nuevo Perfil", command=self.new_profile)
        archivo.add_command(label="Editar Perfil", command=self.edit_profile)
        archivo.add_command(label="Eliminar Perfil…", command=self.delete_profile)
        archivo.add_separator()
        archivo.add_command(label="Nuevo Contexto", command=self.new_context)
        archivo.add_command(label="Editar Contexto", command=self.edit_context)
        archivo.add_command(label="Eliminar Contexto…", command=self.delete_context)
        archivo.add_separator()
        archivo.add_command(label="Nueva Plantilla", command=self.new_template)
        archivo.add_command(label="Editar Plantilla", command=self.edit_template)
        archivo.add_command(label="Eliminar Plantilla…", command=self.delete_template)
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self._on_close)
        menubar.add_cascade(label="Archivo", menu=archivo)

        herramientas = tk.Menu(menubar, tearoff=False)
        herramientas.add_command(label="Importar…", command=self.importar_maestros_csv)
        herramientas.add_command(label="Exportar…", command=self.exportar_maestros_csv)
        herramientas.add_separator()
        herramientas.add_command(label="Asistente IA…", command=self.asistente_ia)
        menubar.add_cascade(label="Herramientas", menu=herramientas)

        self.root.config(menu=menubar)


    def _build_ui(self) -> None:
        root_frame = ttk.Frame(self.root, padding=12)
        root_frame.pack(fill="both", expand=True)
        root_frame.columnconfigure(0, weight=1)
        root_frame.rowconfigure(0, weight=2)
        root_frame.rowconfigure(1, weight=3)
        root_frame.rowconfigure(2, weight=0)

        main_paned = ttk.PanedWindow(root_frame, orient="horizontal")
        main_paned.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        left_panel = ttk.Frame(main_paned)
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(0, weight=1)
        main_paned.add(left_panel, weight=3)

        left = ttk.LabelFrame(left_panel, text="Formulario", padding=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        form_canvas = tk.Canvas(left, highlightthickness=0)
        form_canvas.grid(row=0, column=0, sticky="nsew")
        form_scrollbar = ttk.Scrollbar(left, orient="vertical", command=form_canvas.yview)
        form_scrollbar.grid(row=0, column=1, sticky="ns")
        form_canvas.configure(yscrollcommand=form_scrollbar.set)

        form_inner = ttk.Frame(form_canvas)
        form_inner.columnconfigure(1, weight=1)
        form_window = form_canvas.create_window((0, 0), window=form_inner, anchor="nw")

        def _on_form_configure(_event: tk.Event) -> None:
            form_canvas.configure(scrollregion=form_canvas.bbox("all"))

        def _on_canvas_configure(event: tk.Event) -> None:
            form_canvas.itemconfigure(form_window, width=event.width)

        form_inner.bind("<Configure>", _on_form_configure)
        form_canvas.bind("<Configure>", _on_canvas_configure)

        ttk.Label(form_inner, text="Perfil").grid(row=0, column=0, sticky="w", pady=4)
        self.perfil_combo = ttk.Combobox(form_inner, textvariable=self.perfil_var, state="readonly")
        self.perfil_combo.grid(row=0, column=1, sticky="ew", pady=4)
        self.perfil_combo.bind("<<ComboboxSelected>>", self._on_profile_change)

        ttk.Label(form_inner, text="Contexto").grid(row=1, column=0, sticky="w", pady=4)
        self.contexto_combo = ttk.Combobox(form_inner, textvariable=self.contexto_var, state="readonly")
        self.contexto_combo.grid(row=1, column=1, sticky="ew", pady=4)
        self.contexto_combo.bind("<<ComboboxSelected>>", self._on_context_change)

        ttk.Label(form_inner, text="Plantilla").grid(row=2, column=0, sticky="w", pady=4)
        self.template_combo = ttk.Combobox(form_inner, textvariable=self.template_var, state="readonly")
        self.template_combo.grid(row=2, column=1, sticky="ew", pady=4)
        self.template_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_template_changed())

        start_row = 3
        for offset, (field, label) in enumerate(BASE_FIELDS):
            row = start_row + offset
            ttk.Label(form_inner, text=label).grid(row=row, column=0, sticky="nw", pady=4)
            if field in {"contexto_detallado", "restricciones"}:
                widget: tk.Widget | DictationField = DictationField(
                    form_inner,
                    self.voice_input,
                    multiline=True,
                )
            else:
                widget = ttk.Entry(form_inner)
            widget.grid(row=row, column=1, sticky="ew", pady=4)
            self.base_widgets[field] = widget
            focus_widget = widget.get_widget() if isinstance(widget, DictationField) else widget
            focus_widget.bind("<FocusIn>", lambda _e, f=field: self._update_context_panel(f))
            focus_widget.bind("<KeyRelease>", self._mark_dirty)

        self.profile_extras_frame = ttk.LabelFrame(form_inner, text="Campos personalizados de perfil", padding=8)
        self.profile_extras_frame.grid(row=98, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.profile_extras_frame.columnconfigure(1, weight=1)

        self.context_extras_frame = ttk.LabelFrame(form_inner, text="Campos personalizados de contexto", padding=8)
        self.context_extras_frame.grid(row=99, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.context_extras_frame.columnconfigure(1, weight=1)

        self.template_fields_frame = ttk.LabelFrame(form_inner, text="Campos de plantilla", padding=8)
        self.template_fields_frame.grid(row=100, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.template_fields_frame.columnconfigure(1, weight=1)

        right = ttk.LabelFrame(main_paned, text="Panel contextual dinámico", padding=10)
        main_paned.add(right, weight=2)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        self.context_title = ttk.Label(right, text="Campo activo: -", font=("Segoe UI", 10, "bold"))
        self.context_title.grid(row=0, column=0, sticky="w")

        self.context_examples_title = ttk.Label(right, text="Ejemplos por plantilla", foreground="#1d4ed8")
        self.context_examples_title.grid(row=1, column=0, sticky="w", pady=(8, 4))

        self.context_text = ScrolledText(right, wrap="word")
        self.context_text.grid(row=2, column=0, sticky="nsew")
        self.context_text.configure(state="disabled")

        output_tabs = ttk.Notebook(root_frame)
        output_tabs.grid(row=1, column=0, sticky="nsew")

        prompt_tab = ttk.Frame(output_tabs)
        prompt_tab.columnconfigure(0, weight=1)
        prompt_tab.rowconfigure(0, weight=1)
        output_tabs.add(prompt_tab, text="Prompt generado")

        self.prompt_box = DictationField(prompt_tab, self.voice_input, multiline=True)
        self.prompt_box.grid(row=0, column=0, sticky="nsew")
        self.prompt_box.get_widget().bind("<KeyRelease>", self._mark_dirty)

        attachments_tab = ttk.Frame(output_tabs)
        attachments_tab.columnconfigure(0, weight=1)
        attachments_tab.rowconfigure(0, weight=1)
        output_tabs.add(attachments_tab, text="Archivos adjuntos")

        attachments_frame = ttk.LabelFrame(attachments_tab, text="Archivos adjuntos", padding=8)
        attachments_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        attachments_frame.columnconfigure(0, weight=1)
        attachments_frame.rowconfigure(1, weight=1)

        attachments_buttons = ttk.Frame(attachments_frame)
        attachments_buttons.grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Button(attachments_buttons, text="Adjuntar archivos", command=self.attach_files).pack(side="left")
        ttk.Button(attachments_buttons, text="Eliminar seleccionado", command=self.remove_attachment).pack(side="left", padx=(6, 0))

        self.attachments_listbox = tk.Listbox(attachments_frame, height=4, exportselection=False)
        self.attachments_listbox.grid(row=1, column=0, sticky="nsew")

        history_tab = ttk.Frame(output_tabs)
        history_tab.columnconfigure(0, weight=1)
        history_tab.rowconfigure(0, weight=1)
        output_tabs.add(history_tab, text="Historial rápido")
        ttk.Label(history_tab, text="Historial rápido disponible próximamente.").grid(
            row=0, column=0, sticky="nw", padx=12, pady=12
        )

        actions_row = ttk.Frame(root_frame)
        actions_row.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(actions_row, text="Generar Prompt", command=self._generate_prompt).pack(side="left", padx=(0, 6))
        ttk.Button(actions_row, text="Guardar", command=self._save_prompt).pack(side="left", padx=6)
        ttk.Button(actions_row, text="Nuevo prompt", command=self.new_prompt).pack(side="left", padx=6)
        ttk.Button(actions_row, text="Exportar PDF", command=self._export_pdf).pack(side="left", padx=6)
        ttk.Button(actions_row, text="Historial", command=self._open_history).pack(side="left", padx=6)
        ttk.Button(actions_row, text="📋 Copiar Prompt", command=self._copy_prompt).pack(side="left", padx=6)

    def _mark_dirty(self, _event=None) -> None:
        self.is_dirty = True

    def _has_content_to_lose(self) -> bool:
        has_base_content = any(self._read_widget(self.base_widgets[field]).strip() for field, _ in BASE_FIELDS)
        has_template_content = any(entry.get().strip() for entry in self.template_widgets.values())
        has_profile_content = any(entry.get().strip() for entry in self.profile_extra_widgets.values())
        has_context_content = any(entry.get().strip() for entry in self.context_extra_widgets.values())
        has_prompt_content = bool(self.prompt_box.get_text().strip())
        has_attachments = bool(self.attachment_paths)
        return any(
            [
                has_base_content,
                has_template_content,
                has_profile_content,
                has_context_content,
                has_prompt_content,
                has_attachments,
            ]
        )

    def _reset_form(self) -> None:
        for field, _label in BASE_FIELDS:
            self._write_widget(self.base_widgets[field], "")

        for widget in self.template_widgets.values():
            self._write_widget(widget, "")
        for widget in self.profile_extra_widgets.values():
            self._write_widget(widget, "")
        for widget in self.context_extra_widgets.values():
            self._write_widget(widget, "")

        self.prompt_box.set_text("")
        self.attachment_paths.clear()
        self._refresh_attachment_list()
        self.current_task = None
        self.is_dirty = False
        self.pending_reset_after_save = False

    def new_prompt(self) -> None:
        if not self._has_content_to_lose():
            self._reset_form()
            return

        if self.is_dirty:
            decision = messagebox.askyesnocancel(
                "Nuevo prompt",
                "Tienes cambios sin guardar. ¿Quieres guardar antes de limpiar?",
            )
            if decision is None:
                return
            if decision:
                self.pending_reset_after_save = True
                if not self.save_task():
                    self.pending_reset_after_save = False
                return

        self._reset_form()

    def _generate_prompt(self) -> None:
        self.generate_prompt()

    def _save_prompt(self) -> None:
        self.save_task()

    def _export_pdf(self) -> None:
        self.export_pdf()

    def _open_history(self) -> None:
        self.show_history()

    def _copy_prompt(self) -> None:
        prompt = self.prompt_box.get_text()
        if not prompt:
            messagebox.showwarning("Copiar", "No hay prompt generado.")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(prompt)
        messagebox.showinfo("Copiar", "Prompt copiado al portapapeles.")

    def _selected_template(self) -> dict:
        wanted = self.template_var.get()
        for item in self.plantillas:
            if item.get("nombre") == wanted:
                return item
        return self.plantillas[0] if self.plantillas else {"nombre": "gestion", "fields": [], "ejemplos": []}

    def _template_help(self, field: str) -> tuple[str, str]:
        tpl = self._selected_template()
        for item in tpl.get("fields", []):
            if item.get("key") == field:
                return item.get("help", ""), item.get("example", "")
        return "", ""

    def _update_context_panel(self, field: str) -> None:
        base_help = BASE_HELP.get(field)
        tpl = self._selected_template()
        examples = tpl.get("ejemplos", [])

        if base_help:
            help_text, sample = base_help
        else:
            help_text, sample = self._template_help(field)
            if not help_text:
                profile_meta = self.profile_extra_meta.get(field, {})
                if profile_meta:
                    help_text = profile_meta.get("help", "")
                    sample = profile_meta.get("example", "")
                else:
                    context_meta = self.context_extra_meta.get(field, {})
                    if context_meta:
                        help_text = context_meta.get("help", "")
                        sample = context_meta.get("example", "")

        self.context_title.configure(text=f"Campo activo: {field}")
        self.context_examples_title.configure(text=f"Ejemplos ({tpl.get('nombre', 'plantilla')})")
        content = [
            f"Descripción:\n{help_text or 'Sin descripción'}",
            f"\nEjemplo de campo:\n{sample or 'Sin ejemplo'}",
            "\nEjemplos de uso por plantilla:",
        ]
        content.extend(f"- {example}" for example in examples)

        self.context_text.configure(state="normal")
        self.context_text.delete("1.0", "end")
        self.context_text.insert("1.0", "\n".join(content))
        self.context_text.configure(state="disabled")

    def _on_template_changed(self) -> None:
        self._render_template_fields()
        self._update_context_panel("titulo")

    def _on_profile_change(self, _event=None) -> None:
        self.perfil_activo = self._selected_item(self.perfiles, self.perfil_var.get())
        self._render_profile_extras()

    def _on_context_change(self, _event=None) -> None:
        self.contexto_activo = self._selected_item(self.contextos, self.contexto_var.get())
        self._render_context_extras()

    def _render_profile_extras(self) -> None:
        for widget in self.profile_extras_frame.winfo_children():
            widget.destroy()
        self.profile_extra_widgets.clear()
        self.profile_extra_meta.clear()

        extras_fields = []
        extras_legacy = {}
        if isinstance(self.perfil_activo, dict):
            extras_fields = self.perfil_activo.get("extras_fields", [])
            extras_legacy = self.perfil_activo.get("extras", {})

        if isinstance(extras_fields, list) and extras_fields:
            normalized_fields: list[tuple[str, str, str, str, str]] = []
            for field in extras_fields:
                if not isinstance(field, dict):
                    continue
                key = str(field.get("key", "")).strip()
                if not key:
                    continue
                label = str(field.get("label", "")).strip() or key
                help_text = str(field.get("help", "")).strip()
                example = str(field.get("example", "")).strip()
                default = str(field.get("default", "")).strip()
                normalized_fields.append((label.lower(), key.lower(), key, label, default))
                self.profile_extra_meta[key] = {"help": help_text, "example": example}

            for row_index, (_sort_label, _sort_key, key, label, default) in enumerate(sorted(normalized_fields)):
                ttk.Label(self.profile_extras_frame, text=label).grid(row=row_index, column=0, sticky="w", pady=4, padx=(0, 8))
                entry = ttk.Entry(self.profile_extras_frame)
                if default:
                    entry.insert(0, default)
                entry.grid(row=row_index, column=1, sticky="ew", pady=4)
                entry.bind("<FocusIn>", lambda _e, f=key: self._update_context_panel(f))
                entry.bind("<KeyRelease>", self._mark_dirty)
                self.profile_extra_widgets[key] = entry
            return

        if not isinstance(extras_legacy, dict):
            extras_legacy = {}

        for row_index, key in enumerate(sorted(extras_legacy.keys(), key=lambda item: str(item).lower())):
            value = "" if extras_legacy[key] is None else str(extras_legacy[key])
            ttk.Label(self.profile_extras_frame, text=key).grid(row=row_index, column=0, sticky="w", pady=4, padx=(0, 8))
            entry = ttk.Entry(self.profile_extras_frame)
            entry.insert(0, value)
            entry.grid(row=row_index, column=1, sticky="ew", pady=4)
            entry.bind("<FocusIn>", lambda _e, f=key: self._update_context_panel(f))
            entry.bind("<KeyRelease>", self._mark_dirty)
            self.profile_extra_widgets[key] = entry

    def _render_context_extras(self) -> None:
        for widget in self.context_extras_frame.winfo_children():
            widget.destroy()
        self.context_extra_widgets.clear()
        self.context_extra_meta.clear()

        extras_fields = []
        if isinstance(self.contexto_activo, dict):
            extras_fields = self.contexto_activo.get("extras_fields", [])
        if not isinstance(extras_fields, list):
            extras_fields = []

        row_index = 0
        for field in extras_fields:
            if not isinstance(field, dict):
                continue
            key = str(field.get("key", "")).strip()
            if not key:
                continue
            label = str(field.get("label", "")).strip() or key
            default = str(field.get("default", "")).strip()
            self.context_extra_meta[key] = {
                "help": str(field.get("help", "")).strip(),
                "example": str(field.get("example", "")).strip(),
            }

            ttk.Label(self.context_extras_frame, text=label).grid(row=row_index, column=0, sticky="w", pady=4, padx=(0, 8))
            entry = ttk.Entry(self.context_extras_frame)
            if default:
                entry.insert(0, default)
            entry.grid(row=row_index, column=1, sticky="ew", pady=4)
            entry.bind("<FocusIn>", lambda _e, f=key: self._update_context_panel(f))
            entry.bind("<KeyRelease>", self._mark_dirty)
            self.context_extra_widgets[key] = entry
            row_index += 1

    def _render_template_fields(self) -> None:
        for widget in self.template_fields_frame.winfo_children():
            widget.destroy()
        self.template_widgets.clear()

        tpl = self._selected_template()
        self.template_fields_frame.configure(text=f"Campos de plantilla: {tpl.get('nombre', '')}")

        for idx, field in enumerate(tpl.get("fields", [])):
            key = field.get("key", "")
            label = field.get("label", key)
            ttk.Label(self.template_fields_frame, text=label).grid(row=idx, column=0, sticky="w", pady=4, padx=(0, 8))
            entry = ttk.Entry(self.template_fields_frame)
            default_value = field.get("default", "")
            if default_value is not None and str(default_value).strip():
                entry.insert(0, str(default_value))
            entry.grid(row=idx, column=1, sticky="ew", pady=4)
            entry.bind("<FocusIn>", lambda _e, f=key: self._update_context_panel(f))
            entry.bind("<KeyRelease>", self._mark_dirty)
            self.template_widgets[key] = entry

    def _reload_selectors(self) -> None:
        profile_names = [item.get("nombre", "") for item in self.perfiles]
        context_names = [item.get("nombre", "") for item in self.contextos]
        template_names = [item.get("nombre", "") for item in self.plantillas]

        self.perfil_combo["values"] = profile_names
        self.contexto_combo["values"] = context_names
        self.template_combo["values"] = template_names

        if profile_names and self.perfil_var.get() not in profile_names:
            self.perfil_var.set(profile_names[0])
        if context_names and self.contexto_var.get() not in context_names:
            self.contexto_var.set(context_names[0])
        if template_names:
            if self.template_var.get() not in template_names:
                default = "gestion" if "gestion" in template_names else template_names[0]
                self.template_var.set(default)
            self._render_template_fields()

        self._on_profile_change()
        self._on_context_change()
        self._update_context_panel("titulo")

    def _selected_item(self, collection: list[dict], name: str) -> dict | None:
        for item in collection:
            if item.get("nombre") == name:
                return item
        return None

    @staticmethod
    def _read_widget(widget: tk.Widget | DictationField) -> str:
        if isinstance(widget, DictationField):
            return widget.get_text()
        if isinstance(widget, tk.Text):
            return widget.get("1.0", "end").strip()
        return widget.get().strip()

    @staticmethod
    def _write_widget(widget: tk.Widget | DictationField, value: object) -> None:
        text = "" if value is None else str(value)
        if isinstance(widget, DictationField):
            widget.set_text(text)
            return
        if isinstance(widget, tk.Text):
            widget.delete("1.0", "end")
            widget.insert("1.0", text)
            return
        widget.delete(0, "end")
        widget.insert(0, text)

    def _collect_form_data(self) -> dict[str, str]:
        data = {"area": self.template_var.get()}
        for field, _ in BASE_FIELDS:
            data[field] = self._read_widget(self.base_widgets[field])
        for field, entry in self.template_widgets.items():
            data[field] = entry.get().strip()
        for field, entry in self.profile_extra_widgets.items():
            data[field] = entry.get().strip()
        for field, entry in self.context_extra_widgets.items():
            data[field] = entry.get().strip()

        data["entradas"] = data.get("situacion", "")
        data["prioridad"] = data.get("urgencia", "") or "Media"
        data["formato_salida"] = "Respuesta estructurada"

        if data.get("contexto_detallado"):
            data["restricciones"] = f"{data.get('restricciones', '')}\nContexto adicional: {data['contexto_detallado']}".strip()

        return data

    def _validate_required(self) -> bool:
        required = ["titulo", "objetivo", "situacion", "urgencia"]
        missing = [name for name in required if not self._read_widget(self.base_widgets[name])]
        if missing:
            messagebox.showwarning("Validación", f"Completa los campos obligatorios: {', '.join(missing)}")
            return False
        return True

    def generate_prompt(self) -> None:
        """Genera prompt y lo deja editable. No persiste hasta pulsar Guardar."""
        if not self._validate_required():
            return

        perfil = self._selected_item(self.perfiles, self.perfil_var.get())
        contexto = self._selected_item(self.contextos, self.contexto_var.get())
        if not perfil or not contexto:
            messagebox.showwarning("Datos incompletos", "Selecciona un perfil y un contexto válidos.")
            return

        data = self._collect_form_data()
        try:
            prompt = generar_prompt(data, perfil, contexto, self.attachment_paths)
        except RuntimeError as exc:
            messagebox.showerror("Adjuntos", str(exc))
            return
        self.prompt_box.set_text(prompt)
        payload_json = json.dumps(data, ensure_ascii=False)

        self.current_task = Tarea(
            id=generate_task_id(),
            usuario=perfil.get("nombre", "Usuario"),
            contexto=contexto.get("nombre", "General"),
            area=data.get("area", "gestion"),
            objetivo=data.get("titulo") or data.get("objetivo", ""),
            entradas=data.get("entradas", ""),
            restricciones=data.get("restricciones", ""),
            formato_salida=data.get("formato_salida", ""),
            prioridad=data.get("prioridad", "Media"),
            payload_json=payload_json,
            prompt_generado=prompt,
        )

    def _refresh_attachment_list(self) -> None:
        self.attachments_listbox.delete(0, "end")
        for path in self.attachment_paths:
            self.attachments_listbox.insert("end", path.name)

    def attach_files(self) -> None:
        filenames = filedialog.askopenfilenames(
            title="Seleccionar archivos adjuntos",
            filetypes=[
                ("Archivos soportados", "*.py *.json *.txt *.md *.pdf"),
                ("Python", "*.py"),
                ("JSON", "*.json"),
                ("Texto", "*.txt"),
                ("Markdown", "*.md"),
                ("PDF", "*.pdf"),
            ],
        )
        if not filenames:
            return

        errores: list[str] = []
        for filename in filenames:
            path = Path(filename)
            if not validar_tipo_archivo(path):
                errores.append(f"Tipo no soportado: {path.name}")
                continue
            if path not in self.attachment_paths:
                self.attachment_paths.append(path)

        self._refresh_attachment_list()

        if errores:
            messagebox.showwarning("Adjuntos", "\n".join(errores))

    def remove_attachment(self) -> None:
        selection = self.attachments_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        self.attachment_paths.pop(idx)
        self._refresh_attachment_list()

    def save_task(self) -> bool:
        prompt = self.prompt_box.get_text()
        if not prompt:
            messagebox.showwarning("Sin prompt", "Genera o escribe un prompt antes de guardar.")
            return False

        if self.current_task is None:
            if not self._validate_required():
                return False
            data = self._collect_form_data()
            self.current_task = Tarea(
                id=generate_task_id(),
                usuario=self.perfil_var.get() or "Usuario",
                contexto=self.contexto_var.get() or "General",
                area=data.get("area", "gestion"),
                objetivo=data.get("titulo") or data.get("objetivo", ""),
                entradas=data.get("entradas", ""),
                restricciones=data.get("restricciones", ""),
                formato_salida=data.get("formato_salida", ""),
                prioridad=data.get("prioridad", "Media"),
                payload_json=json.dumps(data, ensure_ascii=False),
                prompt_generado=prompt,
            )
        else:
            self.current_task.prompt_generado = prompt
            if not self.current_task.payload_json:
                self.current_task.payload_json = json.dumps(self._collect_form_data(), ensure_ascii=False)

        future = self.executor.submit(guardar_tarea, self.current_task)
        self.root.after(40, lambda: self._poll_future(future, "Tarea guardada correctamente."))
        return True

    def export_pdf(self) -> None:
        prompt = self.prompt_box.get_text()
        if not prompt:
            messagebox.showwarning("Sin contenido", "No hay prompt para exportar.")
            return

        filename = filedialog.asksaveasfilename(
            title="Exportar prompt a PDF",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"prompt_{self.template_var.get()}.pdf",
        )
        if not filename:
            return

        metadata = {
            "Usuario": self.perfil_var.get(),
            "Contexto": self.contexto_var.get(),
            "Plantilla": self.template_var.get(),
        }
        future = self.executor.submit(export_prompt_to_pdf, "Prompt PROM-9™", metadata, prompt, filename)
        self.root.after(40, lambda: self._poll_future(future, f"PDF exportado en:\n{filename}"))

    def _poll_future(self, future, success_message: str) -> None:
        if not future.done():
            self.root.after(50, lambda: self._poll_future(future, success_message))
            return
        try:
            future.result()
            self._refresh_history()
            if success_message == "Tarea guardada correctamente.":
                self.is_dirty = False
                self.last_saved_prompt = self.prompt_box.get_text()
                if self.pending_reset_after_save:
                    self._reset_form()
            messagebox.showinfo("Operación completada", success_message)
        except RuntimeError as exc:
            self.pending_reset_after_save = False
            messagebox.showerror("Error", str(exc))

    def _refresh_history(self) -> None:
        self.history_cache = listar_tareas()

    def show_history(self) -> None:
        self._refresh_history()
        callbacks = {
            "view": self._history_view_prompt,
            "clone": self._history_clone_task,
            "export": self._history_export_pdf,
            "delete": self._history_delete_task,
        }
        HistoryWindow(self.root, self.history_cache, callbacks)

    def _task_by_id(self, task_id: str) -> Tarea | None:
        return next((item for item in self.history_cache if item.id == task_id), None)

    def _history_view_prompt(self, task_id: str) -> None:
        task = self._task_by_id(task_id)
        if not task:
            return
        self.current_task = task
        self.prompt_box.set_text(task.prompt_generado)
        self.attachment_paths = []
        self._refresh_attachment_list()
        self.is_dirty = False

        payload: dict[str, object] | None = None
        if task.payload_json:
            try:
                loaded = json.loads(task.payload_json)
                if isinstance(loaded, dict):
                    payload = loaded
            except json.JSONDecodeError:
                payload = None

        if payload is not None:
            self._rehydrate_form_from_payload(payload, task.usuario, task.contexto, task.area)
            messagebox.showinfo("Ver prompt", "Formulario rehidratado. Puedes editar y regenerar.")

    def _history_clone_task(self, task_id: str) -> None:
        source = self._task_by_id(task_id)
        if not source:
            return

        clone = Tarea(
            id=generate_task_id(),
            usuario=source.usuario,
            contexto=source.contexto,
            area=source.area,
            objetivo=source.objetivo,
            entradas=source.entradas,
            restricciones=source.restricciones,
            formato_salida=source.formato_salida,
            prioridad=source.prioridad,
            payload_json=source.payload_json,
            prompt_generado=source.prompt_generado,
        )
        self.current_task = clone
        self.prompt_box.set_text(clone.prompt_generado)
        self.attachment_paths = []
        self._refresh_attachment_list()
        self.is_dirty = False

        payload: dict[str, object] | None = None
        if clone.payload_json:
            try:
                loaded = json.loads(clone.payload_json)
                if isinstance(loaded, dict):
                    payload = loaded
            except json.JSONDecodeError:
                payload = None

        if payload is not None:
            self._rehydrate_form_from_payload(payload, clone.usuario, clone.contexto, clone.area)

            messagebox.showinfo("Clonar tarea", "Tarea clonada y formulario rehidratado. Puedes editar y guardar.")
            return

        self._refresh_data_sources()
        if clone.area in list(self.template_combo["values"]):
            self.template_var.set(clone.area)
        if clone.area:
            self._on_template_changed()

        messagebox.showinfo("Clonar tarea", "Tarea clonada en memoria. Puedes editar y guardar.")

    def _rehydrate_form_from_payload(self, payload: dict[str, object], usuario: str, contexto: str, area: str) -> None:
        self._refresh_data_sources()

        perfil_values = list(self.perfil_combo["values"])
        contexto_values = list(self.contexto_combo["values"])
        template_values = list(self.template_combo["values"])

        if usuario in perfil_values:
            self.perfil_var.set(usuario)
        elif perfil_values:
            self.perfil_var.set(perfil_values[0])

        if contexto in contexto_values:
            self.contexto_var.set(contexto)
        elif contexto_values:
            self.contexto_var.set(contexto_values[0])

        if area in template_values:
            self.template_var.set(area)
        elif template_values:
            self.template_var.set(template_values[0])

        self._on_profile_change()
        self._on_context_change()
        self._on_template_changed()

        for field, _label in BASE_FIELDS:
            widget = self.base_widgets.get(field)
            if widget is not None:
                self._write_widget(widget, payload.get(field, ""))

        for key, widget in self.template_widgets.items():
            self._write_widget(widget, payload.get(key, ""))
        for key, widget in self.profile_extra_widgets.items():
            self._write_widget(widget, payload.get(key, ""))
        for key, widget in self.context_extra_widgets.items():
            self._write_widget(widget, payload.get(key, ""))
        self.is_dirty = False

    def _history_export_pdf(self, task_id: str) -> None:
        task = self._task_by_id(task_id)
        if not task:
            return

        filename = filedialog.asksaveasfilename(
            title="Exportar tarea a PDF",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"tarea_{task.id}.pdf",
        )
        if not filename:
            return

        metadata = {
            "ID": task.id,
            "Fecha": task_id_to_human(task.id),
            "Usuario": task.usuario,
            "Plantilla": task.area,
            "Contexto": task.contexto,
        }

        future = self.executor.submit(export_prompt_to_pdf, f"Tarea {task.id}", metadata, task.prompt_generado, filename)
        self.root.after(40, lambda: self._poll_future(future, f"PDF exportado en:\n{filename}"))

    def _history_delete_task(self, task_id: str) -> None:
        if not messagebox.askyesno("Eliminar tarea", f"¿Eliminar la tarea {task_id}?"):
            return
        if eliminar_tarea(task_id):
            self._refresh_history()
            messagebox.showinfo("Historial", "Tarea eliminada correctamente.")

    def _refresh_data_sources(self) -> None:
        self.perfiles = get_perfiles()
        self.contextos = get_contextos()
        self.plantillas = get_plantillas()
        self._reload_selectors()

    def _select_name(self, title: str, options: list[str]) -> str | None:
        if not options:
            messagebox.showwarning(title, "No hay elementos disponibles.")
            return None
        selected = tk.StringVar(value=options[0])
        modal = tk.Toplevel(self.root)
        _set_app_icon(modal)
        modal.title(title)
        modal.transient(self.root)
        modal.grab_set()

        body = ttk.Frame(modal, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Selecciona un elemento").pack(anchor="w")
        combo = ttk.Combobox(body, values=options, textvariable=selected, state="readonly")
        combo.pack(fill="x", pady=(6, 10))

        result = {"name": None}

        def accept() -> None:
            result["name"] = selected.get().strip()
            modal.destroy()

        actions = ttk.Frame(body)
        actions.pack(fill="x")
        ttk.Button(actions, text="Cancelar", command=modal.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(actions, text="Editar", command=accept).pack(side="right")

        self.root.wait_window(modal)
        return result["name"]

    def _select_master_type(self, title: str) -> str | None:
        options = ["Perfil", "Contexto", "Plantilla"]
        selected = tk.StringVar(value=options[0])
        modal = tk.Toplevel(self.root)
        _set_app_icon(modal)
        modal.title(title)
        modal.transient(self.root)
        modal.grab_set()

        body = ttk.Frame(modal, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Selecciona el tipo de maestro").pack(anchor="w")
        combo = ttk.Combobox(body, values=options, textvariable=selected, state="readonly")
        combo.pack(fill="x", pady=(6, 10))

        result = {"kind": None}

        def accept() -> None:
            result["kind"] = selected.get().strip()
            modal.destroy()

        actions = ttk.Frame(body)
        actions.pack(fill="x")
        ttk.Button(actions, text="Cancelar", command=modal.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(actions, text="Aceptar", command=accept).pack(side="right")

        self.root.wait_window(modal)
        return result["kind"]

    def _load_json_field(
        self,
        raw_value: str,
        default_value: list | dict,
        column_name: str | None = None,
    ) -> list | dict:
        clean_value = (raw_value or "").strip()
        if not clean_value:
            return default_value
        try:
            parsed = json.loads(clean_value)
        except json.JSONDecodeError as exc:
            if column_name:
                raise ValueError(f"JSON inválido en columna {column_name}") from exc
            raise ValueError("JSON inválido") from exc
        if isinstance(default_value, list):
            if isinstance(parsed, list):
                return parsed
            raise ValueError("Se esperaba una lista JSON")
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("Se esperaba un objeto JSON")

    def importar_maestros_csv(self) -> None:
        selected_type = self._select_master_type("Importar maestros")
        if not selected_type:
            return

        file_path = filedialog.askopenfilename(
            title="Selecciona archivo CSV",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
        )
        if not file_path:
            return

        master_configs = {
            "Perfil": {
                "required": [
                    "nombre",
                    "rol",
                    "rol_base",
                    "empresa",
                    "ubicacion",
                    "herramientas_json",
                    "estilo",
                    "nivel_tecnico",
                    "prioridades_json",
                    "extras_json",
                    "extras_fields_json",
                ],
                "json_fields": {
                    "herramientas_json": [],
                    "prioridades_json": [],
                    "extras_json": {},
                    "extras_fields_json": [],
                },
            },
            "Contexto": {
                "required": ["nombre", "rol_contextual", "enfoque_json", "no_hacer_json", "extras_fields_json"],
                "json_fields": {
                    "enfoque_json": [],
                    "no_hacer_json": [],
                    "extras_fields_json": [],
                },
            },
            "Plantilla": {
                "required": ["nombre", "label", "fields_json", "ejemplos_json"],
                "json_fields": {
                    "fields_json": [],
                    "ejemplos_json": [],
                },
            },
        }

        config = master_configs[selected_type]
        imported = 0
        updated = 0
        errors: list[str] = []

        try:
            with open(file_path, encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                fieldnames = reader.fieldnames or []
                missing_columns = [column for column in config["required"] if column not in fieldnames]
                if missing_columns:
                    messagebox.showerror(
                        "Importar maestros",
                        "Faltan columnas obligatorias: " + ", ".join(missing_columns),
                    )
                    return

                for row_index, row in enumerate(reader, start=2):
                    try:
                        nombre = (row.get("nombre") or "").strip()
                        if not nombre:
                            raise ValueError("El campo 'nombre' es obligatorio")

                        if selected_type == "Perfil":
                            payload = {
                                "nombre": nombre,
                                "rol": (row.get("rol") or "").strip(),
                                "rol_base": (row.get("rol_base") or "").strip(),
                                "empresa": (row.get("empresa") or "").strip(),
                                "ubicacion": (row.get("ubicacion") or "").strip(),
                                "herramientas": self._load_json_field(
                                    row.get("herramientas_json", ""),
                                    config["json_fields"]["herramientas_json"],
                                    "herramientas_json",
                                ),
                                "estilo": (row.get("estilo") or "").strip(),
                                "nivel_tecnico": (row.get("nivel_tecnico") or "").strip(),
                                "prioridades": self._load_json_field(
                                    row.get("prioridades_json", ""),
                                    config["json_fields"]["prioridades_json"],
                                    "prioridades_json",
                                ),
                                "extras": self._load_json_field(
                                    row.get("extras_json", ""),
                                    config["json_fields"]["extras_json"],
                                    "extras_json",
                                ),
                                "extras_fields": self._load_json_field(
                                    row.get("extras_fields_json", ""),
                                    config["json_fields"]["extras_fields_json"],
                                    "extras_fields_json",
                                ),
                            }
                            if update_perfil(nombre, payload):
                                updated += 1
                            else:
                                insert_perfil(payload)
                                imported += 1

                        elif selected_type == "Contexto":
                            payload = {
                                "nombre": nombre,
                                "rol_contextual": (row.get("rol_contextual") or "").strip(),
                                "enfoque": self._load_json_field(
                                    row.get("enfoque_json", ""),
                                    config["json_fields"]["enfoque_json"],
                                    "enfoque_json",
                                ),
                                "no_hacer": self._load_json_field(
                                    row.get("no_hacer_json", ""),
                                    config["json_fields"]["no_hacer_json"],
                                    "no_hacer_json",
                                ),
                                "extras_fields": self._load_json_field(
                                    row.get("extras_fields_json", ""),
                                    config["json_fields"]["extras_fields_json"],
                                    "extras_fields_json",
                                ),
                            }
                            if update_contexto(nombre, payload):
                                updated += 1
                            else:
                                insert_contexto(payload)
                                imported += 1
                        else:
                            payload = {
                                "nombre": nombre,
                                "label": (row.get("label") or "").strip(),
                                "fields": self._load_json_field(
                                    row.get("fields_json", ""),
                                    config["json_fields"]["fields_json"],
                                    "fields_json",
                                ),
                                "ejemplos": self._load_json_field(
                                    row.get("ejemplos_json", ""),
                                    config["json_fields"]["ejemplos_json"],
                                    "ejemplos_json",
                                ),
                            }
                            if update_plantilla(nombre, payload):
                                updated += 1
                            else:
                                upsert_plantilla(payload)
                                imported += 1
                            self._ensure_template_py_exists(nombre)
                    except Exception as exc:
                        errors.append(f"Fila {row_index}: {exc}")
        except Exception as exc:
            messagebox.showerror("Importar maestros", f"Error al leer el CSV: {exc}")
            return

        self._refresh_data_sources()
        summary = [f"Importados: {imported}", f"Actualizados: {updated}", f"Errores: {len(errors)}"]
        if errors:
            summary.append("\nDetalle de errores:")
            summary.extend(errors[:10])
            if len(errors) > 10:
                summary.append(f"... y {len(errors) - 10} más")
        messagebox.showinfo("Importar maestros", "\n".join(summary))

    def exportar_maestros_csv(self) -> None:
        selected_type = self._select_master_type("Exportar maestros")
        if not selected_type:
            return

        file_path = filedialog.asksaveasfilename(
            title="Guardar CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not file_path:
            return

        if selected_type == "Perfil":
            records = get_perfiles()
            fieldnames = [
                "nombre",
                "rol",
                "rol_base",
                "empresa",
                "ubicacion",
                "herramientas_json",
                "estilo",
                "nivel_tecnico",
                "prioridades_json",
                "extras_json",
                "extras_fields_json",
            ]
            rows = [
                {
                    "nombre": item.get("nombre", ""),
                    "rol": item.get("rol", ""),
                    "rol_base": item.get("rol_base", item.get("rol", "")),
                    "empresa": item.get("empresa", ""),
                    "ubicacion": item.get("ubicacion", ""),
                    "herramientas_json": json.dumps(item.get("herramientas", []), ensure_ascii=False),
                    "estilo": item.get("estilo", ""),
                    "nivel_tecnico": item.get("nivel_tecnico", ""),
                    "prioridades_json": json.dumps(item.get("prioridades", []), ensure_ascii=False),
                    "extras_json": json.dumps(item.get("extras", {}), ensure_ascii=False),
                    "extras_fields_json": json.dumps(item.get("extras_fields", []), ensure_ascii=False),
                }
                for item in records
            ]
        elif selected_type == "Contexto":
            records = get_contextos()
            fieldnames = ["nombre", "rol_contextual", "enfoque_json", "no_hacer_json", "extras_fields_json"]
            rows = [
                {
                    "nombre": item.get("nombre", ""),
                    "rol_contextual": item.get("rol_contextual", ""),
                    "enfoque_json": json.dumps(item.get("enfoque", []), ensure_ascii=False),
                    "no_hacer_json": json.dumps(item.get("no_hacer", []), ensure_ascii=False),
                    "extras_fields_json": json.dumps(item.get("extras_fields", []), ensure_ascii=False),
                }
                for item in records
            ]
        else:
            records = get_plantillas()
            fieldnames = ["nombre", "label", "fields_json", "ejemplos_json"]
            rows = [
                {
                    "nombre": item.get("nombre", ""),
                    "label": item.get("label", ""),
                    "fields_json": json.dumps(item.get("fields", []), ensure_ascii=False),
                    "ejemplos_json": json.dumps(item.get("ejemplos", []), ensure_ascii=False),
                }
                for item in records
            ]

        try:
            with open(file_path, "w", encoding="utf-8-sig", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        except Exception as exc:
            messagebox.showerror("Exportar maestros", f"No se pudo exportar el CSV: {exc}")
            return

        messagebox.showinfo("Exportar maestros", f"Se exportaron {len(rows)} registros en:\n{file_path}")

    def new_profile(self) -> None:
        modal = ProfileEditorDialog(self.root)
        self.root.wait_window(modal)
        if not modal.result:
            return
        selected_name = modal.result.get("nombre", "")
        self.perfiles = get_perfiles()
        self.perfiles.append(modal.result)
        guardar_perfiles(self.perfiles)
        self._refresh_data_sources()
        if selected_name:
            self.perfil_var.set(selected_name)
            self._on_profile_change()

    def edit_profile(self) -> None:
        self.perfiles = get_perfiles()
        profile_names = [item.get("nombre", "") for item in self.perfiles]
        selected_name = self._select_name("Editar Perfil", profile_names)
        if not selected_name:
            return
        try:
            idx = profile_names.index(selected_name)
        except ValueError:
            return
        modal = ProfileEditorDialog(self.root, self.perfiles[idx])
        self.root.wait_window(modal)
        if not modal.result:
            return
        self.perfiles[idx] = modal.result
        guardar_perfiles(self.perfiles)

        self.perfiles = get_perfiles()
        self._refresh_data_sources()
        selected_name = modal.result.get("nombre", selected_name)
        self.perfil_var.set(selected_name)
        self._on_profile_change()

    def delete_profile(self) -> None:
        self.perfiles = get_perfiles()
        selected_name = self._select_name("Eliminar Perfil", [item.get("nombre", "") for item in self.perfiles])
        if not selected_name:
            return
        if not messagebox.askyesno(
            "Eliminar Perfil",
            f"¿Eliminar perfil '{selected_name}'? Esta acción no se puede deshacer.",
        ):
            return

        current = self.perfil_var.get()
        if delete_perfil(selected_name):
            messagebox.showinfo("Perfiles", "Eliminado correctamente.")
            self._refresh_data_sources()
            if current == selected_name:
                options = list(self.perfil_combo["values"])
                self.perfil_var.set(options[0] if options else "")
                self._on_profile_change()
        else:
            messagebox.showerror("Perfiles", "No se pudo eliminar")

    def new_context(self) -> None:
        modal = ContextEditorDialog(self.root)
        self.root.wait_window(modal)
        if not modal.result:
            return
        insert_contexto(modal.result)
        self._refresh_data_sources()

    def edit_context(self) -> None:
        self.contextos = get_contextos()
        selected_name = self._select_name("Editar Contexto", [item.get("nombre", "") for item in self.contextos])
        if not selected_name:
            return
        context = self._selected_item(self.contextos, selected_name)
        if not context:
            return
        original_name = context.get("nombre", "")
        modal = ContextEditorDialog(self.root, context)
        self.root.wait_window(modal)
        if not modal.result:
            return
        updated = modal.result
        update_contexto(original_name, updated)
        self._refresh_data_sources()

    def delete_context(self) -> None:
        self.contextos = get_contextos()
        selected_name = self._select_name("Eliminar Contexto", [item.get("nombre", "") for item in self.contextos])
        if not selected_name:
            return
        if not messagebox.askyesno(
            "Eliminar Contexto",
            f"¿Eliminar contexto '{selected_name}'? Esta acción no se puede deshacer.",
        ):
            return

        current = self.contexto_var.get()
        if delete_contexto(selected_name):
            messagebox.showinfo("Contextos", "Eliminado correctamente.")
            self._refresh_data_sources()
            if current == selected_name:
                options = list(self.contexto_combo["values"])
                self.contexto_var.set(options[0] if options else "")
                self._on_context_change()
        else:
            messagebox.showerror("Contextos", "No se pudo eliminar")

    def _template_path(self, template_name: str) -> Path:
        return get_templates_dir() / f"{template_name}.py"

    @staticmethod
    def _template_stub_content() -> str:
        return (
            '"""Plantilla personalizada PROM-9™."""\n\n'
            "from __future__ import annotations\n\n"
            "from typing import Dict\n\n"
            "from .prom9_base import render_base\n\n\n"
            "def render_custom(payload: Dict[str, str]) -> str:\n"
            "    return render_base(payload)\n"
        )

    def _ensure_template_py_exists(self, nombre: str) -> None:
        get_templates_dir().mkdir(parents=True, exist_ok=True)
        path = self._template_path(nombre)
        if path.exists():
            return
        path.write_text(self._template_stub_content(), encoding="utf-8")

    def asistente_ia(self) -> None:
        dialog = AsistenteIADialog(self)
        self.root.wait_window(dialog)

    def _apply_ai_master_to_form(self, kind: str, payload: dict[str, object]) -> dict[str, object] | None:
        if kind == "perfil":
            modal = ProfileEditorDialog(self.root, payload)
            self.root.wait_window(modal)
            if modal.result:
                return modal.result
            return None

        if kind == "contexto":
            modal = ContextEditorDialog(self.root, payload)
            self.root.wait_window(modal)
            if modal.result:
                return modal.result
            return None

        template_name = str(payload.get("nombre", "")).strip()
        content = str(payload.get("content", "")).strip() or self._template_stub_content()
        template_data = {
            "nombre": template_name,
            "label": str(payload.get("label", "")).strip(),
            "fields": payload.get("fields", []),
            "ejemplos": payload.get("ejemplos", []),
        }
        modal = TemplateEditorDialog(self.root, template_data, content)
        self.root.wait_window(modal)
        if not modal.result:
            return None
        return {
            "nombre": template_name,
            "label": str(modal.result.get("label", "")).strip(),
            "fields": modal.result.get("fields", []),
            "ejemplos": modal.result.get("ejemplos", []),
            "content": str(modal.result.get("content", "")),
        }

    def _save_ai_master(self, kind: str, payload: dict[str, object], parent: tk.Widget | None = None) -> bool:
        nombre = str(payload.get("nombre", "")).strip()
        if not nombre:
            messagebox.showwarning("Asistente IA", "El nombre es obligatorio para guardar.", parent=parent)
            return False

        if kind == "perfil":
            perfiles = get_perfiles()
            existing = self._selected_item(perfiles, nombre)
            if existing and not messagebox.askyesno(
                "Asistente IA",
                f"El perfil '{nombre}' ya existe. ¿Deseas sobrescribirlo?",
                parent=parent,
            ):
                return False

            updated_perfiles: list[dict[str, object]] = []
            replaced = False
            for perfil in perfiles:
                if str(perfil.get("nombre", "")).strip() == nombre:
                    updated_perfiles.append(dict(payload))
                    replaced = True
                else:
                    updated_perfiles.append(perfil)
            if not replaced:
                updated_perfiles.append(dict(payload))

            guardar_perfiles(updated_perfiles)
            self.perfiles = get_perfiles()

        elif kind == "contexto":
            existing = self._selected_item(self.contextos, nombre)
            if existing and not messagebox.askyesno(
                "Asistente IA",
                f"El contexto '{nombre}' ya existe. ¿Deseas sobrescribirlo?",
                parent=parent,
            ):
                return False
            if existing:
                if not update_contexto(nombre, payload):
                    insert_contexto(payload)
            else:
                insert_contexto(payload)

        elif kind == "plantilla":
            existing = self._selected_item(self.plantillas, nombre)
            if existing and not messagebox.askyesno(
                "Asistente IA",
                f"La plantilla '{nombre}' ya existe. ¿Deseas sobrescribirla?",
                parent=parent,
            ):
                return False

            plantilla_payload = {
                "nombre": nombre,
                "label": str(payload.get("label", "")).strip(),
                "fields": payload.get("fields", []),
                "ejemplos": payload.get("ejemplos", []),
            }
            if existing:
                if not update_plantilla(nombre, plantilla_payload):
                    upsert_plantilla(plantilla_payload)
            else:
                upsert_plantilla(plantilla_payload)

            content = str(payload.get("content", ""))
            if content.strip():
                self._template_path(nombre).write_text(content, encoding="utf-8")
            else:
                self._ensure_template_py_exists(nombre)
        else:
            messagebox.showerror("Asistente IA", "Tipo de maestro inválido.", parent=parent)
            return False

        self._refresh_data_sources()
        if kind == "perfil":
            self.perfil_var.set(nombre)
            self._on_profile_change()
        elif kind == "contexto":
            self.contexto_var.set(nombre)
            self._on_context_change()
        elif kind == "plantilla":
            self.template_var.set(nombre)
            self._on_template_changed()

        labels = {"perfil": "Perfil", "contexto": "Contexto", "plantilla": "Plantilla"}
        messagebox.showinfo("Asistente IA", f"{labels.get(kind, kind)} guardado correctamente.", parent=parent)
        return True

    def new_template(self) -> None:
        template_name = simpledialog.askstring("Nueva Plantilla", "Nombre de plantilla (sin .py):", parent=self.root)
        if not template_name:
            return
        template_name = template_name.strip().lower()
        if not template_name:
            return
        tpl_path = self._template_path(template_name)
        initial = '"""Plantilla personalizada PROM-9™."""\n\n' + (
            "def render_custom(payload: dict[str, str]) -> str:\n"
            "    return \"\"\n"
        )
        modal = TemplateEditorDialog(
            self.root,
            {"nombre": template_name, "label": template_name.title(), "fields": [], "ejemplos": []},
            initial,
        )
        self.root.wait_window(modal)
        if not modal.result:
            return
        tpl_path.write_text(str(modal.result.get("content", "")), encoding="utf-8")
        upsert_plantilla(
            {
                "nombre": template_name,
                "label": str(modal.result.get("label", template_name.title())),
                "fields": modal.result.get("fields", []),
                "ejemplos": modal.result.get("ejemplos", []),
            }
        )
        self._refresh_data_sources()

    def edit_template(self) -> None:
        self.plantillas = get_plantillas()
        selected_name = self._select_name("Editar Plantilla", [item.get("nombre", "") for item in self.plantillas])
        if not selected_name:
            return
        tpl_path = self._template_path(selected_name)
        if not tpl_path.exists():
            messagebox.showerror("Plantillas", f"No existe el archivo: {tpl_path.name}")
            return
        tpl_data = self._selected_item(self.plantillas, selected_name) or {
            "nombre": selected_name,
            "label": selected_name.title(),
            "fields": [],
            "ejemplos": [],
        }
        modal = TemplateEditorDialog(self.root, tpl_data, tpl_path.read_text(encoding="utf-8"))
        self.root.wait_window(modal)
        if not modal.result:
            return
        tpl_path.write_text(str(modal.result.get("content", "")), encoding="utf-8")
        saved = update_plantilla(
            selected_name,
            {
                "label": str(modal.result.get("label", tpl_data.get("label", ""))),
                "fields": modal.result.get("fields", []),
                "ejemplos": modal.result.get("ejemplos", []),
            },
        )
        if not saved:
            upsert_plantilla(
                {
                    "nombre": selected_name,
                    "label": str(modal.result.get("label", tpl_data.get("label", ""))),
                    "fields": modal.result.get("fields", []),
                    "ejemplos": modal.result.get("ejemplos", []),
                }
            )
        self._refresh_data_sources()

    def delete_template(self) -> None:
        self.plantillas = get_plantillas()
        selected_name = self._select_name("Eliminar Plantilla", [item.get("nombre", "") for item in self.plantillas])
        if not selected_name:
            return
        core_templates = {"gestion", "it", "ventas", "contabilidad"}
        if selected_name.lower() in core_templates:
            messagebox.showinfo("Plantillas", "No se pueden eliminar las plantillas core.")
            return
        if not messagebox.askyesno(
            "Eliminar Plantilla",
            f"¿Eliminar plantilla '{selected_name}'? Esta acción no se puede deshacer.",
        ):
            return

        current = self.template_var.get()
        if delete_plantilla(selected_name):
            remove_template_file = messagebox.askyesno(
                "Eliminar archivo de plantilla",
                f"¿También quieres eliminar el archivo '{selected_name}.py' asociado?",
                default=messagebox.NO,
            )
            if remove_template_file:
                tpl_path = self._template_path(selected_name)
                if tpl_path.exists():
                    tpl_path.unlink()
            messagebox.showinfo("Plantillas", "Eliminado correctamente.")
            self._refresh_data_sources()
            if current == selected_name:
                options = list(self.template_combo["values"])
                self.template_var.set(options[0] if options else "")
                self._on_template_changed()
        else:
            messagebox.showerror("Plantillas", "No se pudo eliminar")

    def _on_close(self) -> None:
        try:
            if self.voice_input and self.voice_input.is_recording:
                self.voice_input.stop_recording()
        except Exception:
            pass
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def run_ui() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    elif "clam" in style.theme_names():
        style.theme_use("clam")
    PromptEngineUI(root)
    root.mainloop()
