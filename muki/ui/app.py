"""Compact Tkinter shell styled with Scholar Stone Precision."""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

BG, PAPER, INK, MUTED, BORDER = "#F8F9FA", "#FFFFFF", "#0F172A", "#475569", "#CBD5E1"
INDIGO, JADE, AMBER = "#4F46E5", "#0D9488", "#D97706"


class MukiApp(tk.Tk):
    def __init__(self, database):
        super().__init__()
        self.database = database
        self.title("MUKI — Mandarin SRS")
        self.geometry("1024x600")
        self.minsize(800, 500)
        self.configure(bg=BG)
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
        tk.Label(nav, text="BUILD  0.1.0", bg="#F1F5F9", fg="#64748B",
                 font=("TkFixedFont", 8)).pack(side="bottom", anchor="w", padx=13, pady=12)
        self.workspace = tk.Frame(body, bg=BG)
        self.workspace.pack(side="left", fill="both", expand=True)

    def _clear(self):
        for child in self.workspace.winfo_children():
            child.destroy()

    def _heading(self, eyebrow, title, subtitle):
        top = tk.Frame(self.workspace, bg=BG)
        top.pack(fill="x", padx=18, pady=(15, 12))
        tk.Label(top, text=eyebrow.upper(), bg=BG, fg=INDIGO,
                 font=("TkFixedFont", 8, "bold")).pack(anchor="w")
        tk.Label(top, text=title, bg=BG, fg=INK,
                 font=("TkDefaultFont", 20, "bold")).pack(anchor="w", pady=(2, 1))
        tk.Label(top, text=subtitle, bg=BG, fg=MUTED,
                 font=("TkDefaultFont", 9)).pack(anchor="w")

    def _stat(self, parent, label, value, accent):
        card = tk.Frame(parent, bg=PAPER, highlightbackground=BORDER, highlightthickness=1)
        tk.Frame(card, bg=accent, height=3).pack(fill="x")
        inner = tk.Frame(card, bg=PAPER)
        inner.pack(fill="both", expand=True, padx=10, pady=7)
        tk.Label(inner, text=label.upper(), bg=PAPER, fg=MUTED,
                 font=("TkFixedFont", 8)).pack(anchor="w")
        tk.Label(inner, text=str(value), bg=PAPER, fg=INK,
                 font=("TkDefaultFont", 19, "bold")).pack(anchor="w")
        return card

    def show_dashboard(self):
        self._clear()
        stats = self.database.dashboard_stats()
        self._heading("Your workspace", "Good to see you.",
                      "A quiet place to build durable Mandarin knowledge.")
        row = tk.Frame(self.workspace, bg=BG)
        row.pack(fill="x", padx=18, pady=(0, 13))
        for label, key, color in (("Decks", "decks", INDIGO), ("Cards", "cards", JADE),
                                  ("Due now", "due", AMBER), ("Reviews", "reviews", MUTED)):
            self._stat(row, label, stats[key], color).pack(side="left", fill="both", expand=True, padx=(0, 8))
        panel = tk.Frame(self.workspace, bg=PAPER, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        tk.Label(panel, text="TODAY'S STUDY", bg=PAPER, fg=MUTED,
                 font=("TkFixedFont", 8, "bold")).pack(anchor="w", padx=13, pady=(12, 3))
        tk.Label(panel, text="Start with one deliberate review.", bg=PAPER, fg=INK,
                 font=("TkDefaultFont", 14, "bold")).pack(anchor="w", padx=13)
        tk.Label(panel, text="Statistics are read directly from your local MUKI database.",
                 bg=PAPER, fg=MUTED, font=("TkDefaultFont", 9)).pack(anchor="w", padx=13, pady=(3, 12))
        tk.Button(panel, text="Open deck library  →", command=self.show_decks, bg=INDIGO, fg=PAPER,
                  activebackground="#3730A3", activeforeground=PAPER, relief="flat", bd=0,
                  padx=12, pady=7, cursor="hand2").pack(anchor="w", padx=13, pady=(0, 12))

    def show_decks(self):
        self._clear()
        self._heading("Your collection", "Deck library",
                      "Organize vocabulary, characters, grammar and sentences.")
        actions = tk.Frame(self.workspace, bg=BG)
        actions.pack(fill="x", padx=18, pady=(0, 8))
        tk.Button(actions, text="+ New deck", command=self.create_deck, bg=INDIGO, fg=PAPER,
                  activebackground="#3730A3", activeforeground=PAPER, relief="flat", bd=0,
                  padx=12, pady=6, cursor="hand2").pack(side="left")
        tk.Button(actions, text="Refresh", command=self.show_decks, bg=PAPER, fg=INK,
                  activebackground="#EEF2FF", relief="solid", bd=1, padx=10, pady=5).pack(side="left", padx=7)
        frame = tk.Frame(self.workspace, bg=PAPER, highlightbackground=BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        tree = ttk.Treeview(frame, columns=("deck", "cards", "due"), show="headings", height=12)
        tree.heading("deck", text="DECK")
        tree.heading("cards", text="CARDS")
        tree.heading("due", text="DUE")
        tree.column("deck", width=390, anchor="w")
        tree.column("cards", width=90, anchor="e")
        tree.column("due", width=90, anchor="e")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        decks = self.database.list_decks()
        for deck in decks:
            tree.insert("", "end", iid=str(deck["id"]),
                        values=(deck["name"], deck["cards"] or 0, deck["due"] or 0))
        if not decks:
            tk.Label(frame, text="No decks yet — create your first deck to begin.",
                     bg=PAPER, fg=MUTED, font=("TkDefaultFont", 10)).place(relx=0.5, rely=0.52, anchor="center")

    def create_deck(self):
        name = simpledialog.askstring("New deck", "Deck name:", parent=self)
        if name is None:
            return
        try:
            self.database.create_deck(name)
        except ValueError as exc:
            messagebox.showwarning("MUKI", str(exc), parent=self)
        except Exception as exc:
            messagebox.showerror("Could not create deck", str(exc), parent=self)
        self.show_decks()

    def show_study(self):
        self._clear()
        self._heading("Focused practice", "Study session",
                      "Review controls and scheduling arrive in the core SRS milestone.")
        panel = tk.Frame(self.workspace, bg=PAPER, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        tk.Label(panel, text="学习 · LEARN WITH INTENTION", bg=PAPER, fg=INDIGO,
                 font=("TkFixedFont", 10, "bold")).pack(pady=(50, 10))
        tk.Label(panel, text="Your study canvas is ready.", bg=PAPER, fg=INK,
                 font=("TkDefaultFont", 17, "bold")).pack()
        tk.Label(panel, text="Add cards to a deck once the card editor milestone is implemented.",
                 bg=PAPER, fg=MUTED, font=("TkDefaultFont", 9)).pack(pady=(6, 15))
        tk.Button(panel, text="Browse decks", command=self.show_decks, bg=PAPER, fg=INDIGO,
                  activebackground="#EEF2FF", relief="solid", bd=1, padx=12, pady=6).pack()

    def _on_close(self):
        self.database.close()
        self.destroy()
