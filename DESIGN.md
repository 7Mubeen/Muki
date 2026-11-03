# Scholar Stone Precision — MUKI UI Design Reference

## Design tokens
- Primary focus: #4F46E5
- Retention / success: #0D9488
- Due / pending: #D97706
- Error: #DC2626
- Tone 2: #059669; Tone 3: #D97706; Tone 4: #4F46E5; neutral tone: #64748B
- Background: #F8F9FA; cards: #FFFFFF; text: #0F172A; secondary text: #475569; borders: #CBD5E1
- Pinned study toolbar: #FEF3C7

## Typography
Use Inter for interface text where installed, with system sans-serif fallback. Use Noto Sans CJK SC or WenQuanYi Micro Hei for Hanzi. Use JetBrains Mono for metadata and shortcuts where installed, with a monospace fallback. Keep Hanzi at 32–44 px in the review canvas.

## Layout
Target 1024×600. Keep the interface dense and avoid page-level scrolling in the main study workflow. Use 8–12 px outer margins, 4 px spacing increments, compact header/footer strips, and gaps no larger than 16 px in study panes.

## Components
- Buttons: 28–32 px high, 1 px border, 2 px radius.
- Cards/panels: crisp borders and 2–4 px radii; no blurred shadows.
- Inputs: 28 px high with a 2 px indigo focus outline.
- Data rows: approximately 24 px high, alternating white and warm-neutral backgrounds.
- Due chips: amber; new chips: indigo; learned chips: jade.
- Study grades: Again (crimson), Hard (amber), Good (jade), Easy (indigo), with 1–4 keyboard shortcuts.

## Interaction principles
Keyboard-first, low-distraction, no unnecessary animation. Preserve the visual hierarchy and functional intent of the approved reference. Use actual database values for all statistics; never display fabricated progress numbers.

## Hardware adaptation
The design must remain legible and usable at 1024×600 on an Intel Atom N270 with 2 GB RAM and 32-bit antiX. Prefer native Tk widgets, system fonts, and static visual states over GPU-heavy effects.
