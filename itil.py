

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
import time  # <— voor ‘ignore next release’ timing

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
DOT_SIZE = 14      # diameter stip in px

# ---- Dropdown look-and-feel (lijken op Tk menu) ----
MENU_BG   = "#f0f0f0"    # standaard menu-achtig lichtgrijs
SEP_BG    = "#d0d0d0"
HOVER_BG  = "#3875d6"    # menu-blauw (hover)
HOVER_FG  = "white"
TEXT_FG   = "black"

# ------------------------------------------------------------
# Helpers voor paden & data laden
# ------------------------------------------------------------
def resource_dir() -> str:
    """Map van waaruit resources geladen worden (PyInstaller of bronmap)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
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

        # Scores (laatste resultaten per toets)
        self.scores = self._load_scores()
        self.toets_menu_by_group = {}
        self.active_dropdown = None
        self._release_ignore_until = 0.0  # timestamp tot wanneer release events genegeerd worden

        # UI
        self.center_window_main(self.master, 1400, 800)
        self.banner = tk.Label(self.master, text="Itil 4 Foundation", font=F_BANNER)
        self.banner.pack(pady=20)

        self.navbar_frame = tk.Frame(self.master)
        self.navbar_frame.pack()

        self.book_button = tk.Button(
            self.navbar_frame, text="📖", font=F_MENU,
            relief="raised", borderwidth=1, command=self.open_book_pdf
        )
        try:
            base = resource_dir()
            book_icon_path = os.path.join(base, "assets", "afbeeldingen", "book.png")
            if os.path.exists(book_icon_path):
                img = Image.open(book_icon_path)
                img.thumbnail((32, 32), Image.LANCZOS)
                self.book_img = ImageTk.PhotoImage(img)
                self.book_button.configure(image=self.book_img, text="")
        except Exception:
            pass
        self.book_button.pack(side="left", padx=10)

        # Hoofdstuk menu
        self.hoofdstukken_menu = tk.Menubutton(
            self.navbar_frame, text="Hoofdstukken", font=F_MENU,
            relief="raised", borderwidth=1
        )
        self.hoofdstukken_menu.menu = tk.Menu(self.hoofdstukken_menu, tearoff=0, font=F_MENU_ITEM)
        self.hoofdstukken_menu["menu"] = self.hoofdstukken_menu.menu
        self.hoofdstukken_menu.pack(side="left", padx=20)

        # Hoofdstukken 2..5
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

    # ---------------- Scores opslag ----------------
    def _legacy_scores_paths(self):
        """
        Oude locaties uit eerdere versies (AppData of home).
        Wordt gebruikt om 1x te migreren naar assets/score/.
        """
        paths = []
        appdata = os.getenv("APPDATA")
        if appdata:
            paths.append(os.path.join(appdata, "ITIL4Trainer", "scores.json"))
        # fallback/home lokatie
        paths.append(os.path.join(os.path.expanduser("~"), ".itil4_trainer", "scores.json"))
        return paths

    def _scores_path(self) -> str:
        """
        NIEUWE locatie: <project-root>/assets/score/scores.json
        - Werkt dynamisch (waar je map ook staat), dankzij resource_dir().
        - Map wordt aangemaakt als hij nog niet bestaat.
        """
        base = resource_dir()
        score_dir = os.path.join(base, "assets", "score")
        os.makedirs(score_dir, exist_ok=True)
        return os.path.join(score_dir, "scores.json")

    def _load_scores(self) -> dict:
        """
        Scores laden. Als nog geen bestand bestaat in assets/score/,
        proberen we 1x te migreren vanaf legacy locaties.
        """
        path = self._scores_path()

        # 1x migratie vanaf legacy paden
        if not os.path.exists(path):
            for oldp in self._legacy_scores_paths():
                if os.path.exists(oldp):
                    try:
                        with open(oldp, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        with open(path, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        break  # eerste gevonden legacy bestand is gemigreerd
                    except Exception:
                        pass

        # Normaal laden
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_scores(self):
        """Scores bewaren op de nieuwe projectlocatie."""
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
        # herbouw juist menu (op basis van groep uit bestandsnaam)
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
        # Menubutton als tab; we tonen een eigen dropdown bij click
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
                return round(pct, 1)   # <-- 1 decimaal

            # NE items
            for i in range(1, count + 1):
                f_ne = self._find_variant_file(dirp, groep, i, "ne")
                if f_ne and os.path.exists(f_ne):
                    cnt = self.count_questions_in_path(f_ne)
                    base_ne = os.path.basename(f_ne)
                    pct = score_percent(base_ne)
                    left = f"toets {groep}_{i} (NE) ({cnt})"
                    items.append({"type": "item", "left": left, "pct": pct, "file": f_ne, "title": f"ITIL 4 {left}"})

            # scheiding als er ook EN komt
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

        # klik op tab -> open dropdown; negeer release
        mb.unbind("<Button-1>")
        mb.bind("<Button-1>", lambda e, it=items, btn=mb: self._on_tab_click(e, it, btn))

    def _on_tab_click(self, event, items, btn):
        self._open_dropdown(btn, items)
        # release events even negeren zodat dropdown niet direct dicht gaat
        self._release_ignore_until = time.time() + 0.35
        return "break"

    # ---------- Custom dropdown helpers ----------
    def _open_dropdown(self, widget: tk.Widget, items: list):
        self._close_active_dropdown()

        # plaats dropdown onder de knop
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
                # Canvas (stip) heeft geen fg
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

            # rechter kant: score + stip (stip rechts!)
            dot = None
            if pct is not None:
                lbl_score = tk.Label(row, text=f" score {pct:.1f}%", bg=MENU_BG, fg=TEXT_FG, font=F_MENU_ITEM, anchor="e")
                lbl_score.pack(side="left")

                color = "#1f9d3a" if pct >= PASS_THRESHOLD else "#d11d1d"
                dot = tk.Canvas(row, width=DOT_SIZE+2, height=DOT_SIZE+2, bg=MENU_BG, highlightthickness=0)
                dot.create_oval(1, 1, DOT_SIZE, DOT_SIZE, fill=color, outline=color)
                dot.pack(side="right", padx=(6, 0), pady=(DOT_PADY, 0))

            # hover & click
            def on_enter(e):
                color_row(row, HOVER_BG, HOVER_FG)
            def on_leave(e):
                color_row(row, MENU_BG, TEXT_FG)
            def on_click(e):
                self._close_active_dropdown()
                self._start_toets_file(file_path, title)

            row.bind("<Enter>", on_enter)
            row.bind("<Leave>", on_leave)
            row.bind("<Button-1>", on_click)
            lbl_left.bind("<Button-1>", on_click)
            if pct is not None:
                lbl_score.bind("<Button-1>", on_click)
                dot.bind("<Button-1>", on_click)

        # regels
        for it in items:
            t = it.get("type")
            if t == "sep":
                tk.Frame(frame, height=1, bg=SEP_BG).pack(fill="x", pady=2)
            elif t == "item":
                add_item_row(frame, it["left"], it.get("pct"), it["file"], it["title"])
            else:
                tk.Label(frame, text=it.get("text", ""), bg=MENU_BG, fg=TEXT_FG, font=F_MENU_ITEM).pack(padx=8, pady=4)

        # sluit bij focusverlies (klik in ander venster)
        top.bind("<FocusOut>", lambda e: self._close_active_dropdown())
        top.focus_set()

    def _close_active_dropdown(self):
        if self.active_dropdown and self.active_dropdown.winfo_exists():
            self.active_dropdown.destroy()
        self.active_dropdown = None

    def _close_dropdown_global(self, event):
        # release events negeren vlak na openen
        if time.time() < self._release_ignore_until:
            return
        if self.active_dropdown and self.active_dropdown.winfo_exists():
            x1 = self.active_dropdown.winfo_rootx()
            y1 = self.active_dropdown.winfo_rooty()
            x2 = x1 + self.active_dropdown.winfo_width()
            y2 = y1 + self.active_dropdown.winfo_height()
            if not (x1 <= event.x_root <= x2 and y1 <= event.y_root <= y2):
                self._close_active_dropdown()

    # ---------------- Boek openen ----------------
    def open_book_pdf(self):
        base = resource_dir()
        pdf_path = os.path.join(base, "assets", "boek", "itil_4_boek.pdf")
        if not os.path.exists(pdf_path):
            self.show_error_message(f"Boek niet gevonden:\n{pdf_path}")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(pdf_path)
            elif sys.platform == "darwin":
                os.system(f"open \"{pdf_path}\"")
            else:
                webbrowser.open(f"file://{pdf_path}")
        except Exception as e:
            self.show_error_message(f"Kon PDF niet openen: {e}")

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

        self.header_frame = tk.Frame(self.question_win)
        self.header_frame.pack(side="top", fill="x")

        self.chapter_title_label = tk.Label(self.header_frame, text=self.current_session_title, font=F_HEADER, justify="center")
        self.chapter_title_label.pack(pady=(12, 2))

        self.question_counter = tk.Label(self.header_frame, text="", font=F_COUNTER, justify="center")
        self.question_counter.pack(pady=(0, 10))

        self.body_container = tk.Frame(self.question_win)
        self.body_container.pack(fill="both", expand=True)

        self.question_canvas = tk.Canvas(self.body_container, highlightthickness=0)
        self.question_canvas.pack(side="left", fill="both", expand=True)

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

        self.image_label = tk.Label(self.content)
        self.image_label.pack(pady=(0, 15))

        self.options_frame = tk.Frame(self.content)
        self.options_frame.pack(pady=5, fill="x")

        bottom_frame = tk.Frame(self.question_win)
        bottom_frame.pack(side="bottom", pady=(14, 20))
        self.submit_button = tk.Button(bottom_frame, text="Submit", font=F_BUTTON, command=self.submit_answer)
        self.submit_button.pack(side="top", pady=(0, 18))

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
        self.question_canvas.bind_all("<MouseWheel>", self._on_mousewheel_question)

        self.load_question_canvas()

    def _configure_question_content(self, event):
        self.question_canvas.configure(scrollregion=self.question_canvas.bbox("all"))

    def _on_mousewheel_question(self, event):
        self.question_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

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
        self.var_list = []
        for idx, opt in enumerate(options):
            previously_selected = (idx in saved) if saved is not None else False
            var = tk.BooleanVar(value=previously_selected)
            cb = tk.Checkbutton(self.options_frame, text=opt, variable=var,
                                font=F_OPTION, anchor="w", justify="left",
                                wraplength=WRAP_W, padx=6)
            cb.pack(fill="x", anchor="w", pady=4)
            self.var_list.append(var)

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
        selected = [i for i, var in enumerate(self.var_list) if var.get()]
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
        if hasattr(self, 'question_win') and self.question_win:
            self.question_win.destroy()
        messagebox.showinfo("Quiz", "Quiz is afgesloten.", parent=self.master)

    def show_stats(self):
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

        # score opslaan (menu updaten)
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

        review_scrollbar = tk.Scrollbar(container, orient="vertical", command=self.review_canvas.yview)
        review_scrollbar.pack(side="right", fill="y")
        self.review_canvas.configure(yscrollcommand=review_scrollbar.set)

        self.review_content_frame = tk.Frame(self.review_canvas)
        offset_x = 400
        self.review_canvas.create_window((offset_x, 0), window=self.review_content_frame, anchor="nw")

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

        exp = tk.Label(self.options_frame_review, text=f"{opt}: {explanation}", fg="black", font=("Helvetica", 16), wraplength=WRAP_W, justify="left")
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

    def close_question_window(self):
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















    









