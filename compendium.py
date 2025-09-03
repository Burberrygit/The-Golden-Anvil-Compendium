#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import sys
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, List, Tuple

import customtkinter as ctk
try:
    from PIL import Image  # for CTkImage
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

APP_TITLE = "Golden Anvil Compendium"
ICON_FILE = "app_icon.png"     # window/header icon (PNG) placed next to script/exe
DEFAULT_JSON_NAME = "prices.json"  # bundled default data file name
JSON_DIR_NAME = "json_files"       # folder created next to script/exe

# --------- Golden Anvil Palette ----------
# Deep charcoal/indigo base with gold accent and subtle purple highlights
COLORS = {
    "bg": "#0b0d12",         # app background (near-black indigo)
    "panel": "#101421",      # main panels
    "panel_alt": "#131a2a",  # header/toolbar panels
    "border": "#232a3d",     # subtle, cool border tone
    "text": "#f4f6ff",       # high-contrast light
    "muted": "#b7b9d3",      # cool gray-lavender
    "accent": "#d4a017",     # golden accent (buttons)
    "accent_hover": "#c89612",
    "accent_purple": "#7b3ab6"  # optional highlight hue (not overused)
}

# --- Currency conversions (D&D 5e) ---
UNIT_TO_GP = {"pp": 10.0, "gp": 1.0, "ep": 0.5, "sp": 0.1, "cp": 0.01}
UNITS = ["pp", "gp", "ep", "sp", "cp"]


def to_gp(amount: float, unit: str) -> float:
    return float(amount) * UNIT_TO_GP[unit]


def from_gp(gp_value: float) -> dict:
    return {
        "pp": gp_value / UNIT_TO_GP["pp"],
        "gp": gp_value,
        "ep": gp_value / UNIT_TO_GP["ep"],
        "sp": gp_value / UNIT_TO_GP["sp"],
        "cp": gp_value / UNIT_TO_GP["cp"],
    }


def pretty(n: float, as_int_if_clean=True):
    if as_int_if_clean and abs(n - round(n)) < 1e-9:
        return f"{int(round(n))}"
    return f"{n:.2f}"


# ---------- EXE-friendly paths & resources ----------
def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_base_dir() -> str:
    """Directory we read/write beside (exe when frozen, script dir otherwise)."""
    return os.path.dirname(sys.executable) if is_frozen() else os.path.abspath(os.path.dirname(__file__))


def resource_base_dir() -> str:
    """Directory we read bundled resources from (sys._MEIPASS when frozen)."""
    if is_frozen():
        # PyInstaller unpack dir
        return getattr(sys, "_MEIPASS", app_base_dir())
    return app_base_dir()


def resource_path(rel_path: str) -> str:
    """Find a file included with the app (works in dev and frozen modes)."""
    return os.path.join(resource_base_dir(), rel_path)


def writeable_path(rel_path: str) -> str:
    """Path beside the exe/script for writeable assets (json_files, etc.)."""
    return os.path.join(app_base_dir(), rel_path)


