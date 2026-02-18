"""Interfaz gráfica Tkinter para PROM-9™ Prompt Engine."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

from .widgets import DictationField

from .attachments import validar_tipo_archivo
from .motor import generar_prompt
from .pdf_export import export_prompt_to_pdf
from .schemas import Tarea, generate_task_id, task_id_to_human
from .storage import (
    CONTEXTOS_FILE,
    PERFILES_FILE,
    PLANTILLAS_FILE,
    cargar_contextos,
    cargar_perfiles,
    cargar_plantillas,
    eliminar_tarea,
    insertar_registro_json,
    guardar_contextos,
    guardar_perfiles,
    guardar_plantillas,
    guardar_tarea,
    listar_tareas,
    actualizar_registro_json,
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

        initial = dict(profile or {})
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

        actions = ttk.Frame(form)
        actions.grid(row=len(field_defs), column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(actions, text="Cancelar", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(actions, text="Guardar", command=self._save).pack(side="right")

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
        self.result = payload
        self.destroy()


class ContextEditorDialog(tk.Toplevel):
    def __init__(self, master: tk.Widget, context: dict | None = None) -> None:
        super().__init__(master)
        _set_app_icon(self)
        self.title("Contexto")
        self.geometry("560x460")
        self.transient(master)
        self.grab_set()
        self.result: dict | None = None

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
        initial = dict(context or {})

        for idx, (key, label, multiline) in enumerate(field_defs):
            ttk.Label(form, text=label).grid(row=idx, column=0, sticky="nw", pady=4, padx=(0, 8))
            if multiline:
                widget: tk.Widget = ScrolledText(form, height=5, wrap="word")
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

        actions = ttk.Frame(form)
        actions.grid(row=len(field_defs), column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(actions, text="Cancelar", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(actions, text="Guardar", command=self._save).pack(side="right")

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
        self.result = payload
        self.destroy()


class TemplateEditorDialog(tk.Toplevel):
    def __init__(self, master: tk.Widget, template_name: str, content: str) -> None:
        super().__init__(master)
        _set_app_icon(self)
        self.title(f"Plantilla: {template_name}")
        self.geometry("840x600")
        self.transient(master)
        self.grab_set()
        self.content: str | None = None

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.editor = ScrolledText(frame, wrap="word")
        self.editor.grid(row=0, column=0, sticky="nsew")
        self.editor.insert("1.0", content)

        actions = ttk.Frame(frame)
        actions.grid(row=1, column=0, sticky="e", pady=(12, 0))
        ttk.Button(actions, text="Cancelar", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(actions, text="Guardar", command=self._save).pack(side="right")

    def _save(self) -> None:
        self.content = self.editor.get("1.0", "end")
        self.destroy()


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

        self.perfiles = cargar_perfiles()
        self.contextos = cargar_contextos()
        self.plantillas = cargar_plantillas()
        self.history_cache: list[Tarea] = []
        self.current_task: Tarea | None = None

        self.perfil_var = tk.StringVar()
        self.contexto_var = tk.StringVar()
        self.template_var = tk.StringVar()

        self.base_widgets: dict[str, tk.Widget | DictationField] = {}
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
        archivo.add_separator()
        archivo.add_command(label="Nuevo Contexto", command=self.new_context)
        archivo.add_command(label="Editar Contexto", command=self.edit_context)
        archivo.add_separator()
        archivo.add_command(label="Nueva Plantilla", command=self.new_template)
        archivo.add_command(label="Editar Plantilla", command=self.edit_template)
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self._on_close)
        menubar.add_cascade(label="Archivo", menu=archivo)
        self.root.config(menu=menubar)


    def _build_ui(self) -> None:
        root_frame = ttk.Frame(self.root, padding=12)
        root_frame.pack(fill="both", expand=True)
        root_frame.columnconfigure(0, weight=1)
        root_frame.rowconfigure(0, weight=3)
        root_frame.rowconfigure(1, weight=2)
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

        ttk.Label(form_inner, text="Contexto").grid(row=1, column=0, sticky="w", pady=4)
        self.contexto_combo = ttk.Combobox(form_inner, textvariable=self.contexto_var, state="readonly")
        self.contexto_combo.grid(row=1, column=1, sticky="ew", pady=4)

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

        self.template_fields_frame = ttk.LabelFrame(form_inner, text="Campos de plantilla", padding=8)
        self.template_fields_frame.grid(row=99, column=0, columnspan=2, sticky="ew", pady=(8, 0))
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
        ttk.Button(actions_row, text="Exportar PDF", command=self._export_pdf).pack(side="left", padx=6)
        ttk.Button(actions_row, text="Historial", command=self._open_history).pack(side="left", padx=6)
        ttk.Button(actions_row, text="📋 Copiar Prompt", command=self._copy_prompt).pack(side="left", padx=6)

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
            entry.grid(row=idx, column=1, sticky="ew", pady=4)
            entry.bind("<FocusIn>", lambda _e, f=key: self._update_context_panel(f))
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

    def _collect_form_data(self) -> dict[str, str]:
        data = {"area": self.template_var.get()}
        for field, _ in BASE_FIELDS:
            data[field] = self._read_widget(self.base_widgets[field])
        for field, entry in self.template_widgets.items():
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

    def save_task(self) -> None:
        prompt = self.prompt_box.get_text()
        if not prompt:
            messagebox.showwarning("Sin prompt", "Genera o escribe un prompt antes de guardar.")
            return

        if self.current_task is None:
            if not self._validate_required():
                return
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
                prompt_generado=prompt,
            )
        else:
            self.current_task.prompt_generado = prompt

        future = self.executor.submit(guardar_tarea, self.current_task)
        self.root.after(40, lambda: self._poll_future(future, "Tarea guardada correctamente."))

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
            messagebox.showinfo("Operación completada", success_message)
        except RuntimeError as exc:
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
            prompt_generado=source.prompt_generado,
        )
        self.current_task = clone
        self.prompt_box.set_text(clone.prompt_generado)
        self.attachment_paths = []
        self._refresh_attachment_list()

        if clone.usuario:
            self.perfil_var.set(clone.usuario)
        if clone.contexto:
            self.contexto_var.set(clone.contexto)
        if clone.area:
            self.template_var.set(clone.area)
            self._on_template_changed()

        messagebox.showinfo("Clonar tarea", "Tarea clonada en memoria. Puedes editar y guardar.")

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
        self.perfiles = cargar_perfiles()
        self.contextos = cargar_contextos()
        self.plantillas = cargar_plantillas()
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

    def new_profile(self) -> None:
        modal = ProfileEditorDialog(self.root)
        self.root.wait_window(modal)
        if not modal.result:
            return
        insertar_registro_json(PERFILES_FILE, modal.result)
        self._refresh_data_sources()

    def edit_profile(self) -> None:
        self.perfiles = cargar_perfiles()
        selected_name = self._select_name("Editar Perfil", [item.get("nombre", "") for item in self.perfiles])
        if not selected_name:
            return
        profile = self._selected_item(self.perfiles, selected_name)
        if not profile:
            return
        original_name = profile.get("nombre", "")
        modal = ProfileEditorDialog(self.root, profile)
        self.root.wait_window(modal)
        if not modal.result:
            return
        updated = modal.result
        if original_name != updated.get("nombre"):
            perfiles = [item for item in self.perfiles if item.get("nombre") != original_name]
            perfiles.append(updated)
            guardar_perfiles(perfiles)
        else:
            actualizar_registro_json(PERFILES_FILE, original_name, updated)
        self._refresh_data_sources()

    def new_context(self) -> None:
        modal = ContextEditorDialog(self.root)
        self.root.wait_window(modal)
        if not modal.result:
            return
        insertar_registro_json(CONTEXTOS_FILE, modal.result)
        self._refresh_data_sources()

    def edit_context(self) -> None:
        self.contextos = cargar_contextos()
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
        if original_name != updated.get("nombre"):
            contextos = [item for item in self.contextos if item.get("nombre") != original_name]
            contextos.append(updated)
            guardar_contextos(contextos)
        else:
            actualizar_registro_json(CONTEXTOS_FILE, original_name, updated)
        self._refresh_data_sources()

    def _template_path(self, template_name: str) -> Path:
        return PLANTILLAS_FILE.parent / f"{template_name}.py"

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
        modal = TemplateEditorDialog(self.root, template_name, initial)
        self.root.wait_window(modal)
        if modal.content is None:
            return
        tpl_path.write_text(modal.content, encoding="utf-8")

        plantillas = cargar_plantillas()
        if not any(item.get("nombre") == template_name for item in plantillas):
            plantillas.append({"nombre": template_name, "label": template_name.title(), "fields": [], "ejemplos": []})
            guardar_plantillas(plantillas)
        self._refresh_data_sources()

    def edit_template(self) -> None:
        self.plantillas = cargar_plantillas()
        selected_name = self._select_name("Editar Plantilla", [item.get("nombre", "") for item in self.plantillas])
        if not selected_name:
            return
        tpl_path = self._template_path(selected_name)
        if not tpl_path.exists():
            messagebox.showerror("Plantillas", f"No existe el archivo: {tpl_path.name}")
            return
        modal = TemplateEditorDialog(self.root, selected_name, tpl_path.read_text(encoding="utf-8"))
        self.root.wait_window(modal)
        if modal.content is None:
            return
        tpl_path.write_text(modal.content, encoding="utf-8")
        self._refresh_data_sources()

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
