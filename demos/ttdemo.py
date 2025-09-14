# demo_upload_popup.py
from __future__ import annotations
import math, random, os
import tkinter as tk

# Optional: Nova logo (pip install pillow)
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except Exception:
    HAS_PIL = False

ASSET_CANDIDATES = [
    os.path.join("assets", "nova_face_glow.png"),
    "nova_face_glow.png",
]

def _center_geometry(win: tk.Toplevel | tk.Tk, w: int, h: int) -> str:
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    return f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}"

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = [max(0, min(255, int(v))) for v in rgb]
    return f"#{r:02x}{g:02x}{b:02x}"

def _blend(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex((r1+(r2-r1)*t, g1+(g2-g1)*t, b1+(b2-b1)*t))

def show_uploading_dialog(
    text: str = "Uploading image…",
    *,
    auto_close_ms: int = 3000,
    use_system_border: bool = False,
    title: str = "Nova — Uploading",
    pulse_speed_ms: int = 20,          # how fast the fade animates
    dim_color: str = "#a1a6ff",        # fade range (dim → bright)
    bright_color: str = "#ffffff",
):
    """
    Nova-style uploading popup:
      • Optional OS titlebar/border (use_system_border=True) or borderless overlay
      • Centered; deep-violet canvas; drifting stars; orbiting Nova logo (or vector fallback)
      • Pulsing status text to convey activity
      • Returns a close() function you must call when the upload finishes
    """
    root = tk.Tk()
    root.withdraw()

    popup = tk.Toplevel(root)
    popup.withdraw()  # prevent flash

    if use_system_border:
        popup.overrideredirect(False)
        popup.title(title)
        popup.resizable(False, False)
    else:
        popup.overrideredirect(True)

    try: popup.attributes("-topmost", True)
    except Exception: pass

    WIDTH, HEIGHT = 420, 300
    popup.geometry(_center_geometry(popup, WIDTH, HEIGHT))

    # ESC to close
    popup.bind("<Escape>", lambda e: popup.destroy())

    # Canvas background
    canvas = tk.Canvas(popup, width=WIDTH, height=HEIGHT, bg="#1a103d",
                       highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)

    # Star layers (parallax)
    star_layers = {1: [], 2: [], 3: []}
    rng = random.Random(42)
    for layer in star_layers:
        count = 22 if layer == 1 else 14
        for _ in range(count):
            sx = rng.randint(0, WIDTH); sy = rng.randint(0, HEIGHT)
            size = layer  # 1px, 2px, 3px
            star = canvas.create_oval(sx, sy, sx+size, sy+size, fill="#c9cfff", outline="")
            star_layers[layer].append(star)

    closing = [False]
    after_handles = {"stars": None, "orbit": None, "pulse": None}

    def _safe_after(ms, fn):
        if closing[0] or not popup.winfo_exists(): return None
        return popup.after(ms, fn)

    def animate_stars():
        if closing[0] or not popup.winfo_exists(): return
        for layer, stars in star_layers.items():
            dx = 0.2 * layer
            for s in stars:
                canvas.move(s, dx, 0)
                x0, _, x1, _ = canvas.coords(s)
                if x0 > WIDTH:
                    canvas.move(s, -WIDTH - (x1 - x0), 0)
        after_handles["stars"] = _safe_after(50, animate_stars)

    after_handles["stars"] = _safe_after(50, animate_stars)

    # Nova logo (image if available, vector fallback otherwise)
    logo_id = None
    angle = 0
    radius = 10
    cx, cy = WIDTH // 2, 84

    img_tk = None
    if HAS_PIL:
        for candidate in ASSET_CANDIDATES:
            if os.path.exists(candidate):
                try:
                    from PIL import Image
                    img = Image.open(candidate).resize((80, 80))
                    img_tk = ImageTk.PhotoImage(img)
                    break
                except Exception:
                    img_tk = None
    if img_tk:
        logo_id = canvas.create_image(cx, cy, image=img_tk)
    else:
        glow = canvas.create_oval(cx-42, cy-42, cx+42, cy+42, fill="#6a5acd", outline="")
        ring = canvas.create_oval(cx-48, cy-48, cx+48, cy+48, outline="#9b8fff")
        label = canvas.create_text(cx, cy, text="N", fill="#e9e7ff",
                                   font=("Segoe UI", 28, "bold"))
        logo_id = glow  # move the glow; ring + label stay

    def orbit():
        nonlocal angle
        if closing[0] or not popup.winfo_exists(): return
        angle = (angle + 2) % 360
        rad = math.radians(angle)
        ox = cx + radius * math.cos(rad)
        oy = cy + radius * math.sin(rad)
        if img_tk:
            canvas.coords(logo_id, ox, oy)
        else:
            x0, y0, x1, y1 = canvas.coords(logo_id)
            cx_now = (x0 + x1) / 2
            cy_now = (y0 + y1) / 2
            canvas.move(logo_id, ox - cx_now, oy - cy_now)
        after_handles["orbit"] = _safe_after(50, orbit)

    after_handles["orbit"] = _safe_after(50, orbit)

    # Status text (with pulse effect)
    title_id = canvas.create_text(WIDTH // 2, HEIGHT // 2 + 20,
                                  text=text, fill=dim_color,
                                  font=("Segoe UI", 12, "bold"))

    phase = [0.0]
    def pulse_text():
        if closing[0] or not popup.winfo_exists(): return
        # sine wave 0..1
        phase[0] += 0.12
        t = (math.sin(phase[0]) + 1.0) / 2.0
        fill = _blend(dim_color, bright_color, t)
        canvas.itemconfigure(title_id, fill=fill)
        after_handles["pulse"] = _safe_after(pulse_speed_ms, pulse_text)

    after_handles["pulse"] = _safe_after(pulse_speed_ms, pulse_text)

    # Reveal after layout (no flicker), then relax topmost
    popup.deiconify()
    popup.lift()
    try: popup.after(200, lambda: popup.attributes("-topmost", False))
    except Exception: pass

    def close():
        closing[0] = True
        try:
            for k in list(after_handles.keys()):
                if after_handles[k]:
                    popup.after_cancel(after_handles[k])
        except Exception:
            pass
        try:
            popup.destroy()
            root.destroy()
        except Exception:
            pass

    if auto_close_ms and auto_close_ms > 0:
        popup.after(auto_close_ms, close)

    return close

if __name__ == "__main__":
    # Demo: visible borders + keep open so you can inspect it. Press Esc to close.
    show_uploading_dialog(
        "Uploading image…",
        auto_close_ms=0,
        use_system_border=True,
        title="Nova — Uploading"
    )
    tk.mainloop()


