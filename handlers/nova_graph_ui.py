# handlers/nova_graph_ui.py
import os, random, tkinter as tk
from tkinter import filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFilter

# ---------------- Nova theme ----------------
BG    = "#0f0f0f"
FG    = "#e8e8e8"
ACC   = "#00ffee"   # accent cyan
LBL   = "#9ad7d7"   # axis label color
GRID  = "#3a3a3a"
FRAME = "#2a2a2a"
SPINE = "#4a4a4a"
TICK  = "#cfe"      # tick color

# Point to your assets folder one level up from /handlers
ASSETS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets"))

# ---------- tiny color helpers ----------
def _hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def _rgb_to_hex(rgb):
    r, g, b = [max(0, min(255, int(v))) for v in rgb]
    return f"#{r:02x}{g:02x}{b:02x}"

def lighten_hex(hex_color: str, factor: float = 0.18) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    r = r + (255 - r) * factor
    g = g + (255 - g) * factor
    b = b + (255 - b) * factor
    return _rgb_to_hex((r, g, b))

# ---------- starry background ----------
def make_starry_bg(w: int, h: int) -> ImageTk.PhotoImage:
    bg = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(bg)
    for _ in range(170):
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        r = random.choice([1, 1, 2])
        c = random.choice(["#9ff", "#aff", "#cfffff", "#bff"])
        d.ellipse((x - r, y - r, x + r, y + r), fill=c)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for _ in range(10):
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        r = random.randint(16, 34)
        gd.ellipse((x - r, y - r, x + r, y + r), fill=(0, 255, 240, 42))
    glow = glow.filter(ImageFilter.GaussianBlur(6))
    bg = Image.alpha_composite(bg.convert("RGBA"), glow).convert("RGB")
    return ImageTk.PhotoImage(bg)

# ---------- rounded button helpers ----------
def make_rounded_bg(color: str, radius: int = 10, w: int = 120, h: int = 38, outline: str | None = None) -> ImageTk.PhotoImage:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w, h), radius=radius, fill=color, outline=outline, width=1 if outline else 0)
    return ImageTk.PhotoImage(img)