# ---------- Data loading / folder mgmt ----------
def ensure_json_dir() -> str:
    d = writeable_path(JSON_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def list_json_files(folder: str) -> List[str]:
    """Return absolute paths of *.json inside folder."""
    try:
        return sorted(
            [os.path.join(folder, fn) for fn in os.listdir(folder)
             if fn.lower().endswith(".json") and os.path.isfile(os.path.join(folder, fn))]
        )
    except Exception:
        return []


def dedupe_filename(folder: str, filename: str) -> str:
    """If filename exists in folder, append _1, _2, ... before extension."""
    base, ext = os.path.splitext(filename)
    candidate = filename
    i = 1
    while os.path.exists(os.path.join(folder, candidate)):
        candidate = f"{base}_{i}{ext}"
        i += 1
    return candidate


def safe_copy_into_json_dir(src_path: str, json_dir: str) -> str:
    """Copy src into json_dir. Returns absolute path of destination."""
    if not os.path.isfile(src_path):
        raise FileNotFoundError(src_path)
    filename = os.path.basename(src_path)
    if not filename.lower().endswith(".json"):
        filename += ".json"
    filename = dedupe_filename(json_dir, filename)
    dst = os.path.join(json_dir, filename)
    shutil.copy2(src_path, dst)
    return os.path.abspath(dst)


def seed_default_prices(json_dir: str, default_name: str = DEFAULT_JSON_NAME) -> str | None:
    """
    If a bundled default prices.json exists, copy it into json_dir once.
    Returns path to the seeded file if copied; otherwise None.
    """
    dst = os.path.join(json_dir, default_name)
    if os.path.exists(dst):
        return None
    src = resource_path(default_name)
    if os.path.exists(src):
        try:
            shutil.copy2(src, dst)
            return dst
        except Exception:
            return None
    return None


def load_prices_json(path: str) -> Dict[str, float]:
    """Load a simple dict[str->number] JSON. Skips invalid entries gracefully."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    cleaned: Dict[str, float] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            if k is None:
                continue
            name = str(k).strip()
            try:
                price = float(v)
            except (TypeError, ValueError):
                continue
            cleaned[name] = price
    return cleaned


# ---------- App ----------
class App(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"])
        self.master = master
        self.master.title(APP_TITLE)
        self.master.minsize(1180, 720)

        # High-DPI hint for Windows
        if sys.platform.startswith("win"):
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass

        # Set window icon (if available)
        self._set_window_icon(self.master, ICON_FILE)

        # Data state
        self.json_dir = ensure_json_dir()
        # Seed a default prices.json from bundled resources (first run)
        seeded = seed_default_prices(self.json_dir, DEFAULT_JSON_NAME)
        if seeded:
            print(f"Seeded default data: {seeded}")

        self.file_index: Dict[str, str] = {}  # display_name -> abs_path
        self.selected_display_name: str = "All files"
        self.items: Dict[str, float] = {}          # currently loaded dict name->gp
        self.filtered_items: List[Tuple[str, float]] = []  # list[(name, gp)]

        # Root layout
        self.pack(fill="both", expand=True)

        # Build UI
        self._build_header()
        self._build_controls()
        self._build_table()
        self._build_footer()

        # Initial data load
        self._refresh_file_list(select_display="All files")
        self._load_items_for_selection()
        self._apply_filters()

    # ---------- Utilities ----------
    def _set_window_icon(self, window, filename):
        path = resource_path(filename)
        if os.path.exists(path):
            try:
                icon_img_tk = tk.PhotoImage(file=path)
                window.iconphoto(True, icon_img_tk)
                self._icon_for_window = icon_img_tk  # keep ref
            except Exception:
                pass

    def _load_ctk_icon(self, filename, size=(32, 32)):
        """Return a CTkImage for header usage (avoids HiDPI warning)."""
        path = resource_path(filename)
        if not os.path.exists(path):
            return None
        try:
            if PIL_AVAILABLE:
                img = Image.open(path).convert("RGBA")
                img = img.resize(size, Image.LANCZOS)
                return ctk.CTkImage(light_image=img, dark_image=img, size=size)
            else:
                raw = tk.PhotoImage(file=path)  # fallback
                return raw
        except Exception:
            return None

    # ---------- UI Blocks ----------
    def _build_header(self):
        self.header_wrap = ctk.CTkFrame(self, fg_color=COLORS["panel_alt"], corner_radius=18)
        self.header_wrap.pack(side="top", fill="x", padx=16, pady=(16, 10))

        title_row = ctk.CTkFrame(self.header_wrap, fg_color=COLORS["panel_alt"])
        title_row.pack(side="top", fill="x", padx=16, pady=(14, 6))

        self.header_icon_img = self._load_ctk_icon(ICON_FILE, size=(32, 32))
        icon_label = ctk.CTkLabel(
            title_row, image=self.header_icon_img if self.header_icon_img else None,
            text="", width=36, height=36,
        )
        icon_label.pack(side="left", padx=(0, 10))

        self.title_label = ctk.CTkLabel(
            title_row, text=APP_TITLE,
            text_color=COLORS["text"], font=("Segoe UI", 20, "bold"),
        )
        self.title_label.pack(side="left")

        self.file_hint = ctk.CTkLabel(
            title_row, text=f"Folder: ./{JSON_DIR_NAME}",
            text_color=COLORS["muted"], font=("Segoe UI", 12),
        )
        self.file_hint.pack(side="right")

    def _build_controls(self):
        controls = ctk.CTkFrame(self.header_wrap, fg_color=COLORS["panel_alt"])
        controls.pack(side="top", fill="x", padx=16, pady=(4, 14))

        # Row 1: File dropdown + buttons
        row1 = ctk.CTkFrame(controls, fg_color=COLORS["panel_alt"])
        row1.pack(side="top", fill="x")

        left = ctk.CTkFrame(row1, fg_color=COLORS["panel_alt"])
        left.pack(side="left")

        ctk.CTkLabel(left, text="File", text_color=COLORS["text"]).pack(anchor="w")
        self.file_var = tk.StringVar(value="All files")
        self.file_menu = ctk.CTkOptionMenu(
            left, variable=self.file_var, values=["All files"],
            command=self._on_select_file,
            fg_color=COLORS["panel"], button_color=COLORS["panel"],
            button_hover_color="#182036", text_color=COLORS["text"],
            corner_radius=12, width=220
        )
        self.file_menu.pack(fill="x")

        btnbox = ctk.CTkFrame(row1, fg_color=COLORS["panel_alt"])
        btnbox.pack(side="right")

        common_btn = dict(
            fg_color=COLORS["panel"], hover_color="#182036", text_color=COLORS["text"],
            corner_radius=12, border_width=0
        )
        self.load_btn = ctk.CTkButton(btnbox, text="Load JSON...", command=self._choose_and_import_json, **common_btn)
        self.load_btn.pack(side="left", padx=(0, 8))
        self.reload_btn = ctk.CTkButton(btnbox, text="Reload Folder", command=self._reload_folder, **common_btn)
        self.reload_btn.pack(side="left", padx=(0, 8))
        self.clear_btn = ctk.CTkButton(btnbox, text="Clear Filters", command=self._clear_filters, **common_btn)
        self.clear_btn.pack(side="left")

        # Row 2: Filters (name / min / max / unit / apply)
        row2 = ctk.CTkFrame(controls, fg_color=COLORS["panel_alt"])
        row2.pack(side="top", fill="x", pady=(10, 0))

        # Name filter
        name_box = ctk.CTkFrame(row2, fg_color=COLORS["panel_alt"])
        name_box.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(name_box, text="Search name", text_color=COLORS["text"]).pack(anchor="w")
        self.name_var = tk.StringVar()
        self.name_entry = ctk.CTkEntry(
            name_box, textvariable=self.name_var, width=260,
            fg_color=COLORS["bg"], text_color=COLORS["text"], border_color=COLORS["border"],
            corner_radius=12
        )
        self.name_entry.pack(fill="x")
        self.name_entry.bind("<Return>", lambda e: self._apply_filters())

        # Min price
        min_box = ctk.CTkFrame(row2, fg_color=COLORS["panel_alt"])
        min_box.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(min_box, text="Min price", text_color=COLORS["text"]).pack(anchor="w")
        self.min_var = tk.StringVar()
        self.min_entry = ctk.CTkEntry(
            min_box, textvariable=self.min_var, width=120,
            fg_color=COLORS["bg"], text_color=COLORS["text"], border_color=COLORS["border"],
            corner_radius=12
        )
        self.min_entry.pack(fill="x")
        self.min_entry.bind("<Return>", lambda e: self._apply_filters())

        # Max price
        max_box = ctk.CTkFrame(row2, fg_color=COLORS["panel_alt"])
        max_box.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(max_box, text="Max price", text_color=COLORS["text"]).pack(anchor="w")
        self.max_var = tk.StringVar()
        self.max_entry = ctk.CTkEntry(
            max_box, textvariable=self.max_var, width=120,
            fg_color=COLORS["bg"], text_color=COLORS["text"], border_color=COLORS["border"],
            corner_radius=12
        )
        self.max_entry.pack(fill="x")
        self.max_entry.bind("<Return>", lambda e: self._apply_filters())

        # Unit
        unit_box = ctk.CTkFrame(row2, fg_color=COLORS["panel_alt"])
        unit_box.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(unit_box, text="Unit", text_color=COLORS["text"]).pack(anchor="w")
        self.unit_var = tk.StringVar(value="gp")
        self.unit_menu = ctk.CTkOptionMenu(
            unit_box, values=UNITS, variable=self.unit_var,
            fg_color=COLORS["panel"], button_color=COLORS["panel"],
            button_hover_color="#182036", text_color=COLORS["text"],
            corner_radius=12
        )
        self.unit_menu.pack(fill="x")

        # Apply button (gold accent)
        apply_box = ctk.CTkFrame(row2, fg_color=COLORS["panel_alt"])
        apply_box.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(apply_box, text=" ", text_color=COLORS["text"]).pack(anchor="w")
        self.apply_btn = ctk.CTkButton(
            apply_box, text="Apply Filters", command=self._apply_filters,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], text_color="#1a1100",
            corner_radius=14, height=38, font=("Segoe UI Semibold", 12), border_width=0
        )
        self.apply_btn.pack(side="left")

    def _build_table(self):
        self.table_wrap = ctk.CTkFrame(self, fg_color=COLORS["panel"], corner_radius=18)
        self.table_wrap.pack(side="top", fill="both", expand=True, padx=16, pady=(0, 12))

        inner = ctk.CTkFrame(self.table_wrap, fg_color=COLORS["panel"])
        inner.pack(fill="both", expand=True, padx=12, pady=12)

        columns = ("name", "pp", "gp", "ep", "sp", "cp")
        self.tree = ttk.Treeview(inner, columns=columns, show="headings", selectmode="browse")

        # Headings
        self.tree.heading("name", text="Item Name", command=lambda: self._sort_by("name", False))
        self.tree.heading("pp", text="pp", command=lambda: self._sort_by("pp", False))
        self.tree.heading("gp", text="gp", command=lambda: self._sort_by("gp", False))
        self.tree.heading("ep", text="ep", command=lambda: self._sort_by("ep", False))
        self.tree.heading("sp", text="sp", command=lambda: self._sort_by("sp", False))
        self.tree.heading("cp", text="cp", command=lambda: self._sort_by("cp", False))

        # Column widths
        self.tree.column("name", width=520, anchor="w")
        for col in ("pp", "gp", "ep", "sp", "cp"):
            self.tree.column(col, width=100, anchor="e")

        # ttk theme for table (Golden Anvil colors)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=COLORS["panel"],
            fieldbackground=COLORS["panel"],
            foreground=COLORS["text"],
            rowheight=30,
            font=("Segoe UI", 11),
        )
        style.configure(
            "Treeview.Heading",
            background=COLORS["panel_alt"],
            foreground=COLORS["text"],
            font=("Segoe UI Semibold", 11),
        )
        style.map("Treeview.Heading", background=[("active", COLORS["panel_alt"])])

        vsb = ttk.Scrollbar(inner, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        inner.rowconfigure(0, weight=1)
        inner.columnconfigure(0, weight=1)

    def _build_footer(self):
        self.footer = ctk.CTkFrame(self, fg_color=COLORS["panel"], corner_radius=14)
        self.footer.pack(side="bottom", fill="x", padx=16, pady=(0, 16))

        tip = ctk.CTkLabel(
            self.footer,
            text="Tip: Choose a file in the dropdown to view only that JSON. 'All files' merges everything.",
            text_color=COLORS["muted"], font=("Segoe UI", 12),
        )
        tip.pack(side="left", padx=12, pady=10)

    # ---------- Folder / files ----------
    def _refresh_file_list(self, select_display: str = None):
        """Rescan ./json_files and update dropdown."""
        paths = list_json_files(self.json_dir)
        # Build mapping display -> path
        self.file_index.clear()
        for p in paths:
            base = os.path.basename(p)
            name_no_ext = os.path.splitext(base)[0]
            self.file_index[name_no_ext] = os.path.abspath(p)

        # Dropdown values
        values = ["All files"] + sorted(self.file_index.keys(), key=str.lower)
        self.file_menu.configure(values=values)

        # Select requested or keep current
        if select_display and select_display in values:
            self.file_var.set(select_display)
        elif self.file_var.get() not in values:
            self.file_var.set("All files")

        self.selected_display_name = self.file_var.get()

    def _on_select_file(self, choice: str):
        self.selected_display_name = choice
        self._load_items_for_selection()
        self._apply_filters()

    def _choose_and_import_json(self):
        path = filedialog.askopenfilename(
            title="Select a JSON file to import",
            initialdir=self.json_dir,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            dst = safe_copy_into_json_dir(path, self.json_dir)
            # Refresh list and auto-select the new file
            disp_name = os.path.splitext(os.path.basename(dst))[0]
            self._refresh_file_list(select_display=disp_name)
            self._load_items_for_selection()
            self._apply_filters()
            messagebox.showinfo("Imported", f"Copied into {JSON_DIR_NAME}:\n{os.path.basename(dst)}")
        except Exception as e:
            messagebox.showerror("Import failed", f"Could not import file:\n{e}")

    def _reload_folder(self):
        self._refresh_file_list(select_display=self.file_var.get())
        self._load_items_for_selection()
        self._apply_filters()

    def _load_items_for_selection(self):
        """Load self.items from currently selected file, or merge all if 'All files'."""
        sel = self.file_var.get()
        merged: Dict[str, float] = {}

        if sel == "All files":
            # Merge all files; later files can overwrite earlier ones with same key
            for _, path in self.file_index.items():
                try:
                    data = load_prices_json(path)
                    merged.update(data)
                except Exception:
                    continue
        else:
            path = self.file_index.get(sel)
            if path:
                try:
                    merged = load_prices_json(path)
                except Exception:
                    merged = {}

        self.items = merged

    # ---------- Filters / sorting ----------
    def _clear_filters(self):
        self.name_var.set("")
        self.min_var.set("")
        self.max_var.set("")
        self.unit_var.set("gp")
        self._apply_filters()

    def _apply_filters(self):
        name_query = self.name_var.get().strip().lower()
        min_s = self.min_var.get().strip()
        max_s = self.max_var.get().strip()
        unit = self.unit_var.get()

        # Convert range to gp
        min_gp = None
        max_gp = None
        try:
            if min_s != "":
                min_gp = to_gp(float(min_s), unit)
            if max_s != "":
                max_gp = to_gp(float(max_s), unit)
        except ValueError:
            messagebox.showwarning("Invalid Range", "Min/Max must be numbers.")
            return

        results: List[Tuple[str, float]] = []
        for name, price_gp in self.items.items():
            if name_query and name_query not in name.lower():
                continue
            if min_gp is not None and price_gp < min_gp:
                continue
            if max_gp is not None and price_gp > max_gp:
                continue
            results.append((name, price_gp))

        self.filtered_items = results
        self._refresh_table(results)

    def _refresh_table(self, items: List[Tuple[str, float]]):
        self.tree.delete(*self.tree.get_children())
        for name, gp_value in items:
            conv = from_gp(gp_value)
            self.tree.insert(
                "", "end",
                values=(
                    name,
                    pretty(conv["pp"]),
                    pretty(conv["gp"]),
                    pretty(conv["ep"]),
                    pretty(conv["sp"]),
                    pretty(conv["cp"]),
                ),
            )

    def _sort_by(self, col_key, descending):
        numeric_cols = {"pp", "gp", "ep", "sp", "cp"}
        rows = []
        for iid in self.tree.get_children(""):
            vals = self.tree.item(iid, "values")
            row = dict(zip(("name", "pp", "gp", "ep", "sp", "cp"), vals))
            rows.append((row[col_key], iid))
        if col_key in numeric_cols:
            def to_num(s):
                try:
                    return float(s)
                except Exception:
                    return float("inf")
            rows.sort(key=lambda t: to_num(t[0]), reverse=descending)
        else:
            rows.sort(key=lambda t: str(t[0]).lower(), reverse=descending)
        for idx, (_, iid) in enumerate(rows):
            self.tree.move(iid, "", idx)
        self.tree.heading(col_key, command=lambda: self._sort_by(col_key, not descending))


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    root = ctk.CTk()
    root.configure(fg_color=COLORS["bg"])
    app = App(master=root)

    root.geometry("1280x780+80+80")
    root.mainloop()


if __name__ == "__main__":
    main()




