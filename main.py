"""ESP32 R4sGate Wallpaper Studio — Tkinter front end.

Converts images into an RGB565 ``wallpaper.h`` for the
ESP32-R4sGate-for-Redmond firmware and restores PNG previews from such headers.
"""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Final, Literal, Sequence

from PIL import Image, ImageTk

import converter
from converter import (
    DEFAULT_ARRAY_NAME,
    HEADER_SUFFIXES,
    IMAGE_SUFFIXES,
    MAX_DIMENSION,
    PRESETS,
    ConverterError,
    HeaderInfo,
    Resolution,
    ResizeMode,
    build_rgb565,
    build_header,
    load_image,
    quantized_image,
    read_header,
    restore_image,
    rgb565_to_image,
    save_image,
    save_restored_png,
    suggest_resolutions,
    validate_array_name,
    write_text,
)
from localization import (
    LANGUAGES,
    LANGUAGE_NAMES,
    Localization,
    detect_system_language,
)

APP_VERSION: Final = "1.0.0"
PreviewMode = Literal["none", "image", "header"]


def _preset_labels(i18n: Localization) -> dict[str, str]:
    return {preset.key: i18n.t(preset.key) for preset in PRESETS}


def _preset_from_label(labels: dict[str, str], label: str) -> str | None:
    for key, value in labels.items():
        if value == label:
            return key
    return None


def create_root() -> tuple[tk.Tk, bool]:
    """Create the root window, using optional tkinterdnd2 drag & drop support."""

    try:
        from tkinterdnd2 import TkinterDnD  # type: ignore[import-not-found]

        return TkinterDnD.Tk(), True
    except Exception:
        return tk.Tk(), False


def enable_high_dpi() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # type: ignore[attr-defined]
        except Exception:
            pass


def apply_dpi_scaling(root: tk.Tk) -> None:
    try:
        dpi = root.winfo_fpixels("1i")
        root.tk.call("tk", "scaling", max(1.0, float(dpi) / 72.0))
    except tk.TclError:
        pass


