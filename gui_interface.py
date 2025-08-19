# gui_interface.py — Nova main UI
# (starry background + smoother logo + never-under-taskbar + mic click-to-talk)
# + ghost scrollbar (hidden until edge-hover) + no-flicker reveal

import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import font as tkfont
from PIL import Image, ImageTk  # ← needed for starfield + logo images
import os, math, time, ctypes, threading  # threading for push-to-talk

# ✅ Single source of truth for app resources / callbacks
from utils import resource_path, set_gui_callback

# ✅ Reuse the exact starfield used by your graph preview
try:
    from handlers.nova_graph_ui import make_starry_bg, BG as STAR_BG
except Exception:
    STAR_BG = "#0f0f0f"
    def make_starry_bg(w, h):
        img = Image.new("RGB", (w, h), STAR_BG)
        return ImageTk.PhotoImage(img)

# 🌈 Language → glow color
LANG_GLOW_COLORS = {
    "en": "#00ffcc", "hi": "#ff9933", "fr": "#3399ff",
    "de": "#66cc66", "es": "#ff6666",
}

# ---------- Windows work-area helpers (per-monitor; excludes taskbar) ----------
def _win_work_area_for_window(hwnd) -> tuple[int,int,int,int] | None:
    """Return (L,T,R,B) of the *work area* for the monitor where hwnd is, or None."""
    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        MONITOR_DEFAULTTONEAREST = 2

        class RECT(ctypes.Structure):
            _fields_ = (('left', ctypes.c_long), ('top', ctypes.c_long),
                        ('right', ctypes.c_long), ('bottom', ctypes.c_long))

        class MONITORINFO(ctypes.Structure):
            _fields_ = (('cbSize', ctypes.c_ulong),
                        ('rcMonitor', RECT),
                        ('rcWork', RECT),
                        ('dwFlags', ctypes.c_ulong))

        MonitorFromWindow = user32.MonitorFromWindow
        GetMonitorInfoW   = user32.GetMonitorInfoW

        hmon = MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        if not hmon:
            return None
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        ok = GetMonitorInfoW(hmon, ctypes.byref(mi))
        if not ok:
            return None
        wa = mi.rcWork
        return wa.left, wa.top, wa.right, wa.bottom
    except Exception:
        return None

def _windows_work_area_for_root(root) -> tuple[int,int,int,int] | None:
    try:
        hwnd = root.winfo_id()
        return _win_work_area_for_window(hwnd)
    except Exception:
        return None

