"""Interfaz gráfica Tkinter profesional para PROM-9™ Prompt Engine."""

from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from .motor import generar_prompt
from .pdf_export import export_prompt_to_pdf
from .schemas import Tarea
from .storage import (
    CONTEXTOS_FILE,
    PERFILES_FILE,
    cargar_contextos,
    cargar_perfiles,
    guardar_tarea,
    listar_tareas,
)

BASE_FIELDS = [
    ("titulo", "Título"),
    ("objetivo", "Objetivo"),
    ("situacion", "Tipo de situación"),
    ("urgencia", "Urgencia"),
    ("contexto_detallado", "Contexto detallado"),
    ("restricciones", "Restricciones"),
]

BASE_HELP = {
    "titulo": (
        "Nombre breve y reconocible de la tarea.",
        "Ejemplo: 'Plan comercial Q4 para clientes B2B'.",
    ),
    "objetivo": (
        "Resultado concreto que necesitas conseguir.",
        "Ejemplo: 'Diseñar una propuesta de upselling en 30 días'.",
    ),
    "situacion": (
        "Tipo de caso que debe analizar el asistente.",
        "Ejemplo: 'Incidencia técnica en sistema de pedidos'.",
    ),
    "urgencia": (
        "Nivel de prioridad temporal del trabajo.",
        "Ejemplo: 'Alta: debe resolverse hoy'.",
    ),
    "contexto_detallado": (
        "Información operativa o del negocio que aporta precisión.",
        "Ejemplo: 'Cooperativa con 2 centros logísticos y 40 usuarios'.",
    ),
    "restricciones": (
        "Límites que la respuesta debe respetar.",
        "Ejemplo: 'No usar herramientas de pago ni contratar personal'.",
    ),
}

TEMPLATE_CONFIG = {
    "it": {
        "label": "IT",
        "fields": [
            ("stack", "Stack tecnológico"),
            ("nivel_tecnico", "Nivel técnico"),
        ],
        "help": {
            "stack": (
                "Tecnologías disponibles o preferidas para la solución.",
                "Ejemplo: 'Python, FastAPI, PostgreSQL, Docker'.",
            ),
            "nivel_tecnico": (
                "Profundidad técnica esperada en la respuesta.",
                "Ejemplo: 'Intermedio con pasos reproducibles'.",
            ),
        },
    },
    "ventas": {
        "label": "Ventas",
        "fields": [
            ("segmento", "Segmento"),
            ("propuesta_valor", "Propuesta de valor"),
        ],
        "help": {
            "segmento": (
                "Cliente objetivo principal.",
                "Ejemplo: 'Pymes agroalimentarias de Andalucía'.",
            ),
            "propuesta_valor": (
                "Beneficio diferenciador de la oferta.",
                "Ejemplo: 'Reducción de costes operativos en 20%'.",
            ),
        },
    },
    "contabilidad": {
        "label": "Contabilidad",
        "fields": [
            ("normativa", "Normativa"),
            ("periodo", "Periodo"),
        ],
        "help": {
            "normativa": (
                "Marco contable y fiscal aplicable.",
                "Ejemplo: 'PGC España + criterios internos SCA'.",
            ),
            "periodo": (
                "Tramo temporal analizado.",
                "Ejemplo: 'Cierre mensual de septiembre 2026'.",
            ),
        },
    },
    "gestion": {
        "label": "Gestión",
        "fields": [
            ("area_operativa", "Área operativa"),
            ("horizonte", "Horizonte"),
        ],
        "help": {
            "area_operativa": (
                "Unidad o proceso de gestión afectado.",
                "Ejemplo: 'Planificación de turnos y mantenimiento'.",
            ),
            "horizonte": (
                "Plazo de aplicación de la propuesta.",
                "Ejemplo: '90 días con revisión quincenal'.",
            ),
        },
    },
}