def _center_window(window: tk.Misc, width: int, height: int) -> None:
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    left = max(0, (screen_width - width) // 2)
    top = max(0, (screen_height - height) // 2)
    window.geometry(f"{width}x{height}+{left}+{top}")


class DimensionDialog:
    """Asks for a resolution when a header has no WALLPAPER_WIDTH/HEIGHT defines.

    If the pixel count matches several common resolutions, all of them are shown
    in a list so the user can pick the correct one.
    """

    def __init__(
        self,
        parent: tk.Misc,
        i18n: Localization,
        pixel_count: int,
        suggestions: Sequence[Resolution],
        initial: Resolution | None,
    ) -> None:
        self.i18n = i18n
        self.pixel_count = pixel_count
        self.suggestions = list(suggestions)
        self._result: Resolution | None = None
        self._preset_key = "preset.custom"
        self._labels = _preset_labels(i18n)
        self._labels_to_key = {value: key for key, value in self._labels.items()}

        default = self.suggestions[0] if self.suggestions else (initial or Resolution(320, 240))
        self.width_var = tk.StringVar(value=str(default.width))
        self.height_var = tk.StringVar(value=str(default.height))
        self.preset_var = tk.StringVar()

        self.window = tk.Toplevel(parent)
        self.window.title(i18n.t("dialog.dimensions.title"))
        self.window.transient(parent)
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)

        self._build()
        self.window.bind("<Return>", lambda _event: self._ok())
        self.window.bind("<Escape>", lambda _event: self._cancel())

    def show(self) -> Resolution | None:
        self.window.update_idletasks()
        _center_window(self.window, self.window.winfo_reqwidth(), self.window.winfo_reqheight())
        try:
            self.window.wait_visibility()
            self.window.grab_set()
        except tk.TclError:
            pass
        if self.suggestions:
            self.suggestions_list.focus_set()
        else:
            self.width_entry.focus_set()
        self.window.wait_window()
        return self._result

    def _build(self) -> None:
        container = ttk.Frame(self.window, padding=16)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)

        message = ttk.Label(
            container,
            text=self.i18n.t("dialog.dimensions.message"),
            wraplength=420,
            justify="left",
            style="Orange.TLabel",
        )
        message.pack(anchor="w")

        info = ttk.Label(
            container,
            text=self.i18n.t(
                "dialog.dimensions.info", count=self.pixel_count
            ),
            wraplength=420,
            justify="left",
            style="Orange.TLabel",
        )
        info.pack(anchor="w", pady=(6, 0))

        if self.suggestions:
            hint = ttk.Label(
                container,
                text=self.i18n.t("dialog.dimensions.suggestions_hint"),
                wraplength=420,
                justify="left",
                style="Orange.TLabel",
            )
            hint.pack(anchor="w", pady=(6, 8))

            list_frame = ttk.Frame(container)
            list_frame.pack(fill="both", expand=True, pady=(0, 10))
            scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
            scrollbar.pack(side="right", fill="y")
            self.suggestions_list = tk.Listbox(
                list_frame,
                height=min(6, max(2, len(self.suggestions))),
                selectmode="single",
                activestyle="none",
                yscrollcommand=scrollbar.set,
            )
            self.suggestions_list.pack(side="left", fill="both", expand=True)
            scrollbar.configure(command=self.suggestions_list.yview)
            for index, resolution in enumerate(self.suggestions):
                self.suggestions_list.insert(index, str(resolution))
            self.suggestions_list.select_set(0)
            self.suggestions_list.bind("<<ListboxSelect>>", self._on_suggestion)
            self.suggestions_list.bind("<Double-Button-1>", lambda _event: self._ok())
        else:
            manual = ttk.Label(
                container,
                text=self.i18n.t("dialog.dimensions.manual"),
                style="Hint.TLabel",
            )
            manual.pack(anchor="w", pady=(6, 12))

        controls = ttk.Frame(container)
        controls.pack(fill="x", pady=(8, 0))

        ttk.Label(controls, text=self.i18n.t("target.preset")).grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        preset_box = ttk.Combobox(
            controls,
            textvariable=self.preset_var,
            state="readonly",
            values=[self._labels[preset.key] for preset in PRESETS],
            width=24,
        )
        preset_box.grid(row=0, column=1, columnspan=3, sticky="ew", pady=(0, 6))
        preset_box.bind("<<ComboboxSelected>>", self._on_preset)
        self.preset_var.set(self._labels["preset.custom"])

        ttk.Label(controls, text=self.i18n.t("target.width")).grid(
            row=1, column=0, sticky="w", pady=4
        )
        self.width_entry = ttk.Spinbox(
            controls,
            from_=1,
            to=MAX_DIMENSION,
            textvariable=self.width_var,
            width=8,
        )
        self.width_entry.grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(controls, text=self.i18n.t("target.height")).grid(
            row=1, column=2, sticky="e", padx=(12, 6), pady=4
        )
        self.height_entry = ttk.Spinbox(
            controls,
            from_=1,
            to=MAX_DIMENSION,
            textvariable=self.height_var,
            width=8,
        )
        self.height_entry.grid(row=1, column=3, sticky="w", pady=4)

        self.error_label = ttk.Label(
            container, text="", style="Error.TLabel", wraplength=420, justify="left"
        )
        self.error_label.pack(anchor="w", pady=(8, 0))

        buttons = ttk.Frame(container)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(
            buttons, text=self.i18n.t("dialog.cancel"), command=self._cancel
        ).pack(side="right")
        ttk.Button(
            buttons,
            text=self.i18n.t("dialog.ok"),
            style="Accent.TButton",
            command=self._ok,
        ).pack(side="right", padx=(0, 8))

    def _on_suggestion(self, _event: tk.Event[tk.Misc]) -> None:
        selection = self.suggestions_list.curselection()
        if not selection:
            return
        index = selection[0]
        if 0 <= index < len(self.suggestions):
            resolution = self.suggestions[index]
            self.width_var.set(str(resolution.width))
            self.height_var.set(str(resolution.height))
            self.preset_var.set(self._labels["preset.custom"])

    def _on_preset(self, _event: tk.Event[tk.Misc]) -> None:
        key = self._labels_to_key.get(self.preset_var.get())
        if key is None:
            return
        self._preset_key = key
        preset = next((item for item in PRESETS if item.key == key), None)
        if preset is not None and preset.width is not None and preset.height is not None:
            self.width_var.set(str(preset.width))
            self.height_var.set(str(preset.height))

    def _ok(self) -> None:
        try:
            width = int(self.width_var.get().strip())
            height = int(self.height_var.get().strip())
        except ValueError:
            self.error_label.configure(
                text=self.i18n.error("invalid_resolution_number")
            )
            return
        try:
            resolution = Resolution(width, height)
        except ConverterError as exc:
            self.error_label.configure(text=self.i18n.error(exc.code, exc.params))
            return
        self._result = resolution
        self.window.destroy()

    def _cancel(self) -> None:
        self._result = None
        self.window.destroy()


