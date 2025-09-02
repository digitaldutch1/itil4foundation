

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
import time  # voor 'ignore next release' timing

# ------------------------------------------------------------
# DPI awareness (Windows) + consistente Tk-scaling
# ------------------------------------------------------------
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Per-monitor DPI (Win 8.1+)
except Exception:
    pass

# ---------- UI constants ----------
WRAP_W = 1000            # wrap-breedte in pixels voor vraag/opties
CONTENT_MAX_W = 1100     # max breedte van de inhoud in de quiz
OPTIONS_LEFT_PAD = 70    # vaste linkermarge voor alle opties (in px)

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

# ---- Custom dropdown stip-tuning ----
DOT_PADY = 0      # <0 = stip iets omhoog; >0 = omlaag
DOT_SIZE = 14     # diameter stip in px

# ---- Dropdown look-and-feel (lijken op Tk menu) ----
MENU_BG   = "#f0f0f0"    # standaard menu-achtig lichtgrijs
SEP_BG    = "#d0d0d0"
HOVER_BG  = "#3875d6"    # menu-blauw (hover)
HOVER_FG  = "white"
TEXT_FG   = "black"

# ---- Timer settings ----
TIMER_START_SECS = 60 * 60                  # 60 minuten
TIMER_WARN_SECS  = 5 * 60                   # onder 5 minuten oranje
TIMER_FONT       = ("Helvetica", 35, "bold")
TIMER_COLOR_OK   = "black"
TIMER_COLOR_WARN = "#ff8c00"
TIMER_COLOR_END  = "#d11d1d"

# Timer-positie (rechtsboven)
TIMER_OFFSET_X = -100   # negatief = meer naar links
TIMER_OFFSET_Y = 30     # positief = omlaag, negatief = omhoog
TIMER_BTN_FONT  = ("Helvetica", 35, "bold")
TIMER_BTN_WIDTH = 3

# Scrollbar zichtbaar maken? (False = verbergen, muiswiel blijft werken)
SHOW_SCROLLBAR = False

# ---- Icons lesmateriaal dropdown (uitlijning & padding) ----
ICON_SIZE = 22
ROW_PAD_X = 6
ICON_PAD_LEFT = 2

ICON_TEXT_GAP = 2        # gewenste ruimte tussen icoon en tekst (mag negatief worden ingevoerd)
ICON_NUDGE = {
    "slides.png": 30,
    # "book.png": 0,
    # "target.png": 0,
    # "summary.png": 0,
}

# ✅ clamp: Tkinter staat geen negatieve padding toe
_ICON_TEXT_GAP = max(0, ICON_TEXT_GAP)

# Kolombreedte: groot genoeg voor icoon + maximale nudge + gap
ICON_COL_W = ICON_SIZE + (max([0] + list(ICON_NUDGE.values()))) + _ICON_TEXT_GAP

# ------------------------------------------------------------
# Helpers voor paden & data laden
# ------------------------------------------------------------
def resource_dir() -> str:
    """Basismap voor resources (PyInstaller of bronmap)."""
    if getattr(sys, "frozen", False):
        # Onefile: alles wordt naar _MEIPASS uitgepakt
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def load_questions_from_json(filename: str):
    base = resource_dir()
    candidate_dirs = [
        os.path.join(base, "assets", "itil_vragen"),
        os.path.join(base, "assets", "linux_questions"),
    ]
    for d in candidate_dirs:
        full_path = os.path.join(d, filename)
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data["chapters"][0]
            except Exception as e:
                messagebox.showerror("Error", f"Kon vragen niet laden uit {full_path}: {e}")
                return {}
    return {}