def position_main_window(root, w=820, h=680, upward_bias=120, min_top=24, safe_bottom=120):
    """
    Center inside the current monitor's WORK AREA (excludes taskbar),
    then nudge upward; finally clamp so bottom stays above the taskbar.
    """
    root.update_idletasks()

    wa = _windows_work_area_for_root(root)
    if wa:
        l, t, r, b = wa
        sw, sh = (r - l), (b - t)
        x = l + max(0, (sw - w) // 2)
        y = t + max(min_top, (sh - h) // 2 - upward_bias)
        # clamp so bottom is above taskbar by safe_bottom px
        y = min(y, b - h - safe_bottom)
        y = max(t + min_top, y)
        root.geometry(f"{w}x{h}+{x}+{y}")
        return

    # Fallback (non-Windows): center with a bottom margin
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    x = max(0, (sw - w) // 2)
    y = max(min_top, (sh - h) // 2 - upward_bias)
    y = min(y, max(0, sh - h - safe_bottom))
    root.geometry(f"{w}x{h}+{x}+{y}")

# ✅ precise upper-center placer with a second pass (never under taskbar)
def _place_main_window_safely(root: tk.Tk, y_percent: float = 0.26, bottom_margin: int = 64, _second_pass: bool = False):
    try:
        root.update_idletasks()
        wa = _windows_work_area_for_root(root)
        if not wa:
            raise RuntimeError("no work area")
        l, t, r, b = wa
        w = root.winfo_width()
        h = root.winfo_height()
        work_w, work_h = (r - l), (b - t)
        x = l + (work_w - w) // 2
        y = t + int(work_h * y_percent)
        y = max(t, min(y, b - bottom_margin - h))  # clamp
        root.geometry(f"+{x}+{y}")
        if not _second_pass:
            root.after(220, lambda: _place_main_window_safely(root, y_percent, bottom_margin, True))
    except Exception:
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = root.winfo_width(), root.winfo_height()
        x = (sw - w) // 2
        y = max(0, (sh - h) // 2 - 120)
        root.geometry(f"+{x}+{y}")
        if not _second_pass:
            root.after(220, lambda: _place_main_window_safely(root, y_percent, bottom_margin, True))

class Tooltip:
    def __init__(self, widget, text='Tooltip'):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show_tooltip)
        widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tip_window or not self.text:
            return
        try:
            x, y, _, _ = self.widget.bbox("insert")
        except Exception:
            x = y = 0
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 10
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw, text=self.text, justify='left',
            background="#333333", foreground="white",
            relief='solid', borderwidth=1, font=("Consolas", 9)
        ).pack(ipadx=4, ipady=2)

    def hide_tooltip(self, event=None):
        try:
            if self.tip_window and self.tip_window.winfo_exists():
                self.tip_window.destroy()
        except Exception:
            pass
        finally:
            self.tip_window = None

# -----------------------------  Nova Solution popup -----------------------------
POP_BG        = "#0f0f0f"
POP_CARD_BG   = "#131313"
POP_TEXT_FG   = "#e8e8e8"
POP_SOFT_FG   = "#b4b4b4"
POP_DIVIDER   = "#dcdcdc"
POP_ACCENT    = "#ffd166"
POP_DIV_CHAR  = "━"

NOVA_PRIMARY_BG = "#00ffee"
NOVA_PRIMARY_FG = "#0f0f0f"
NOVA_PRIMARY_BG_HOVER = "#00d5d5"
NOVA_GHOST_BG = "#202020"
NOVA_GHOST_FG = "#00ffee"
NOVA_GHOST_BG_HOVER = "#2a2a2a"
NOVA_GHOST_FG_HOVER = "#a7fff9"

class _SolutionPopup(tk.Toplevel):
    class _NovaBadge(tk.Canvas):
        def __init__(self, master, size=42, accent=POP_ACCENT,
                     fade_strength=0.80, face_bleach=0.28,
                     orbit_speed=0.55, precess_speed=0.035,
                     ellipticity=0.88, swell_strength=0.06,
                     shimmer_strength=0.06, **kw):
            super().__init__(master, width=size, height=size, bg=POP_BG, highlightthickness=0, **kw)
            self.size=size; self.accent=accent; self.cx=self.cy=size//2
            self.fade_strength=fade_strength; self.face_bleach=face_bleach
            self.orbit_speed=orbit_speed; self.precess_speed=precess_speed
            self.ellipticity=ellipticity; self.swell_strength=swell_strength
            self.shimmer_strength=shimmer_strength
            self._pulse_phase=0.0; self._precess=0.0
            self._pil_base=None
            try:
                pil = Image.open(resource_path(os.path.join("assets","nova_face.png"))).convert("RGBA")
                target_h=int(size*0.78); r=target_h/pil.height
                self._pil_base=pil.resize((int(pil.width*r), target_h), Image.LANCZOS)
            except Exception:
                pass
            self._white_img = Image.new("RGBA", self._pil_base.size, (255,255,255,255)) if self._pil_base else None
            self.halo_id=self.create_oval(0,0,0,0, outline=self.accent, width=2); self.itemconfig(self.halo_id, fill="")
            self.N=6; self.base_orbit_r=(size/2)-6; self.stars_a=[]; self.stars_b=[]
            for i in range(self.N):
                pa=self.create_polygon(0,0,0,0,0,0,0,0, fill=self.accent, outline=self.accent, width=1)
                pb=self.create_polygon(0,0,0,0,0,0,0,0, fill=self.accent, outline=self.accent, width=1)
                phase=i*(2*math.pi/self.N)
                self.stars_a.append({"poly":pa,"phase":phase})
                self.stars_b.append({"poly":pb,"phase":phase})
            self.img_id=None; self._img_tk=None
            if self._pil_base:
                self._set_face_tint(0.0)
                self.img_id=self.create_image(self.cx,self.cy,image=self._img_tk)
                self.tag_raise(self.img_id)
            self._fps_ms=16
            self.after(self._fps_ms, self._animate)

        @staticmethod
        def _mix_to_white(hx, frac):
            r=int(hx[1:3],16); g=int(hx[3:5],16); b=int(hx[5:7],16)
            r=int(r+(255-r)*frac); g=int(g+(255-g)*frac); b=int(b+(255-b)*frac)
            return f"#{r:02x}{g:02x}{b:02x}"

        def _star_points(self, cx, cy, r_out, r_in, angle_offset=0.0):
            pts=[]
            for k in range(8):
                ang=angle_offset+k*(math.pi/4.0)
                r=r_out if (k%2==0) else r_in
                pts.extend([cx+r*math.cos(ang), cy+r*math.sin(ang)])
            return pts

        def _set_face_tint(self, bleach_frac: float):
            if not (self._pil_base and self._white_img): return
            pil=Image.blend(self._pil_base, self._white_img,
                            max(0.0,min(1.0,bleach_frac))*self.face_bleach)
            self._img_tk=ImageTk.PhotoImage(pil)
            if self.img_id:
                self.itemconfig(self.img_id, image=self._img_tk)

        def _animate(self):
            self._pulse_phase=(self._pulse_phase+0.12)%(2*math.pi)
            self._precess=(self._precess+self.precess_speed)%(2*math.pi)
            luma=0.5+0.5*math.sin(self._pulse_phase)
            p=self.fade_strength*luma
            base_color=self._mix_to_white(self.accent,p)
            halo_r=(self.size*0.42)
            self.coords(self.halo_id, self.cx-halo_r, self.cy-halo_r, self.cx+halo_r, self.cy+halo_r)
            self.itemconfig(self.halo_id, outline=base_color, width=2)
            R0=self.base_orbit_r
            Rx=R0*(1.00+0.06*math.sin(self._pulse_phase))
            Ry=R0*(0.88+0.06*math.cos(self._pulse_phase))
            t=self._pulse_phase*self.orbit_speed; size_scale=1.0+0.06*(2.0*luma-1.0)
            angle_offset=math.pi/8.0
            def draw_swarm(stars, base_tilt, sign):
                tilt=base_tilt+self._precess; ct,st=math.cos(tilt),math.sin(tilt)
                for s in stars:
                    theta=sign*t+s["phase"]
                    x=Rx*math.cos(theta); y=Ry*math.sin(theta)
                    xr=x*ct - y*st; yr=x*st + y*ct
                    cx,cy=(self.cx+xr,self.cy+yr)
                    r_out=2.4*size_scale; r_in=r_out*0.52
                    self.coords(s["poly"], *self._star_points(cx,cy,r_out,r_in,angle_offset))
                    self.itemconfig(s["poly"], fill=base_color, outline=base_color)
            draw_swarm(self.stars_a, base_tilt= math.pi/4.0,  sign=+1.0)
            draw_swarm(self.stars_b, base_tilt=-math.pi/4.0,  sign=-1.0)
            self._set_face_tint(p)
            self.after(self._fps_ms, self._animate)

    def __init__(self, master, mode="Physics", emoji="⚛️", first_answer="", **kw):
        super().__init__(master, **kw)
        self.title("Solution")
        self.configure(bg=POP_BG)
        self.geometry("920x660+180+120")
        self.minsize(680, 480)
        self.mode = mode; self.emoji = emoji; self.accent = POP_ACCENT
        self._build_header(); self._build_body()
        self._build_action_bar(); self._build_footer_actions()
        self.start_new_solution_block(first_answer or "...")
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-s>", lambda e: self._save_txt())
        self.bind("<Command-s>", lambda e: self._save_txt())
        self.bind("<Control-c>", lambda e: self._copy_all())
        self.bind("<Command-c>", lambda e: self._copy_all())
    # (popup internals unchanged)

# ✅ Tiny helper for logo sparkles (4-point star polygon)
def _star_points(cx, cy, r_out, r_in, points=4, angle_offset=0.0):
    pts = []
    for k in range(points * 2):
        ang = angle_offset + k * (math.pi / points)
        r = r_out if (k % 2 == 0) else r_in
        pts.extend([cx + r * math.cos(ang), cy + r * math.sin(ang)])
    return pts

# ----------------------------- Starry “Ghost” Scrollbar -----------------------------
class GhostScrollbar(tk.Canvas):
    """A custom canvas-based vertical scrollbar that:
       • stays hidden until the cursor nears the right edge or over the bar
       • matches the starry theme
       • pill thumb: black fill with outline in current language glow color
       • supports Up/Down arrow keys to scroll (thumb visible while moving)
    """
    def __init__(self, master, accent="#00ffcc", width=10, **kw):
        super().__init__(master, width=width, highlightthickness=0, bd=0, bg=STAR_BG, **kw)
        self.accent = accent
        self._text = None
        self._first = 0.0
        self._last  = 1.0
        self._thumb_id = None
        self._dragging = False
        self._drag_offset = 0.0
        self._hide_after_id = None
        self._visible = False
        self._min_thumb_px = 28
        self._hover_zone_px = 28
        self._track_color = "#151515"  # subtle track to fit dark theme
        self._thumb_fill  = "#000000"  # ← black fill, as you wanted

        # drawing & interactions
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Enter>", self._show_now)
        self.bind("<Leave>", self._schedule_hide)
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>", self._maybe_hover)

    # Attach to a Text widget
    def attach(self, text_widget: tk.Text):
        self._text = text_widget
        text_widget.configure(yscrollcommand=self.on_textscroll)
        # show on wheel
        text_widget.bind("<MouseWheel>", lambda e: (self._show_now(e), self._wheel(e)), add="+")
        # reveal when cursor approaches right edge
        text_widget.bind("<Motion>", self._edge_probe, add="+")
        # Up/Down arrow keys also scroll & reveal
        text_widget.bind_all("<Up>", self._on_arrow, add="+")
        text_widget.bind_all("<Down>", self._on_arrow, add="+")
        self._redraw()

    # yscrollcommand from Text → update fractions and redraw
    def on_textscroll(self, first, last):
        try:
            self._first = float(first)
            self._last  = float(last)
        except Exception:
            self._first, self._last = 0.0, 1.0
        self._redraw()
        # Hide entirely if everything fits
        if self._first <= 0.0001 and self._last >= 0.9999:
            self._hide_now()
        else:
            self._show_now()
        return

    # pill thumb helper: center rectangle + two rounded caps
    def _draw_pill(self, x0, y0, x1, y1, fill, outline, width=1):
        try:
            r = int(min(x1 - x0, y1 - y0) // 2)
            body = self.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, outline=outline, width=width)
            self.create_oval(x0, y0, x0 + 2*r, y0 + 2*r, fill=fill, outline=outline, width=width)
            self.create_oval(x1 - 2*r, y1 - 2*r, x1, y1, fill=fill, outline=outline, width=width)
            return body
        except Exception:
            return self.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=width)

    # Text wheel → forward to yview
    def _wheel(self, evt):
        if not self._text: return
        delta_lines = -1 * (evt.delta // 120)
        self._text.yview_scroll(delta_lines, "units")
        self._show_now()

    # If cursor near right inside edge of text area, reveal the bar
    def _edge_probe(self, evt):
        try:
            w = evt.widget.winfo_width()
            if evt.x >= max(0, w - self._hover_zone_px):
                self._show_now()
            else:
                self._schedule_hide()
        except Exception:
            pass

    # Keyboard arrows: scroll & reveal
    def _on_arrow(self, evt):
        if not self._text: return
        try:
            if evt.keysym == "Up":
                self._text.yview_scroll(-3, "units")
            elif evt.keysym == "Down":
                self._text.yview_scroll(3, "units")
            else:
                return
            self._show_now()
            self._schedule_hide()
        except Exception:
            pass

    def _show_now(self, _evt=None):
        if not self._visible:
            self.grid()  # ensure it's gridded
            self._visible = True
        # cancel pending hide
        if self._hide_after_id:
            try: self.after_cancel(self._hide_after_id)
            except Exception: pass
            self._hide_after_id = None
        self._redraw()

    def _schedule_hide(self, _evt=None):
        if self._dragging: return
        if self._hide_after_id:
            try: self.after_cancel(self._hide_after_id)
            except Exception: pass
        self._hide_after_id = self.after(700, self._hide_now)

    def _hide_now(self):
        if self._dragging: return
        if self._visible:
            self.grid_remove()
            self._visible = False

    def _thumb_rect(self):
        H = max(1, self.winfo_height())
        top = int(H * self._first)
        bot = int(H * self._last)
        if bot - top < self._min_thumb_px:
            mid = (top + bot) // 2
            top = max(0, mid - self._min_thumb_px // 2)
            bot = min(H, top + self._min_thumb_px)
        # small insets
        x0, x1 = 2, max(2, self.winfo_width() - 2)
        return x0, top, x1, bot

    def _redraw(self):
        self.delete("all")
        w = self.winfo_width(); h = self.winfo_height()
        # track
        self.create_rectangle(0, 0, w, h, fill=STAR_BG, outline="")
        self.create_rectangle(2, 2, w - 2, h - 2, fill=self._track_color, outline="")
        # thumb only if scrollable
        if self._last - self._first >= 0.9999:
            return
        x0, y0, x1, y1 = self._thumb_rect()
        # slight inset for neat edges
        x0 += 1; x1 -= 1
        self._thumb_id = self._draw_pill(x0, y0, x1, y1, fill=self._thumb_fill, outline=self.accent, width=1)

    # Mouse interactions
    def _on_click(self, evt):
        if not self._text: return
        self._dragging = True
        _, y0, _, y1 = self._thumb_rect()
        self._drag_offset = evt.y - y0 if (y0 <= evt.y <= y1) else (self._min_thumb_px // 2)
        self._jump_to(evt.y)
        self._show_now()

    def _on_drag(self, evt):
        if not self._dragging or not self._text: return
        self._jump_to(evt.y)

    def _on_release(self, _evt):
        self._dragging = False
        self._schedule_hide()

    def _jump_to(self, y):
        h = max(1, self.winfo_height() - self._min_thumb_px)
        frac = max(0.0, min(1.0, (y - self._drag_offset) / h))
        try:
            self._text.yview_moveto(frac)
        except Exception:
            pass

    # allow external accent update
    def set_accent(self, accent_hex: str):
        self.accent = accent_hex or self.accent
        try:
            if self._thumb_id:
                self.itemconfig(self._thumb_id, outline=self.accent)
        except Exception:
            pass

    def _maybe_hover(self, evt):
        # keep visible while hovering over bar area
        self._show_now()
        self._schedule_hide()

# ----------------------------- Main GUI -----------------------------
class NovaGUI:
    def __init__(self):
        from utils import selected_language, get_wake_mode
        self.language = selected_language
        self.glow_color = LANG_GLOW_COLORS.get(self.language, "#00ffcc")

        # 🔔 Animation gate for main.py
        self.animation_ready = False
        self._anim_started_frames = 0

        # Build hidden, then show with no flicker
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("NOVA - AI Assistant")

        # Wider so pills never clip
        W, H = 820, 680
        self.root.geometry(f"{W}x{H}")
        position_main_window(self.root, W, H)  # compute final position BEFORE showing
        self.root.configure(bg=STAR_BG)
        self.root.resizable(False, False)

        # Starry background
        self._bg_img = make_starry_bg(W, H)
        self._bg_label = tk.Label(self.root, image=self._bg_img, bd=0)
        self._bg_label.image = self._bg_img
        self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg_label.lower()
        # keep a PIL copy of the big starfield for exact crops
        self._bg_pil = ImageTk.getimage(self._bg_img).copy()

        # --- Logo + sparkles (smoother) ---
        self.logo_canvas = tk.Canvas(self.root, width=160, height=160, bg=STAR_BG, highlightthickness=0, bd=0)
        self.logo_canvas.pack(pady=(6, 2))
        # background image item we will fill with an exact crop
        self.logo_bg_item = self.logo_canvas.create_image(0, 0, anchor="nw")

        try:
            image_path = resource_path(os.path.join("assets", "nova_face_glow.png"))
            if not os.path.exists(image_path):
                image_path = resource_path(os.path.join("assets", "nova_face.png"))
            image = Image.open(image_path).resize((120, 120), Image.LANCZOS)
            self.nova_photo = ImageTk.PhotoImage(image)
        except Exception:
            fallback = Image.new("RGBA", (120,120), (0,0,0,0))
            self.nova_photo = ImageTk.PhotoImage(fallback)

        self.face_center = (80, 80)
        self.face_orbit_r = 10
        self.face_angle = 0.0
        self.face_id = self.logo_canvas.create_image(*self.face_center, image=self.nova_photo)

        # Starry sparkles (4-point stars) instead of dots
        self.sparkles = []
        self.sparkle_angle = 0.0
        self.sparkle_r = 62
        for _ in range(6):
            s = self.logo_canvas.create_polygon(
                0, 0, 0, 0, 0, 0, 0, 0,
                fill=self.glow_color, outline=self.glow_color, width=1
            )
            self.sparkles.append(s)

        self._last_anim_t = time.perf_counter()
        self._animate_logo_and_sparkles()

        # Status pills
        self.status_bar = tk.Frame(self.root, bg=STAR_BG)
        self.status_bar.pack(pady=(0, 6), fill="x")
        self._build_mode_status_bar()

        # --- Chat area with custom “ghost” scrollbar (no mid-word splits) ---
        chat_wrap = tk.Frame(self.root, bg=STAR_BG)
        chat_wrap.pack(padx=10, pady=5, fill="x")

        self.text_display = tk.Text(
            chat_wrap, height=18, width=86, bg="#111116",
            fg=self.glow_color, font=("Consolas", 10), bd=0,
            wrap="word"
        )

        # Starry Ghost scrollbar (hidden until edge-hover)
        self.ghost_scroll = GhostScrollbar(chat_wrap, accent=self.glow_color, width=10)
        # grid layout: text in col 0, ghost bar in col 1
        self.text_display.grid(row=0, column=0, sticky="nsew")
        self.ghost_scroll.grid(row=0, column=1, sticky="ns")  # will hide itself when not needed
        chat_wrap.grid_columnconfigure(0, weight=1)
        chat_wrap.grid_rowconfigure(0, weight=1)

        # tie text ↔ scrollbar
        self.ghost_scroll.attach(self.text_display)

        # Mouse wheel (extra binding in case focus elsewhere)
        def _on_mousewheel(evt):
            self.text_display.yview_scroll(-1 * (evt.delta // 120), "units")
            self.ghost_scroll._show_now()
        self.text_display.bind("<Enter>", lambda e: self.text_display.bind_all("<MouseWheel>", _on_mousewheel))
        self.text_display.bind("<Leave>", lambda e: self.text_display.unbind_all("<MouseWheel>"))

        # Typing hint
        self.typing_label = tk.Label(self.root, font=("Consolas", 9), bg=STAR_BG, fg="gray")
        self.typing_label.pack()

        # Input
        self.input_entry = tk.Entry(self.root, width=60, font=("Consolas", 11))
        self.input_entry.pack(pady=8)

        # Mode toggles (glow ovals sized to text)
        self.math_mode_var = tk.BooleanVar()
        self.plot_mode_var = tk.BooleanVar()
        self.physics_mode_var = tk.BooleanVar()
        self.chemistry_mode_var = tk.BooleanVar()

        self.checkbox_canvas = tk.Canvas(self.root, width=W-20, height=44, bg=STAR_BG, highlightthickness=0)
        self.checkbox_canvas.pack(pady=(0, 10))

        cb_font = tkfont.Font(family="Consolas", size=11, weight="bold")
        labels = [
            ("🧠 Math Mode",    self.math_mode_var),
            ("📈 Plot Mode",    self.plot_mode_var),
            ("⚛️ Physics Mode", self.physics_mode_var),
            ("🧪 Chemistry Mode", self.chemistry_mode_var),
        ]
        CW = W - 20
        centers = [int(CW*(1/8)), int(CW*(3/8)), int(CW*(5/8)), int(CW*(7/8))]
        y = 22

        self._glow_ids = []
        self._cb_widgets = []
        for i, (text, var) in enumerate(labels):
            tw = cb_font.measure(text)
            pad_x = 26
            half = (tw + pad_x) // 2
            glow = self.checkbox_canvas.create_oval(centers[i]-half, y-12, centers[i]+half, y+12,
                                                    fill=self.glow_color, outline="", stipple="gray25")
            self._glow_ids.append(glow)
            cb = tk.Checkbutton(
                self.checkbox_canvas, text=text, variable=var,
                bg=STAR_BG, fg=self.glow_color,
                activebackground=STAR_BG, activeforeground=self.glow_color,
                selectcolor="#15151a", font=("Consolas", 11, "bold"),
                highlightthickness=0, bd=0
            )
            self.checkbox_canvas.create_window(centers[i], y, window=cb)
            self._cb_widgets.append(cb)

        self.math_checkbox, self.plot_checkbox, self.physics_checkbox, self.chemistry_checkbox = self._cb_widgets

        Tooltip(self.math_checkbox,"Enable this to type math directly. Like: integrate(x^2, x)")
        Tooltip(self.plot_checkbox,"Use this to graph equations or data, e.g. y=x^2 or x=[1,2], y=[3,4]")
        Tooltip(self.physics_checkbox,"Solve physics with units (v = u + a*t, etc.)")
        Tooltip(self.chemistry_checkbox,"Chemistry: molar mass, pH/pOH, stoichiometry, gas laws, dilution…")

        self._pulse_checkbox_glow()

        def _sync_modes_to_utils(*_):
            self._update_status_pills()
            try:
                from utils import set_mode_state
                set_mode_state("math", self.math_mode_var.get())
                set_mode_state("plot", self.plot_mode_var.get())
                set_mode_state("physics", self.physics_mode_var.get())
                set_mode_state("chemistry", self.chemistry_mode_var.get())
            except Exception:
                pass
        for var in (self.math_mode_var, self.plot_mode_var, self.physics_mode_var, self.chemistry_mode_var):
            var.trace_add("write", lambda *_: _sync_modes_to_utils())
        _sync_modes_to_utils()

        # Buttons (keep your original tk.Button)
        button_frame = tk.Frame(self.root, bg=STAR_BG); button_frame.pack()
        self.send_button  = tk.Button(button_frame, text="Send",  command=self._on_send, width=12,
                                      bg="#202033", fg="white", relief="flat", bd=0, highlightthickness=0,
                                      activebackground="#202033", activeforeground="white")
        self.clear_button = tk.Button(button_frame, text="Clear", command=self._on_clear, width=12,
                                      bg="#202033", fg="white", relief="flat", bd=0, highlightthickness=0,
                                      activebackground="#202033", activeforeground="white")
        self.send_button.grid(row=0, column=0, padx=6)
        self.clear_button.grid(row=0, column=1, padx=6)

        # Mic + wake label
        try:
            mic_on_path  = resource_path(os.path.join("assets", "mic_on.png"))
            mic_off_path = resource_path(os.path.join("assets", "mic_off.png"))
            self.mic_on_img  = ImageTk.PhotoImage(Image.open(mic_on_path).resize((20, 20)))
            self.mic_off_img = ImageTk.PhotoImage(Image.open(mic_off_path).resize((20, 20)))
        except Exception:
            img = Image.new("RGB", (20, 20), "gray")
            self.mic_on_img = self.mic_off_img = ImageTk.PhotoImage(img)

        self.mic_canvas = tk.Canvas(self.root, width=40, height=40, bg=STAR_BG, highlightthickness=0, cursor="hand2")
        self.mic_canvas.pack(pady=2)
        # background image item filled with an exact crop
        self.mic_bg_item = self.mic_canvas.create_image(0, 0, anchor="nw")
        self.mic_img_obj = self.mic_canvas.create_image(20, 20, image=self.mic_off_img)

        self.pulse_radius = 22
        self.pulse_circle = None
        self.pulse_growing = True
        self.hover_circle = None
        self.glow_active = False
        self.mic_canvas.bind("<Enter>", self._start_hover_glow)
        self.mic_canvas.bind("<Leave>", self._stop_hover_glow)
        self.mic_canvas.bind("<Button-1>", self._on_mic_click)   # ← CLICK TO TALK (Wake OFF)
        self.mic_tooltip = Tooltip(self.mic_canvas, text="Click the mic to talk 🎤")

        from utils import get_wake_mode
        self.wake_status = tk.StringVar()
        _mode = get_wake_mode()
        _is_on = _mode in ("on", "always_on")
        self.wake_status.set("Wake Mode: ON" if _is_on else "Wake Mode: OFF")

        # Your original comfy button — now bigger
        self.wake_button = tk.Button(
            self.root, textvariable=self.wake_status,
            command=self._toggle_wake_mode,
            bg="#10131a", fg=self.glow_color,
            activebackground="#10131a", activeforeground=self.glow_color,
            relief="flat", bd=0, highlightthickness=0,
            font=("Consolas", 12, "bold"),
            width=24, padx=22, pady=10
        )
        self.wake_button.pack(pady=(4, 10))

        # Sync mic icon + tooltip with ON at boot
        self.update_mic_icon(_is_on)

        self.external_callback = None
        self._start_idle_check()
        self.input_entry.bind("<Return>", lambda event: self._on_send())

        # ---- Reveal window with no flicker:
        # 1) final geometry already set; 2) show at alpha=0; 3) safe clamp pass; 4) fade in.
        self._reveal_window_fade_in()

        # After layout, paint exact patches so patterns line up
        self.root.after(50, self._refresh_bg_patches)
        self.root.after(250, self._refresh_bg_patches)

        # Hold single solution popup
        self._solution_popup = None

        # Internal flag for one-shot mic capture
        self._ptt_busy = False

        # Re-clamp on configure (move/resize) to keep bottom clear AND refresh patches
        self.root.bind("<Configure>", lambda e: (self._ensure_above_taskbar(), self._refresh_bg_patches()))

    # ---- exact background crops for seamless canvases ----
    def _crop_from_bg(self, x, y, w, h):
        """Crop a WxH patch from the main starfield at window-local (x,y)."""
        try:
            box = (int(x), int(y), int(x + w), int(y + h))
            patch = self._bg_pil.crop(box)
            return ImageTk.PhotoImage(patch)
        except Exception:
            return None

    def _refresh_bg_patches(self):
        """Update the exact background under logo/mic so there’s zero seam."""
        try:
            self.root.update_idletasks()
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()

            # Logo canvas (160x160)
            lx = self.logo_canvas.winfo_rootx() - rx
            ly = self.logo_canvas.winfo_rooty() - ry
            p1 = self._crop_from_bg(lx, ly, 160, 160)
            if p1:
                self.logo_canvas.itemconfig(self.logo_bg_item, image=p1)
                self.logo_canvas._bg_patch_ref = p1  # prevent GC

            # Mic canvas (40x40)
            mx = self.mic_canvas.winfo_rootx() - rx
            my = self.mic_canvas.winfo_rooty() - ry
            p2 = self._crop_from_bg(mx, my, 40, 40)
            if p2:
                self.mic_canvas.itemconfig(self.mic_bg_item, image=p2)
                self.mic_canvas._bg_patch_ref = p2
        except Exception:
            pass

    def _ensure_above_taskbar(self):
        """If the window bottom drifts below the current work-area, nudge it up."""
        try:
            wa = _windows_work_area_for_root(self.root)
            if not wa:
                return
            l, t, r, b = wa
            safe = 12
            geo = self.root.winfo_geometry()
            parts = geo.split("+")
            w, h = map(int, parts[0].split("x"))
            x = int(parts[1]); y = int(parts[2])
            bottom = y + h
            max_y = b - h - safe
            if bottom > (b - safe):
                y = max(t + 8, max_y)
                self.root.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _set_alpha(self, a: float):
        try:
            self.root.wm_attributes("-alpha", float(a))
        except Exception:
            pass

    def _reveal_window_fade_in(self):
        # geometry already set to the final spot by position_main_window()
        self._set_alpha(0.0)
        self.root.deiconify()
        self.root.update_idletasks()
        # one safe placement pass (invisible), then fade in
        _place_main_window_safely(self.root, y_percent=0.26, bottom_margin=64)
        self.root.after(260, lambda: (self._set_alpha(1.0), self._ensure_above_taskbar()))

    # ---------- animate logo + sparkles (time-based; ~30 FPS) ----------
    def _animate_logo_and_sparkles(self):
        now = time.perf_counter()
        dt = max(0.0, min(0.1, now - getattr(self, "_last_anim_t", now)))
        self._last_anim_t = now

        face_speed = 60.0  # deg/s
        ring_speed = 60.0

        self.face_angle = (self.face_angle + face_speed * dt) % 360.0
        rad = math.radians(self.face_angle)
        cx, cy = self.face_center
        fx = cx + self.face_orbit_r * math.cos(rad)
        fy = cy + self.face_orbit_r * math.sin(rad)
        self.logo_canvas.coords(self.face_id, fx, fy)

        # Twinkling 4-point stars rotating around the logo
        self.sparkle_angle = (self.sparkle_angle + ring_speed * dt) % 360.0
        for i, s in enumerate(self.sparkles):
            ang = math.radians(self.sparkle_angle + (360 / len(self.sparkles)) * i)
            cx = self.face_center[0] + self.sparkle_r * math.cos(ang)
            cy = self.face_center[1] + self.sparkle_r * math.sin(ang)
            size = 4 + 2 * (0.5 + 0.5 * math.sin(self.sparkle_angle + i))  # gentle twinkle
            pts = _star_points(cx, cy, size, size * 0.45, points=4, angle_offset=ang / 2)
            self.logo_canvas.coords(s, *pts)
            self.logo_canvas.itemconfig(s, fill=self.glow_color, outline=self.glow_color)

        if not self.animation_ready:
            self._anim_started_frames += 1
            if self._anim_started_frames >= 3:
                self.animation_ready = True

        self.logo_canvas.after(33, self._animate_logo_and_sparkles)

    # ---------- minimal API for popup ----------
    def show_solution(self, mode: str, emoji: str, answer_text: str):
        try:
            if self._solution_popup and self._solution_popup.winfo_exists():
                self._solution_popup.destroy()
        except Exception:
            pass
        self._solution_popup = _SolutionPopup(self.root, mode=mode, emoji=emoji, first_answer=answer_text)

    def append_solution(self, answer_text: str):
        if self._solution_popup and self._solution_popup.winfo_exists():
            self._solution_popup.append_followup(answer_text)

    # ---------- status pills ----------
    def _build_mode_status_bar(self):
        left = tk.Label(self.status_bar, text="Modes:", bg=STAR_BG, fg="#88a",
                        font=("Consolas", 10, "bold"))
        left.grid(row=0, column=0, padx=(8, 8), sticky="w")

        wrap = tk.Frame(self.status_bar, bg=STAR_BG)
        wrap.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        for c in range(4):
            wrap.grid_columnconfigure(c, weight=1, uniform="pill")

        def _pill(txt):
            return tk.Label(
                wrap, text=txt, bg="#15151a", fg="#666",
                font=("Consolas", 10, "bold"), padx=8, pady=2, relief="flat"
            )

        self.pill_math = _pill("🧠 Math")
        self.pill_plot = _pill("📈 Plot")
        self.pill_phys = _pill("⚛️ Physics")
        self.pill_chem = _pill("🧪 Chemistry")

        self.pill_math.grid(row=0, column=0, padx=4, sticky="ew")
        self.pill_plot.grid(row=0, column=1, padx=4, sticky="ew")
        self.pill_phys.grid(row=0, column=2, padx=4, sticky="ew")
        self.pill_chem.grid(row=0, column=3, padx=4, sticky="ew")

        self.status_bar.grid_columnconfigure(1, weight=1)

    def _update_status_pills(self):
        glow = self.glow_color
        off = "#666666"
        on_bg = "#10131a"
        off_bg = "#15151a"
        def set_pill(pill, active):
            pill.config(fg=(glow if active else off), bg=(on_bg if active else off_bg))
        set_pill(self.pill_math, self.math_mode_var.get())
        set_pill(self.pill_plot, self.plot_mode_var.get())
        set_pill(self.pill_phys, self.physics_mode_var.get())
        set_pill(self.pill_chem, self.chemistry_mode_var.get())

    def apply_language_color(self, code: str):
        self.language = (code or "en").lower()
        self.glow_color = LANG_GLOW_COLORS.get(self.language, "#00ffcc")
        try: self.text_display.config(fg=self.glow_color)
        except Exception: pass
        for cb in (self.math_checkbox, self.plot_checkbox, self.physics_checkbox, self.chemistry_checkbox):
            try: cb.config(fg=self.glow_color, activeforeground=self.glow_color)
            except Exception: pass
        for oid in self._glow_ids:
            try: self.checkbox_canvas.itemconfig(oid, fill=self.glow_color)
            except Exception: pass
        try:
            for s in self.sparkles:
                self.logo_canvas.itemconfig(s, fill=self.glow_color)
            if self.hover_circle:
                self.mic_canvas.itemconfig(self.hover_circle, outline=self.glow_color)
            self.wake_button.config(fg=self.glow_color, activeforeground=self.glow_color)
            # update ghost scrollbar accent too
            self.ghost_scroll.set_accent(self.glow_color)
        except Exception: pass
        self._update_status_pills()
        self.update_typing_label()

    # 🔆 soft pulse on the checkbox glows
    def _pulse_checkbox_glow(self):
        bases = [self.checkbox_canvas.bbox(oid) for oid in getattr(self, "_glow_ids", [])]
        min_r, max_r = 3, 8
        radius = [min_r]; growing = [True]
        def animate():
            if growing[0]:
                radius[0] += 0.5
                if radius[0] >= max_r: growing[0] = False
            else:
                radius[0] -= 0.5
                if radius[0] <= min_r: growing[0] = True
            for i, base in enumerate(bases):
                if not base: continue
                x0, y0, x1, y1 = base
                self.checkbox_canvas.coords(self._glow_ids[i], x0 - radius[0], y0 - radius[0], x1 + radius[0], y1 + radius[0])
            self.root.after(80, animate)
        self.root.after(800, animate)

    # ---------- messaging / input ----------
    def _on_send(self):
        user_text = self.input_entry.get().strip()
        if user_text:
            self.show_message("YOU", user_text)
            self.input_entry.delete(0, tk.END)
            from core_engine import process_command
            is_math   = self.math_mode_var.get()
            is_plot   = self.plot_mode_var.get()
            is_physics= self.physics_mode_var.get()
            is_chem   = self.chemistry_mode_var.get()
            try:
                process_command(
                    user_text,
                    is_math_override=is_math,
                    is_plot_override=is_plot,
                    is_physics_override=is_physics,
                    is_chemistry_override=is_chem
                )
            except TypeError:
                process_command(
                    user_text,
                    is_math_override=is_math,
                    is_plot_override=is_plot,
                    is_physics_override=is_physics
                )
        self.input_entry.focus_set()

    def _on_clear(self):
        self.text_display.configure(state='normal')
        self.text_display.delete('1.0', tk.END)
        self.text_display.configure(state='disabled')

    def show_message(self, who: str, text: str):
        self.text_display.configure(state='normal')
        self.text_display.insert(tk.END, f"{'🟢' if who.upper()=='NOVA' else '👤'} {who.upper()}: {text}\n")
        self.text_display.see(tk.END)
        self.text_display.configure(state='disabled')

    # ---------- typing hint / wake toggle ----------
    def update_typing_label(self):
        from utils import get_wake_mode
        mode_texts = {
            "en": {"on": "🎤 Say 'Hey Nova' or type below.", "off": "🎤 Click the mic to talk, or type below."},
            "hi": {"on": "🎤 'हे नोवा' बोलें या नीचे टाइप करें।", "off": "🎤 बोलने के लिए माइक पर क्लिक करें, या नीचे टाइप करें।"},
            "fr": {"on": "🎤 Dites « Hey Nova » ou tapez ci-dessous.", "off": "🎤 Cliquez sur le micro pour parler, ou tapez ci-dessous."},
            "de": {"on": "🎤 Sag „Hey Nova“ oder tippe unten.", "off": "🎤 Klicke auf das Mikro, um zu sprechen, oder tippe unten."},
            "es": {"on": "🎤 Di «Hey Nova» o escribe abajo.", "off": "🎤 Haz clic en el micrófono para hablar, o escribe abajo."}
        }
        mode = get_wake_mode()
        if mode == "always_on": mode = "on"
        msg = mode_texts.get(self.language, mode_texts["en"]).get(mode, "🎤 Click the mic to talk, or type below.")
        self.typing_label.config(text=msg)

    def _toggle_wake_mode(self):
        from utils import get_wake_mode, set_wake_mode
        current_mode = get_wake_mode()
        if current_mode in ("on", "always_on"):
            set_wake_mode(False)
            try:
                from wake_word_listener import stop_wake_listener_thread
                stop_wake_listener_thread()
            except Exception:
                pass
            self.wake_status.set("Wake Mode: OFF")
            self.update_mic_icon(False)
            self.show_message("NOVA", "Wake mode disabled. Click the mic to talk or type below.")
        else:
            set_wake_mode(True)
            try:
                from wake_word_listener import start_wake_listener_thread
                start_wake_listener_thread()
            except Exception:
                pass
            self.wake_status.set("Wake Mode: ON")
            self.update_mic_icon(True)
            self.show_message("NOVA", "Wake mode enabled. Say 'Hey Nova' to begin.")
        self.update_typing_label()

    # ---------- Mic: icon, glow, push-to-talk ----------
    def update_mic_icon(self, is_on: bool):
        img = self.mic_on_img if is_on else self.mic_off_img
        self.mic_canvas.itemconfig(self.mic_img_obj, image=img)
        self.mic_tooltip.text = ("Wake Mode is Active 🔊 — say 'Hey Nova'." if is_on
                                 else "Click the mic to talk 🎤")
        self.start_pulse() if is_on else self.stop_pulse()
        self.update_typing_label()

    def start_pulse(self):
        self.stop_pulse()
        self.glow_active = True
        self.pulse_radius = 22
        self._pulse_animation()

    def stop_pulse(self):
        self.glow_active = False
        if self.pulse_circle:
            self.mic_canvas.delete(self.pulse_circle)
            self.pulse_circle = None

    def _pulse_animation(self):
        if not self.glow_active: return
        if self.pulse_circle:
            self.mic_canvas.delete(self.pulse_circle)
        r = self.pulse_radius
        self.pulse_circle = self.mic_canvas.create_oval(20 - r, 20 - r, 20 + r, 20 + r, outline=self.glow_color, width=2)
        self.pulse_radius += 1 if self.pulse_growing else -1
        self.pulse_growing = not (self.pulse_radius in (22, 28))
        self.root.after(80, self._pulse_animation)

    def _start_hover_glow(self, event=None):
        if self.hover_circle is None:
            self.hover_circle = self.mic_canvas.create_oval(5, 5, 35, 35, outline=self.glow_color, width=1)

    def _stop_hover_glow(self, event=None):
        if self.hover_circle:
            self.mic_canvas.delete(self.hover_circle)
            self.hover_circle = None

    # ---- Push-to-talk flow (one-shot) ----
    def _on_mic_click(self, _evt=None):
        from utils import get_wake_mode
        if get_wake_mode() in ("on", "always_on"):
            self.show_message("NOVA", "Wake Mode is on — just say 'Hey Nova'.")
            return
        if self._ptt_busy:
            return
        self._ptt_busy = True
        self.start_pulse()
        threading.Thread(target=self._ptt_capture_once, daemon=True).start()

    def _ptt_capture_once(self):
        from utils import listen_command
        try:
            text = listen_command()
        except Exception:
            text = ""
        self.root.after(0, lambda t=text: self._ptt_handle_result(t))

    def _ptt_handle_result(self, text: str):
        self.stop_pulse()
        self._ptt_busy = False
        if not text:
            self.show_message("NOVA", "Sorry, I didn’t catch that. Please try again.")
            return
        self.show_message("YOU", text)
        from core_engine import process_command
        try:
            process_command(
                text,
                is_math_override=self.math_mode_var.get(),
                is_plot_override=self.plot_mode_var.get(),
                is_physics_override=self.physics_mode_var.get(),
                is_chemistry_override=self.chemistry_mode_var.get(),
            )
        except TypeError:
            process_command(
                text,
                is_math_override=self.math_mode_var.get(),
                is_plot_override=self.plot_mode_var.get(),
                is_physics_override=self.physics_mode_var.get(),
            )

    def _start_idle_check(self):  # placeholder
        pass

    def mainloop(self):
        self.root.mainloop()

    def hide(self):
        try: self.root.withdraw()
        except Exception: pass

    def show(self):
        try: self.root.deiconify()
        except Exception: pass

# ----------------------------- Lazy singleton factory -----------------------------
_nova_gui = None
def get_gui():
    """Create the GUI only when called (after language is hydrated)."""
    global _nova_gui
    if _nova_gui is None:
        _nova_gui = NovaGUI()
    return _nova_gui

def gui_if_ready():
    """Return GUI instance if already created; don't auto-create."""
    return _nova_gui

# ---- Bridge for solver popups (unchanged logic, but no auto-create) ----
_MODE_META = {
    "math": ("Math Mode", "🧠"),
    "plot": ("Plot Mode", "📈"),
    "physics": ("Physics Mode", "⚛️"),
    "chemistry": ("Chemistry Mode", "🧪"),
}

def show_mode_solution(mode_key: str, text: str):
    name, emoji = _MODE_META.get(mode_key.lower(), ("Solution", "✨"))
    g = gui_if_ready()
    if not g: return
    try:
        g.root.after(0, lambda: g.show_solution(mode=name, emoji=emoji, answer_text=text))
    except Exception:
        pass

def append_mode_solution(mode_key: str, text: str):
    g = gui_if_ready()
    if not g: return
    try:
        g.root.after(0, lambda: g.append_solution(text))
    except Exception:
        pass

import utils
def _gui_solution_bridge(channel, payload):
    g = gui_if_ready()
    MODE_MAP = _MODE_META
    ch = str(channel or "").strip().lower()
    if ch not in MODE_MAP:
        txt = payload if isinstance(payload, str) else (payload or {}).get("html", "")
        if txt and g:
            try:
                g.root.after(0, lambda: g.show_message("NOVA", txt))
            except Exception:
                pass
        return

    if isinstance(payload, str):
        html = payload; actions = {}; ctx = {}; action_hint = None
    else:
        html   = (payload or {}).get("html", "")
        actions= (payload or {}).get("actions") or {}
        ctx    = (payload or {}).get("ctx") or {}
        action_hint = (payload or {}).get("action")

    if not html or not g: return
    name, emoji = MODE_MAP[ch]

    def _apply():
        if action_hint == "append":
            g.append_solution(html)
        else:
            if getattr(g, "_solution_popup", None) and g._solution_popup.winfo_exists():
                g.append_solution(html)
            else:
                g.show_solution(mode=name, emoji=emoji, first_answer=html)

        primary = actions.get("primary")
        chips   = actions.get("chips") or []
        inline  = actions.get("inline")
        original_text = ctx.get("original_text", "") or (payload or {}).get("question", "")

        primary_label = None; primary_cmd = None
        chip_labels, chip_cmds = [], []

        if primary and isinstance(primary, dict) and primary.get("id") == "more_detail":
            primary_label = primary.get("label", "✦ More detail")
            def _on_more_detail():
                try:
                    from handlers.chemistry_solver import CHEM_CTX
                    from core_engine import process_command
                    CHEM_CTX["force_verbose_once"] = True
                    process_command(original_text or "", is_chemistry_override=True)
                except Exception as e:
                    g.append_solution(f"(Could not expand: {e})")
            primary_cmd = _on_more_detail

        if primary and isinstance(primary, dict) and primary.get("id") == "plot_it":
            primary_label = primary.get("label", "✦ Plot it")
            def _on_plot_it():
                try:
                    from handlers.physics_solver import handle_graph_confirmation
                    handle_graph_confirmation("graph it")
                except Exception as e:
                    try: g.append_solution(f"(Could not plot: {e})")
                    except Exception: pass
            primary_cmd = _on_plot_it

        for chip in chips:
            lab = chip.get("label") if isinstance(chip, dict) else str(chip)
            if not lab: continue
            chip_labels.append(lab)
            def _make_cmd(q=lab):
                def _cmd():
                    try:
                        from handlers.chemistry_solver import CHEM_CTX, handle_chemistry_query
                        CHEM_CTX["force_verbose_once"] = False
                        handle_chemistry_query(q)
                    except Exception as e:
                        g.append_solution(f"(Could not run follow-up: {e})")
                return _cmd
            chip_cmds.append(_make_cmd())

        if getattr(g, "_solution_popup", None) and g._solution_popup.winfo_exists():
            try:
                if primary_label and primary_cmd:
                    g._solution_popup.set_actions(primary_label, primary_cmd, chip_labels, chip_cmds)
                else:
                    g._solution_popup.set_actions(None, None, chip_labels, chip_cmds)
            except Exception:
                pass

        if inline and isinstance(inline, dict) and inline.get("id") == "plot_it":
            inline_label = inline.get("label", "✦ Plot it")
            anchor_text  = inline.get("anchor", "Plot it")
            def _on_plot_it_inline():
                try:
                    from handlers.physics_solver import handle_graph_confirmation
                    handle_graph_confirmation("graph it")
                except Exception as e:
                    try: g.append_solution(f"(Could not plot: {e})")
                    except Exception: pass
            try:
                if getattr(g, "_solution_popup", None) and hasattr(g._solution_popup, "add_inline_button"):
                    g._solution_popup.add_inline_button(inline_label, _on_plot_it_inline, anchor_text=anchor_text)
                elif getattr(g, "_solution_popup", None) and hasattr(g._solution_popup, "set_actions"):
                    g._solution_popup.set_actions(inline_label, _on_plot_it_inline, [], [])
            except Exception:
                pass

    try:
        if g:
            g.root.after(0, _apply)
    except Exception:
        pass

set_gui_callback(_gui_solution_bridge)
