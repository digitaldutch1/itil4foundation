

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import json
import os
import sys
import random
import traceback
import webbrowser
import re
import time
from pathlib import Path

# ------------------------------------------------------------
# DPI awareness (Windows) + consistente Tk-scaling
# ------------------------------------------------------------
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Per-monitor DPI (Win 8.1+)
except Exception:
    pass

# ---------- UI constants ----------
WRAP_W = 1000
CONTENT_MAX_W = 1100
OPTIONS_LEFT_PAD = 70

F_BANNER     = ("Helvetica", 44, "bold")
F_MENU       = ("Helvetica", 28, "bold")
F_MENU_ITEM  = ("Helvetica", 20)
F_HEADER     = ("Helvetica", 26, "bold")
F_COUNTER    = ("Helvetica", 20)
F_QUESTION   = ("Helvetica", 20)
F_OPTION     = ("Helvetica", 20)
F_BUTTON     = ("Helvetica", 18)

# ---- Slaaggrens voor de score (%)
PASS_THRESHOLD = 65.0

# ---- Dropdown look-and-feel ----
MENU_BG   = "#f0f0f0"
SEP_BG    = "#d0d0d0"
HOVER_BG  = "#3875d6"
HOVER_FG  = "white"
TEXT_FG   = "black"

# ---- Timer settings ----
TIMER_START_SECS = 60 * 60
TIMER_WARN_SECS  = 5 * 60
TIMER_FONT       = ("Helvetica", 35, "bold")
TIMER_COLOR_OK   = "black"
TIMER_COLOR_WARN = "#ff8c00"
TIMER_COLOR_END  = "#d11d1d"

# Timer-positie
TIMER_OFFSET_X = -100
TIMER_OFFSET_Y = 30

# Scrollbar zichtbaar?
SHOW_SCROLLBAR = False

# ---- Icons lesmateriaal dropdown ----
ICON_SIZE = 22
ROW_PAD_X = 6
ICON_PAD_LEFT = 2
ICON_TEXT_GAP = 2
ICON_NUDGE = {"slides.png": 0}
_ICON_TEXT_GAP = max(0, ICON_TEXT_GAP)
_MAX_NUDGE = max([0] + list(ICON_NUDGE.values()))
ICON_COL_W = ICON_SIZE + _MAX_NUDGE + _ICON_TEXT_GAP

# ------------------------------------------------------------
# Pad helpers
# ------------------------------------------------------------
def resource_dir() -> str:
    """Map met de (read-only) resources. Bij PyInstaller is dit _MEIPASS."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def project_dir() -> Path:
    """Schrijfbare projectmap naast de .py of .exe (hier bewaren we scores)."""
    if getattr(sys, "frozen", False):
        return Path(os.path.dirname(sys.executable))
    return Path(os.path.dirname(os.path.abspath(__file__)))

def score_file_path() -> Path:
    """Scores ALLEEN hier opslaan: <project>/assets/score/scores.json."""
    base = project_dir() / "assets" / "score"
    base.mkdir(parents=True, exist_ok=True)
    return base / "scores.json"

def atomic_write_text(path: Path, text: str, encoding: str = "utf-8"):
    """Schrijf veilig naar bestand (voorkomt 0 kB bij crash)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding)
    os.replace(tmp, path)