def make_icon(kind: str, color_fg: str, size: int = 22) -> ImageTk.PhotoImage:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img); w = h = size
    if kind == "arrow":
        pad = 4
        stem_w = max(3, int(w * 0.18))
        stem_x1 = (w - stem_w) // 2; stem_x2 = stem_x1 + stem_w
        stem_y1 = pad; stem_y2 = int(h * 0.54)
        d.rectangle([stem_x1, stem_y1, stem_x2, stem_y2], fill=color_fg)
        head_top_y = int(h * 0.44); tip_y = h - pad
        head_lx = pad; head_rx = w - pad
        d.polygon([(head_lx, head_top_y), (head_rx, head_top_y), (w // 2, tip_y)], fill=color_fg)
    elif kind == "close":
        stroke = max(3, int(w * 0.18)); pad = max(4, stroke)
        d.line([(pad, pad), (w - pad, h - pad)], fill=color_fg, width=stroke)
        d.line([(w - pad, pad), (pad, h - pad)], fill=color_fg, width=stroke)
    return ImageTk.PhotoImage(img)

def rounded_button(parent, text: str, bg_color: str, fg_color: str,
                   icon_kind: str, command, w: int = 120, h: int = 38):
    frame = tk.Frame(parent, width=w, height=h, bg=BG)
    frame.pack_propagate(False)

    hover_color = lighten_hex(bg_color, 0.45)
    dark_outline = "#1a1a1a" if bg_color.lower() == "#000000" else None

    normal_img = make_rounded_bg(bg_color, w=w, h=h, outline=dark_outline)
    hover_img  = make_rounded_bg(hover_color, w=w, h=h, outline=dark_outline)

    bg_label = tk.Label(frame, image=normal_img, bd=0, bg=BG)
    bg_label.image = normal_img; bg_label.hover = hover_img
    bg_label.place(x=0, y=0, relwidth=1, relheight=1); bg_label.lower()

    row = tk.Frame(frame, bg=bg_color)
    row.place(relx=0.5, rely=0.5, anchor="center")

    icon_size = 24 if icon_kind == "arrow" else 22
    icon = make_icon(icon_kind, fg_color, size=icon_size)
    icon_lbl = tk.Label(row, image=icon, bg=bg_color)
    icon_lbl.image = icon; icon_lbl.pack(side="left", padx=(0, 3))

    extra_pad_left = 1 if len(text) < 5 else 0
    txt_lbl = tk.Label(row, text=text, bg=bg_color, fg=fg_color,
                       font=("Segoe UI", 10, "bold"), padx=extra_pad_left)
    txt_lbl.pack(side="left")

    def set_row_bg(c: str):
        row.configure(bg=c); icon_lbl.configure(bg=c); txt_lbl.configure(bg=c)

    def on_enter(_):
        bg_label.configure(image=bg_label.hover); set_row_bg(hover_color)
    def on_leave(_):
        bg_label.configure(image=bg_label.image); set_row_bg(bg_color)
    def on_click(_):
        try: command()
        except Exception as e: print("Button error:", e)

    for wdg in (frame, bg_label, row, icon_lbl, txt_lbl):
        wdg.bind("<Enter>", on_enter); wdg.bind("<Leave>", on_leave)
        wdg.bind("<Button-1>", on_click); wdg.configure(cursor="hand2")

    return frame

# ---------- build figure (dynamic x,y + labels) ----------
def build_interactive_figure(x, y, *, x_label: str, y_label: str, series_label: str):
    """
    Nova-themed figure with hover dot + tooltip.
    This reproduces your demo's look, but uses provided data & labels.
    """
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)

    fig, ax = plt.subplots(figsize=(5.6, 3.3), dpi=120)

    # data line (legend label is dynamic)
    [line] = ax.plot(x_arr, y_arr, linewidth=2.4, color=ACC, label=series_label)

    # theming (EXACTLY like your demo)
    ax.set_xlabel(x_label, color=LBL, fontsize=11, fontweight="bold", labelpad=8)
    ax.set_ylabel(y_label, color=LBL, fontsize=11, fontweight="bold", labelpad=8)
    ax.set_facecolor(BG); fig.patch.set_facecolor(BG)
    ax.tick_params(colors=TICK)
    for s in ax.spines.values(): s.set_color(SPINE)
    ax.grid(True, color=GRID, linestyle="--", alpha=0.65)

    fig.subplots_adjust(top=0.85)
    leg = ax.legend(frameon=True, loc="upper center", bbox_to_anchor=(0.5, 1.21),
                    ncol=1, borderaxespad=0.0)
    leg.get_frame().set_facecolor(BG)
    leg.get_frame().set_edgecolor(SPINE)
    for txt in leg.get_texts(): txt.set_color(FG)

    plt.tight_layout()

    # --- hover UI bits (EXACTLY as in demo) ---
    dot, = ax.plot([], [], marker="o", markersize=6, color="#000000",
                   linestyle="None", zorder=6)
    ann = ax.annotate(
        "", xy=(0, 0), xytext=(10, 10), textcoords="offset points",
        fontsize=10, color=FG,
        bbox=dict(boxstyle="round,pad=0.25", fc=BG, ec=ACC, lw=1, alpha=0.95),
        annotation_clip=False,  # don't clip at axes edge
        zorder=7
    )
    ann.set_visible(False); dot.set_visible(False)

    # line hover styling
    hover_color = lighten_hex(ACC, 0.6)
    base_color  = ACC
    base_lw     = 2.4
    hover_lw    = base_lw + 0.8

    # how close to the curve to count as "on it"
    y_thresh = 0.12

    def adjust_annot_position(xd, yd):
        """Keep the annotation box fully visible by flipping its side near edges."""
        canvas = fig.canvas
        w, h = canvas.get_width_height()
        x_disp, y_disp = ax.transData.transform((xd, yd))

        # default offset & alignment
        ox, oy = 10, 10
        ha, va = 'left', 'bottom'

        # size of text box (after text set)
        renderer = canvas.get_renderer()
        bbox = ann.get_window_extent(renderer=renderer)
        bw, bh = bbox.width, bbox.height
        margin = 6  # a little breathing room

        # flip horizontally if it would overflow right/left
        if x_disp + ox + bw + margin > w:
            ha = 'right'; ox = -10
        elif x_disp - bw - margin < 0:
            ha = 'left'; ox = 10

        # flip vertically if it would overflow top/bottom
        if y_disp + oy + bh + margin > h:
            va = 'top'; oy = -10
        elif y_disp - bh - margin < 0:
            va = 'bottom'; oy = 10

        ann.set_ha(ha); ann.set_va(va)
        ann.set_position((ox, oy))

    def hide_marker_and_reset_line():
        changed = False
        if dot.get_visible(): dot.set_visible(False); changed = True
        if ann.get_visible(): ann.set_visible(False); changed = True
        if (line.get_color().lower() != base_color.lower()) or (line.get_linewidth() != base_lw):
            line.set_color(base_color); line.set_linewidth(base_lw); changed = True
        if changed: fig.canvas.draw_idle()

    def on_motion(event):
        if event.inaxes != ax or event.xdata is None or event.ydata is None:
            hide_marker_and_reset_line()
            return

        # snap to nearest plotted x sample
        idx = np.searchsorted(x_arr, event.xdata)
        idx = np.clip(idx, 0, len(x_arr) - 1)
        x0, y0 = float(x_arr[idx]), float(y_arr[idx])

        if abs(event.ydata - y0) <= y_thresh:
            # show black dot + label at the snapped sample
            dot.set_data([x0], [y0])
            dot.set_visible(True)

            ann.xy = (x0, y0)
            ann.set_text(f"({x0:.2f}, {y0:.2f})")
            ann.set_visible(True)

            # adjust label position to stay in-bounds
            adjust_annot_position(x0, y0)

            # brighten line only while near the curve
            line.set_color(hover_color)
            line.set_linewidth(hover_lw)
        else:
            hide_marker_and_reset_line()

        event.canvas.draw_idle()

    def on_enter_axes(_): pass
    def on_leave_axes(_): hide_marker_and_reset_line()

    callbacks = dict(on_motion=on_motion, on_enter_axes=on_enter_axes, on_leave_axes=on_leave_axes)
    return fig, callbacks

# ---------- Nova-styled preview window (Save / Close) ----------
def open_graph_preview(fig, callbacks, *, title_text: str = "Graph generated by Nova", suggested_name: str = "physics_graph"):
    """
    Opens the exact Nova-styled preview window you demoed, embeds the passed-in figure,
    wires hover callbacks, and returns the saved path (or None if closed).
    """
    # Choose Tk root or Toplevel
    try:
        win = tk.Toplevel()
    except tk.TclError:
        win = tk.Tk()
    win.title("Graph"); win.resizable(False, False); win.configure(bg=BG); win.grab_set()

    W, H = 860, 560
    star_img = make_starry_bg(W, H)
    bg = tk.Label(win, image=star_img); bg.image = star_img
    bg.place(x=0, y=0, relwidth=1, relheight=1)

    container = tk.Frame(win, bg=BG, highlightthickness=1, highlightbackground=FRAME)
    container.pack(padx=14, pady=12)

    # Header (logo optional, name beside logo from title_text)
    header = tk.Frame(container, bg=BG); header.pack(fill="x", padx=14, pady=(12, 6))
    logo_path = os.path.join(ASSETS_DIR, "nova_face.png")
    if os.path.exists(logo_path):
        logo_img = Image.open(logo_path).resize((26, 26), Image.LANCZOS)
        logo_photo = ImageTk.PhotoImage(logo_img)
        tk.Label(header, image=logo_photo, bg=BG).pack(side="left"); header.logo = logo_photo
    else:
        tk.Label(header, text="◈", bg=BG, fg=ACC, font=("Consolas", 16, "bold")).pack(side="left")
    tk.Label(header, text=title_text, bg=BG, fg=ACC, font=("Consolas", 13, "bold")).pack(side="left", padx=(8, 0))

    # Embed live Matplotlib figure
    canvas = FigureCanvasTkAgg(fig, master=container)
    graph_widget = canvas.get_tk_widget()
    graph_widget.configure(bg=BG, highlightthickness=0)
    graph_widget.pack(padx=14, pady=(4, 8))
    canvas.draw()

    # Connect hover callbacks
    if callbacks:
        canvas.mpl_connect("motion_notify_event", callbacks["on_motion"])
        canvas.mpl_connect("axes_enter_event",   callbacks["on_enter_axes"])
        canvas.mpl_connect("axes_leave_event",   callbacks["on_leave_axes"])

    # Buttons row
    btn_row = tk.Frame(container, bg=BG); btn_row.pack(fill="x", padx=14, pady=(2, 12))
    saved = {"path": None}

    def save_graph():
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")],
            initialfile=f"{suggested_name}.png",
            title="Save Graph As..."
        )
        if file_path:
            fig.savefig(file_path, facecolor=BG, bbox_inches="tight")
            saved["path"] = file_path
            win.destroy()

    def close_preview(): win.destroy()
    win.protocol("WM_DELETE_WINDOW", close_preview)

    right = tk.Frame(btn_row, bg=BG); right.pack(side="right")
    rounded_button(right, text="Save",  bg_color=ACC,      fg_color="#001010",
                   icon_kind="arrow", command=save_graph,  w=120, h=34).pack(side="left")
    tk.Frame(right, width=12, bg=BG).pack(side="left")
    rounded_button(right, text="Close", bg_color="#000000", fg_color="#ffffff",
                   icon_kind="close", command=close_preview, w=120, h=38).pack(side="left")

    # center + run
    win.geometry(f"{W}x{H}")
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{W}x{H}+{(sw//2)-(W//2)}+{(sh//2)-(H//2)}")
    win.mainloop()
    plt.close(fig)
    return saved["path"]