class WallpaperStudioApp:
    def __init__(
        self, root: tk.Tk, i18n: Localization, dnd_enabled: bool = False
    ) -> None:
        self.root = root
        self.i18n = i18n
        self._dnd_enabled = dnd_enabled

        self._source_image: Image.Image | None = None
        self._source_path: Path | None = None
        self._restored_image: Image.Image | None = None
        self._restored_path: Path | None = None
        self._restored_name: str = ""
        self._preview_photo: ImageTk.PhotoImage | None = None
        self._preview_job: str | None = None
        self._menu_job: str | None = None
        self._suggestion_path: Path | None = None
        self._suggestion_values: tuple[int, ...] = ()
        self._suggestion_resolutions: list[Resolution] = []
        self._preview_mode: PreviewMode = "none"
        self._status_key = "status.ready"
        self._status_params: dict[str, object] = {}
        self._last_directory = Path.home()
        self._preset_key = PRESETS[0].key
        self._syncing = False
        self._menubar: tk.Menu | None = None
        self._header_info: HeaderInfo | None = None
        self._header_path: Path | None = None
        self._header_suggestions: list[Resolution] = []

        self.preset_var = tk.StringVar()
        self.width_var = tk.StringVar(value=str(PRESETS[0].width or 320))
        self.height_var = tk.StringVar(value=str(PRESETS[0].height or 240))
        self.mode_var = tk.StringVar(value=ResizeMode.CROP.value)
        self.array_var = tk.StringVar(value=DEFAULT_ARRAY_NAME)
        self.path_var = tk.StringVar()
        self.language_var = tk.StringVar(value=i18n.language)

        self._configure_root()
        self._configure_styles()
        self._build_menu()
        self._build_layout()
        self._bind_shortcuts()
        self._bind_variables()
        self._setup_drag_and_drop()
        self.i18n.subscribe(self._retranslate)

        self._retranslate()
        self._sync_preset_controls()
        self._refresh_source_info()
        self._update_output_info()
        self._set_status("status.ready")
        self._preview_mode = "none"
        self._render_preview()

    def _configure_root(self) -> None:
        self.root.option_add("*tearOff", False)
        self.root.title(self.i18n.t("app.title"))
        self.root.minsize(960, 680)
        _center_window(self.root, 1120, 780)
        self._create_icon()
        self.root.report_callback_exception = self._report_callback_exception  # type: ignore[method-assign]
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_icon(self) -> None:
        try:
            icon = tk.PhotoImage(master=self.root, width=32, height=32)
            for index, color in enumerate(
                ("#0f766e", "#0d9488", "#14b8a6", "#5eead4")
            ):
                icon.put(color, to=(0, index * 8, 32, index * 8 + 8))
            self.root.iconphoto(True, icon)
            self._icon = icon
        except tk.TclError:
            pass

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        for theme in ("vista", "winnative", "clam", "default"):
            if theme in style.theme_names():
                try:
                    style.theme_use(theme)
                except tk.TclError:
                    continue
                break
        family = tkfont.nametofont("TkDefaultFont").cget("family")
        style.configure("Title.TLabel", font=(family, 16, "bold"))
        style.configure("Subtitle.TLabel", font=(family, 9), foreground="#5f6b76")
        style.configure("Card.TLabelframe", padding=10)
        style.configure("Card.TLabelframe.Label", font=(family, 10, "bold"))
        style.configure("Hint.TLabel", foreground="#6b7280")
        style.configure("Orange.TLabel", foreground="#f97316")
        style.configure("Error.TLabel", foreground="#b91c1c")
        style.configure("Output.TLabel", font=(family, 9))
        style.configure("Accent.TButton", font=(family, 10, "bold"))
        style.configure("PreviewInfo.TLabel", foreground="#4b5563")

    def _build_menu(self) -> None:
        if self._menu_job is not None:
            try:
                self.root.after_cancel(self._menu_job)
            except tk.TclError:
                pass
            self._menu_job = None
        if self._menubar is not None:
            try:
                self.root.config(menu="")
            except tk.TclError:
                pass
            try:
                self._menubar.destroy()
            except tk.TclError:
                pass
            self._menubar = None

        t = self.i18n.t
        self.language_var.set(self.i18n.language)
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(
            label=t("menu.file.open_image"),
            accelerator="Ctrl+O",
            command=self._choose_image,
        )
        file_menu.add_command(
            label=t("menu.file.open_header"),
            accelerator="Ctrl+H",
            command=self._choose_header,
        )
        file_menu.add_command(
            label=t("menu.file.generate"),
            accelerator="Ctrl+G",
            command=self._generate_header,
        )
        file_menu.add_command(
            label=t("menu.file.save_image"),
            accelerator="Ctrl+S",
            command=self._save_image,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label=t("menu.file.exit"),
            accelerator="Ctrl+Q",
            command=self._on_close,
        )
        menubar.add_cascade(label=t("menu.file"), menu=file_menu)

        language_menu = tk.Menu(menubar, tearoff=False)
        for code in LANGUAGES:
            language_menu.add_radiobutton(
                label=LANGUAGE_NAMES[code],
                value=code,
                variable=self.language_var,
                command=self._on_language_selected,
            )
        menubar.add_cascade(label=t("menu.language"), menu=language_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label=t("menu.help.about"), command=self._show_about)
        menubar.add_cascade(label=t("menu.help"), menu=help_menu)

        self.root.config(menu=menubar)
        self._menubar = menubar

    def _build_layout(self) -> None:
        main = ttk.Frame(self.root, padding=(18, 14, 18, 10))
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        header = ttk.Frame(main)
        header.grid(row=0, column=0, sticky="ew")
        self.title_label = ttk.Label(header, style="Title.TLabel")
        self.title_label.pack(anchor="w")
        self.subtitle_label = ttk.Label(header, style="Subtitle.TLabel")
        self.subtitle_label.pack(anchor="w", pady=(2, 10))
        ttk.Separator(main, orient="horizontal").grid(
            row=0, column=0, sticky="sew", pady=(0, 0)
        )

        body = ttk.Frame(main)
        body.grid(row=1, column=0, sticky="nsew", pady=(12, 10))
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        controls = ttk.Frame(body)
        controls.grid(row=0, column=0, sticky="nsw", padx=(0, 14))
        controls.columnconfigure(0, weight=1)

        self._build_source_section(controls)
        self._build_target_section(controls)
        self._build_mode_section(controls)
        self._build_array_section(controls)
        self._build_actions(controls)
        controls.columnconfigure(0, weight=1)

        self._build_preview(body)
        self._build_statusbar(main)

    def _build_source_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, style="Card.TLabelframe")
        frame.pack(fill="x", pady=(0, 10))
        self.source_frame = frame

        self.source_button = ttk.Button(frame, command=self._choose_image)
        self.source_button.pack(fill="x")
        self.source_entry = ttk.Entry(frame, textvariable=self.path_var, state="readonly")
        self.source_entry.pack(fill="x", pady=(8, 0))
        self.source_hint = ttk.Label(frame, style="Hint.TLabel")
        self.source_hint.pack(anchor="w", pady=(4, 0))
        self.source_info = ttk.Label(frame, style="Hint.TLabel")
        self.source_info.pack(anchor="w", pady=(4, 0))

    def _build_target_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, style="Card.TLabelframe")
        frame.pack(fill="x", pady=(0, 10))
        self.target_frame = frame
        frame.columnconfigure(1, weight=1)

        self.preset_label = ttk.Label(frame)
        self.preset_label.grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.preset_combo = ttk.Combobox(
            frame,
            textvariable=self.preset_var,
            state="readonly",
            width=24,
        )
        self.preset_combo.grid(
            row=0, column=1, columnspan=3, sticky="ew", pady=(0, 6)
        )
        self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_selected)

        self.width_label = ttk.Label(frame)
        self.width_label.grid(row=1, column=0, sticky="w", pady=4)
        self.width_spin = ttk.Spinbox(
            frame,
            from_=1,
            to=MAX_DIMENSION,
            textvariable=self.width_var,
            width=8,
        )
        self.width_spin.grid(row=1, column=1, sticky="w", pady=4)
        self.height_label = ttk.Label(frame)
        self.height_label.grid(row=1, column=2, sticky="e", padx=(12, 6), pady=4)
        self.height_spin = ttk.Spinbox(
            frame,
            from_=1,
            to=MAX_DIMENSION,
            textvariable=self.height_var,
            width=8,
        )
        self.height_spin.grid(row=1, column=3, sticky="w", pady=4)

        self.output_label = ttk.Label(frame, style="Output.TLabel")
        self.output_label.grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(8, 0)
        )

    def _build_mode_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, style="Card.TLabelframe")
        frame.pack(fill="x", pady=(0, 10))
        self.mode_frame = frame
        self.crop_radio = ttk.Radiobutton(
            frame,
            variable=self.mode_var,
            value=ResizeMode.CROP.value,
            command=self._on_mode_changed,
        )
        self.crop_radio.pack(anchor="w")
        self.stretch_radio = ttk.Radiobutton(
            frame,
            variable=self.mode_var,
            value=ResizeMode.STRETCH.value,
            command=self._on_mode_changed,
        )
        self.stretch_radio.pack(anchor="w", pady=(4, 0))

    def _build_array_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, style="Card.TLabelframe")
        frame.pack(fill="x", pady=(0, 10))
        self.array_frame = frame

        self.array_label = ttk.Label(frame)
        self.array_label.pack(anchor="w")
        self.array_entry = ttk.Entry(frame, textvariable=self.array_var)
        self.array_entry.pack(fill="x", pady=(4, 0))
        self.array_hint = ttk.Label(frame, style="Hint.TLabel")
        self.array_hint.pack(anchor="w", pady=(4, 0))
        self.array_error = ttk.Label(
            frame, style="Error.TLabel", wraplength=320, justify="left"
        )
        self.array_error.pack(anchor="w", pady=(2, 0))

    def _build_actions(self, parent: ttk.Frame) -> None:
        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=(2, 0))
        self.generate_button = ttk.Button(
            actions, style="Accent.TButton", command=self._generate_header
        )
        self.generate_button.pack(fill="x")
        self.open_header_button = ttk.Button(
            actions, command=self._choose_header
        )
        self.open_header_button.pack(fill="x", pady=(8, 0))
        self.save_image_button = ttk.Button(actions, command=self._save_image)
        self.save_image_button.pack(fill="x", pady=(8, 0))

    def _build_preview(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, style="Card.TLabelframe")
        frame.grid(row=0, column=1, sticky="nsew")
        self.preview_frame = frame
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        self.preview_suggestion_frame = ttk.Frame(frame)
        self.preview_suggestion_label = ttk.Label(
            self.preview_suggestion_frame, style="Orange.TLabel", wraplength=420
        )
        self.preview_suggestion_label.pack(side="left", padx=(0, 8))
        self.preview_suggestion_combo = ttk.Combobox(
            self.preview_suggestion_frame,
            state="readonly",
            width=18,
        )
        self.preview_suggestion_combo.pack(side="left")
        self.preview_suggestion_combo.bind(
            "<<ComboboxSelected>>", self._on_preview_suggestion_selected
        )
        self.preview_suggestion_frame.grid(
            row=0, column=0, sticky="ew", pady=(0, 8)
        )
        self.preview_suggestion_frame.grid_remove()

        self.preview_canvas = tk.Canvas(
            frame,
            background="#1f2226",
            highlightthickness=0,
            bd=0,
        )
        self.preview_canvas.grid(row=1, column=0, sticky="nsew")
        self.preview_canvas.bind("<Configure>", self._on_preview_resize)
        self.preview_info = ttk.Label(frame, style="PreviewInfo.TLabel", anchor="w")
        self.preview_info.grid(row=2, column=0, sticky="ew", pady=(8, 0))

    def _show_preview_suggestions(
        self,
        header_path: Path,
        values: Sequence[int],
        suggestions: Sequence[Resolution],
        selected: Resolution | None = None,
    ) -> None:
        if not suggestions:
            self._clear_preview_suggestions()
            return
        self._suggestion_path = header_path
        self._suggestion_values = tuple(values)
        self._suggestion_resolutions = list(suggestions)
        labels = [str(resolution) for resolution in suggestions]
        self.preview_suggestion_combo.configure(values=labels)
        if selected is not None:
            try:
                index = self._suggestion_resolutions.index(selected)
            except ValueError:
                index = 0
        else:
            index = 0
        self.preview_suggestion_combo.current(index)
        self.preview_suggestion_label.configure(
            text=self.i18n.t("preview.suggestions.label")
        )
        self.preview_suggestion_frame.grid()

    def _clear_preview_suggestions(self) -> None:
        self._suggestion_path = None
        self._suggestion_values = ()
        self._suggestion_resolutions = []
        self.preview_suggestion_combo.configure(values=[])
        self.preview_suggestion_frame.grid_remove()

    def _on_preview_suggestion_selected(self, _event: tk.Event[tk.Misc]) -> None:
        if not self._suggestion_resolutions or not self._suggestion_values:
            return
        index = self.preview_suggestion_combo.current()
        if index < 0 or index >= len(self._suggestion_resolutions):
            return
        resolution = self._suggestion_resolutions[index]
        try:
            image = restore_image(self._suggestion_values, resolution)
        except ConverterError as exc:
            self._show_error(exc)
            return
        self._restored_image = image
        self._restored_name = self._suggestion_path.name if self._suggestion_path else ""
        self._apply_resolution_to_ui(resolution)
        preview_path: Path | None = None
        if self._suggestion_path is not None:
            try:
                preview_path = save_restored_png(self._suggestion_path, image)
            except ConverterError:
                preview_path = None
        self._restored_path = preview_path
        self._preview_mode = "header"
        self._render_preview()
        if preview_path is not None:
            self._set_status(
                "status.restored",
                name=self._suggestion_path.name,
                width=resolution.width,
                height=resolution.height,
                path=str(preview_path),
            )
        else:
            self._set_status(
                "status.restored_no_file",
                name=self._suggestion_path.name,
                width=resolution.width,
                height=resolution.height,
            )

    def _build_statusbar(self, parent: ttk.Frame) -> None:
        status = ttk.Frame(parent)
        status.grid(row=2, column=0, sticky="ew")
        ttk.Separator(status, orient="horizontal").pack(fill="x", pady=(0, 6))
        row = ttk.Frame(status)
        row.pack(fill="x")
        self.status_label = ttk.Label(row, style="Hint.TLabel", anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True)
        self.version_label = ttk.Label(
            row, text=f"v{APP_VERSION}", style="Hint.TLabel"
        )
        self.version_label.pack(side="right")

    def _bind_shortcuts(self) -> None:
        self.root.bind_all("<Control-o>", lambda _event: self._choose_image())
        self.root.bind_all("<Control-h>", lambda _event: self._choose_header())
        self.root.bind_all("<Control-g>", lambda _event: self._generate_header())
        self.root.bind_all("<Control-s>", lambda _event: self._save_image())
        self.root.bind_all("<Control-q>", lambda _event: self._on_close())

    def _bind_variables(self) -> None:
        self.width_var.trace_add("write", self._on_resolution_edited)
        self.height_var.trace_add("write", self._on_resolution_edited)
        self.array_var.trace_add("write", self._on_array_name_edited)

    def _setup_drag_and_drop(self) -> None:
        if not self._dnd_enabled:
            return
        try:
            self.root.drop_target_register("DND_Files")  # type: ignore[attr-defined]
            self.root.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore[attr-defined]
        except (AttributeError, tk.TclError):
            self._dnd_enabled = False

    def _on_drop(self, event: tk.Event[tk.Misc]) -> None:
        data = getattr(event, "data", "")
        if not data:
            return
        try:
            paths = self.root.tk.splitlist(data)
        except tk.TclError:
            paths = [data]
        for raw in paths:
            path = Path(str(raw).strip("{}"))
            suffix = path.suffix.lower()
            if suffix in HEADER_SUFFIXES:
                self._open_header(path)
                return
            if suffix in IMAGE_SUFFIXES:
                self._open_image(path)
                return

    def _retranslate(self) -> None:
        t = self.i18n.t
        self.root.title(t("app.title"))
        self.language_var.set(self.i18n.language)
        self.title_label.configure(text=t("app.title"))
        self.subtitle_label.configure(text=t("app.subtitle"))
        self.source_frame.configure(text=t("section.source"))
        self.target_frame.configure(text=t("section.target"))
        self.mode_frame.configure(text=t("section.mode"))
        self.array_frame.configure(text=t("section.array"))
        self.preview_frame.configure(text=t("section.preview"))
        self.source_button.configure(text=t("source.choose"))
        self.source_hint.configure(text=t("source.hint"))
        self.preset_label.configure(text=t("target.preset"))
        self.width_label.configure(text=t("target.width"))
        self.height_label.configure(text=t("target.height"))
        self.crop_radio.configure(text=t("mode.crop"))
        self.stretch_radio.configure(text=t("mode.stretch"))
        self.array_label.configure(text=t("array.label"))
        self.array_hint.configure(text=t("array.hint"))
        self.generate_button.configure(text=t("button.generate"))
        self.open_header_button.configure(text=t("button.open_header"))
        self.save_image_button.configure(text=t("button.save_image"))
        if self._suggestion_resolutions:
            self.preview_suggestion_label.configure(
                text=t("preview.suggestions.label")
            )
            current = self.preview_suggestion_combo.current()
            self.preview_suggestion_combo.configure(
                values=[str(resolution) for resolution in self._suggestion_resolutions]
            )
            if 0 <= current < len(self._suggestion_resolutions):
                self.preview_suggestion_combo.current(current)
        self.version_label.configure(text=f"v{APP_VERSION}")
        self._refresh_presets()
        self._refresh_source_info()
        self._update_output_info()
        self._validate_array_name_ui()
        self._refresh_status()
        if self._menu_job is not None:
            try:
                self.root.after_cancel(self._menu_job)
            except tk.TclError:
                pass
        self._menu_job = self.root.after_idle(self._build_menu)
        self._schedule_preview(10)

    def _refresh_presets(self) -> None:
        labels = _preset_labels(self.i18n)
        self._preset_labels = labels
        self._preset_keys_by_label = {value: key for key, value in labels.items()}
        self.preset_combo.configure(values=[labels[preset.key] for preset in PRESETS])
        self.preset_var.set(labels.get(self._preset_key, labels["preset.custom"]))

    def _sync_preset_controls(self) -> None:
        custom = self._preset_key == "preset.custom"
        state = "normal" if custom else "disabled"
        self.width_spin.configure(state=state)
        self.height_spin.configure(state=state)

    def _on_preset_selected(self, _event: tk.Event[tk.Misc]) -> None:
        label = self.preset_var.get()
        key = getattr(self, "_preset_keys_by_label", {}).get(label)
        if key is None:
            return
        self._preset_key = key
        preset = next((item for item in PRESETS if item.key == key), None)
        if preset is not None and preset.width is not None and preset.height is not None:
            self._syncing = True
            self.width_var.set(str(preset.width))
            self.height_var.set(str(preset.height))
            self._syncing = False
        self._sync_preset_controls()
        self._update_output_info()
        self._switch_preview_to_result()
        self._schedule_preview(120)

    def _on_resolution_edited(self, *_args: str) -> None:
        if self._syncing:
            return
        self._update_output_info()
        self._switch_preview_to_result()
        self._schedule_preview(250)

    def _switch_preview_to_result(self) -> None:
        if self._source_image is not None:
            self._preview_mode = "image"
        elif self._restored_image is not None:
            self._preview_mode = "header"

    def _on_mode_changed(self) -> None:
        self._switch_preview_to_result()
        self._schedule_preview(120)

    def _on_array_name_edited(self, *_args: str) -> None:
        self._validate_array_name_ui()

    def _mode(self) -> ResizeMode:
        try:
            return ResizeMode(self.mode_var.get())
        except ValueError:
            return ResizeMode.CROP

    def _current_resolution_or_none(self) -> Resolution | None:
        try:
            width = int(self.width_var.get().strip())
            height = int(self.height_var.get().strip())
        except ValueError:
            return None
        try:
            return Resolution(width, height)
        except ConverterError:
            return None

    def _resolution_or_error(self) -> Resolution | None:
        try:
            width = int(self.width_var.get().strip())
            height = int(self.height_var.get().strip())
        except ValueError:
            self._show_error(ConverterError("invalid_resolution_number"))
            return None
        try:
            return Resolution(width, height)
        except ConverterError as exc:
            self._show_error(exc)
            return None

    def _validate_array_name_ui(self) -> str | None:
        try:
            name = validate_array_name(self.array_var.get())
        except ConverterError as exc:
            self.array_error.configure(text=self.i18n.error(exc.code, exc.params))
            return None
        self.array_error.configure(text="")
        return name

    def _array_name_or_error(self) -> str | None:
        name = self._validate_array_name_ui()
        if name is None:
            self._show_error(ConverterError("array_name"))
            self.array_entry.focus_set()
        return name

    def _refresh_source_info(self) -> None:
        if self._source_image is None:
            self.source_info.configure(text=self.i18n.t("source.none"))
            return
        self.source_info.configure(
            text=self.i18n.t(
                "source.info",
                width=self._source_image.width,
                height=self._source_image.height,
            )
        )

    def _update_output_info(self) -> None:
        resolution = self._current_resolution_or_none()
        if resolution is None:
            self.output_label.configure(text="—")
            return
        self.output_label.configure(
            text=self.i18n.t(
                "target.output",
                width=resolution.width,
                height=resolution.height,
                count=resolution.pixel_count,
            )
        )

    def _set_status(self, key: str, **params: object) -> None:
        self._status_key = key
        self._status_params = params
        self._refresh_status()

    def _refresh_status(self) -> None:
        self.status_label.configure(
            text=self.i18n.t(self._status_key, **self._status_params)
        )

    def _choose_image(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title=self.i18n.t("menu.file.open_image"),
            initialdir=str(self._last_directory),
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.bmp"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("BMP", "*.bmp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            self._set_status("status.cancelled")
            return
        self._open_image(Path(path))

    def _open_image(self, path: Path) -> None:
        self._clear_preview_suggestions()
        try:
            image = load_image(path)
        except ConverterError as exc:
            self._show_error(exc)
            return
        self._source_image = image
        self._source_path = path
        self._last_directory = path.parent
        self.path_var.set(str(path))
        self._preview_mode = "image"
        self._refresh_source_info()
        self._render_source_thumbnail()
        self._set_status(
            "status.image_loaded",
            name=path.name,
            width=image.width,
            height=image.height,
        )
        self._schedule_preview(350)

    def _choose_header(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title=self.i18n.t("menu.file.open_header"),
            initialdir=str(self._last_directory),
            filetypes=[("C header", "*.h"), ("All files", "*.*")],
        )
        if not path:
            self._set_status("status.cancelled")
            return
        self._open_header(Path(path))

    def _open_header(self, path: Path) -> None:
        try:
            info = read_header(path)
        except ConverterError as exc:
            self._show_error(exc)
            return

        resolution: Resolution | None = None
        suggestions: list[Resolution] = []
        if info.width is not None and info.height is not None:
            try:
                resolution = Resolution(info.width, info.height)
            except ConverterError:
                resolution = None

        if resolution is None:
            suggestions = suggest_resolutions(len(info.values))
            dialog = DimensionDialog(
                self.root,
                self.i18n,
                pixel_count=len(info.values),
                suggestions=suggestions,
                initial=self._current_resolution_or_none(),
            )
            resolution = dialog.show()
            if resolution is None:
                self._set_status("status.cancelled")
                return

        try:
            image = restore_image(info.values, resolution)
        except ConverterError as exc:
            self._show_error(exc)
            return

        excess = len(info.values) - resolution.pixel_count
        self._restored_image = image
        self._restored_name = path.name
        self._preview_mode = "header"
        self._last_directory = path.parent
        self._apply_resolution_to_ui(resolution)
        if info.array_name:
            try:
                self.array_var.set(validate_array_name(info.array_name))
            except ConverterError:
                pass

        if info.width is None or info.height is None:
            self._show_preview_suggestions(
                path, info.values, suggestions, selected=resolution
            )
        else:
            self._clear_preview_suggestions()

        preview_path: Path | None = None
        save_error: ConverterError | None = None
        try:
            preview_path = save_restored_png(path, image)
            self._restored_path = preview_path
        except ConverterError as exc:
            self._restored_path = None
            save_error = exc

        if preview_path is not None:
            self._set_status(
                "status.restored",
                name=path.name,
                width=resolution.width,
                height=resolution.height,
                path=str(preview_path),
            )
        else:
            self._set_status(
                "status.restored_no_file",
                name=path.name,
                width=resolution.width,
                height=resolution.height,
            )
        self._render_preview()

        if excess > 0:
            messagebox.showwarning(
                self.i18n.t("warning.title"),
                self.i18n.t(
                    "warning.excess_values",
                    name=path.name,
                    found=len(info.values),
                    expected=resolution.pixel_count,
                    width=resolution.width,
                    height=resolution.height,
                ),
                parent=self.root,
            )
        if save_error is not None:
            self._show_error(save_error)

    def _apply_resolution_to_ui(self, resolution: Resolution) -> None:
        matching = next(
            (
                preset
                for preset in PRESETS
                if preset.width == resolution.width
                and preset.height == resolution.height
            ),
            None,
        )
        self._preset_key = matching.key if matching is not None else "preset.custom"
        self._syncing = True
        self.width_var.set(str(resolution.width))
        self.height_var.set(str(resolution.height))
        self._syncing = False
        self._refresh_presets()
        self._sync_preset_controls()
        self._update_output_info()

    def _generate_header(self) -> None:
        self._clear_preview_suggestions()
        if self._source_image is None:
            self._show_error(ConverterError("no_image"))
            return
        resolution = self._resolution_or_error()
        if resolution is None:
            return
        name = self._array_name_or_error()
        if name is None:
            return
        try:
            values = build_rgb565(self._source_image, resolution, self._mode())
            text = build_header(values, resolution, name)
        except ConverterError as exc:
            self._show_error(exc)
            return

        default_name = "wallpaper.h" if name == DEFAULT_ARRAY_NAME else f"{name}.h"
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title=self.i18n.t("menu.file.generate"),
            initialdir=str(self._last_directory),
            initialfile=default_name,
            defaultextension=".h",
            filetypes=[("C header", "*.h"), ("All files", "*.*")],
        )
        if not path:
            self._set_status("status.cancelled")
            return
        target = Path(path)
        try:
            write_text(target, text)
        except ConverterError as exc:
            self._show_error(exc)
            return
        self._last_directory = target.parent
        self._set_status("status.generated", path=str(target), count=len(values))
        self._preview_mode = "image"
        self._render_preview()

    def _save_image(self) -> None:
        image: Image.Image | None = None
        initial_name = "wallpaper_restored.png"
        if self._preview_mode == "header" and self._restored_image is not None:
            image = self._restored_image
            if self._restored_path is not None:
                initial_name = self._restored_path.name
        elif self._source_image is not None:
            resolution = self._current_resolution_or_none()
            if resolution is not None:
                try:
                    image = quantized_image(
                        self._source_image, resolution, self._mode()
                    )
                except ConverterError as exc:
                    self._show_error(exc)
                    return
                initial_name = f"{resolution.width}x{resolution.height}.png"
        if image is None:
            self._show_error(ConverterError("no_restored"))
            return

        path = filedialog.asksaveasfilename(
            parent=self.root,
            title=self.i18n.t("menu.file.save_image"),
            initialdir=str(self._last_directory),
            initialfile=initial_name,
            defaultextension=".png",
            filetypes=[
                ("PNG image", "*.png"),
                ("JPEG image", "*.jpg *.jpeg"),
                ("BMP image", "*.bmp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            self._set_status("status.cancelled")
            return
        target = Path(path)
        try:
            save_image(image, target)
        except ConverterError as exc:
            self._show_error(exc)
            return
        self._last_directory = target.parent
        self._set_status("status.image_saved", path=str(target))

    def _on_language_selected(self) -> None:
        self.i18n.set_language(self.language_var.get())

    def _show_about(self) -> None:
        messagebox.showinfo(
            self.i18n.t("about.title"),
            self.i18n.t("about.text", version=APP_VERSION),
            parent=self.root,
        )

    def _show_error(self, exc: ConverterError) -> None:
        messagebox.showerror(
            self.i18n.t("error.title"),
            self.i18n.error(exc.code, exc.params),
            parent=self.root,
        )

    def _report_callback_exception(
        self, exc_type: type[BaseException], exc_value: BaseException, _traceback: object
    ) -> None:
        messagebox.showerror(
            self.i18n.t("error.title"),
            self.i18n.t("error.unexpected", detail=str(exc_value)),
            parent=self.root,
        )

    def _on_close(self) -> None:
        self.root.destroy()

    def _on_preview_resize(self, _event: tk.Event[tk.Misc]) -> None:
        self._schedule_preview(90)

    def _schedule_preview(self, delay: int = 180) -> None:
        if self._preview_job is not None:
            try:
                self.root.after_cancel(self._preview_job)
            except tk.TclError:
                pass
        self._preview_job = self.root.after(delay, self._render_preview)

    def _render_preview(self) -> None:
        self._preview_job = None
        if self._preview_mode == "image" and self._source_image is not None:
            resolution = self._current_resolution_or_none()
            if resolution is None:
                self._draw_message("preview.invalid")
                return
            try:
                values = build_rgb565(self._source_image, resolution, self._mode())
                image = rgb565_to_image(values, resolution)
            except ConverterError:
                self._draw_message("preview.invalid")
                return
            self._draw_image(
                image,
                "preview.result",
                width=resolution.width,
                height=resolution.height,
                mode=self.i18n.t(f"mode.{self._mode().value}"),
            )
            return
        if self._preview_mode == "header" and self._restored_image is not None:
            self._draw_image(
                self._restored_image,
                "preview.restored",
                width=self._restored_image.width,
                height=self._restored_image.height,
                name=self._restored_name,
            )
            return
        self._draw_message("preview.empty")

    def _render_source_thumbnail(self) -> None:
        if self._source_image is None:
            return
        self._draw_image(
            self._source_image,
            "preview.source",
            width=self._source_image.width,
            height=self._source_image.height,
        )

    def _preview_size(self) -> tuple[int, int]:
        width = self.preview_canvas.winfo_width()
        height = self.preview_canvas.winfo_height()
        if width <= 1 or height <= 1:
            width = max(self.preview_canvas.winfo_reqwidth(), 480)
            height = max(self.preview_canvas.winfo_reqheight(), 360)
        return width, height

    def _draw_message(self, key: str) -> None:
        width, height = self._preview_size()
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(
            width // 2,
            height // 2,
            text=self.i18n.t(key),
            fill="#9ca3af",
            width=max(120, width - 80),
            justify="center",
            font=("TkDefaultFont", 10),
        )
        self.preview_info.configure(text="")

    def _draw_image(self, image: Image.Image, meta_key: str, **params: object) -> None:
        width, height = self._preview_size()
        if width < 60 or height < 60:
            return
        available_width = max(1, width - 24)
        available_height = max(1, height - 24)
        scale = min(available_width / image.width, available_height / image.height)

        if scale < 1:
            target_size = (
                max(1, int(image.width * scale)),
                max(1, int(image.height * scale)),
            )
            display = image.resize(target_size, Image.Resampling.LANCZOS)
        else:
            factor = max(1, int(scale))
            display = image.resize(
                (image.width * factor, image.height * factor),
                Image.Resampling.NEAREST,
            )

        self._preview_photo = ImageTk.PhotoImage(display, master=self.root)
        self.preview_canvas.delete("all")
        left = (width - display.width) // 2
        top = (height - display.height) // 2
        self.preview_canvas.create_image(
            left, top, anchor="nw", image=self._preview_photo
        )
        self.preview_canvas.create_rectangle(
            left - 1,
            top - 1,
            left + display.width,
            top + display.height,
            outline="#4b5563",
        )
        self.preview_info.configure(text=self.i18n.t(meta_key, **params))


def main() -> int:
    enable_high_dpi()
    root, dnd_enabled = create_root()
    apply_dpi_scaling(root)
    i18n = Localization(detect_system_language())
    WallpaperStudioApp(root, i18n, dnd_enabled=dnd_enabled)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