def load_questions_from_json(filename: str):
    base = resource_dir()
    for d in [os.path.join(base, "assets", "itil_vragen"),
              os.path.join(base, "assets", "linux_questions")]:
        full = os.path.join(d, filename)
        if os.path.exists(full):
            try:
                with open(full, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data["chapters"][0]
            except Exception as e:
                messagebox.showerror("Error", f"Kon vragen niet laden uit {full}: {e}")
                return {}
    return {}

def _count_questions_in_loaded_data(data: dict) -> int:
    try:
        return len(data["chapters"][0]["questions"])
    except Exception:
        return 0

# ------------------------------------------------------------
# Custom button: ÉÉN afgeronde buitenrand + icoon (geen inner border)
# ------------------------------------------------------------
class OuterBorderIconButton(tk.Canvas):
    def __init__(self, master, icon_text: str, command,
                 w=56, h=48, radius=12, border=3, pad=3,
                 font=("Helvetica", 28, "bold"),
                 fg="black", outline="black", bg=MENU_BG, **kwargs):
        super().__init__(master, width=w, height=h, bg=bg, highlightthickness=0, **kwargs)
        self.w, self.h, self.r, self.border, self.pad = w, h, radius, border, pad
        self.font = font
        self.fg = fg
        self.bg = bg
        self.outline = outline
        self.icon_text = icon_text
        self.command = command
        self._rect_id = None
        self._text_id = None
        self._draw()
        self.bind("<Button-1>", lambda e: self.command())

    def set_icon(self, text: str):
        self.icon_text = text
        if self._text_id:
            self.itemconfigure(self._text_id, text=self.icon_text)

    def _draw_round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [
            x1+r,y1, x2-r,y1, x2,y1, x2,y1+r,
            x2,y2-r, x2,y2, x2-r,y2,
            x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1
        ]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self):
        self.delete("all")
        x1, y1 = 2, 2
        x2, y2 = self.w-2, self.h-2
        self._rect_id = self._draw_round_rect(
            x1, y1, x2, y2, self.r,
            fill=self.bg, outline=self.outline, width=self.border
        )
        self._text_id = self.create_text(
            (self.w//2, self.h//2), text=self.icon_text, font=self.font, fill=self.fg
        )

# ------------------------------------------------------------
# Hoofdapp
# ------------------------------------------------------------
class QuizApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("Itil 4 Foundation")
        self.master.geometry("1400x800")
        try:
            self.master.tk.call("tk", "scaling", 1.0)
        except Exception:
            pass

        # State
        self.current_chapter_data = None
        self.questions = []
        self.shuffled_options = []
        self.current_question_index = 0
        self.correct_answers = []
        self.user_answers = []
        self.session_active = False
        self.assessment_mode = False
        self.current_session_title = ""
        self.info_images = {}
        self.current_json_path = None

        # Timer state
        self.timer_total_secs = TIMER_START_SECS
        self.timer_remaining = TIMER_START_SECS
        self.timer_running   = True
        self.timer_job       = None
        self.timer_label     = None
        self.timer_btn       = None
        self.timer_reset_btn = None
        self.timer_right_frame = None

        # Scores
        self.scores = self._load_scores()
        self.toets_menu_by_group = {}
        self.active_dropdown = None
        self._release_ignore_until = 0.0

        # Icon cache
        self._icon_cache = {}

        # UI
        self.center_window_main(self.master, 1400, 800)
        self.banner = tk.Label(self.master, text="Itil 4 Foundation", font=F_BANNER)
        self.banner.pack(pady=20)

        self.navbar_frame = tk.Frame(self.master)
        self.navbar_frame.pack()

        self.materials_button = tk.Menubutton(self.navbar_frame, text="Lesmateriaal", font=F_MENU,
                                              relief="raised", borderwidth=1, cursor="hand2")
        self.materials_button.pack(side="left", padx=10)
        self.materials_button.bind("<Button-1>", self._on_materials_click)

        # Hoofdstukken dropdown met scores
        self.hoofdstukken_menu = tk.Menubutton(self.navbar_frame, text="Hoofdstukken", font=F_MENU,
                                               relief="raised", borderwidth=1, cursor="hand2")
        self.hoofdstukken_menu.pack(side="left", padx=20)
        self.build_hoofdstukken_tab()

        # Toetsen tabs met scores
        self.build_bilingual_toetsen_tab("Toetsen 1", groep=1, count=6)
        self.build_bilingual_toetsen_tab("Toetsen 2", groep=2, count=6)
        self.build_bilingual_toetsen_tab("Toetsen 3", groep=3, count=6)
        self.build_bilingual_toetsen_tab("Toetsen 4", groep=4, count=6)
        self.build_bilingual_toetsen_tab("Toetsen 5", groep=5, count=6)

        self.add_image()

        self.master.bind("<ButtonRelease-1>", self._close_dropdown_global, add="+")
        self.master.bind("<Control-b>", lambda e: self.open_book_pdf())

    # ---------------- Scores opslag ----------------
    def _load_scores(self) -> dict:
        p = score_file_path()
        try:
            if p.exists() and p.stat().st_size > 0:
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_scores(self):
        try:
            atomic_write_text(score_file_path(), json.dumps(self.scores, ensure_ascii=False, indent=2))
        except Exception:
            pass

    def _store_last_score(self, pct: float):
        if not self.current_json_path:
            return
        key = os.path.basename(self.current_json_path)
        self.scores[key] = {"pct": round(pct, 2)}
        self._save_scores()

        # Refresh Toetsen tab wanneer relevant
        m = re.match(r"^toets(\d+)_", key, re.IGNORECASE)
        if m:
            g = int(m.group(1))
            self.build_bilingual_toetsen_tab(f"Toetsen {g}", groep=g, count=6)

        # Altijd Hoofdstukken tab verversen
        self.build_hoofdstukken_tab()

    # ---------------- Count helpers ----------------
    def count_questions_in_file(self, filename: str) -> int:
        base = resource_dir()
        path = os.path.join(base, "assets", "itil_vragen", filename)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return _count_questions_in_loaded_data(data)
            except Exception:
                return 0
        return 0

    def count_questions_in_path(self, path: str) -> int:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return _count_questions_in_loaded_data(data)
        except Exception:
            return 0

    # ---------------- Menutab (custom dropdown) ----------------
    def _find_variant_file(self, dirp: str, groep: int, idx: int, lang: str):
        pat_lang = re.compile(rf"^toets{groep}_{idx}\s*([_.])\s*{lang}\.json\s*$", re.IGNORECASE)
        pat_fallback = re.compile(rf"^toets{groep}_{idx}\s*\.json\s*$", re.IGNORECASE)
        fallback = None
        try:
            for name in os.listdir(dirp):
                name_stripped = name.rstrip()
                if pat_lang.match(name_stripped):
                    return os.path.join(dirp, name)
                if fallback is None and pat_fallback.match(name_stripped):
                    fallback = os.path.join(dirp, name)
        except Exception:
            pass
        return fallback

    def build_bilingual_toetsen_tab(self, label: str, groep: int, count: int = 6):
        if groep in getattr(self, "toets_menu_by_group", {}):
            mb = self.toets_menu_by_group[groep]
        else:
            mb = tk.Menubutton(self.navbar_frame, text=label, font=F_MENU, relief="raised", borderwidth=1)
            mb.pack(side="left", padx=10)
            self.toets_menu_by_group[groep] = mb

        base = resource_dir()
        dirp = os.path.join(base, "assets", "itil_vragen")
        items = []

        if not os.path.isdir(dirp):
            items.append({"type": "text", "text": "(map assets/itil_vragen niet gevonden)"})
        else:
            def score_percent(basename: str):
                s = self.scores.get(basename)
                if not s:
                    return None
                try:
                    pct = float(s.get("pct"))
                except (TypeError, ValueError):
                    return None
                return round(pct, 1)

            for i in range(1, count + 1):
                f_ne = self._find_variant_file(dirp, groep, i, "ne")
                if f_ne and os.path.exists(f_ne):
                    cnt = self.count_questions_in_path(f_ne)
                    base_ne = os.path.basename(f_ne)
                    pct = score_percent(base_ne)
                    left = f"toets {groep}_{i} (NE) ({cnt})"
                    items.append({"type": "item", "left": left, "pct": pct, "file": f_ne, "title": f"ITIL 4 {left}"})

            has_ne = any(it.get("type") == "item" and " (NE) " in it.get("left", "") for it in items)

            en_items = []
            for i in range(1, count + 1):
                f_en = self._find_variant_file(dirp, groep, i, "en")
                if f_en and os.path.exists(f_en):
                    cnt = self.count_questions_in_path(f_en)
                    base_en = os.path.basename(f_en)
                    pct = score_percent(base_en)
                    left = f"toets {groep}_{i} (EN) ({cnt})"
                    en_items.append({"type": "item", "left": left, "pct": pct, "file": f_en, "title": f"ITIL 4 {left}"})

            if has_ne and en_items:
                items.append({"type": "sep"})
            items.extend(en_items)

        mb.unbind("<Button-1>")
        mb.bind("<Button-1>", lambda e, it=items, btn=mb: self._on_tab_click(e, it, btn))

    # ---------------- Hoofdstukken custom dropdown met score ----------------
    def build_hoofdstukken_tab(self):
        base = resource_dir()
        dirp = os.path.join(base, "assets", "itil_vragen")

        def score_percent(basename: str):
            s = self.scores.get(basename)
            if not s:
                return None
            try:
                pct = float(s.get("pct"))
            except (TypeError, ValueError):
                return None
            return round(pct, 1)

        items = []
        for h in (1, 2, 3, 4, 5):
            filename = f"hoofdstuk{h}.json"
            full = os.path.join(dirp, filename)
            if os.path.exists(full):
                cnt = self.count_questions_in_file(filename)
                pct = score_percent(filename)
                left = f"ITIL 4 hoofdstuk {h} ({cnt})"
                items.append({
                    "type": "item",
                    "left": left,
                    "pct": pct,
                    "file": full,
                    "title": f"ITIL 4 hoofdstuk {h}"
                })

        self.hoofdstukken_menu.unbind("<Button-1>")
        self.hoofdstukken_menu.bind(
            "<Button-1>",
            lambda e, it=items, btn=self.hoofdstukken_menu: self._on_tab_click(e, it, btn)
        )

    def _on_tab_click(self, event, items, btn):
        self._open_dropdown(btn, items)
        self._release_ignore_until = time.time() + 0.35
        return "break"

    def _open_dropdown(self, widget: tk.Widget, items: list):
        self._close_active_dropdown()
        x = widget.winfo_rootx()
        y = widget.winfo_rooty() + widget.winfo_height()

        top = tk.Toplevel(self.master)
        top.overrideredirect(True)
        top.geometry(f"+{x}+{y}")
        top.configure(bg=MENU_BG)
        self.active_dropdown = top

        frame = tk.Frame(top, bg=MENU_BG, bd=1, relief="solid")
        frame.pack(fill="both", expand=True)

        def color_row(row, bg, fg):
            row.configure(bg=bg)
            for c in row.winfo_children():
                try:
                    c.configure(bg=bg)
                except Exception:
                    pass
                if hasattr(c, "configure") and "fg" in c.configure():
                    try:
                        c.configure(fg=fg)
                    except Exception:
                        pass

        def add_item_row(parent, left_text, pct, file_path, title):
            row = tk.Frame(parent, bg=MENU_BG)
            row.pack(fill="x", padx=8, pady=3)

            lbl_left  = tk.Label(row, text=left_text, bg=MENU_BG, fg=TEXT_FG, font=F_MENU_ITEM, anchor="w")
            lbl_left.pack(side="left")

            if pct is not None:
                lbl_score = tk.Label(row, text=f" score {pct:.1f}%", bg=MENU_BG, fg=TEXT_FG, font=F_MENU_ITEM, anchor="e")
                lbl_score.pack(side="left")

                color = "#1f9d3a" if pct >= PASS_THRESHOLD else "#d11d1d"
                dot = tk.Canvas(row, width=16, height=16, bg=MENU_BG, highlightthickness=0)
                dot.create_oval(2, 2, 14, 14, fill=color, outline=color)
                dot.pack(side="right", padx=(6, 0))

            def on_enter(e): color_row(row, HOVER_BG, HOVER_FG)
            def on_leave(e): color_row(row, MENU_BG, TEXT_FG)
            def on_click(e):
                self._close_active_dropdown()
                self._start_toets_file(file_path, title)

            row.bind("<Enter>", on_enter)
            row.bind("<Leave>", on_leave)
            row.bind("<Button-1>", on_click)
            lbl_left.bind("<Button-1>", on_click)
            for child in row.winfo_children():
                child.bind("<Button-1>", on_click)

        for it in items:
            t = it.get("type")
            if t == "sep":
                tk.Frame(frame, height=1, bg=SEP_BG).pack(fill="x", pady=2)
            elif t == "item":
                add_item_row(frame, it["left"], it.get("pct"), it["file"], it["title"])
            else:
                tk.Label(frame, text=it.get("text", ""), bg=MENU_BG, fg=TEXT_FG, font=F_MENU_ITEM).pack(padx=8, pady=4)

        top.bind("<FocusOut>", lambda e: self._close_active_dropdown())
        top.focus_set()

    def _close_active_dropdown(self):
        if self.active_dropdown and self.active_dropdown.winfo_exists():
            self.active_dropdown.destroy()
        self.active_dropdown = None

    def _close_dropdown_global(self, event):
        if time.time() < self._release_ignore_until:
            return
        if self.active_dropdown and self.active_dropdown.winfo_exists():
            x1 = self.active_dropdown.winfo_rootx()
            y1 = self.active_dropdown.winfo_rooty()
            x2 = x1 + self.active_dropdown.winfo_width()
            y2 = y1 + self.active_dropdown.winfo_height()
            if not (x1 <= event.x_root <= x2 and y1 <= event.y_root <= y2):
                self._close_active_dropdown()

    # --------------- Lesmateriaal dropdown -------------------
    def _on_materials_click(self, event=None):
        items = self._build_materials_items()
        self._open_materials_dropdown(self.materials_button, items)
        self._release_ignore_until = time.time() + 0.35
        return "break"

    def _norm_name(self, s: str) -> str:
        return re.sub(r'[\W_]+', '', (s or '').lower())

    def _resolve_in_dir(self, folder: str, expected: str):
        try:
            if not (folder and os.path.isdir(folder) and expected):
                return None
            exact = os.path.join(folder, expected)
            if os.path.isfile(exact):
                return exact
            exp_norm = self._norm_name(expected)
            tokens = [t for t in re.split(r'\s+', expected.lower()) if t]
            best = None
            for name in os.listdir(folder):
                full = os.path.join(folder, name)
                if not os.path.isfile(full):
                    continue
                if name.lower() == expected.lower():
                    return full
                if self._norm_name(name) == exp_norm:
                    best = best or full
                    continue
                nl = name.lower()
                if all(t in nl for t in tokens):
                    best = best or full
            return best
        except Exception:
            return None

    def _build_materials_items(self):
        base = resource_dir()
        lm_dir = os.path.join(base, "assets", "lesmateriaal")

        defs = [
            ("ITIL 4 foundation boek (NE)",      "itil_4_boek.pdf",                   "book.png",    "📘"),
            ("Presentatie Deel 1",               "ITIL4_presentatie_deel1.pdf",       "slides.png",  "🖥️"),
            ("Presentatie Deel 2",               "ITIL4_presentatie_deel2.pdf",       "slides.png",  "🖥️"),
            ("Examen objectives",                "itil4_exam_objectives.pdf",         "target.png",  "🎯"),
            ("Examen objectives samenvatting",   "itil4_samenvatting_objectives.pdf", "summary.png", "📝"),
        ]

        items = []
        for label, filename, icon, emoji in defs:
            resolved = self._resolve_in_dir(lm_dir, filename) or os.path.join(lm_dir, filename)
            img = self._load_menu_icon(icon)
            items.append({"label": label, "path": resolved, "img": img, "emoji": emoji, "icon_key": icon})
        return items

    def _load_menu_icon(self, filename: str, size: int = ICON_SIZE):
        key = (filename.lower(), size)
        if key in self._icon_cache:
            return self._icon_cache[key]
        base = resource_dir()
        p = os.path.join(base, "assets", "afbeeldingen", filename)
        try:
            if os.path.exists(p):
                img = Image.open(p).convert("RGBA")
                alpha = img.getchannel("A")
                bbox = alpha.getbbox()
                if bbox:
                    img = img.crop(bbox)
                img.thumbnail((size, size), Image.LANCZOS)
                ph = ImageTk.PhotoImage(img)
                self._icon_cache[key] = ph
                return ph
        except Exception:
            pass
        self._icon_cache[key] = None
        return None

    def _open_materials_dropdown(self, widget: tk.Widget, items: list):
        self._close_active_dropdown()
        x = widget.winfo_rootx()
        y = widget.winfo_rooty() + widget.winfo_height()
        top = tk.Toplevel(self.master)
        top.overrideredirect(True)
        top.geometry(f"+{x}+{y}")
        top.configure(bg=MENU_BG)
        self.active_dropdown = top
        frame = tk.Frame(top, bg=MENU_BG, bd=1, relief="solid")
        frame.pack(fill="both", expand=True)

        def _set_bg_recursive(w, bg, fg):
            try: w.configure(bg=bg)
            except Exception: pass
            try: w.configure(fg=fg)
            except Exception: pass
            for ch in w.winfo_children(): _set_bg_recursive(ch, bg, fg)

        def color_row(row, bg, fg):
            _set_bg_recursive(row, bg, fg)

        for it in items:
            row = tk.Frame(frame, bg=MENU_BG)
            row.pack(fill="x", padx=(ROW_PAD_X, ROW_PAD_X), pady=4)

            icon_cell = tk.Frame(row, width=ICON_COL_W, height=ICON_SIZE, bg=MENU_BG)
            icon_cell.pack(side="left", padx=(ICON_PAD_LEFT, 0))
            icon_cell.pack_propagate(False)

            if it["img"] is not None:
                nudge_left = ICON_NUDGE.get(it.get("icon_key", ""), 0)
                right_gap  = _ICON_TEXT_GAP + (_MAX_NUDGE - nudge_left)
                icon_lbl = tk.Label(icon_cell, image=it["img"], bg=MENU_BG)
                icon_lbl.image = it["img"]
                icon_lbl.pack(anchor="w", padx=(nudge_left, right_gap))
            else:
                right_gap = _ICON_TEXT_GAP + _MAX_NUDGE
                tk.Label(icon_cell, text=it.get("emoji", "📄"), bg=MENU_BG, fg=TEXT_FG,
                         font=("Helvetica", 18)).pack(anchor="w", padx=(0, right_gap))

            lbl = tk.Label(row, text=it["label"], bg=MENU_BG, fg=TEXT_FG, font=F_MENU_ITEM, anchor="w")
            lbl.pack(side="left")

            def on_enter(e, r=row): color_row(r, HOVER_BG, HOVER_FG)
            def on_leave(e, r=row): color_row(r, MENU_BG, TEXT_FG)
            def on_click(e, p=it["path"]):
                self._close_active_dropdown()
                self._open_pdf_path(p)

            for w in (row, icon_cell, lbl):
                w.bind("<Enter>", on_enter); w.bind("<Leave>", on_leave); w.bind("<Button-1>", on_click)

        top.bind("<FocusOut>", lambda e: self._close_active_dropdown())
        top.focus_set()

    # ---------------- Timer helpers ----------------
    def _teardown_timer_ui(self):
        try:
            qw = getattr(self, "question_win", None)
            if self.timer_job and qw and qw.winfo_exists():
                qw.after_cancel(self.timer_job)
        except Exception:
            pass
        self.timer_job = None
        for attr in ("timer_label", "timer_btn", "timer_reset_btn", "timer_right_frame"):
            w = getattr(self, attr, None)
            try:
                if w and hasattr(w, "winfo_exists") and w.winfo_exists():
                    w.destroy()
            except Exception:
                pass
            setattr(self, attr, None)

    def _reset_timer(self, start_running: bool = True):
        self.timer_total_secs = TIMER_START_SECS
        self.timer_remaining = TIMER_START_SECS
        self.timer_running = start_running
        try:
            qw = getattr(self, "question_win", None)
            if self.timer_job and qw and qw.winfo_exists():
                qw.after_cancel(self.timer_job)
        except Exception:
            pass
        self.timer_job = None
        if self.timer_btn and hasattr(self.timer_btn, "winfo_exists") and self.timer_btn.winfo_exists():
            self.timer_btn.set_icon("⏸" if self.timer_running else "▶")
        self._update_timer_label()
        qw = getattr(self, "question_win", None)
        if self.timer_running and qw and qw.winfo_exists():
            self._schedule_timer_tick()

    def _ensure_timer_ui(self, parent: tk.Widget):
        exists = self.timer_right_frame and self.timer_right_frame.winfo_exists()
        if not exists:
            self.timer_right_frame = tk.Frame(parent, bg=parent["bg"])
            self.timer_right_frame.place(relx=1.0, x=TIMER_OFFSET_X, y=TIMER_OFFSET_Y, anchor="ne")

            self.timer_reset_btn = OuterBorderIconButton(
                self.timer_right_frame, "↺", lambda: self._reset_timer(True),
                w=32, h=32, radius=9, border=3, font=("Helvetica", 26, "bold"),
                fg="black", outline="black", bg=parent["bg"]
            )
            self.timer_reset_btn.pack(side="left", padx=(0, 10), pady=2)

            self.timer_btn = OuterBorderIconButton(
                self.timer_right_frame, ("⏸" if self.timer_running else "▶"),
                self._toggle_timer,
                w=56, h=48, radius=12, border=0, font=("Helvetica", 28, "bold"),
                fg="black", outline=parent["bg"], bg=parent["bg"]
            )
            self.timer_btn.pack(side="left", padx=(0, 10), pady=2)

            self.timer_label = tk.Label(self.timer_right_frame, text="", font=TIMER_FONT,
                                        fg=TIMER_COLOR_OK, bg=parent["bg"])
            self.timer_label.pack(side="left")

            self._update_timer_label()
            if self.timer_running:
                self._schedule_timer_tick()
        else:
            self._update_timer_label()
            if self.timer_btn and self.timer_btn.winfo_exists():
                self.timer_btn.set_icon("⏸" if self.timer_running else "▶")

    def _seconds_to_mmss(self, secs: int) -> str:
        secs = max(0, int(secs))
        m, s = divmod(secs, 60)
        return f"{m:02d}:{s:02d}"

    def _update_timer_label(self):
        lbl = self.timer_label
        if not (lbl and hasattr(lbl, "winfo_exists") and lbl.winfo_exists()):
            return
        txt = self._seconds_to_mmss(self.timer_remaining)
        color = TIMER_COLOR_OK
        suffix = ""
        if self.timer_remaining <= 0:
            color = TIMER_COLOR_END
            suffix = " !"
        elif self.timer_remaining < TIMER_WARN_SECS:
            color = TIMER_COLOR_WARN
        try:
            lbl.config(text=txt + suffix, fg=color)
        except Exception:
            pass

    def _schedule_timer_tick(self):
        try:
            qw = getattr(self, "question_win", None)
            if self.timer_job and qw and qw.winfo_exists():
                qw.after_cancel(self.timer_job)
        except Exception:
            pass
        qw = getattr(self, "question_win", None)
        if qw and qw.winfo_exists():
            self.timer_job = qw.after(1000, self._timer_tick)
        else:
            self.timer_job = None

    def _timer_tick(self):
        if self.timer_running and self.timer_remaining > 0:
            self.timer_remaining -= 1
            self._update_timer_label()
        if self.timer_remaining <= 0:
            self.timer_running = False
            self._update_timer_label()
            self.timer_job = None
            return
        self._schedule_timer_tick()

    def _toggle_timer(self):
        self.timer_running = not self.timer_running
        if self.timer_btn and self.timer_btn.winfo_exists():
            self.timer_btn.set_icon("⏸" if self.timer_running else "▶")
        if self.timer_running and self.timer_job is None and self.timer_remaining > 0:
            self._schedule_timer_tick()

    # ---------------- Bestanden openen ----------------
    def _open_pdf_path(self, path: str):
        try_path = path
        if not try_path or not os.path.exists(try_path):
            base = resource_dir()
            lm_dir = os.path.join(base, "assets", "lesmateriaal")
            try_path = self._resolve_in_dir(lm_dir, os.path.basename(path)) if path else None

        if not try_path or not os.path.exists(try_path):
            self.show_error_message(f"Bestand niet gevonden:\n{path}")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(try_path)
            elif sys.platform == "darwin":
                os.system(f'open "{try_path}"')
            else:
                webbrowser.open(f"file://{try_path}")
        except Exception as e:
            self.show_error_message(f"Kon PDF niet openen: {e}")

    def open_book_pdf(self):
        base = resource_dir()
        pdf_path = os.path.join(base, "assets", "lesmateriaal", "itil_4_boek.pdf")
        self._open_pdf_path(pdf_path)

    # ---------------- Start functies ----------------
    def start_itil_hoofdstuk(self, hoofdstuk: int):
        self.reset_statistics()
        if hoofdstuk not in (1, 2, 3, 4, 5):
            self.show_error_message(f"Onbekend hoofdstuk: {hoofdstuk}")
            return
        filename = f"hoofdstuk{hoofdstuk}.json"
        base = resource_dir()
        full = os.path.join(base, "assets", "itil_vragen", filename)
        self.current_json_path = full

        self.current_chapter_data = load_questions_from_json(filename)
        if not self.current_chapter_data or "questions" not in self.current_chapter_data:
            self.show_error_message(f"Geen vragen gevonden in {filename}.")
            return

        self.questions = self.current_chapter_data["questions"]
        random.shuffle(self.questions)

        self.shuffled_options = []
        for q in self.questions:
            opts = list(q.get("options", []))
            ans = q.get("answer")
            if isinstance(ans, list):
                for a in ans:
                    if a not in opts:
                        opts.append(a)
            else:
                if ans not in opts:
                    opts.append(ans)
            random.shuffle(opts)
            self.shuffled_options.append(opts)

        self.current_question_index = 0
        self.user_answers = [None] * len(self.questions)
        self.correct_answers = []

        total = len(self.questions)
        display_title = self.current_chapter_data.get("chapter") or self.current_chapter_data.get("description") or f"ITIL 4 hoofdstuk {hoofdstuk}"
        self.current_session_title = f"{display_title} ({total})"

        self._reset_timer(start_running=True)

        self.session_active = True
        self.assessment_mode = True
        self.question_window()

    def _start_toets_file(self, filepath: str, title: str):
        self.reset_statistics()
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            chapter = data["chapters"][0]
            self.current_json_path = filepath
        except Exception as e:
            self.show_error_message(f"Fout bij laden {filepath}: {e}")
            return

        self.questions = chapter.get("questions", [])
        random.shuffle(self.questions)

        self.shuffled_options = []
        for q in self.questions:
            opts = list(q.get("options", []))
            ans = q.get("answer")
            if isinstance(ans, list):
                for a in ans:
                    if a not in opts:
                        opts.append(a)
            else:
                if ans not in opts:
                    opts.append(ans)
            random.shuffle(opts)
            self.shuffled_options.append(opts)

        self.current_question_index = 0
        self.user_answers = [None] * len(self.questions)
        self.correct_answers = []

        total = len(self.questions)
        display_title = chapter.get("chapter") or chapter.get("description") or title
        self.current_session_title = f"{display_title} ({total})"

        self._reset_timer(start_running=True)

        self.session_active = True
        self.assessment_mode = True
        self.question_window()

    # ---------------- UI helpers ----------------
    def add_image(self):
        try:
            base = resource_dir()
            image_path = os.path.join(base, 'assets', 'afbeeldingen', 'itil_4_foundation.jpg')
            if not os.path.exists(image_path):
                return
            img = Image.open(image_path)
            img.thumbnail((WRAP_W, 500), Image.LANCZOS)
            self.main_banner_img = ImageTk.PhotoImage(img)
            self.main_image_label = tk.Label(self.master, image=self.main_banner_img)
            self.main_image_label.pack(pady=(50, 20))
        except Exception as e:
            messagebox.showerror("Error", f"Kon banner niet laden: {e}", parent=self.master)

    def question_window(self):
        self.question_win = tk.Toplevel(self.master)
        win_title = f"Quiz – {os.path.basename(self.current_json_path)}" if self.current_json_path else "Quiz"
        self.question_win.title(win_title)
        self.center_toplevel(self.question_win, 1600, 900)
        self.question_win.protocol("WM_DELETE_WINDOW", self.close_question_window)

        # Header
        self.header_frame = tk.Frame(self.question_win)
        self.header_frame.pack(side="top", fill="x")

        self.chapter_title_label = tk.Label(self.header_frame, text=self.current_session_title, font=F_HEADER, justify="center")
        self.chapter_title_label.pack(pady=(12, 2))

        self.question_counter = tk.Label(self.header_frame, text="", font=F_COUNTER, justify="center")
        self.question_counter.pack(pady=(0, 10))

        self._ensure_timer_ui(self.header_frame)

        # Body
        self.body_container = tk.Frame(self.question_win)
        self.body_container.pack(fill="both", expand=True, padx=12, pady=(0,10))

        self.question_canvas = tk.Canvas(self.body_container, highlightthickness=0)
        self.question_canvas.pack(side="left", fill="both", expand=True)

        if SHOW_SCROLLBAR:
            self.question_scrollbar = tk.Scrollbar(self.body_container, orient="vertical", command=self.question_canvas.yview)
            self.question_scrollbar.pack(side="right", fill="y")
            self.question_canvas.configure(yscrollcommand=self.question_scrollbar.set)

        self.page_frame = tk.Frame(self.question_canvas)
        self.page_window = self.question_canvas.create_window((0, 0), window=self.page_frame, anchor="nw")
        self.page_frame.grid_columnconfigure(0, weight=1)
        self.page_frame.grid_columnconfigure(2, weight=1)

        self.content = tk.Frame(self.page_frame, width=CONTENT_MAX_W)
        self.content.grid(row=0, column=1, sticky="n", pady=(10, 20))

        self.question_label = tk.Label(self.content, text="", wraplength=WRAP_W, font=F_QUESTION, justify="center")
        self.question_label.pack(pady=(5, 15))

        self.options_frame = tk.Frame(self.content)
        self.options_frame.pack(pady=5, fill="x")

        for w in (self.question_win, self.question_canvas, self.page_frame, self.content, self.options_frame):
            w.bind("<MouseWheel>", self._on_mousewheel_question, add="+")

        self.image_label = tk.Label(self.content)
        self.image_label.pack(pady=(0, 15))

        bottom_frame = tk.Frame(self.question_win)
        bottom_frame.pack(side="bottom", pady=(14, 20))
        self.submit_button = tk.Button(bottom_frame, text="Submit", font=F_BUTTON, command=self.submit_answer)
        self.submit_button.pack(pady=(0, 18))

        nav_btns_frame = tk.Frame(bottom_frame)
        nav_btns_frame.pack()
        tk.Button(nav_btns_frame, text="Previous", font=F_BUTTON, command=self.previous_question).pack(side="left", padx=15)
        tk.Button(nav_btns_frame, text="Stop",     font=F_BUTTON, command=self.show_stats).pack(side="left", padx=15)
        tk.Button(nav_btns_frame, text="Exit",     font=F_BUTTON, command=self.exit_quiz).pack(side="left", padx=15)
        tk.Button(nav_btns_frame, text="Next",     font=F_BUTTON, command=self.next_question).pack(side="left", padx=15)

        def _show_src_info(event=None):
            msg = f"Bestand:\n{self.current_json_path or '-'}\n\nVragen: {len(self.questions)}"
            messagebox.showinfo("Huidige bron", msg, parent=self.question_win)
        self.question_win.bind("<Control-i>", _show_src_info)

        self.content.bind("<Configure>", self._configure_question_content)
        self.question_canvas.bind("<Configure>", lambda e: self.question_canvas.itemconfig(self.page_window, width=e.width))

        self.load_question_canvas()

    # -------- Scroll helpers ----------
    def _configure_question_content(self, event):
        self.question_canvas.configure(scrollregion=self.question_canvas.bbox("all"))

    def _on_mousewheel_question(self, event: tk.Event):
        canvas = getattr(self, "question_canvas", None)
        if not canvas or not canvas.winfo_exists():
            return
        if sys.platform.startswith("win"):
            steps = int(-1 * (event.delta / 120))
        elif sys.platform == "darwin":
            steps = int(-1 * event.delta)
        else:
            steps = int(-1 * (event.delta))
        try:
            canvas.yview_scroll(steps, "units")
        except tk.TclError:
            pass

    def load_question_canvas(self):
        self.chapter_title_label.config(text=self.current_session_title)
        self.question_counter.config(text=f"Question {self.current_question_index + 1} / {len(self.questions)}")

        if hasattr(self, "submit_button"):
            self.submit_button.config(state="normal")

        q = self.questions[self.current_question_index]
        self.question_label.config(text=q["question"])

        self.display_question_image_canvas()

        for w in self.options_frame.winfo_children():
            w.destroy()

        options = self.shuffled_options[self.current_question_index]
        saved = self.user_answers[self.current_question_index]

        self._opt_vars = []
        for idx, opt in enumerate(options):
            var = tk.BooleanVar(value=(idx in saved) if saved is not None else False)
            row = tk.Frame(self.options_frame)
            row.pack(fill="x")
            cb = tk.Checkbutton(row, text=opt, variable=var, font=F_OPTION,
                                anchor="w", justify="left", wraplength=WRAP_W, padx=0)
            cb.pack(side="left", anchor="w", padx=(OPTIONS_LEFT_PAD, 0), pady=6, fill="x")
            self._opt_vars.append(var)

    def display_question_image_canvas(self):
        q = self.questions[self.current_question_index]
        image_path = q.get("image")
        if not image_path:
            self.image_label.configure(image="", height=1)
            self.image_label.image = None
            return
        base = resource_dir()
        full = os.path.join(base, os.path.normpath(image_path)) if not os.path.isabs(image_path) else os.path.normpath(image_path)
        if not os.path.exists(full):
            self.image_label.configure(image="", height=1)
            self.image_label.image = None
            return
        try:
            img = Image.open(full)
            img.thumbnail((WRAP_W, 500), Image.LANCZOS)
            ph = ImageTk.PhotoImage(img)
            self.image_label.configure(image=ph)
            self.image_label.image = ph
        except Exception:
            self.image_label.configure(image="", height=1)
            self.image_label.image = None

    def previous_question(self):
        if self.current_question_index > 0:
            self.current_question_index -= 1
            self.load_question_canvas()

    def next_question(self):
        if self.current_question_index < len(self.questions) - 1:
            self.current_question_index += 1
            self.load_question_canvas()
        else:
            self.show_stats()

    def submit_answer(self):
        selected = [i for i, var in enumerate(getattr(self, "_opt_vars", [])) if var.get()]
        self.user_answers[self.current_question_index] = selected

        correct = self.questions[self.current_question_index]["answer"]
        options = self.shuffled_options[self.current_question_index]

        if isinstance(correct, list):
            correct_indices = [options.index(ans) for ans in correct if ans in options]
            score = len(set(correct_indices).intersection(selected)) / len(correct_indices) if correct_indices else 0.0
            self.correct_answers.append(score)
        else:
            try:
                correct_index = options.index(correct)
                self.correct_answers.append(1.0 if selected == [correct_index] else 0.0)
            except ValueError:
                self.correct_answers.append(0.0)

        if hasattr(self, "submit_button"):
            self.submit_button.config(state="disabled")

        if self.current_question_index < len(self.questions) - 1:
            self.next_question()
        else:
            self.show_stats()

    def reset_statistics(self):
        self.correct_answers = []
        self.user_answers = [None] * len(self.questions)

    def exit_quiz(self):
        self.session_active = False
        self._unbind_local_scroll()
        self._teardown_timer_ui()
        if hasattr(self, 'question_win') and self.question_win:
            self.question_win.destroy()
        messagebox.showinfo("Quiz", "Quiz is afgesloten.", parent=self.master)

    def show_stats(self):
        self._unbind_local_scroll()
        self._teardown_timer_ui()
        if hasattr(self, 'question_win') and self.question_win:
            self.question_win.destroy()

        self.stats_win = tk.Toplevel(self.master)
        self.stats_win.title("Statistics")
        self.center_toplevel(self.stats_win, 600, 400)

        correct_count = sum(1 for s in self.correct_answers if s == 1.0)
        incorrect_count = sum(1 for s in self.correct_answers if s == 0.0)
        skipped_count = sum(1 for a in self.user_answers if a is None)
        total = len(self.questions)
        total_score = sum(self.correct_answers)
        pct = (total_score / total * 100) if total > 0 else 0

        self._store_last_score(pct)

        tk.Label(self.stats_win, text=f"You scored {total_score:.2f} out of {total} correct!", font=("Helvetica", 24)).pack(pady=10)
        tk.Label(self.stats_win, text=f"Correct Answers: {correct_count}", font=("Helvetica", 20)).pack(pady=5)
        tk.Label(self.stats_win, text=f"Incorrect Answers: {incorrect_count}", font=("Helvetica", 20)).pack(pady=5)
        tk.Label(self.stats_win, text=f"Skipped Questions: {skipped_count}", font=("Helvetica", 20)).pack(pady=5)

        passed = pct >= PASS_THRESHOLD
        color = "green" if passed else "red"
        tick = "✓" if passed else "✗"
        score_text = f"Score: {pct:.2f} %  {tick}"
        tk.Label(self.stats_win, text=score_text, font=("Helvetica", 22, "bold"), fg=color).pack(pady=10)

        nav = tk.Frame(self.stats_win)
        nav.pack(side="bottom", pady=(20, 20))
        tk.Button(nav, text="Review Answers", font=F_BUTTON, command=self.review_answers).pack(side=tk.LEFT, padx=20)
        tk.Button(nav, text="Finish", font=F_BUTTON, command=self.stats_win.destroy).pack(side=tk.LEFT, padx=20)

    def review_answers(self):
        self._unbind_local_scroll()
        self.stats_win.destroy()
        self.current_question_index = 0
        self.review_window()

    def review_window(self):
        self.review_win = tk.Toplevel(self.master)
        self.review_win.title("Review Answers")
        self.center_toplevel(self.review_win, 1600, 900)

        container = tk.Frame(self.review_win)
        container.pack(fill="both", expand=True)

        self.review_canvas = tk.Canvas(container)
        self.review_canvas.pack(side="left", fill="both", expand=True)

        if SHOW_SCROLLBAR:
            review_scrollbar = tk.Scrollbar(container, orient="vertical", command=self.review_canvas.yview)
            review_scrollbar.pack(side="right", fill="y")
            self.review_canvas.configure(yscrollcommand=review_scrollbar.set)

        self.review_content_frame = tk.Frame(self.review_canvas)
        offset_x = 400
        self.review_canvas.create_window((offset_x, 0), window=self.review_content_frame, anchor="nw")

        for w in (self.review_win, self.review_canvas, self.review_content_frame):
            w.bind("<MouseWheel>", self._on_mousewheel_question, add="+")

        self.review_content_frame.bind("<Configure>", self._configure_review_content)

        bottom_frame = tk.Frame(self.review_win)
        bottom_frame.pack(side="bottom", pady=(30, 30))

        title_text = self.current_session_title if self.current_session_title else "Review Answers"
        self.review_title_label = tk.Label(self.review_content_frame, text=title_text, font=F_HEADER, justify="center")
        self.review_title_label.pack(pady=10)

        self.question_counter_review = tk.Label(self.review_content_frame, text=f"Question {self.current_question_index + 1} / {len(self.questions)}", font=F_COUNTER, justify="center")
        self.question_counter_review.pack(pady=10)

        self.review_question_label = tk.Label(self.review_content_frame, wraplength=WRAP_W, font=F_QUESTION, justify="center")
        self.review_question_label.pack(pady=10)

        self.options_frame_review = tk.Frame(self.review_content_frame)
        self.options_frame_review.pack(pady=15, fill="x")

        btn_frame = tk.Frame(bottom_frame)
        btn_frame.pack()
        tk.Button(btn_frame, text="Previous",  font=F_BUTTON, command=self.prev_review_question).pack(side=tk.LEFT, padx=20)
        tk.Button(btn_frame, text="Next",      font=F_BUTTON, command=self.next_review_question).pack(side=tk.LEFT, padx=20)
        tk.Button(btn_frame, text="Statistics",font=F_BUTTON, command=self.show_stats).pack(side=tk.LEFT, padx=20)
        tk.Button(btn_frame, text="Finish",    font=F_BUTTON, command=self.finish_review).pack(side=tk.LEFT, padx=20)

        self.load_review_question()

    def _configure_review_content(self, event):
        self.review_canvas.configure(scrollregion=self.review_canvas.bbox("all"))

    def prev_review_question(self):
        if self.current_question_index > 0:
            self.current_question_index -= 1
            self.load_review_question()

    def next_review_question(self):
        if self.current_question_index < len(self.questions) - 1:
            self.current_question_index += 1
            self.load_review_question()

    def finish_review(self):
        self.review_win.destroy()
        self.session_active = False

    def load_review_question(self):
        for w in self.options_frame_review.winfo_children():
            w.destroy()

        idx_q = self.current_question_index
        current_q = self.questions[idx_q]
        options = self.shuffled_options[idx_q]
        explanations = current_q.get("explanation", {}) or {}
        user_selected = self.user_answers[idx_q] if self.user_answers[idx_q] is not None else []
        correct = current_q.get("answer")
        correct_set = set(correct) if isinstance(correct, list) else {correct}

        self.review_question_label.config(text=current_q["question"])
        self.question_counter_review.config(text=f"Question {idx_q + 1} / {len(self.questions)}")

        for i, opt in enumerate(options):
            explanation = explanations.get(opt, "")
            user_sel = (i in user_selected)
            is_correct = (opt in correct_set)

            if user_sel and is_correct:
                txt, fg, font = f"[Correct ✓] {opt}", "green", ("Helvetica", 18, "bold")
            elif user_sel and not is_correct:
                txt, fg, font = f"[Incorrect ✗] {opt}", "red", ("Helvetica", 18, "bold")
            elif not user_sel and is_correct:
                txt, fg, font = f"{opt}", "green", ("Helvetica", 18)
            else:
                txt, fg, font = f"{opt}", "red", ("Helvetica", 18)

            tk.Label(self.options_frame_review, text=txt, fg=fg, font=font)\
              .pack(anchor="w", pady=(10, 0))

            if explanation:
                tk.Label(self.options_frame_review, text=explanation, fg="#444444",
                         font=("Helvetica", 16), wraplength=WRAP_W, justify="left")\
                  .pack(anchor="w", padx=(24, 0), pady=(0, 6))

    # ---------------- Window helpers & errors ----------------
    def center_window_main(self, window, w, h):
        window.update_idletasks()
        sw = window.winfo_screenwidth()
        x = (sw // 2) - (w // 2)
        y = (window.winfo_screenheight() // 2) - (h // 2)
        window.geometry(f"{w}x{h}+{x}+{y}")

    def center_toplevel(self, window, w=1600, h=900):
        window.update_idletasks()
        x = (window.winfo_screenwidth() // 2) - (w // 2)
        y = (window.winfo_screenheight() // 2) - (h // 2)
        window.geometry(f"{w}x{h}+{x}+{y}")

    def _unbind_local_scroll(self):
        for attr in ("question_win", "question_canvas", "page_frame", "content", "options_frame",
                     "review_win", "review_canvas", "review_content_frame"):
            w = getattr(self, attr, None)
            try:
                if w and w.winfo_exists():
                    w.unbind("<MouseWheel>")
            except Exception:
                pass

    def close_question_window(self):
        self._unbind_local_scroll()
        self._teardown_timer_ui()
        if hasattr(self, 'question_win') and self.question_win:
            self.question_win.destroy()

    def show_error_message(self, message: str):
        parent = None
        for w in (getattr(self, 'question_win', None), getattr(self, 'review_win', None), self.master):
            if w is not None and (not hasattr(w, 'winfo_exists') or w.winfo_exists()):
                parent = w
                break
        messagebox.showerror("Error", message, parent=parent)
        if parent is not None:
            try: parent.lift()
            except Exception: pass

# ------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = QuizApp(root)
        root.mainloop()
    except Exception:
        err = traceback.format_exc()
        try:
            tk.Tk().withdraw()
            messagebox.showerror("Startup error", err)
        finally:
            try:
                (Path(resource_dir()) / "startup_error.log").write_text(err, encoding="utf-8")
            except Exception:
                pass



































    