def _save_json(path: Path, payload: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


class Tooltip:
    """Tooltip simple al pasar el cursor por un widget."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip_window: tk.Toplevel | None = None
        self.widget.bind("<Enter>", self._show)
        self.widget.bind("<Leave>", self._hide)

    def _show(self, _event=None) -> None:
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = ttk.Label(
            tw,
            text=self.text,
            background="#fefce8",
            relief="solid",
            borderwidth=1,
            padding=(8, 4),
            justify="left",
            wraplength=360,
        )
        label.pack()

    def _hide(self, _event=None) -> None:
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class JsonRecordDialog(tk.Toplevel):
    """Modal para crear o editar un perfil/contexto como pares clave-valor."""

    def __init__(self, master: tk.Tk, title: str, initial: dict | None = None) -> None:
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.grab_set()
        self.result: dict | None = None
        self.rows: list[tuple[ttk.Entry, ttk.Entry]] = []

        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)

        ttk.Label(container, text="Clave").grid(row=0, column=0, sticky="w")
        ttk.Label(container, text="Valor").grid(row=0, column=1, sticky="w")

        seed = initial if initial else {"nombre": ""}
        for idx, (k, v) in enumerate(seed.items(), start=1):
            self._add_row(container, idx, str(k), str(v))

        controls = ttk.Frame(container)
        controls.grid(row=999, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(controls, text="+ Campo", command=lambda: self._add_row(container, len(self.rows) + 1, "", "")).pack(side="left")
        ttk.Button(controls, text="Cancelar", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(controls, text="Guardar", command=self._save).pack(side="right")

    def _add_row(self, parent: ttk.Frame, row: int, key: str, value: str) -> None:
        key_entry = ttk.Entry(parent)
        key_entry.insert(0, key)
        key_entry.grid(row=row, column=0, sticky="ew", pady=3, padx=(0, 6))

        value_entry = ttk.Entry(parent)
        value_entry.insert(0, value)
        value_entry.grid(row=row, column=1, sticky="ew", pady=3)
        self.rows.append((key_entry, value_entry))

    def _save(self) -> None:
        payload: dict[str, str] = {}
        for key_entry, value_entry in self.rows:
            key = key_entry.get().strip()
            if not key:
                continue
            payload[key] = value_entry.get().strip()

        if not payload.get("nombre"):
            messagebox.showwarning("Validación", "El campo 'nombre' es obligatorio.", parent=self)
            return
        self.result = payload
        self.destroy()


class RecordsManagerDialog(tk.Toplevel):
    """Gestión visual de perfiles o contextos con listado y detalle."""

    def __init__(
        self,
        master: tk.Tk,
        title: str,
        records: list[dict],
    ) -> None:
        super().__init__(master)
        self.title(title)
        self.geometry("900x500")
        self.transient(master)
        self.grab_set()
        self.records = [dict(item) for item in records]
        self.saved = False

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

        left_buttons = ttk.Frame(left)
        left_buttons.pack(fill="x")
        ttk.Button(left_buttons, text="Nuevo", command=self._new_item).pack(side="left")
        ttk.Button(left_buttons, text="Editar", command=self._edit_item).pack(side="left", padx=6)

        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        ttk.Label(right, text="Detalle").pack(anchor="w")
        self.detail = ScrolledText(right, height=12, wrap="word")
        self.detail.pack(fill="both", expand=True, pady=(6, 8))
        self.detail.configure(state="disabled")

        footer = ttk.Frame(main)
        footer.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(footer, text="Cancelar", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="Guardar cambios", command=self._save_and_close).pack(side="right")

        self._refresh_list()

    def _refresh_list(self) -> None:
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
        index = selection[0]
        record = self.records[index]
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", json.dumps(record, ensure_ascii=False, indent=2))
        self.detail.configure(state="disabled")

    def _new_item(self) -> None:
        modal = JsonRecordDialog(self, "Nuevo registro")
        self.wait_window(modal)
        if modal.result:
            self.records.append(modal.result)
            self._refresh_list()

    def _edit_item(self) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        index = selection[0]
        modal = JsonRecordDialog(self, "Editar registro", initial=self.records[index])
        self.wait_window(modal)
        if modal.result:
            self.records[index] = modal.result
            self._refresh_list()
            self.listbox.selection_set(index)
            self._on_select(None)

    def _save_and_close(self) -> None:
        self.saved = True
        self.destroy()


class PromptEngineUI:
    """Ventana principal de trabajo de PROM-9™."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Prompt Engine PROM-9™")
        self.root.geometry("1260x840")

        self.executor = ThreadPoolExecutor(max_workers=2)
        self.perfiles = cargar_perfiles()
        self.contextos = cargar_contextos()
        self.current_task: Tarea | None = None
        self.history_cache: list[Tarea] = []

        self.perfil_var = tk.StringVar()
        self.contexto_var = tk.StringVar()
        self.template_var = tk.StringVar(value="gestion")

        self.base_widgets: dict[str, tk.Widget] = {}
        self.template_widgets: dict[str, ttk.Entry] = {}
        self.help_texts: dict[str, tuple[str, str]] = dict(BASE_HELP)

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
        archivo.add_command(label="Salir", command=self._on_close)
        menubar.add_cascade(label="Archivo", menu=archivo)
        self.root.config(menu=menubar)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=3)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(1, weight=1)
        container.rowconfigure(2, weight=1)

        controls = ttk.LabelFrame(container, text="Configuración de tarea", padding=10)
        controls.grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=(0, 10))
        for i in range(3):
            controls.columnconfigure(i, weight=1)

        ttk.Label(controls, text="Perfil").grid(row=0, column=0, sticky="w")
        self.perfil_combo = ttk.Combobox(controls, textvariable=self.perfil_var, state="readonly")
        self.perfil_combo.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        ttk.Label(controls, text="Contexto").grid(row=0, column=1, sticky="w")
        self.contexto_combo = ttk.Combobox(controls, textvariable=self.contexto_var, state="readonly")
        self.contexto_combo.grid(row=1, column=1, sticky="ew", padx=(0, 8))

        ttk.Label(controls, text="Plantilla").grid(row=0, column=2, sticky="w")
        self.template_combo = ttk.Combobox(
            controls,
            textvariable=self.template_var,
            state="readonly",
            values=list(TEMPLATE_CONFIG.keys()),
        )
        self.template_combo.grid(row=1, column=2, sticky="ew")
        self.template_combo.bind("<<ComboboxSelected>>", lambda _: self._render_template_fields())

        form_panel = ttk.LabelFrame(container, text="Formulario", padding=10)
        form_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        form_panel.columnconfigure(1, weight=1)

        for idx, (field, label) in enumerate(BASE_FIELDS):
            ttk.Label(form_panel, text=label).grid(row=idx, column=0, sticky="nw", padx=(0, 8), pady=4)
            widget: tk.Widget
            if field in {"objetivo", "contexto_detallado", "restricciones"}:
                widget = tk.Text(form_panel, height=3, wrap="word")
            else:
                widget = ttk.Entry(form_panel)
            widget.grid(row=idx, column=1, sticky="ew", pady=4)
            self.base_widgets[field] = widget
            self._bind_help(widget, field)

        self.template_panel = ttk.LabelFrame(form_panel, text="Datos de plantilla", padding=8)
        self.template_panel.grid(row=len(BASE_FIELDS), column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.template_panel.columnconfigure(1, weight=1)
        self._render_template_fields()

        actions = ttk.Frame(container)
        actions.grid(row=2, column=0, sticky="ew", padx=(0, 10), pady=(0, 10))
        ttk.Button(actions, text="Generar prompt", command=self.generate_prompt).pack(side="left")
        ttk.Button(actions, text="Guardar prompt en historial", command=self.save_task).pack(side="left", padx=6)
        ttk.Button(actions, text="Exportar prompt a PDF", command=self.export_pdf).pack(side="left", padx=6)
        ttk.Button(actions, text="Listar historial de tareas", command=self.show_history).pack(side="left", padx=6)
        ttk.Button(actions, text="Clonar tarea", command=self.clone_task).pack(side="left")

        output_panel = ttk.LabelFrame(container, text="Salida editable", padding=10)
        output_panel.grid(row=3, column=0, sticky="nsew", padx=(0, 10))
        output_panel.columnconfigure(0, weight=1)
        output_panel.rowconfigure(0, weight=1)
        self.prompt_box = ScrolledText(output_panel, wrap="word", height=16)
        self.prompt_box.grid(row=0, column=0, sticky="nsew")
        ttk.Button(output_panel, text="Copiar al portapapeles", command=self.copy_prompt).grid(
            row=1,
            column=0,
            sticky="e",
            pady=(8, 0),
        )

        right_panel = ttk.LabelFrame(container, text="Ayuda contextual", padding=10)
        right_panel.grid(row=0, column=1, rowspan=4, sticky="nsew")
        right_panel.rowconfigure(1, weight=1)
        ttk.Label(right_panel, text="Campo activo", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.help_title = ttk.Label(right_panel, text="Selecciona un campo", foreground="#1d4ed8")
        self.help_title.grid(row=1, column=0, sticky="nw", pady=(6, 8))
        self.help_text = ScrolledText(right_panel, wrap="word", height=25)
        self.help_text.grid(row=2, column=0, sticky="nsew")
        self.help_text.configure(state="disabled")

        history_panel = ttk.LabelFrame(container, text="Historial", padding=8)
        history_panel.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        history_panel.columnconfigure(0, weight=1)
        columns = ("id", "usuario", "contexto", "area")
        self.history_tree = ttk.Treeview(history_panel, columns=columns, show="headings", height=8)
        for col in columns:
            self.history_tree.heading(col, text=col.upper())
            self.history_tree.column(col, width=200)
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        self.history_tree.bind("<Double-1>", self._load_selected_history)

    def _bind_help(self, widget: tk.Widget, field: str) -> None:
        """Actualiza panel lateral al recibir foco y define tooltip por campo."""
        widget.bind("<FocusIn>", lambda _event, f=field: self._update_help_panel(f))
        short, example = self.help_texts.get(field, ("", ""))
        Tooltip(widget, f"{short}\n{example}")

    def _update_help_panel(self, field: str) -> None:
        """Renderiza explicación y ejemplo en panel lateral contextual."""
        brief, example = self.help_texts.get(field, ("Campo sin ayuda disponible.", ""))
        self.help_title.configure(text=field)
        self.help_text.configure(state="normal")
        self.help_text.delete("1.0", "end")
        self.help_text.insert("1.0", f"Descripción:\n{brief}\n\nEjemplo práctico:\n{example}")
        self.help_text.configure(state="disabled")

    def _reload_selectors(self) -> None:
        profile_names = [item.get("nombre", "") for item in self.perfiles]
        context_names = [item.get("nombre", "") for item in self.contextos]
        self.perfil_combo["values"] = profile_names
        self.contexto_combo["values"] = context_names
        if profile_names and self.perfil_var.get() not in profile_names:
            self.perfil_var.set(profile_names[0])
        if context_names and self.contexto_var.get() not in context_names:
            self.contexto_var.set(context_names[0])

    def _render_template_fields(self) -> None:
        for widget in self.template_panel.winfo_children():
            widget.destroy()
        self.template_widgets.clear()

        cfg = TEMPLATE_CONFIG.get(self.template_var.get(), TEMPLATE_CONFIG["gestion"])
        self.template_panel.configure(text=f"Datos de plantilla: {cfg['label']}")

        for idx, (field, label) in enumerate(cfg["fields"]):
            ttk.Label(self.template_panel, text=label).grid(row=idx, column=0, sticky="w", padx=(0, 8), pady=4)
            entry = ttk.Entry(self.template_panel)
            entry.grid(row=idx, column=1, sticky="ew", pady=4)
            self.template_widgets[field] = entry
            self.help_texts[field] = cfg["help"][field]
            self._bind_help(entry, field)

    def _selected_item(self, collection: list[dict], name: str) -> dict | None:
        for item in collection:
            if item.get("nombre") == name:
                return item
        return None

    def _read_widget(self, widget: tk.Widget) -> str:
        if isinstance(widget, tk.Text):
            return widget.get("1.0", "end").strip()
        return widget.get().strip()

    def _collect_form_data(self) -> dict[str, str]:
        data = {"area": self.template_var.get()}
        for field, _label in BASE_FIELDS:
            data[field] = self._read_widget(self.base_widgets[field])
        for field, entry in self.template_widgets.items():
            data[field] = entry.get().strip()

        # Integración con motor.py: se mapean claves de formulario a claves esperadas por generar_prompt.
        data["entradas"] = data.get("situacion", "")
        data["prioridad"] = data.get("urgencia", "") or "Media"
        data["formato_salida"] = "Respuesta estructurada"
        if data.get("contexto_detallado"):
            data["restricciones"] = (
                f"{data.get('restricciones', '')}\nContexto adicional: {data['contexto_detallado']}"
            ).strip()
        return data

    def _validate_required(self) -> bool:
        required = ["titulo", "objetivo", "situacion", "urgencia"]
        missing = [field for field in required if not self._read_widget(self.base_widgets[field])]
        if missing:
            labels = ", ".join(field.replace("_", " ") for field in missing)
            messagebox.showwarning("Validación", f"Completa los campos obligatorios: {labels}.")
            return False
        return True

    def generate_prompt(self) -> None:
        if not self._validate_required():
            return
        perfil = self._selected_item(self.perfiles, self.perfil_var.get())
        contexto = self._selected_item(self.contextos, self.contexto_var.get())
        if not perfil or not contexto:
            messagebox.showwarning("Datos incompletos", "Selecciona un perfil y un contexto válidos.")
            return

        data = self._collect_form_data()
        # Integración directa con motor existente.
        prompt = generar_prompt(data, perfil, contexto)
        self.prompt_box.delete("1.0", "end")
        self.prompt_box.insert("1.0", prompt)

        self.current_task = Tarea(
            id=str(uuid.uuid4()),
            usuario=perfil.get("nombre", "Usuario"),
            contexto=contexto.get("nombre", "General"),
            area=data.get("area", "gestion"),
            objetivo=data.get("objetivo", ""),
            entradas=data.get("entradas", ""),
            restricciones=data.get("restricciones", ""),
            formato_salida=data.get("formato_salida", ""),
            prioridad=data.get("prioridad", "Media"),
            prompt_generado=prompt,
        )

    def save_task(self) -> None:
        prompt = self.prompt_box.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("Sin prompt", "Genera o escribe un prompt antes de guardar.")
            return

        if self.current_task is None:
            if not self._validate_required():
                return
            data = self._collect_form_data()
            self.current_task = Tarea(
                id=str(uuid.uuid4()),
                usuario=self.perfil_var.get() or "Usuario",
                contexto=self.contexto_var.get() or "General",
                area=data.get("area", "gestion"),
                objetivo=data.get("objetivo", ""),
                entradas=data.get("entradas", ""),
                restricciones=data.get("restricciones", ""),
                formato_salida=data.get("formato_salida", ""),
                prioridad=data.get("prioridad", "Media"),
                prompt_generado=prompt,
            )
        else:
            self.current_task.prompt_generado = prompt

        # Operación en segundo plano para no bloquear la UI durante guardado.
        future = self.executor.submit(guardar_tarea, self.current_task)
        self.root.after(30, lambda: self._poll_future(future, "Tarea guardada correctamente."))

    def export_pdf(self) -> None:
        prompt = self.prompt_box.get("1.0", "end").strip()
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

        # Operación en segundo plano para no bloquear UI en exportación.
        future = self.executor.submit(export_prompt_to_pdf, "Prompt PROM-9™", metadata, prompt, filename)
        self.root.after(30, lambda: self._poll_future(future, f"PDF exportado en:\n{filename}"))

    def _poll_future(self, future, success_message: str) -> None:
        if not future.done():
            self.root.after(50, lambda: self._poll_future(future, success_message))
            return
        try:
            future.result()
            messagebox.showinfo("Operación completada", success_message)
            self._refresh_history()
        except RuntimeError as exc:
            messagebox.showerror("Error", str(exc))

    def _refresh_history(self) -> None:
        self.history_cache = listar_tareas()
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        for task in self.history_cache[-80:]:
            self.history_tree.insert("", "end", iid=task.id, values=(task.id, task.usuario, task.contexto, task.area))

    def show_history(self) -> None:
        self._refresh_history()
        messagebox.showinfo("Historial", "Historial actualizado. Doble clic en una fila para cargarla.")

    def _load_selected_history(self, _event) -> None:
        selected = self.history_tree.selection()
        if not selected:
            return
        task_id = selected[0]
        task = next((item for item in self.history_cache if item.id == task_id), None)
        if not task:
            return

        self.current_task = task
        self.prompt_box.delete("1.0", "end")
        self.prompt_box.insert("1.0", task.prompt_generado)

    def clone_task(self) -> None:
        selected = self.history_tree.selection()
        if not selected:
            messagebox.showwarning("Clonar tarea", "Selecciona una tarea del historial para clonar.")
            return
        task_id = selected[0]
        source = next((item for item in self.history_cache if item.id == task_id), None)
        if not source:
            return
        clone = Tarea(
            id=str(uuid.uuid4()),
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
        self.prompt_box.delete("1.0", "end")
        self.prompt_box.insert("1.0", clone.prompt_generado)
        messagebox.showinfo("Clonar tarea", "Tarea clonada en memoria. Puedes editar y guardar.")

    def copy_prompt(self) -> None:
        prompt = self.prompt_box.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("Portapapeles", "No hay contenido para copiar.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(prompt)
        messagebox.showinfo("Portapapeles", "Prompt copiado al portapapeles.")

    def _persist_collection(self, records: list[dict], path: Path) -> None:
        future = self.executor.submit(_save_json, path, records)
        self.root.after(30, lambda: self._poll_future(future, "Cambios guardados."))

    def _open_records_manager(self, title: str, records: list[dict], path: Path, is_profile: bool) -> None:
        modal = RecordsManagerDialog(self.root, title, records)
        self.root.wait_window(modal)
        if not modal.saved:
            return
        self._persist_collection(modal.records, path)
        if is_profile:
            self.perfiles = modal.records
        else:
            self.contextos = modal.records
        self._reload_selectors()

    def new_profile(self) -> None:
        self._open_records_manager("Gestión de perfiles", self.perfiles, PERFILES_FILE, is_profile=True)

    def edit_profile(self) -> None:
        self._open_records_manager("Gestión de perfiles", self.perfiles, PERFILES_FILE, is_profile=True)

    def new_context(self) -> None:
        self._open_records_manager("Gestión de contextos", self.contextos, CONTEXTOS_FILE, is_profile=False)

    def edit_context(self) -> None:
        self._open_records_manager("Gestión de contextos", self.contextos, CONTEXTOS_FILE, is_profile=False)

    def _on_close(self) -> None:
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
