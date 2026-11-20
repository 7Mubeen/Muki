"""Mandarin card editor, deck browser and audio-enabled review UI."""
import json
from pathlib import Path
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

from muki.audio.backend import play, record, playback_command, recording_command
from muki.anki.importer import import_apkg, AnkiImportError
from muki.study import (
    MODES, check_answer, practice_priority_label, prompt_for_mode,
    weighted_shuffle_cards,
)

BG, PAPER, INK, MUTED, BORDER = "#F8F9FA", "#FFFFFF", "#0F172A", "#475569", "#CBD5E1"
INDIGO, JADE, AMBER, RED = "#4F46E5", "#0D9488", "#D97706", "#DC2626"


class MukiApp(tk.Tk):
    def __init__(self, database):
        super().__init__()
        self.database = database
        self.media_dir = database.path.parent / "media"
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.title("MUKI — Mandarin SRS")
        self.geometry("1024x600")
        self.minsize(800, 500)
        self.configure(bg=BG)
        self.current_deck_id = None
        self.study_card = None
        self.study_started = None
        self._configure_styles()
        self._build_shell()
        self.show_dashboard()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=25, background=PAPER, fieldbackground=PAPER,
                        foreground=INK, bordercolor=BORDER, font=("TkDefaultFont", 10))
        style.configure("Treeview.Heading", background="#F1F5F9", foreground=MUTED,
                        relief="flat", font=("TkDefaultFont", 9, "bold"))
        style.map("Treeview", background=[("selected", "#EEF2FF")], foreground=[("selected", INK)])

    def _build_shell(self):
        header = tk.Frame(self, bg=PAPER, height=42, highlightbackground=BORDER, highlightthickness=1)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="MUKI", bg=PAPER, fg=INDIGO,
                 font=("TkDefaultFont", 15, "bold")).pack(side="left", padx=(14, 18))
        tk.Label(header, text="MANDARIN LEARNING WORKSPACE", bg=PAPER, fg=MUTED,
                 font=("TkFixedFont", 8)).pack(side="left")
        tk.Label(header, text="OFFLINE · LOCAL DATABASE", bg=PAPER, fg=JADE,
                 font=("TkFixedFont", 8)).pack(side="right", padx=14)
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        nav = tk.Frame(body, bg="#F1F5F9", width=166, highlightbackground=BORDER, highlightthickness=1)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        tk.Label(nav, text="WORKSPACE", bg="#F1F5F9", fg=MUTED,
                 font=("TkFixedFont", 8, "bold")).pack(anchor="w", padx=13, pady=(18, 8))
        for label, command in (("Overview", self.show_dashboard), ("Deck library", self.show_decks),
                               ("Study session", self.show_study)):
            tk.Button(nav, text=label, command=command, anchor="w", relief="flat", bd=0,
                      bg="#F1F5F9", fg=INK, activebackground="#EEF2FF",
                      activeforeground=INDIGO, padx=13, pady=8, cursor="hand2").pack(fill="x", padx=5, pady=1)
        tk.Label(nav, text="BUILD  0.5.3-dev", bg="#F1F5F9", fg="#64748B",
                 font=("TkFixedFont", 8)).pack(side="bottom", anchor="w", padx=13, pady=12)
        self.workspace = tk.Frame(body, bg=BG)
        self.workspace.pack(side="left", fill="both", expand=True)

    def _clear(self):
        # Do not leave review hotkeys active after navigating away from a session.
        for sequence in ("<space>", "<Escape>", "<Key-1>", "<Key-2>", "<Key-3>", "<Key-4>"):
            self.unbind(sequence)
        self.study_card = None
        self.study_answer_shown = False
        for child in self.workspace.winfo_children():
            child.destroy()

    def _heading(self, eyebrow, title, subtitle):
        top = tk.Frame(self.workspace, bg=BG)
        top.pack(fill="x", padx=18, pady=(12, 9))
        tk.Label(top, text=eyebrow.upper(), bg=BG, fg=INDIGO,
                 font=("TkFixedFont", 8, "bold")).pack(anchor="w")
        tk.Label(top, text=title, bg=BG, fg=INK,
                 font=("TkDefaultFont", 19, "bold")).pack(anchor="w", pady=(1, 0))
        tk.Label(top, text=subtitle, bg=BG, fg=MUTED,
                 font=("TkDefaultFont", 9)).pack(anchor="w")

    def _button(self, parent, label, command, primary=False):
        return tk.Button(parent, text=label, command=command,
                         bg=INDIGO if primary else PAPER, fg=PAPER if primary else INK,
                         activebackground="#3730A3" if primary else "#EEF2FF",
                         activeforeground=PAPER if primary else INDIGO,
                         relief="flat" if primary else "solid", bd=0 if primary else 1,
                         padx=11, pady=5, cursor="hand2")

    def _stat(self, parent, label, value, accent):
        card = tk.Frame(parent, bg=PAPER, highlightbackground=BORDER, highlightthickness=1)
        tk.Frame(card, bg=accent, height=3).pack(fill="x")
        inner = tk.Frame(card, bg=PAPER)
        inner.pack(fill="both", expand=True, padx=10, pady=6)
        tk.Label(inner, text=label.upper(), bg=PAPER, fg=MUTED,
                 font=("TkFixedFont", 8)).pack(anchor="w")
        tk.Label(inner, text=str(value), bg=PAPER, fg=INK,
                 font=("TkDefaultFont", 18, "bold")).pack(anchor="w")
        return card

    def show_dashboard(self):
        self._clear()
        stats = self.database.dashboard_stats()
        self._heading("Your workspace", "Good to see you.", "A quiet place to build durable Mandarin knowledge.")
        row = tk.Frame(self.workspace, bg=BG)
        row.pack(fill="x", padx=18, pady=(0, 12))
        for label, key, color in (("Decks", "decks", INDIGO), ("Cards", "cards", JADE),
                                  ("Due now", "due", AMBER), ("Reviews", "reviews", MUTED)):
            self._stat(row, label, stats[key], color).pack(side="left", fill="both", expand=True, padx=(0, 8))
        panel = tk.Frame(self.workspace, bg=PAPER, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        tk.Label(panel, text="TODAY'S STUDY", bg=PAPER, fg=MUTED,
                 font=("TkFixedFont", 8, "bold")).pack(anchor="w", padx=13, pady=(12, 3))
        tk.Label(panel, text="Learn the sound, not just the character.", bg=PAPER, fg=INK,
                 font=("TkDefaultFont", 14, "bold")).pack(anchor="w", padx=13)
        tk.Label(panel, text="Cards can include pinyin, example sentences and separate word/sentence recordings.",
                 bg=PAPER, fg=MUTED, font=("TkDefaultFont", 9)).pack(anchor="w", padx=13, pady=(3, 12))
        self._button(panel, "Open deck library  →", self.show_decks, True).pack(anchor="w", padx=13, pady=(0, 12))

    def show_decks(self):
        self._clear()
        self._heading("Your collection", "Deck library", "Double-click a deck to open it and add Mandarin cards.")
        actions = tk.Frame(self.workspace, bg=BG)
        actions.pack(fill="x", padx=18, pady=(0, 8))
        self._button(actions, "+ New deck", self.create_deck, True).pack(side="left")
        self._button(actions, "Import Anki .apkg", self.import_anki).pack(side="left", padx=7)
        self._button(actions, "Delete selected deck", lambda: self._delete_selected_deck(tree),).pack(side="left", padx=7)
        self._button(actions, "Refresh", self.show_decks).pack(side="left", padx=7)
        frame = tk.Frame(self.workspace, bg=PAPER, highlightbackground=BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        tree = ttk.Treeview(frame, columns=("deck", "cards", "due"), show="headings", height=12)
        for col, label, width, anchor in (("deck", "DECK", 390, "w"), ("cards", "CARDS", 90, "e"), ("due", "DUE", 90, "e")):
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor=anchor)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for deck in self.database.list_decks():
            tree.insert("", "end", iid=str(deck["id"]), values=(deck["name"], deck["cards"] or 0, deck["due"] or 0))
        tree.bind("<Double-1>", lambda event: self.open_selected_deck(tree))
        if not tree.get_children():
            tk.Label(frame, text="No decks yet — create your first deck to begin.",
                     bg=PAPER, fg=MUTED).place(relx=0.5, rely=0.52, anchor="center")
        self.deck_tree = tree

    def import_anki(self):
        package = filedialog.askopenfilename(
            parent=self, title="Import an Anki deck",
            filetypes=[("Anki packages", "*.apkg *.oapkg"), ("All files", "*.*")]
        )
        if not package:
            return
        try:
            result = import_apkg(package, self.database, self.media_dir)
        except AnkiImportError as exc:
            messagebox.showerror("Anki import failed", str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Anki import failed", "The package could not be imported safely. Details: " + str(exc), parent=self)
            return
        lines = [
            "Import complete",
            "",
            "Decks: {decks}".format(**result),
            "Notes: {notes}".format(**result),
            "Cards: {cards}".format(**result),
            "Media files extracted: {media}".format(**result),
            "Duplicates skipped: {duplicates}".format(**result),
        ]
        if result.get("warnings"):
            lines.extend(["", "Notes and limitations:"] + ["• " + item for item in result["warnings"]])
        messagebox.showinfo("MUKI · Anki import report", "\n".join(lines), parent=self)
        self.show_decks()

    def _delete_selected_deck(self, tree):
        if not tree.selection():
            messagebox.showinfo("Select a deck", "Choose a deck before deleting it.", parent=self)
            return
        deck_id = int(tree.selection()[0])
        deck = self.database.get_deck(deck_id)
        if deck is None:
            self.show_decks()
            return
        card_count = len(self.database.list_cards(deck_id))
        prompt = (
            "Permanently delete deck ‘{name}’ and its {count} card(s)?\n\n"
            "Its notes, cards, and review history will be deleted. This cannot be undone. "
            "Audio files are left in the media folder so shared files are not accidentally removed."
        ).format(name=deck["name"], count=card_count)
        if not messagebox.askyesno("Delete deck?", prompt, icon="warning", parent=self):
            return
        if self.database.delete_deck(deck_id):
            self.current_deck_id = None
            self.show_decks()

    def _delete_selected_card(self, tree, deck_id):
        card_id = getattr(self, "card_focus_id", None)
        if card_id is None:
            messagebox.showinfo("Select a card", "Click a card row before deleting it.", parent=self)
            return
        card_id = int(card_id)
        card = self.database.get_card(card_id)
        if card is None:
            self.show_deck(deck_id)
            return
        fields = json.loads(card["fields_json"] or "{}")
        label = fields.get("hanzi") or card["front"]
        prompt = (
            "Permanently delete card ‘{label}’?\n\n"
            "Its review history will also be deleted. This cannot be undone. "
            "Attached audio files are left in the media folder."
        ).format(label=label)
        if not messagebox.askyesno("Delete card?", prompt, icon="warning", parent=self):
            return
        if self.database.delete_card(card_id):
            self.show_deck(deck_id)

    def create_deck(self):
        name = simpledialog.askstring("New deck", "Deck name:", parent=self)
        if name is None:
            return
        try:
            deck_id = self.database.create_deck(name)
        except ValueError as exc:
            messagebox.showwarning("MUKI", str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Could not create deck", str(exc), parent=self)
            return
        # Take the user directly into the new deck so the next action is obvious.
        self.show_deck(deck_id)

    def open_selected_deck(self, tree=None):
        widget = tree or getattr(self, "deck_tree", None)
        if widget is None or not widget.selection():
            return
        self.show_deck(int(widget.selection()[0]))

    def show_deck(self, deck_id):
        deck = self.database.get_deck(deck_id)
        if deck is None:
            messagebox.showerror("MUKI", "That deck no longer exists.")
            self.show_decks()
            return
        self.current_deck_id = deck_id
        self._clear()
        self._heading("Deck workspace", deck["name"], "Create, edit and review cards in this deck.")
        actions = tk.Frame(self.workspace, bg=BG)
        actions.pack(fill="x", padx=18, pady=(0, 8))
        self._button(actions, "+ Add card", lambda: self.edit_card(), True).pack(side="left")
        self._button(actions, "Edit selected", lambda: self._edit_selected_card(tree)).pack(side="left", padx=6)
        self._button(actions, "Delete selected", lambda: self._delete_selected_card(tree, deck_id)).pack(side="left", padx=6)
        self._button(actions, "Study selected", lambda: self._study_selected_cards(tree, deck_id), True).pack(side="left", padx=6)
        self._button(actions, "Study all", lambda: self.show_study(deck_id)).pack(side="left", padx=6)
        self._button(actions, "All decks", self.show_decks).pack(side="left")
        panel = tk.Frame(self.workspace, bg=PAPER, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        selection_bar = tk.Frame(panel, bg=PAPER)
        selection_bar.pack(fill="x", padx=10, pady=(8, 4))
        self._button(selection_bar, "Select all", self._select_all_cards).pack(side="left")
        self._button(selection_bar, "Deselect all", self._deselect_all_cards).pack(side="left", padx=6)
        self.card_selection_count = tk.StringVar(value="0 selected")
        tk.Label(selection_bar, textvariable=self.card_selection_count,
                 bg=PAPER, fg=MUTED).pack(side="right")
        tk.Label(panel, text="Tick cards to include them. Click a row to focus it; double-click to edit.",
                 bg=PAPER, fg=MUTED).pack(anchor="w", padx=10, pady=(0, 4))

        list_shell = tk.Frame(panel, bg=PAPER)
        list_shell.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.card_list_canvas = tk.Canvas(list_shell, bg=PAPER, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(list_shell, orient="vertical", command=self.card_list_canvas.yview)
        self.card_list_canvas.configure(yscrollcommand=scrollbar.set)
        self.card_list_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.card_list_frame = tk.Frame(self.card_list_canvas, bg=PAPER)
        self.card_list_window = self.card_list_canvas.create_window(
            (0, 0), window=self.card_list_frame, anchor="nw"
        )
        self.card_list_frame.bind(
            "<Configure>",
            lambda event: self.card_list_canvas.configure(
                scrollregion=self.card_list_canvas.bbox("all")
            ),
        )
        self.card_list_canvas.bind(
            "<Configure>",
            lambda event: self.card_list_canvas.itemconfigure(
                self.card_list_window, width=event.width
            ),
        )

        cards = self.database.list_cards(deck_id)
        self.card_selection_ids = set()
        self.card_selection_vars = {}
        self.card_row_frames = {}
        self.card_focus_id = None
        if not cards:
            tk.Label(self.card_list_frame,
                     text="This deck is empty. Select + Add card to create your first entry.",
                     bg=PAPER, fg=MUTED).pack(pady=30)
        for card in cards:
            card_id = int(card["id"])
            fields = json.loads(card["fields_json"] or "{}")
            row = tk.Frame(self.card_list_frame, bg=PAPER, highlightthickness=1,
                           highlightbackground=BORDER)
            row.pack(fill="x", pady=1)
            self.card_row_frames[card_id] = row
            selected_var = tk.BooleanVar(value=False)
            self.card_selection_vars[card_id] = selected_var
            tk.Checkbutton(
                row, variable=selected_var,
                command=lambda cid=card_id: self._set_card_checked(cid),
                bg=PAPER, activebackground=PAPER, selectcolor=PAPER,
                relief="flat", bd=0, padx=8, pady=5,
                takefocus=True,
            ).pack(side="left")
            text_area = tk.Frame(row, bg=PAPER)
            text_area.pack(side="left", fill="x", expand=True, padx=(2, 8), pady=4)
            hanzi = fields.get("hanzi", card["front"])
            pinyin = fields.get("pinyin", "")
            meaning = fields.get("meaning", "")
            tk.Label(text_area, text=hanzi, bg=PAPER, fg=INK,
                     font=("TkDefaultFont", 11, "bold"), anchor="w").pack(
                         side="left", padx=(0, 18)
                     )
            tk.Label(text_area, text=pinyin, bg=PAPER, fg=JADE,
                     anchor="w", width=18).pack(side="left", padx=(0, 12))
            tk.Label(text_area, text=meaning, bg=PAPER, fg=MUTED,
                     anchor="w", justify="left", wraplength=520).pack(
                         side="left", fill="x", expand=True
                     )
            for widget in (row, text_area, *text_area.winfo_children()):
                widget.bind("<Button-1>", lambda event, cid=card_id: self._focus_card_row(cid))
                widget.bind("<Double-Button-1>",
                            lambda event, cid=card_id: self._edit_selected_card(None, cid))
        self._update_card_selection_count()

    def _focus_card_row(self, card_id):
        self.card_focus_id = int(card_id)
        for current_id, row in getattr(self, "card_row_frames", {}).items():
            color = "#EEF2FF" if current_id == self.card_focus_id else PAPER
            row.configure(bg=color, highlightbackground=INDIGO if current_id == self.card_focus_id else BORDER)
            for child in row.winfo_children():
                if isinstance(child, tk.Frame):
                    child.configure(bg=color)
                    for label in child.winfo_children():
                        if isinstance(label, tk.Label):
                            label.configure(bg=color)

    def _set_card_checked(self, card_id):
        variable = self.card_selection_vars.get(int(card_id))
        if variable is None:
            return
        if variable.get():
            self.card_selection_ids.add(str(card_id))
        else:
            self.card_selection_ids.discard(str(card_id))
        self._update_card_selection_count()

    def _update_card_selection_count(self):
        count = len(getattr(self, "card_selection_ids", set()))
        variable = getattr(self, "card_selection_count", None)
        if variable is not None:
            variable.set("{} selected".format(count))

    def _select_all_cards(self):
        for card_id, variable in getattr(self, "card_selection_vars", {}).items():
            variable.set(True)
            self.card_selection_ids.add(str(card_id))
        self._update_card_selection_count()

    def _deselect_all_cards(self):
        for card_id, variable in getattr(self, "card_selection_vars", {}).items():
            variable.set(False)
        self.card_selection_ids.clear()
        self._update_card_selection_count()

    def _study_selected_cards(self, tree, deck_id):
        selected = sorted(self.card_selection_ids, key=lambda value: int(value))
        if not selected:
            messagebox.showinfo(
                "Select cards",
                "Tick the checkbox beside one or more cards first.",
                parent=self,
            )
            return
        self.show_study(deck_id, card_ids=[int(card_id) for card_id in selected])

    def _edit_selected_card(self, tree, card_id=None):
        focused_id = card_id if card_id is not None else getattr(self, "card_focus_id", None)
        if focused_id is not None:
            self.edit_card(int(focused_id))

    def _store_audio(self, source):
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(source)
        suffix = source.suffix.lower() or ".audio"
        target = self.media_dir / (f"audio_{__import__('time').time_ns()}{suffix}")
        shutil.copy2(source, target)
        return str(target)

    def edit_card(self, card_id=None):
        existing = self.database.get_card(card_id) if card_id else None
        fields = json.loads(existing["fields_json"]) if existing else {}
        deck_id = existing["deck_id"] if existing else self.current_deck_id
        if deck_id is None:
            messagebox.showinfo("Choose a deck", "Open a deck before adding a card.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Edit Mandarin card" if card_id else "New Mandarin card")
        dialog.configure(bg=BG)
        dialog.geometry("660x560")
        dialog.transient(self)
        dialog.grab_set()
        # The editor contains several Mandarin fields and audio controls. Keep it
        # scrollable so every field remains reachable on 1024x600 displays.
        shell = tk.Frame(dialog, bg=BG)
        shell.pack(fill="both", expand=True, padx=10, pady=8)
        canvas = tk.Canvas(shell, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        form = tk.Frame(canvas, bg=BG)
        window_id = canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"))
        canvas.bind_all("<Button-4>", lambda event: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda event: canvas.yview_scroll(1, "units"))
        dialog.protocol("WM_DELETE_WINDOW", lambda: self._close_card_dialog(dialog, canvas))
        entries = {}
        definitions = [
            ("hanzi", "Chinese characters *", False),
            ("pinyin", "Pinyin (tone marks optional; recommended when known)", False),
            ("meaning", "Meaning / translation *", False),
            ("sentence", "Example sentence", False),
            ("sentence_pinyin", "Sentence pinyin", False),
            ("sentence_translation", "Sentence translation", False),
            ("notes", "Usage notes / homophone distinction", True),
        ]
        for key, label, multiline in definitions:
            tk.Label(form, text=label, bg=BG, fg=INK, font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(3, 1))
            if multiline:
                widget = tk.Text(form, height=2, wrap="word", font=("TkDefaultFont", 9))
                widget.pack(fill="x")
                widget.insert("1.0", fields.get(key, ""))
            else:
                widget = tk.Entry(form, font=("TkDefaultFont", 10))
                widget.pack(fill="x", ipady=3)
                widget.insert(0, fields.get(key, ""))
            entries[key] = widget

        audio_frame = tk.LabelFrame(form, text="Local audio · optional", bg=BG, fg=INK, padx=8, pady=5)
        audio_frame.pack(fill="x", pady=(8, 4))
        audio_vars = {}
        for key, label in (("word_audio", "Word pronunciation"), ("sentence_audio", "Sentence pronunciation")):
            line = tk.Frame(audio_frame, bg=BG)
            line.pack(fill="x", pady=2)
            tk.Label(line, text=label, width=22, anchor="w", bg=BG, fg=MUTED).pack(side="left")
            var = tk.StringVar(value=fields.get(key, ""))
            audio_vars[key] = var
            tk.Label(line, textvariable=var, bg=BG, fg=MUTED, anchor="w").pack(side="left", fill="x", expand=True)
            self._button(line, "Choose file", lambda v=var: self._choose_audio(v)).pack(side="right")
            self._button(line, "Record 6s", lambda v=var, k=key: self._record_audio(v, k)).pack(side="right", padx=4)
            self._button(line, "Play", lambda v=var: self._play_audio(v.get())).pack(side="right", padx=4)

        buttons = tk.Frame(form, bg=BG)
        buttons.pack(fill="x", pady=(8, 0))
        self._button(buttons, "Save card", lambda: self._save_card(dialog, entries, audio_vars, deck_id, card_id), True).pack(side="right")
        self._button(buttons, "Cancel", lambda: self._close_card_dialog(dialog, canvas)).pack(side="right", padx=6)

    def _close_card_dialog(self, dialog, canvas):
        try:
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")
        except tk.TclError:
            pass
        dialog.destroy()

    def _choose_audio(self, variable):
        path = filedialog.askopenfilename(parent=self, title="Choose audio",
            filetypes=[("Audio files", "*.mp3 *.wav *.ogg *.flac *.m4a"), ("All files", "*")])
        if path:
            try:
                variable.set(self._store_audio(path))
            except OSError as exc:
                messagebox.showerror("Audio file", str(exc), parent=self)

    def _record_audio(self, variable, kind):
        target = self.media_dir / ("recording_" + __import__("time").strftime("%Y%m%d_%H%M%S") + "_" + kind + ".wav")
        try:
            process = record(target, seconds=6)
        except Exception as exc:
            messagebox.showerror("Audio recording", str(exc), parent=self)
            return
        messagebox.showinfo("Recording", "Recording started for up to 6 seconds. Keep speaking, then wait for it to finish.", parent=self)
        def check_recording():
            status = process.poll()
            if status is None:
                self.after(200, check_recording)
            elif status == 0 and target.is_file() and target.stat().st_size > 44:
                variable.set(str(target))
                messagebox.showinfo("Recording saved", "Your recording has been attached to this card.", parent=self)
            else:
                messagebox.showerror("Recording failed", "The recording command did not produce a usable WAV file. Check your microphone and ALSA device.", parent=self)
        self.after(200, check_recording)

    def _play_audio(self, path):
        if not path:
            messagebox.showinfo("No audio", "Choose or record an audio file first.", parent=self)
            return
        try:
            play(path)
        except Exception as exc:
            messagebox.showerror("Audio playback", str(exc), parent=self)

    def _save_card(self, dialog, entries, audio_vars, deck_id, card_id):
        fields = {}
        for key, widget in entries.items():
            fields[key] = widget.get("1.0", "end-1c").strip() if isinstance(widget, tk.Text) else widget.get().strip()
        for key, variable in audio_vars.items():
            fields[key] = variable.get().strip()
        try:
            if card_id:
                # Preserve imported Anki fields, tags, template metadata and extra media
                # when a learner edits the MUKI-facing Mandarin fields.
                existing = self.database.get_card(card_id)
                if existing:
                    preserved = json.loads(existing["fields_json"] or "{}")
                    preserved.update(fields)
                    fields = preserved
                self.database.update_card(card_id, fields)
            else:
                self.database.create_card(deck_id, fields)
        except Exception as exc:
            messagebox.showerror("Could not save card", str(exc), parent=dialog)
            return
        self._close_card_dialog(dialog, dialog.winfo_children()[0].winfo_children()[0])
        self.show_deck(deck_id)

    def show_study(self, deck_id=None, listening=False, mode=None, card_ids=None):
        self._clear()
        if mode is None:
            mode = "audio_to_hanzi" if listening else "hanzi_to_pinyin"
        if mode not in MODES:
            mode = "hanzi_to_pinyin"
        self.study_mode = mode
        self.study_deck_id = deck_id
        self.study_card_ids = list(dict.fromkeys(int(card_id) for card_id in card_ids)) if card_ids is not None else None
        self.study_listening = mode == "audio_to_hanzi"
        self.study_card = None
        self.study_started = None
        self.study_answer_shown = False
        self._heading("Active recall", "Mandarin practice", "Choose what to retrieve. Type your answer; pinyin tones are optional.")
        controls = tk.Frame(self.workspace, bg=BG)
        controls.pack(fill="x", padx=18, pady=(0, 8))
        tk.Label(controls, text="PROMPT MODE", bg=BG, fg=MUTED,
                 font=("TkFixedFont", 8, "bold")).pack(side="left", padx=(0, 8))
        self.study_mode_var = tk.StringVar(value=MODES[mode][0])
        choices = [(label, key) for key, (label, _, _) in MODES.items()]
        self.study_mode_keys = {label: key for label, key in choices}
        selector = ttk.Combobox(controls, textvariable=self.study_mode_var,
                                values=[label for label, _ in choices],
                                state="readonly", width=22)
        selector.pack(side="left", padx=(0, 12))
        selector.bind("<<ComboboxSelected>>", self._change_study_mode)
        tk.Label(controls, text="SESSION", bg=BG, fg=MUTED,
                 font=("TkFixedFont", 8, "bold")).pack(side="left", padx=(0, 7))
        self.study_scope_var = tk.StringVar(value="SRS: new + due")
        self.study_scope_keys = {"SRS: new + due": "srs", "Practice: all cards": "all"}
        scope_selector = ttk.Combobox(
            controls, textvariable=self.study_scope_var,
            values=list(self.study_scope_keys), state="readonly", width=20
        )
        scope_selector.pack(side="left")
        scope_selector.bind("<<ComboboxSelected>>", self._change_study_scope)
        self.study_scope_mode = "srs"
        self.study_seen_ids = set()
        self.study_round_queue = []
        self.study_round_number = 0
        self._grading_in_progress = False
        self.study_panel = tk.Frame(self.workspace, bg=PAPER, highlightbackground=BORDER, highlightthickness=1)
        self.study_panel.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        # Keep the action area outside the scrollable card content. This ensures
        # Check/Reveal and the SRS rating buttons remain visible on 1024x600 screens.
        self.study_panel.grid_rowconfigure(0, weight=1)
        self.study_panel.grid_columnconfigure(0, weight=1)
        content_shell = tk.Frame(self.study_panel, bg=PAPER)
        content_shell.grid(row=0, column=0, sticky="nsew")
        self.study_canvas = tk.Canvas(content_shell, bg=PAPER, highlightthickness=0, bd=0)
        content_scrollbar = ttk.Scrollbar(content_shell, orient="vertical", command=self.study_canvas.yview)
        self.study_canvas.configure(yscrollcommand=content_scrollbar.set)
        self.study_canvas.pack(side="left", fill="both", expand=True)
        content_scrollbar.pack(side="right", fill="y")
        self.study_card_body = tk.Frame(self.study_canvas, bg=PAPER)
        self.study_canvas_window = self.study_canvas.create_window(
            (0, 0), window=self.study_card_body, anchor="nw"
        )
        self.study_card_body.bind(
            "<Configure>",
            lambda event: self.study_canvas.configure(scrollregion=self.study_canvas.bbox("all")),
        )
        self.study_canvas.bind(
            "<Configure>",
            lambda event: self.study_canvas.itemconfigure(self.study_canvas_window, width=event.width),
        )
        self.study_footer = tk.Frame(self.study_panel, bg=PAPER)
        self.study_footer.grid(row=1, column=0, sticky="ew", padx=8, pady=(2, 7))
        self._next_study_card()

    def _change_study_scope(self, event=None):
        self.study_scope_mode = self.study_scope_keys.get(self.study_scope_var.get(), "srs")
        self.study_seen_ids = set()
        self.study_round_queue = []
        self.study_round_number = 0
        self._next_study_card()

    def _change_study_mode(self, event=None):
        label = self.study_mode_var.get()
        self.study_mode = self.study_mode_keys.get(label, "hanzi_to_pinyin")
        self.study_listening = self.study_mode == "audio_to_hanzi"
        if getattr(self, "study_scope_mode", "srs") == "all" and self.study_card is not None:
            # Changing prompt direction must not silently skip the current card.
            pending_mistakes = getattr(self, "study_mistakes", 0)
            self.study_round_queue.insert(0, {
                "card": self.study_card,
                "weakness_score": self.study_current_priority
                if self.study_current_priority is not None else 2.0,
                "has_history": getattr(self, "study_current_has_history", False),
            })
            self._next_study_card()
            self.study_mistakes = pending_mistakes
            return
        self._next_study_card()

    def _start_practice_round(self):
        entries = self.database.practice_cards(
            getattr(self, "study_deck_id", None),
            selected_card_ids=getattr(self, "study_card_ids", None),
        )
        self.study_round_queue = weighted_shuffle_cards(entries)
        if self.study_round_queue:
            self.study_round_number += 1

    def _next_study_card(self):
        for child in self.study_card_body.winfo_children():
            child.destroy()
        for child in self.study_footer.winfo_children():
            child.destroy()
        self.study_canvas.yview_moveto(0)
        practice_all = getattr(self, "study_scope_mode", "srs") == "all"
        self.study_current_priority = None
        self.study_current_has_history = False
        if practice_all:
            # Refill automatically when a round ends. Each round is shuffled
            # again, with higher-weakness cards weighted towards the front.
            if not self.study_round_queue:
                self._start_practice_round()
            if self.study_round_queue:
                entry = self.study_round_queue.pop(0)
                card = entry["card"]
                self.study_current_priority = entry["weakness_score"]
                self.study_current_has_history = entry["has_history"]
            else:
                card = None
        else:
            card = self.database.next_study_card(
                getattr(self, "study_deck_id", None),
                selected_card_ids=getattr(self, "study_card_ids", None),
            )
        self.study_card = card
        self.study_answer_shown = False
        self.study_mistakes = 0
        if card is None:
            title = "No cards available to practise." if practice_all else "All caught up."
            detail = (
                "This deck or selected-card group has no available cards."
                if practice_all
                else "No new or due cards in this study scope."
            )
            tk.Label(self.study_card_body, text=title, bg=PAPER, fg=JADE,
                     font=("TkDefaultFont", 19, "bold")).pack(pady=(55, 8))
            tk.Label(self.study_card_body, text=detail, bg=PAPER, fg=MUTED,
                     wraplength=650).pack()
            self._button(self.study_card_body, "Back to decks", self.show_decks).pack(pady=8)
            return
        self.study_started = __import__("time").monotonic()
        fields = json.loads(card["fields_json"] or "{}")
        self.study_fields = fields
        mode = self.study_mode
        mode_label, prompt_key, answer_key = MODES[mode]
        tk.Label(self.study_card_body, text=mode_label.upper(), bg=PAPER, fg=MUTED,
                 font=("TkFixedFont", 8, "bold")).pack(pady=(18, 4))
        if practice_all:
            priority = practice_priority_label(
                self.study_current_priority, self.study_current_has_history
            )
            priority_color = {
                "High": RED, "Medium": AMBER, "Low": JADE, "Unassessed": MUTED
            }[priority]
            tk.Label(
                self.study_card_body,
                text="PRACTICE PRIORITY · " + priority.upper(),
                bg=PAPER, fg=priority_color,
                font=("TkFixedFont", 8, "bold"),
            ).pack(pady=(0, 5))
        if mode == "audio_to_hanzi":
            tk.Label(self.study_card_body, text="Listen carefully, then type the word.", bg=PAPER,
                     fg=INK, font=("TkDefaultFont", 15, "bold")).pack(pady=8)
            self._button(self.study_card_body, "▶ Play word audio",
                         lambda: self._play_audio(fields.get("word_audio", "")), True).pack(pady=8)
        else:
            prompt = prompt_for_mode(fields, mode)
            tk.Label(self.study_card_body, text=prompt or "(No prompt field on this card)",
                     bg=PAPER, fg=INK, wraplength=680,
                     font=("TkDefaultFont", 30 if mode in ("hanzi_to_pinyin", "pinyin_to_hanzi") else 19,
                           "bold")).pack(pady=(12, 16))
            if mode == "hanzi_to_pinyin":
                self._button(self.study_card_body, "▶ Hear pronunciation (optional)",
                             lambda: self._play_audio(fields.get("word_audio", ""))).pack(pady=(0, 8))
        self.study_answer_var = tk.StringVar()
        answer_row = tk.Frame(self.study_card_body, bg=PAPER)
        answer_row.pack(fill="x", padx=30, pady=8)
        tk.Label(answer_row, text="YOUR ANSWER", bg=PAPER, fg=MUTED,
                 font=("TkFixedFont", 8, "bold")).pack(anchor="w")
        answer_entry = tk.Entry(answer_row, textvariable=self.study_answer_var,
                                font=("TkDefaultFont", 17), justify="center")
        answer_entry.pack(fill="x", ipady=7, pady=(3, 7))
        answer_entry.bind("<Return>", lambda event: self._check_study_answer())
        answer_entry.focus_set()
        self.study_feedback = tk.Label(self.study_card_body, text="",
                                        bg=PAPER, fg=JADE, font=("TkDefaultFont", 10, "bold"))
        self.study_feedback.pack(pady=3)
        buttons = tk.Frame(self.study_footer, bg=PAPER)
        buttons.pack(pady=2)
        self._button(buttons, "Check answer", self._check_study_answer, True).pack(side="left", padx=5)
        self._button(buttons, "Reveal answer", self._reveal_answer).pack(side="left", padx=5)
        self.bind("<Escape>", lambda event: self._reveal_answer())

    def _check_study_answer(self):
        if not self.study_card or self.study_answer_shown:
            return
        answer = self.study_answer_var.get()
        if check_answer(self.study_fields, self.study_mode, answer):
            self.study_feedback.configure(text="Correct — well recalled.", fg=JADE)
            self._reveal_answer()
        else:
            if getattr(self, "study_scope_mode", "srs") == "all":
                self.study_mistakes = getattr(self, "study_mistakes", 0) + 1
            self.study_feedback.configure(text="Not quite. Try again, or reveal the answer.", fg=RED)

    def _reveal_answer(self):
        if not self.study_card or not self.study_card_body.winfo_exists():
            return
        for child in self.study_card_body.winfo_children():
            child.destroy()
        for child in self.study_footer.winfo_children():
            child.destroy()
        self.study_canvas.yview_moveto(0)
        f = self.study_fields
        self.study_answer_shown = True
        tk.Label(self.study_card_body, text=f.get("hanzi", ""), bg=PAPER, fg=INK,
                 font=("TkDefaultFont", 30, "bold")).pack(pady=(8, 2))
        tk.Label(self.study_card_body, text=f.get("pinyin", ""), bg=PAPER, fg=JADE,
                 font=("TkDefaultFont", 15)).pack(pady=(0, 4))
        tk.Label(self.study_card_body, text=f.get("meaning", ""), bg=PAPER, fg=INK,
                 font=("TkDefaultFont", 18, "bold")).pack(pady=(4, 5))
        self._button(self.study_card_body, "▶ Play word audio",
                     lambda: self._play_audio(f.get("word_audio", ""))).pack(pady=3)
        if f.get("sentence"):
            tk.Label(self.study_card_body, text=f["sentence"], bg=PAPER, fg=INK,
                     font=("TkDefaultFont", 15)).pack(pady=(7, 1))
            tk.Label(self.study_card_body, text=f.get("sentence_pinyin", ""), bg=PAPER, fg=JADE).pack()
            tk.Label(self.study_card_body, text=f.get("sentence_translation", ""), bg=PAPER, fg=MUTED).pack()
            self._button(self.study_card_body, "▶ Play sentence audio",
                         lambda: self._play_audio(f.get("sentence_audio", ""))).pack(pady=5)
        if f.get("notes"):
            tk.Label(self.study_card_body, text=f["notes"], bg=PAPER, fg=MUTED, wraplength=650).pack(pady=5)
        tk.Label(self.study_card_body, text="How well did you remember?", bg=PAPER, fg=MUTED).pack(pady=(10, 5))
        grades = tk.Frame(self.study_footer, bg=PAPER)
        grades.pack(pady=2)
        for rating, label, color in ((1, "1  Again", RED), (2, "2  Hard", AMBER),
                                     (3, "3  Good", JADE), (4, "4  Easy", INDIGO)):
            tk.Button(grades, text=label, command=lambda r=rating: self._grade(r),
                       bg=color, fg=PAPER, activebackground=color, relief="flat", bd=0,
                       padx=13, pady=8).pack(side="left", padx=5)
        self.bind("<Key-1>", lambda event: self._grade(1))
        self.bind("<Key-2>", lambda event: self._grade(2))
        self.bind("<Key-3>", lambda event: self._grade(3))
        self.bind("<Key-4>", lambda event: self._grade(4))

    def _grade(self, rating):
        if (
            not self.study_card
            or not getattr(self, "study_answer_shown", False)
            or getattr(self, "_grading_in_progress", False)
        ):
            return
        self._grading_in_progress = True
        elapsed = int((__import__("time").monotonic() - self.study_started) * 1000)
        card_id = int(self.study_card["id"])
        practice_all = getattr(self, "study_scope_mode", "srs") == "all"
        try:
            if practice_all:
                # Practice feedback is stored separately and must never move
                # the normal SRS due date or alter its ease/repetition values.
                self.database.record_practice_result(
                    card_id, rating, elapsed, mode=self.study_mode,
                    mistakes=getattr(self, "study_mistakes", 0),
                )
            else:
                self.database.grade_card(card_id, rating, elapsed)
        except Exception as exc:
            self._grading_in_progress = False
            messagebox.showerror("Could not save review", str(exc), parent=self)
            return
        self._grading_in_progress = False
        if practice_all:
            self.study_seen_ids.add(card_id)
        self._next_study_card()

    def _on_close(self):
        self.database.close()
        self.destroy()
