"""Mandarin card editor, deck browser and audio-enabled review UI."""
import json
from pathlib import Path
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

from muki.audio.backend import play, record, playback_command, recording_command
from muki.anki.importer import import_apkg, AnkiImportError
from muki.study import MODES, check_answer, prompt_for_mode

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
        tk.Label(nav, text="BUILD  0.4.0", bg="#F1F5F9", fg="#64748B",
                 font=("TkFixedFont", 8)).pack(side="bottom", anchor="w", padx=13, pady=12)
        self.workspace = tk.Frame(body, bg=BG)
        self.workspace.pack(side="left", fill="both", expand=True)

    def _clear(self):
        # Do not leave review hotkeys active after navigating away from a session.
        for sequence in ("<space>", "<Key-1>", "<Key-2>", "<Key-3>", "<Key-4>"):
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
            filetypes=[("Anki packages", "*.apkg"), ("All files", "*.*")]
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
        self._button(actions, "Study / recall modes", lambda: self.show_study(deck_id)).pack(side="left", padx=6)
        self._button(actions, "All decks", self.show_decks).pack(side="left")
        panel = tk.Frame(self.workspace, bg=PAPER, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        tree = ttk.Treeview(panel, columns=("hanzi", "pinyin", "meaning"), show="headings")
        for col, label, width in (("hanzi", "HANZI", 150), ("pinyin", "PINYIN", 180), ("meaning", "MEANING", 380)):
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        cards = self.database.list_cards(deck_id)
        for card in cards:
            fields = json.loads(card["fields_json"] or "{}")
            tree.insert("", "end", iid=str(card["id"]),
                        values=(fields.get("hanzi", card["front"]), fields.get("pinyin", ""), fields.get("meaning", "")))
        tree.bind("<Double-1>", lambda event: self._edit_selected_card(tree))
        if not cards:
            tk.Label(panel, text="This deck is empty. Select + Add card to create your first entry.",
                     bg=PAPER, fg=MUTED).place(relx=0.5, rely=0.5, anchor="center")
        self.card_tree = tree

    def _edit_selected_card(self, tree):
        if tree.selection():
            self.edit_card(int(tree.selection()[0]))

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
            ("pinyin", "Pinyin (include tone marks)", False),
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

    def show_study(self, deck_id=None, listening=False, mode=None):
        self._clear()
        if mode is None:
            mode = "audio_to_hanzi" if listening else "hanzi_to_pinyin"
        if mode not in MODES:
            mode = "hanzi_to_pinyin"
        self.study_mode = mode
        self.study_deck_id = deck_id
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
                                state="readonly", width=24)
        selector.pack(side="left")
        selector.bind("<<ComboboxSelected>>", self._change_study_mode)
        self.study_panel = tk.Frame(self.workspace, bg=PAPER, highlightbackground=BORDER, highlightthickness=1)
        self.study_panel.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        self._next_study_card()

    def _change_study_mode(self, event=None):
        label = self.study_mode_var.get()
        self.study_mode = self.study_mode_keys.get(label, "hanzi_to_pinyin")
        self.study_listening = self.study_mode == "audio_to_hanzi"
        self._next_study_card()

    def _next_study_card(self):
        for child in self.study_panel.winfo_children():
            child.destroy()
        card = self.database.next_study_card(getattr(self, "study_deck_id", None))
        self.study_card = card
        self.study_answer_shown = False
        if card is None:
            tk.Label(self.study_panel, text="All caught up.", bg=PAPER, fg=JADE,
                     font=("TkDefaultFont", 19, "bold")).pack(pady=(65, 8))
            tk.Label(self.study_panel, text="No new or due cards in this study scope.", bg=PAPER, fg=MUTED).pack()
            self._button(self.study_panel, "Back to decks", self.show_decks).pack(pady=15)
            return
        self.study_started = __import__("time").monotonic()
        fields = json.loads(card["fields_json"] or "{}")
        self.study_fields = fields
        mode = self.study_mode
        mode_label, prompt_key, answer_key = MODES[mode]
        tk.Label(self.study_panel, text=mode_label.upper(), bg=PAPER, fg=MUTED,
                 font=("TkFixedFont", 8, "bold")).pack(pady=(24, 8))
        if mode == "audio_to_hanzi":
            tk.Label(self.study_panel, text="Listen carefully, then type the word.", bg=PAPER,
                     fg=INK, font=("TkDefaultFont", 15, "bold")).pack(pady=8)
            self._button(self.study_panel, "▶ Play word audio",
                         lambda: self._play_audio(fields.get("word_audio", "")), True).pack(pady=8)
        else:
            prompt = prompt_for_mode(fields, mode)
            tk.Label(self.study_panel, text=prompt or "(No prompt field on this card)",
                     bg=PAPER, fg=INK, wraplength=680,
                     font=("TkDefaultFont", 30 if mode in ("hanzi_to_pinyin", "pinyin_to_hanzi") else 19,
                           "bold")).pack(pady=(12, 16))
            if mode == "hanzi_to_pinyin":
                self._button(self.study_panel, "▶ Hear pronunciation (optional)",
                             lambda: self._play_audio(fields.get("word_audio", ""))).pack(pady=(0, 8))
        self.study_answer_var = tk.StringVar()
        answer_row = tk.Frame(self.study_panel, bg=PAPER)
        answer_row.pack(fill="x", padx=30, pady=8)
        tk.Label(answer_row, text="YOUR ANSWER", bg=PAPER, fg=MUTED,
                 font=("TkFixedFont", 8, "bold")).pack(anchor="w")
        answer_entry = tk.Entry(answer_row, textvariable=self.study_answer_var,
                                font=("TkDefaultFont", 17), justify="center")
        answer_entry.pack(fill="x", ipady=7, pady=(3, 7))
        answer_entry.bind("<Return>", lambda event: self._check_study_answer())
        answer_entry.focus_set()
        self.study_feedback = tk.Label(self.study_panel, text="",
                                        bg=PAPER, fg=JADE, font=("TkDefaultFont", 10, "bold"))
        self.study_feedback.pack(pady=3)
        buttons = tk.Frame(self.study_panel, bg=PAPER)
        buttons.pack(pady=7)
        self._button(buttons, "Check answer", self._check_study_answer, True).pack(side="left", padx=5)
        self._button(buttons, "Reveal answer", self._reveal_answer).pack(side="left", padx=5)
        self.bind("<space>", lambda event: self._reveal_answer())

    def _check_study_answer(self):
        if not self.study_card or self.study_answer_shown:
            return
        answer = self.study_answer_var.get()
        if check_answer(self.study_fields, self.study_mode, answer):
            self.study_feedback.configure(text="Correct — well recalled.", fg=JADE)
            self._reveal_answer()
        else:
            self.study_feedback.configure(text="Not quite. Try again, or reveal the answer.", fg=RED)

    def _reveal_answer(self):
        if not self.study_card or not self.study_panel.winfo_exists():
            return
        for child in self.study_panel.winfo_children():
            child.destroy()
        f = self.study_fields
        self.study_answer_shown = True
        tk.Label(self.study_panel, text=f.get("hanzi", ""), bg=PAPER, fg=INK,
                 font=("TkDefaultFont", 30, "bold")).pack(pady=(8, 2))
        tk.Label(self.study_panel, text=f.get("pinyin", ""), bg=PAPER, fg=JADE,
                 font=("TkDefaultFont", 15)).pack(pady=(0, 4))
        tk.Label(self.study_panel, text=f.get("meaning", ""), bg=PAPER, fg=INK,
                 font=("TkDefaultFont", 18, "bold")).pack(pady=(4, 5))
        self._button(self.study_panel, "▶ Play word audio",
                     lambda: self._play_audio(f.get("word_audio", ""))).pack(pady=3)
        if f.get("sentence"):
            tk.Label(self.study_panel, text=f["sentence"], bg=PAPER, fg=INK,
                     font=("TkDefaultFont", 15)).pack(pady=(7, 1))
            tk.Label(self.study_panel, text=f.get("sentence_pinyin", ""), bg=PAPER, fg=JADE).pack()
            tk.Label(self.study_panel, text=f.get("sentence_translation", ""), bg=PAPER, fg=MUTED).pack()
            self._button(self.study_panel, "▶ Play sentence audio",
                         lambda: self._play_audio(f.get("sentence_audio", ""))).pack(pady=5)
        if f.get("notes"):
            tk.Label(self.study_panel, text=f["notes"], bg=PAPER, fg=MUTED, wraplength=650).pack(pady=5)
        tk.Label(self.study_panel, text="How well did you remember?", bg=PAPER, fg=MUTED).pack(pady=(10, 5))
        grades = tk.Frame(self.study_panel, bg=PAPER)
        grades.pack()
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
        if not self.study_card or not getattr(self, "study_answer_shown", False):
            return
        elapsed = int((__import__("time").monotonic() - self.study_started) * 1000)
        self.database.grade_card(self.study_card["id"], rating, elapsed)
        self._next_study_card()

    def _on_close(self):
        self.database.close()
        self.destroy()