def _count_questions_in_loaded_data(data: dict) -> int:
    try:
        return len(data["chapters"][0]["questions"])
    except Exception:
        return 0


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
        self.correct_answers = []      # per vraag: 1.0/0.0 of deelscore
        self.user_answers = []         # per vraag: lijst indices
        self.session_active = False
        self.assessment_mode = False
        self.current_session_title = ""
        self.info_images = {}
        self.current_json_path = None

        # Timer state (globaal voor de hele quiz-sessie)
        self.timer_total_secs = TIMER_START_SECS
        self.timer_remaining = TIMER_START_SECS
        self.timer_running   = True
        self.timer_job       = None
        self.timer_label     = None
        self.timer_btn       = None

        # Scores
        self.scores = self._load_scores()
        self.toets_menu_by_group = {}
        self.active_dropdown = None
        self._release_ignore_until = 0.0  # timestamp tot wanneer release events genegeerd worden

        # Icon cache voor dropdowns
        self._icon_cache = {}

        # UI
        self.center_window_main(self.master, 1400, 800)
        self.banner = tk.Label(self.master, text="Itil 4 Foundation", font=F_BANNER)
        self.banner.pack(pady=20)

        self.navbar_frame = tk.Frame(self.master)
        self.navbar_frame.pack()

        # ======= Lesmateriaal dropdown-knop =======
        self.materials_button = tk.Menubutton(
            self.navbar_frame, text="Lesmateriaal", font=F_MENU,
            relief="raised", borderwidth=1, cursor="hand2"
        )
        self.materials_button.pack(side="left", padx=10)
        self.materials_button.bind("<Button-1>", self._on_materials_click)

        # Hoofdstuk menu
        self.hoofdstukken_menu = tk.Menubutton(
            self.navbar_frame, text="Hoofdstukken", font=F_MENU,
            relief="raised", borderwidth=1
        )
        self.hoofdstukken_menu.menu = tk.Menu(self.hoofdstukken_menu, tearoff=0, font=F_MENU_ITEM)
        self.hoofdstukken_menu["menu"] = self.hoofdstukken_menu.menu
        self.hoofdstukken_menu.pack(side="left", padx=20)

        # Hoofdstukken 1..5
        cnt_h1 = self.count_questions_in_file("hoofdstuk1.json")
        cnt_h2 = self.count_questions_in_file("hoofdstuk2.json")
        cnt_h3 = self.count_questions_in_file("hoofdstuk3.json")
        cnt_h4 = self.count_questions_in_file("hoofdstuk4.json")
        cnt_h5 = self.count_questions_in_file("hoofdstuk5.json")
        self.hoofdstukken_menu.menu.add_command(label=f"ITIL 4 hoofdstuk 1 ({cnt_h1})", command=lambda: self.start_itil_hoofdstuk(1))
        self.hoofdstukken_menu.menu.add_command(label=f"ITIL 4 hoofdstuk 2 ({cnt_h2})", command=lambda: self.start_itil_hoofdstuk(2))
        self.hoofdstukken_menu.menu.add_command(label=f"ITIL 4 hoofdstuk 3 ({cnt_h3})", command=lambda: self.start_itil_hoofdstuk(3))
        self.hoofdstukken_menu.menu.add_command(label=f"ITIL 4 hoofdstuk 4 ({cnt_h4})", command=lambda: self.start_itil_hoofdstuk(4))
        self.hoofdstukken_menu.menu.add_command(label=f"ITIL 4 hoofdstuk 5 ({cnt_h5})", command=lambda: self.start_itil_hoofdstuk(5))
        self.hoofdstukken_menu.menu.add_separator()

        # Toetsen tabs (1..6) -> custom dropdown
        self.build_bilingual_toetsen_tab("Toetsen 1", groep=1, count=6)
        self.build_bilingual_toetsen_tab("Toetsen 2", groep=2, count=6)
        self.build_bilingual_toetsen_tab("Toetsen 3", groep=3, count=6)
        self.build_bilingual_toetsen_tab("Toetsen 4", groep=4, count=6)
        self.build_bilingual_toetsen_tab("Toetsen 5", groep=5, count=6)

        self.add_image()

        # Sluit dropdown bij muisklik buiten (op release)
        self.master.bind("<ButtonRelease-1>", self._close_dropdown_global, add="+")
        # Sneltoets naar boek
        self.master.bind("<Control-b>", lambda e: self.open_book_pdf())

    # ---------------- Scores opslag ----------------
    def _legacy_scores_paths(self):
        paths = []
        appdata = os.getenv("APPDATA")
        if appdata:
            paths.append(os.path.join(appdata, "ITIL4Trainer", "scores.json"))
        paths.append(os.path.join(os.path.expanduser("~"), ".itil4_trainer", "scores.json"))
        return paths

    def _scores_path(self) -> str:
        base = resource_dir()
        score_dir = os.path.join(base, "assets", "score")
        os.makedirs(score_dir, exist_ok=True)
        return os.path.join(score_dir, "scores.json")

    def _load_scores(self) -> dict:
        path = self._scores_path()

        if not os.path.exists(path):
            for oldp in self._legacy_scores_paths():
                if os.path.exists(oldp):
                    try:
                        with open(oldp, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        with open(path, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        break
                    except Exception:
                        pass

        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_scores(self):
        try:
            with open(self._scores_path(), "w", encoding="utf-8") as f:
                json.dump(self.scores, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _store_last_score(self, pct: float):
        if not self.current_json_path:
            return
        key = os.path.basename(self.current_json_path)
        self.scores[key] = {"pct": round(pct, 2)}
        self._save_scores()
        m = re.match(r"^toets(\d+)_", key, re.IGNORECASE)
        if m:
            g = int(m.group(1))
            self.build_bilingual_toetsen_tab(f"Toetsen {g}", groep=g, count=6)

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

            # NE items
            for i in range(1, count + 1):
                f_ne = self._find_variant_file(dirp, groep, i, "ne")
                if f_ne and os.path.exists(f_ne):
                    cnt = self.count_questions_in_path(f_ne)
                    base_ne = os.path.basename(f_ne)
                    pct = score_percent(base_ne)
                    left = f"toets {groep}_{i} (NE) ({cnt})"
                    items.append({"type": "item", "left": left, "pct": pct, "file": f_ne, "title": f"ITIL 4 {left}"})

            has_ne = any(it.get("type") == "item" and " (NE) " in it.get("left", "") for it in items)

            # EN items
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

    def _on_tab_click(self, event, items, btn):
        self._open_dropdown(btn, items)
        self._release_ignore_until = time.time() + 0.35
        return "break"

    def _open_dropdown(self, widget: tk.Widget, items: list):
        """Algemene dropdown (voor Toetsen)"""
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
                dot = tk.Canvas(row, width=DOT_SIZE+2, height=DOT_SIZE+2, bg=MENU_BG, highlightthickness=0)
                dot.create_oval(1, 1, DOT_SIZE, DOT_SIZE, fill=color, outline=color)
                dot.pack(side="right", padx=(6, 0), pady=(DOT_PADY, 0))

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
        """Open de lesmateriaal-dropdown onder de knop."""
        items = self._build_materials_items()
        self._open_materials_dropdown(self.materials_button, items)
        self._release_ignore_until = time.time() + 0.35
        return "break"

    def _norm_name(self, s: str) -> str:
        return re.sub(r'[\W_]+', '', (s or '').lower())

    def _resolve_in_dir(self, folder: str, expected: str):
        """Zoek expected in folder (tolerant)."""
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

        # label, bestandsnaam, icoon (png in assets/afbeeldingen), emoji fallback
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
        """Laad icoon en snij transparante randen weg (optisch strakker)."""
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
        """Custom dropdown met vaste icon-kolom; gap tussen icoon en tekst = _ICON_TEXT_GAP."""
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
            for ch in w.winfo_children():
                _set_bg_recursive(ch, bg, fg)

        def color_row(row, bg, fg):
            _set_bg_recursive(row, bg, fg)

        for it in items:
            row = tk.Frame(frame, bg=MENU_BG)
            row.pack(fill="x", padx=(ROW_PAD_X, ROW_PAD_X), pady=4)

            # --- vaste icon-kolom ---
            icon_cell = tk.Frame(row, width=ICON_COL_W, height=ICON_SIZE, bg=MENU_BG)
            icon_cell.pack(side="left", padx=(ICON_PAD_LEFT, 0))
            icon_cell.pack_propagate(False)

            if it["img"] is not None:
                extra_left = ICON_NUDGE.get(it.get("icon_key", ""), 0)
                icon_lbl = tk.Label(icon_cell, image=it["img"], bg=MENU_BG)
                icon_lbl.image = it["img"]
                icon_lbl.pack(anchor="w", padx=(extra_left, _ICON_TEXT_GAP))
            else:
                tk.Label(icon_cell, text=it.get("emoji", "📄"), bg=MENU_BG, fg=TEXT_FG,
                         font=("Helvetica", 18)).pack(anchor="w", padx=(0, _ICON_TEXT_GAP))

            # tekst start direct na icon-kolom; geen extra padx nodig
            lbl = tk.Label(row, text=it["label"], bg=MENU_BG, fg=TEXT_FG, font=F_MENU_ITEM, anchor="w")
            lbl.pack(side="left")

            def on_enter(e, r=row): color_row(r, HOVER_BG, HOVER_FG)
            def on_leave(e, r=row): color_row(r, MENU_BG, TEXT_FG)
            def on_click(e, p=it["path"]):
                self._close_active_dropdown()
                self._open_pdf_path(p)

            for w in (row, icon_cell, lbl):
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                w.bind("<Button-1>", on_click)

        top.bind("<FocusOut>", lambda e: self._close_active_dropdown())
        top.focus_set()

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

    # (compat) oude snelkoppeling naar het boek
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
            max_w, max_h = WRAP_W, 500
            img.thumbnail((max_w, max_h), Image.LANCZOS)
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

        # Timer rechtsboven
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

        # lokale muiswiel-binding (geen bind_all!)
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

    # -------- Timer-UI & logica --------
    def _ensure_timer_ui(self, parent: tk.Widget):
        if not hasattr(self, "timer_right_frame") or not self.timer_right_frame.winfo_exists():
            self.timer_right_frame = tk.Frame(parent)
            self.timer_right_frame.place(relx=1.0, x=TIMER_OFFSET_X, y=TIMER_OFFSET_Y, anchor="ne")

            self.timer_btn = tk.Button(
                self.timer_right_frame,
                text="⏸" if self.timer_running else "▶",
                font=TIMER_BTN_FONT,
                width=TIMER_BTN_WIDTH,
                command=self._toggle_timer,
                relief="flat",
                cursor="hand2"
            )
            self.timer_btn.pack(side="left", padx=(0, 10), pady=2)

            self.timer_label = tk.Label(
                self.timer_right_frame,
                text="",
                font=TIMER_FONT,
                fg=TIMER_COLOR_OK
            )
            self.timer_label.pack(side="left")

            # Start de tick-loop slechts éénmaal
            self._update_timer_label()
            self._schedule_timer_tick()
        else:
            self._update_timer_label()
            if self.timer_btn:
                self.timer_btn.config(text="⏸" if self.timer_running else "▶")

    def _seconds_to_mmss(self, secs: int) -> str:
        secs = max(0, int(secs))
        m, s = divmod(secs, 60)
        return f"{m:02d}:{s:02d}"

    def _update_timer_label(self):
        txt = self._seconds_to_mmss(self.timer_remaining)
        color = TIMER_COLOR_OK
        suffix = ""

        if self.timer_remaining <= 0:
            color = TIMER_COLOR_END
            suffix = " !"
        elif self.timer_remaining < TIMER_WARN_SECS:
            color = TIMER_COLOR_WARN

        if self.timer_label:
            self.timer_label.config(text=txt + suffix, fg=color)

    def _schedule_timer_tick(self):
        if self.timer_job:
            try:
                self.question_win.after_cancel(self.timer_job)
            except Exception:
                pass
            self.timer_job = None
        self.timer_job = self.question_win.after(1000, self._timer_tick)

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
        if self.timer_btn:
            self.timer_btn.config(text="⏸" if self.timer_running else "▶")
        if self.timer_running and self.timer_job is None and self.timer_remaining > 0:
            self._schedule_timer_tick()
    # -------- einde timer --------

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
    # -------- einde scroll helpers ----

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

        # checkbuttons met vaste linkermarge + wrap
        for idx, opt in enumerate(options):
            previously_selected = (idx in saved) if saved is not None else False
            var = tk.BooleanVar(value=previously_selected)

            opt_row = tk.Frame(self.options_frame)
            opt_row.pack(fill="x")

            cb = tk.Checkbutton(
                opt_row,
                text=opt,
                variable=var,
                font=F_OPTION,
                anchor="w",
                justify="left",
                wraplength=WRAP_W,
                padx=0
            )
            cb.pack(side="left", anchor="w", padx=(OPTIONS_LEFT_PAD, 0), pady=6, fill="x")
            if not hasattr(self, "_opt_vars"):
                self._opt_vars = []
            self._opt_vars.append(var)

    def display_question_image_canvas(self):
        q = self.questions[self.current_question_index]
        image_path = q.get("image")
        if not image_path:
            self.image_label.configure(image="", height=1)
            self.image_label.image = None
            return
        base = resource_dir()
        full_image_path = os.path.join(base, os.path.normpath(image_path)) if not os.path.isabs(image_path) else os.path.normpath(image_path)
        if not os.path.exists(full_image_path):
            self.image_label.configure(image="", height=1)
            self.image_label.image = None
            return
        try:
            img = Image.open(full_image_path)
            max_width, max_height = WRAP_W, 500
            w, h = img.size
            scale = min(max_width / w, max_height / h)
            if scale < 1:
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
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
        selected = []
        for i, child in enumerate(self.options_frame.winfo_children()):
            if hasattr(self, "_opt_vars"):
                try:
                    var = self._opt_vars[-len(self.options_frame.winfo_children()) + i]
                except Exception:
                    var = None
            else:
                var = None
            if var and var.get():
                selected.append(i)

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
        if hasattr(self, 'question_win') and self.question_win:
            self.question_win.destroy()
        messagebox.showinfo("Quiz", "Quiz is afgesloten.", parent=self.master)

    def show_stats(self):
        self._unbind_local_scroll()

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
        tick = "✓" if passed else "✗"
        color = "green" if passed else "red"
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

        current_q = self.questions[self.current_question_index]
        options = self.shuffled_options[self.current_question_index]
        explanations = current_q.get("explanation", {})
        user_selected = self.user_answers[self.current_question_index] if self.user_answers[self.current_question_index] is not None else []
        correct = current_q.get("answer")
        correct_set = set(correct) if isinstance(correct, list) else {correct}

        self.review_question_label.config(text=current_q["question"])
        self.question_counter_review.config(text=f"Question {self.current_question_index + 1} / {len(self.questions)}")

        last_opt_text = ""
        last_expl = ""
        for idx, opt in enumerate(options):
            explanation = explanations.get(opt, "")
            user_sel = (idx in user_selected)
            is_correct = (opt in correct_set)

            if user_sel and is_correct:
                lbl = tk.Label(self.options_frame_review, text=f"[Correct ✓] {opt}", fg="green", font=("Helvetica", 18, "bold"))
            elif user_sel and not is_correct:
                lbl = tk.Label(self.options_frame_review, text=f"[Incorrect X] {opt}", fg="red", font=("Helvetica", 18, "bold"))
            elif not user_sel and is_correct:
                lbl = tk.Label(self.options_frame_review, text=f"{opt}", fg="green", font=("Helvetica", 18))
            else:
                lbl = tk.Label(self.options_frame_review, text=f"{opt}", fg="red", font=("Helvetica", 18))
            lbl.pack(anchor="w", pady=(10, 0))

            last_opt_text = opt
            last_expl = explanation

        exp = tk.Label(self.options_frame_review, text=f"{last_opt_text}: {last_expl}", fg="black", font=("Helvetica", 16), wraplength=WRAP_W, justify="left")
        exp.pack(anchor="w", pady=(0, 10))

    # ---------------- Window helpers & errors ----------------
    def center_window_main(self, window, w, h):
        window.update_idletasks()
        screen_width = window.winfo_screenwidth()
        x = (screen_width // 2) - (w // 2)
        y = (window.winfo_screenheight() // 2) - (h // 2)
        window.geometry(f"{w}x{h}+{x}+{y}")

    def center_toplevel(self, window, w=1600, h=900):
        window.update_idletasks()
        x = (window.winfo_screenwidth() // 2) - (w // 2)
        y = (window.winfo_screenheight() // 2) - (h // 2)
        window.geometry(f"{w}x{h}+{x}+{y}")

    def _unbind_local_scroll(self):
        """Maak lokale muiswiel-bindings los (veilig bij sluiten)."""
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
            try:
                parent.lift()
            except Exception:
                pass


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
                with open(os.path.join(resource_dir(), "startup_error.log"), "w", encoding="utf-8") as f:
                    f.write(err)
            except Exception:
                pass


























    









