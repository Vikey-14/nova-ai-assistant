from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import font as tkfont
from PIL import Image, ImageTk
import os, sys, math, time, ctypes, threading, subprocess, shutil
import re, webbrowser
from say_show import say_show

# --- Nova interaction gating (don't speak while language flow or TTS is busy) ---
import utils
from utils import LANGUAGE_FLOW_ACTIVE


def _multilang(**kw):
    """
    Usage: _multilang(en="...", hi="...", fr="...", de="...", es="...")
    Chooses a string by the current UI language; falls back to English/first provided.
    """
    try:
        # Try the live GUI language
        g = gui_if_ready()
        lang = (getattr(g, "language", "en") or "en").split("-")[0].lower()
    except Exception:
        # Fallback to utils' selected_language
        try:
            lang = (utils.selected_language or "en").split("-")[0].lower()
        except Exception:
            lang = "en"

    if lang in kw and kw[lang]:
        return kw[lang]
    if "en" in kw and kw["en"]:
        return kw["en"]
    for v in kw.values():
        if v:
            return v
    return ""


def _interaction_gate_open() -> bool:
    try:
        tts_busy = getattr(utils, "tts_busy", None)
        is_tts_busy = bool(tts_busy and tts_busy.is_set())
    except Exception:
        is_tts_busy = False
    return (not LANGUAGE_FLOW_ACTIVE) and (not is_tts_busy)

from utils import resource_path, set_gui_callback

IS_WSL = bool(os.environ.get("WSL_DISTRO_NAME"))
IS_LINUX = sys.platform.startswith("linux")
IS_LINUX_OR_WSL = IS_LINUX or IS_WSL

try:
    from handlers.nova_graph_ui import make_starry_bg, BG as STAR_BG
except Exception:
    STAR_BG = "#0f0f0f"
    def make_starry_bg(w, h):
        img = Image.new("RGB", (w, h), STAR_BG)
        return ImageTk.PhotoImage(img)

LANG_GLOW_COLORS = {
    "en": "#00ffcc", "hi": "#ff9933", "fr": "#3399ff",
    "de": "#66cc66", "es": "#ff6666",
}

TIP_TEXTS = {
    "en": {
        "math":      "Enable this to type math directly. Like: integrate(x^2, x)",
        "plot":      "Use this to graph equations or data, e.g. y=x^2 or x=[1,2], y=[3,4]",
        "physics":   "Solve physics with units (v = u + a*t, etc.)",
        "chemistry": "Chemistry: molar mass, pH/pOH, stoichiometry, gas laws, dilution…",
    },
    "hi": {
        "math":      "इसे चालू करें ताकि आप सीधे गणित टाइप कर सकें। जैसे: integrate(x^2, x)",
        "plot":      "समीकरण/डेटा का ग्राफ बनाने के लिए इसका उपयोग करें, जैसे: y=x^2 या x=[1,2], y=[3,4]",
        "physics":   "इकाइयों के साथ भौतिकी हल करें (v = u + a*t, आदि)",
        "chemistry": "रसायन: मोलर द्रव्यमान, pH/pOH, स्टॉइकियोमेट्री, गैस नियम, घोलना…",
    },
    "fr": {
        "math":      "Activez ceci pour taper des maths directement. Ex : integrate(x^2, x)",
        "plot":      "Servez-vous-en pour tracer équations ou données (p. ex. y=x^2 ou x=[1,2], y=[3,4])",
        "physics":   "Résoudre la physique avec unités (v = u + a*t, etc.)",
        "chemistry": "Chimie : masse molaire, pH/pOH, stœchiométrie, lois des gaz, dilution…",
    },
    "de": {
        "math":      "Aktivieren, um direkt Mathematik zu tippen. Z. B.: integrate(x^2, x)",
        "plot":      "Zum Plotten von Gleichungen/Daten, z. B. y=x^2 oder x=[1,2], y=[3,4]",
        "physics":   "Physik mit Einheiten lösen (v = u + a*t usw.)",
        "chemistry": "Chemie: Molmasse, pH/pOH, Stöchiometrie, Gasgesetze, Verdünnung…",
    },
    "es": {
        "math":      "Activa esto para escribir matemáticas directamente. Ej.: integrate(x^2, x)",
        "plot":      "Úsalo para graficar ecuaciones o datos, p. ej. y=x^2 o x=[1,2], y=[3,4]",
        "physics":   "Resuelve física con unidades (v = u + a*t, etc.)",
        "chemistry": "Química: masa molar, pH/pOH, estequiometría, leyes de gases, dilución…",
    },
}

# ---------- Windows work-area helpers ----------
def _win_work_area_for_window(hwnd) -> tuple[int,int,int,int] | None:
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
    root.update_idletasks()
    wa = _windows_work_area_for_root(root)
    if wa:
        l, t, r, b = wa
        sw, sh = (r - l), (b - t)
        x = l + max(0, (sw - w) // 2)
        y = t + max(min_top, (sh - h) // 2 - upward_bias)
        y = min(y, b - h - safe_bottom)
        y = max(t + min_top, y)
        root.geometry(f"{w}x{h}+{x}+{y}")
        return

    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    x = max(0, (sw - w) // 2)
    y_pref = (sh - h) // 2 - upward_bias
    y = max(min_top, y_pref)
    bottom_guard = 72 if IS_LINUX_OR_WSL else 12
    y = min(y, max(min_top, sh - h - bottom_guard))
    y = max(0, y)
    root.geometry(f"{w}x{h}+{x}+{y}")

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
        y = max(t, min(y, b - bottom_margin - h))
        root.geometry(f"+{x}+{y}")
        if not _second_pass:
            root.after(220, lambda: _place_main_window_safely(root, y_percent, bottom_margin, True))
    except Exception:
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = root.winfo_width(), root.winfo_height()
        x = (sw - w) // 2
        y = max(0, (sh - h) // 2 - 120)
        guard = bottom_margin if IS_LINUX_OR_WSL else 12
        y = min(y, max(0, sh - h - guard))
        root.geometry(f"+{x}+{y}")
        if not _second_pass:
            root.after(220, lambda: _place_main_window_safely(root, y_percent, bottom_margin, True))

def _fit_linux_size(root: tk.Tk, min_w=720, min_h=560, side_margin=12, top_margin=24, bottom_margin=72):
    if not IS_LINUX_OR_WSL:
        return
    try:
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        req_w, req_h = root.winfo_reqwidth(), root.winfo_reqheight()
        W = min(max(req_w, min_w), max(320, sw - 2*side_margin))
        H = min(max(req_h, min_h), max(320, sh - (top_margin + bottom_margin)))
        root.geometry(f"{int(W)}x{int(H)}")
        root.minsize(int(W), int(H))
    except Exception:
        pass

def _linux_center_now(root: tk.Tk, y_bias: int = 60, bottom_guard: int = 120):
    if not IS_LINUX_OR_WSL:
        return
    try:
        root.update_idletasks()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h   = root.winfo_width(), root.winfo_height()
        x = max(0, (sw - w) // 2)
        y = max(24, min((sh - h) // 2 - y_bias, sh - h - bottom_guard))
        root.geometry(f"+{x}+{y}")
    except Exception:
        pass

def _linux_center_after_map(root: tk.Tk):
    if not IS_LINUX_OR_WSL:
        return
    _linux_center_now(root)
    root.after(200, lambda: _linux_center_now(root))
    root.after(700, lambda: _linux_center_now(root))

class Tooltip:
    def __init__(self, widget, text='Tooltip', font_family=None, fg=None):
        self.widget = widget
        self.text = text or ""
        self.font_family = (font_family or "Consolas")
        self.fg = fg or "white"
        self.tip_window = None
        self._label = None

        widget.bind("<Enter>", self.show_tooltip)
        widget.bind("<Leave>", self.hide_tooltip)

    def set_text(self, text: str):
        self.text = text or ""
        if self._label and self._label.winfo_exists():
            try:
                self._label.config(text=self.text)
            except Exception:
                pass

    def set_font_family(self, family: str):
        if not family:
            return
        self.font_family = family
        if self._label and self._label.winfo_exists():
            try:
                self._label.config(font=(self.font_family, 9))
            except Exception:
                pass

    def set_fg(self, color: str):
        if not color:
            return
        self.fg = color
        if self._label and self._label.winfo_exists():
            try:
                self._label.config(foreground=self.fg)
            except Exception:
                pass

    def show_tooltip(self, event=None):
        if self.tip_window or not self.text:
            return
        try:
            x, y, _, _ = self.widget.bbox("insert")
        except Exception:
            x = y = 0
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 10

        tw = tk.Toplevel(self.widget)
        self.tip_window = tw
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        self._label = tk.Label(
            tw, text=self.text, justify='left',
            background="#333333", foreground=self.fg,
            relief='solid', borderwidth=1,
            font=(self.font_family, 9)
        )
        self._label.pack(ipadx=4, ipady=2)

    def hide_tooltip(self, event=None):
        try:
            if self.tip_window and self.tip_window.winfo_exists():
                self.tip_window.destroy()
        except Exception:
            pass
        finally:
            self.tip_window = None
            self._label = None

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
        try:
            self.iconbitmap(resource_path("nova_icon_big.ico"))
        except Exception:
            pass
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

def _star_points(cx, cy, r_out, r_in, points=4, angle_offset=0.0):
    pts = []
    for k in range(points * 2):
        ang = angle_offset + k * (math.pi / points)
        r = r_out if (k % 2 == 0) else r_in
        pts.extend([cx + r * math.cos(ang), cy + r * math.sin(ang)])
    return pts

class GhostScrollbar(tk.Canvas):
    BTN_H = 16
    PAD   = 0
    MIN_THUMB = 36
    EDGE_SAFE = 1
    STROKE_W = 1
    TRI_INSET = 0
    TRI_FILL_SCALE = 1.0

    SHOW_SECS = 7.0
    HOVER_ZONE_PX = 56
    POLL_MS = 200

    def __init__(self, master, accent="#00ffcc", width=20, **kw):
        super().__init__(master, width=width, highlightthickness=0, bd=0, bg=STAR_BG, **kw)
        self.accent = accent
        self._text: tk.Text | None = None
        self._first, self._last = 0.0, 1.0
        self._drawn = False
        self._dragging = False
        self._drag_offset = 0
        self._scrollable = False
        self._hovering = False
        self._watchdog_id = None
        self._last_alive = time.monotonic()
        self._repeat_id = None
        self._btn_up = self._btn_dn = None
        self._btn_up_fill = self._btn_dn_fill = None
        self._thumb_border = None
        self._thumb_fill = None
        self._track_color = "#151515"
        self._fill_black  = "#000000"

        self.bind("<Configure>", lambda e: self._redraw_if_drawn(), add="+")
        self.bind("<Enter>",     lambda e: (self._set_hover(True),  self._show_now()), add="+")
        self.bind("<Leave>",     lambda e: (self._set_hover(False), self._poke()), add="+")
        self.bind("<Button-1>",  self._on_click, add="+")
        self.bind("<B1-Motion>", self._on_drag, add="+")
        self.bind("<ButtonRelease-1>", self._on_release, add="+")
        self.bind("<Motion>",    lambda e: (self._show_now(), self._poke()), add="+")

        self.after_idle(self._clear_drawings)

    def _set_hover(self, v: bool): self._hovering = bool(v)
    def _poke(self): self._last_alive = time.monotonic()

    def _clear_drawings(self):
        self.delete("all")
        self._drawn = False
        w = int(self.winfo_width()); h = int(self.winfo_height())
        if w > 0 and h > 0:
            self.create_rectangle(0, 0, w, h, fill=STAR_BG, outline="")

    def _redraw_if_drawn(self):
        if self._drawn:
            self._redraw()

    def _sync_from_text(self, repaint=True):
        if not self._text:
            return
        try:
            f, l = self._text.yview()
            self._first, self._last = float(f), float(l)
            if repaint and self._drawn:
                self._redraw()
        except Exception:
            pass

    def attach(self, text_widget: tk.Text):
        self._text = text_widget
        text_widget.configure(yscrollcommand=self.on_textscroll)
        text_widget.bind("<MouseWheel>", lambda e: (self._show_now(e), self._wheel(e), self._poke()), add="+")
        text_widget.bind("<Motion>", self._edge_probe, add="+")
        text_widget.bind_all("<Up>",   self._on_arrow, add="+")
        text_widget.bind_all("<Down>", self._on_arrow, add="+")
        self.after_idle(self._clear_drawings)

    def on_textscroll(self, first, last):
        try:
            self._first, self._last = float(first), float(last)
        except Exception:
            self._first, self._last = 0.0, 1.0
        self._show_now() if (self._last - self._first) < 0.9999 else self._hide_now()

    def _track_area(self):
        w = int(self.winfo_width()); h = int(self.winfo_height())
        return (self.PAD, self.BTN_H, w - self.PAD, h - self.BTN_H)

    def _triangle_pts(self, top=True, inset=0):
        w = int(self.winfo_width()); h = int(self.winfo_height())
        L = self.PAD + inset
        R = w - self.PAD - inset
        if top:
            A = (w//2, self.EDGE_SAFE + inset)
            B = (R,    self.BTN_H - self.EDGE_SAFE - inset)
            C = (L,    self.BTN_H - self.EDGE_SAFE - inset)
        else:
            A = (w//2,  h - self.EDGE_SAFE - inset)
            B = (R,     h - self.BTN_H + self.EDGE_SAFE + inset)
            C = (L,     h - self.BTN_H + self.EDGE_SAFE + inset)
        return (*A, *B, *C)

    def _thumb_rect(self):
        x0, y0, x1, y1 = self._track_area()
        H = max(1, y1 - y0)
        top = int(y0 + H * self._first)
        bot = int(y0 + H * self._last)
        if bot - top < self.MIN_THUMB:
            mid = (top + bot) // 2
            top = max(y0, mid - self.MIN_THUMB // 2)
            bot = min(y1, top + self.MIN_THUMB)
        return int(x0), int(top), int(x1), int(bot)

    def _draw_triangle_pair(self, top=True):
        fill_pts   = self._triangle_pts(top=top, inset=0)
        stroke_pts = self._triangle_pts(top=top, inset=self.EDGE_SAFE)
        fill_poly  = self.create_polygon(*fill_pts,   fill=self._fill_black, outline="")
        stroke     = self.create_polygon(*stroke_pts, fill="", outline=self.accent,
                                         width=self.STROKE_W, joinstyle="miter")
        if top:  self._btn_up_fill, self._btn_up = fill_poly, stroke
        else:    self._btn_dn_fill, self._btn_dn = fill_poly, stroke

    def _draw_rect_thumb(self, x0, y0, x1, y1, bind_drag=True):
        s = self.EDGE_SAFE
        self._thumb_fill   = self.create_rectangle(x0, y0, x1, y1, fill=self._fill_black, outline="")
        self._thumb_border = self.create_rectangle(x0 + s, y0, x1 - s, y1, fill="", outline=self.accent, width=self.STROKE_W)
        if bind_drag:
            self.tag_bind(self._thumb_fill, "<ButtonPress-1>",   self._start_drag)
            self.tag_bind(self._thumb_fill, "<B1-Motion>",       self._on_drag)
            self.tag_bind(self._thumb_fill, "<ButtonRelease-1>", self._on_release)

    def _redraw(self):
        self.delete("all")
        w = int(self.winfo_width()); h = int(self.winfo_height())
        if w <= 2 or h <= 2:
            self._drawn = False
            return
        self.create_rectangle(0, 0, w, h, fill=STAR_BG, outline="")
        self.create_rectangle(2, 2, w-2, h-2, fill=self._track_color, outline="")
        self._draw_triangle_pair(top=True)
        self._draw_triangle_pair(top=False)
        for stroke, fill, dirn in (
            (self._btn_up, self._btn_up_fill, -1),
            (self._btn_dn, self._btn_dn_fill, +1),
        ):
            for item in (stroke, fill):
                self.tag_bind(item, "<ButtonPress-1>",  lambda e, d=dirn: (self._press_button(d), self._poke()))
                self.tag_bind(item, "<ButtonRelease-1>", self._stop_repeat)
                self.tag_bind(item, "<Leave>",           self._stop_repeat)
        tx0, ty0, tx1, ty1 = self._track_area()
        self._scrollable = (self._last - self._first) < 0.9999
        if self._scrollable:
            x0, y0, x1, y1 = self._thumb_rect()
            self._draw_rect_thumb(x0, y0, x1, y1, bind_drag=True)
        else:
            cy = (ty0 + ty1) // 2
            y0 = cy - self.MIN_THUMB // 2
            y1 = y0 + self.MIN_THUMB
            self._draw_rect_thumb(tx0, y0, tx1, y1, bind_drag=False)
        self._drawn = True

    def _wheel(self, evt):
        if not self._text: return
        delta = evt.delta if hasattr(evt, "delta") else 0
        steps = -1 * (delta // 120) if delta else (-1 if getattr(evt, "num", 0) == 4 else (1 if getattr(evt, "num", 0) == 5 else 0))
        if steps:
            self._text.yview_scroll(steps, "units")
            self._sync_from_text(repaint=True)
            self._show_now()

    def _edge_probe(self, evt):
        try:
            w = evt.widget.winfo_width()
            if evt.x >= max(0, w - self.HOVER_ZONE_PX):
                self._show_now()
        except Exception:
            pass

    def _on_arrow(self, evt):
        if not self._text: return
        if   evt.keysym == "Up":   self._text.yview_scroll(-3, "units")
        elif evt.keysym == "Down": self._text.yview_scroll(3, "units")
        else: return
        self._sync_from_text(repaint=True)
        self._show_now()

    def _on_click(self, evt):
        if not self._text: return
        x0, y0, x1, y1 = self._thumb_rect()
        if y0 <= evt.y <= y1 and self._scrollable:
            self._start_drag(evt); return
        tx0, ty0, tx1, ty1 = self._track_area()
        if ty0 <= evt.y <= ty1:
            self._text.yview_scroll(-1 if evt.y < y0 else +1, "pages")
            self._sync_from_text(repaint=True)
            self._show_now()

    def _start_drag(self, evt):
        if not self._scrollable: return
        self._dragging = True
        _, y0, _, _ = self._thumb_rect()
        self._drag_offset = int(evt.y) - int(y0)
        self._jump_to(evt.y); self._show_now()

    def _on_drag(self, evt):
        if not (self._dragging and self._text and self._scrollable): return
        self._jump_to(evt.y)

    def _on_release(self, _evt=None):
        self._dragging = False
        self._poke()

    def _jump_to(self, y):
        _, ty0, _, ty1 = self._track_area()
        track_h = max(1, (ty1 - ty0) - self.MIN_THUMB)
        frac = max(0.0, min(1.0, (int(y) - ty0 - self._drag_offset) / track_h))
        try:
            self._text.yview_moveto(frac)
            self._sync_from_text(repaint=True)
        except Exception:
            pass

    def _press_button(self, direction: int):
        if not self._text: return
        self._text.yview_scroll(-3 if direction < 0 else 3, "units")
        self._sync_from_text(repaint=True)
        self._show_now()
        self._stop_repeat()
        self._repeat_id = self.after(60, lambda: self._press_button(direction))

    def _stop_repeat(self, *_):
        if self._repeat_id:
            try: self.after_cancel(self._repeat_id)
            except Exception: pass
            self._repeat_id = None

    def _is_pointer_near_edge(self) -> bool:
        try:
            if not self._text: return False
            rx = self._text.winfo_rootx()
            ry = self._text.winfo_rooty()
            w  = self._text.winfo_width()
            h  = self._text.winfo_height()
            px = self._text.winfo_pointerx()
            py = self._text.winfo_pointery()
            inside_y = ry <= py <= ry + h
            return inside_y and (px >= rx + w - self.HOVER_ZONE_PX)
        except Exception:
            return False

    def _watchdog_tick(self):
        if self._hovering or self._dragging or self._is_pointer_near_edge():
            self._poke()
        if self._drawn and (time.monotonic() - self._last_alive) < self.SHOW_SECS:
            self._watchdog_id = self.after(self.POLL_MS, self._watchdog_tick)
        else:
            self._watchdog_id = None
            self._hide_now()

    def _start_watchdog(self):
        if not self._watchdog_id:
            self._watchdog_id = self.after(self.POLL_MS, self._watchdog_tick)

    def _show_now(self, *_):
        if not self._drawn:
            self._redraw()
        self._poke()
        self._start_watchdog()

    def _hide_now(self):
        if self._dragging or self._hovering or self._is_pointer_near_edge():
            self._poke(); self._start_watchdog(); return
        self._clear_drawings()
        if self._watchdog_id:
            try: self.after_cancel(self._watchdog_id)
            except Exception: pass
            self._watchdog_id = None

    def set_accent(self, accent_hex: str):
        self.accent = accent_hex or self.accent
        if self._drawn:
            try:
                if self._btn_up:       self.itemconfig(self._btn_up,       outline=self.accent)
                if self._btn_dn:       self.itemconfig(self._btn_dn,       outline=self.accent)
                if self._thumb_border: self.itemconfig(self._thumb_border, outline=self.accent)
            except Exception: pass
            self._redraw()

class NovaGUI:
    URL_RE = re.compile(r"(https?://[^\s<>()]+|www\.[^\s<>()]+)", re.IGNORECASE)
    TRAIL_PUNCT = ".,!?:;)]}›»”'"

    def __init__(self):
        from utils import selected_language, get_wake_mode
        self.language = selected_language
        self.glow_color = LANG_GLOW_COLORS.get(self.language, "#00ffcc")

        self.animation_ready = False
        self._anim_started_frames = 0

        self.root = tk.Tk()
        self._closing = False
        self._after_ids = set()

        if os.name != "nt":
            try:
                self.root.wm_class("Nova")
            except Exception:
                pass

        try:
            self.root.iconphoto(
                True,
                tk.PhotoImage(file=resource_path(os.path.join("assets", "nova_icon_256.png")))
            )
        except Exception:
            pass

        if os.name != "nt":
            try:
                preferred = "Noto Sans Devanagari"
                fallback  = "Noto Sans"
                def _set_family(font_name: str):
                    try:
                        f = tkfont.nametofont(font_name); f.configure(family=preferred)
                    except Exception:
                        try:
                            f = tkfont.nametofont(font_name); f.configure(family=fallback)
                        except Exception:
                            pass
                for fam in ("TkDefaultFont","TkTextFont","TkFixedFont","TkMenuFont","TkHeadingFont"):
                    _set_family(fam)
            except Exception:
                pass

        self.root.withdraw()
        self.root.title("Nova - AI Assistant")
        try:
            self.root.iconbitmap(resource_path("nova_icon_big.ico"))
        except Exception:
            pass

        W, H = 820, 680
        IS_LINUX_OR_WSL_LOCAL = IS_LINUX_OR_WSL
        if IS_LINUX_OR_WSL_LOCAL:
            try:
                sh = self.root.winfo_screenheight()
                SAFE_DECOR = 120
                H = min(H, max(560, sh - SAFE_DECOR))
            except Exception:
                pass

        self.root.geometry(f"{W}x{H}")
        position_main_window(self.root, W, H)
        self.root.configure(bg=STAR_BG)

        if IS_LINUX_OR_WSL_LOCAL:
            self.root.resizable(True, True)
            self.root.minsize(max(540, W - 140), 540)
        else:
            self.root.resizable(False, False)

        self._bg_img = make_starry_bg(W, H)
        self._bg_label = tk.Label(self.root, image=self._bg_img, bd=0)
        self._bg_label.image = self._bg_img
        self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg_label.lower()
        self._bg_pil = ImageTk.getimage(self._bg_img).copy()

        self.logo_canvas = tk.Canvas(self.root, width=160, height=160, bg=STAR_BG, highlightthickness=0, bd=0)
        self.logo_canvas.pack(pady=(6, 2))
        self.logo_bg_item = self.logo_canvas.create_image(0, 0, anchor="nw")

        try:
            image_path = resource_path(os.path.join("assets", "nova_face_glow.png"))
            if not os.path.exists(image_path):
                image_path = resource_path(os.path.join("assets", "nova_face.png"))
            image = Image.open(image_path).resize((120, 120), Image.LANCZOS)
            self.nova_photo = ImageTk.PhotoImage(image)
        except Exception:
            self.nova_photo = ImageTk.PhotoImage(Image.new("RGBA", (120,120), (0,0,0,0)))

        self.face_center = (80, 80)
        self.face_orbit_r = 10
        self.face_angle = 0.0
        self.face_id = self.logo_canvas.create_image(*self.face_center, image=self.nova_photo)

        self.sparkles = []
        self.sparkle_angle = 0.0
        self.sparkle_r = 62
        for _ in range(6):
            s = self.logo_canvas.create_polygon(0,0,0,0,0,0,0,0, fill=self.glow_color, outline=self.glow_color, width=1)
            self.sparkles.append(s)

        self._last_anim_t = time.perf_counter()
        self._animate_logo_and_sparkles()

        self.status_bar = tk.Frame(self.root, bg=STAR_BG)
        self.status_bar.pack(pady=(0, 6), fill="x")
        self._build_mode_status_bar()

        chat_wrap = tk.Frame(self.root, bg=STAR_BG)
        chat_wrap.pack(padx=10, pady=5, fill="x")

        chat_font = ("Consolas", 10) if os.name == "nt" else ("Noto Sans Devanagari", 10)

        self.text_display = tk.Text(
            chat_wrap, height=18, width=86, bg="#111116",
            fg=self.glow_color, font=chat_font, bd=0,
            wrap="word", cursor="xterm", undo=False
        )
        self._install_readonly_bindings(self.text_display)

        self._ctx_menu = tk.Menu(self.root, tearoff=0)
        self.text_display.bind("<Button-3>", self._on_right_click, add="+")
        self.text_display.bind("<Button-2>", self._on_right_click, add="+")

        self.ghost_scroll = GhostScrollbar(chat_wrap, accent=self.glow_color, width=10)
        self.text_display.grid(row=0, column=0, sticky="nsew")
        self.ghost_scroll.grid(row=0, column=1, sticky="ns")
        chat_wrap.grid_columnconfigure(0, weight=1)
        chat_wrap.grid_rowconfigure(0, weight=1)
        self.ghost_scroll.attach(self.text_display)

        def _on_mousewheel(evt):
            self.text_display.yview_scroll(-1 * (evt.delta // 120), "units")
            self.ghost_scroll._show_now()
        self.text_display.bind("<Enter>", lambda e: self.text_display.bind_all("<MouseWheel>", _on_mousewheel))
        self.text_display.bind("<Leave>", lambda e: self.text_display.unbind_all("<MouseWheel>"))

        self.typing_label = tk.Label(self.root, font=("Consolas", 9), bg=STAR_BG, fg="gray")
        self.typing_label.pack()

        self.input_entry = tk.Entry(self.root, width=60, font=("Consolas", 11))
        self.input_entry.pack(pady=8)

        try:
            self.input_entry.focus_set()
            self.root.after(300, lambda: self.input_entry.focus_set())
        except Exception:
            pass

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

        self.tip_math      = Tooltip(self.math_checkbox,      self._tip("math"),      font_family=self._tip_font(), fg=self.glow_color)
        self.tip_plot      = Tooltip(self.plot_checkbox,      self._tip("plot"),      font_family=self._tip_font(), fg=self.glow_color)
        self.tip_physics   = Tooltip(self.physics_checkbox,   self._tip("physics"),   font_family=self._tip_font(), fg=self.glow_color)
        self.tip_chemistry = Tooltip(self.chemistry_checkbox, self._tip("chemistry"), font_family=self._tip_font(), fg=self.glow_color)

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

        button_frame = tk.Frame(self.root, bg=STAR_BG); button_frame.pack()
        self.send_button  = tk.Button(
            button_frame, text="Send",
            command=self._on_send,
            width=12,
            bg="#202033", fg="white", relief="flat", bd=0, highlightthickness=0,
            activebackground="#202033", activeforeground="white"
        )
        self.clear_button = tk.Button(button_frame, text="Clear", command=self._on_clear, width=12,
                                      bg="#202033", fg="white", relief="flat", bd=0, highlightthickness=0,
                                      activebackground="#202033", activeforeground="white")
        self.send_button.grid(row=0, column=0, padx=6)
        self.clear_button.grid(row=0, column=1, padx=6)

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
        self.mic_bg_item = self.mic_canvas.create_image(0, 0, anchor="nw")
        self.mic_img_obj = self.mic_canvas.create_image(20, 20, image=self.mic_off_img)

        self.pulse_radius = 22
        self.pulse_circle = None
        self.pulse_growing = True
        self.hover_circle = None
        self.glow_active = False
        self.mic_canvas.bind("<Enter>", self._start_hover_glow)
        self.mic_canvas.bind("<Leave>", self._stop_hover_glow)
        self.mic_canvas.bind("<Button-1>", self._on_mic_click)
        self.mic_tooltip = Tooltip(self.mic_canvas, text="Click the mic to talk 🎤")

        _is_on = bool(get_wake_mode())
        initial_label = "Wake Mode: ON" if _is_on else "Wake Mode: OFF"

        self.wake_button = tk.Button(
            self.root, text=initial_label,
            command=self._toggle_wake_mode,
            bg="#10131a", fg=self.glow_color,
            activebackground="#10131a", activeforeground=self.glow_color,
            relief="flat", bd=0, highlightthickness=0,
            font=("Consolas", 12, "bold"),
            width=24, padx=22, pady=10
        )
        self.wake_button.pack(pady=(4, 10))
        self.update_mic_icon(_is_on)

        self.external_callback = None
        self._start_idle_check()

        # Enter sends (no debug echo)
        self.input_entry.bind("<Return>",   lambda e: (self._on_send(), "break"))
        self.input_entry.bind("<KP_Enter>", lambda e: (self._on_send(), "break"))

        self.root.update_idletasks()
        _fit_linux_size(self.root, bottom_margin=72)

        if IS_LINUX_OR_WSL_LOCAL:
            self._compact_linux_ui()

        self._reveal_window_fade_in()
        self.root.after(50, self._refresh_bg_patches)
        self.root.after(250, self._refresh_bg_patches)

        self._solution_popup = None
        self._ptt_busy = False

        self.root.bind("<Configure>", lambda e: (self._ensure_above_taskbar(), self._refresh_bg_patches))
        if IS_LINUX_OR_WSL_LOCAL:
            self.root.bind("<Map>", lambda e: _linux_center_after_map(self.root))

        self._url_tag_map: dict[str, str] = {}
        self._last_link_open_time = 0.0
        self._last_link_open_url  = ""

    def _install_readonly_bindings(self, text: tk.Text):
        ALLOW_KEYS = {"Left","Right","Up","Down","Home","End","Next","Prior","Tab","ISO_Left_Tab"}
        def _on_key(e):
            ctrl = (e.state & 0x4) != 0 or (e.state & 0x20000) != 0
            if ctrl and e.keysym.lower() in ("c", "a"):
                if e.keysym.lower() == "a":
                    text.tag_add("sel", "1.0", "end-1c")
                return None
            if e.keysym in ALLOW_KEYS:
                return None
            if e.keysym in ("Return","BackSpace","Delete","Escape"):
                return "break"
            if e.char and ord(e.char) >= 32:
                return "break"
            return None
        text.bind("<Key>", _on_key, add="+")

    def _mix_to_white(self, hex_color: str, frac: float) -> str:
        try:
            h = hex_color.lstrip('#')
            r = int(h[0:2], 16); g = int(h[2:4], 16); b = int(h[4:6], 16)
            r = int(r + (255 - r) * frac)
            g = int(g + (255 - g) * frac)
            b = int(b + (255 - b) * frac)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    def _open_url_platform_fallback(self, url: str) -> bool:
        candidates = [
            "windows-default", "chrome", "msedge", "firefox", "safari", "opera"
        ]
        for name in candidates:
            try:
                b = webbrowser.get(name)
                if b.open(url, new=2):
                    return True
            except Exception:
                pass
        try:
            if sys.platform.startswith("win"):
                os.startfile(url)  # type: ignore[attr-defined]
                return True
        except Exception:
            pass
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", url], check=True)
                return True
        except Exception:
            pass
        try:
            if sys.platform.startswith("linux"):
                if shutil.which("xdg-open"):
                    subprocess.run(["xdg-open", url], check=True)
                    return True
                if shutil.which("gio"):
                    subprocess.run(["gio", "open", url], check=True)
                    return True
        except Exception:
            pass
        return False

    def _speak(self, text: str):
        try:
            from utils import speak_text as _speak_text
            _speak_text(text)
            return
        except Exception:
            pass
        try:
            import tts_driver as tts
            tts.speak(text, lang=getattr(self, "language", "en"))
        except Exception:
            pass

    def _msg_link_fail_voice(self) -> str:
        lang = (getattr(self, "language", "en") or "en").lower()
        return {
            "en": "I couldn’t open that link automatically. I’ve copied it—just paste it into your browser.",
            "hi": "मैं यह लिंक अपने-आप नहीं खोल पाई। मैंने इसे कॉपी कर दिया है—कृपया इसे अपने ब्राउज़र में पेस्ट करें।",
            "de": "Ich konnte den Link nicht automatisch öffnen. Ich habe ihn kopiert — bitte im Browser einfügen.",
            "fr": "Je n’ai pas pu ouvrir ce lien automatiquement. Je l’ai copié — collez-le dans votre navigateur.",
            "es": "No pude abrir el enlace automáticamente. Lo copié — pégalo en tu navegador.",
        }.get(lang, 
              "I couldn’t open that link automatically. I’ve copied it—just paste it into your browser.")

    def _msg_link_fail_ui(self, url: str) -> str:
        lang = (getattr(self, "language", "en") or "en").lower()
        txts = {
            "en": "Couldn’t open link. Copied to clipboard:\n{url}",
            "hi": "लिंक नहीं खुला। क्लिपबोर्ड में कॉपी कर दिया है:\n{url}",
            "de": "Link konnte nicht geöffnet werden. In die Zwischenablage kopiert:\n{url}",
            "fr": "Impossible d’ouvrir le lien. Copié dans le presse-papiers :\n{url}",
            "es": "No se pudo abrir el enlace. Copiado al portapapeles:\n{url}",
        }
        return (txts.get(lang, txts["en"])).format(url=url)

    def _on_link_open_failed(self, url: str):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.root.update()
        except Exception:
            pass
        if _interaction_gate_open():
            self._speak(self._msg_link_fail_voice())
        try:
            self.show_message("", self._msg_link_fail_ui(url))
        except Exception:
            pass

    def _crop_from_bg(self, x, y, w, h):
        try:
            box = (int(x), int(y), int(x + w), int(y + h))
            patch = self._bg_pil.crop(box)
            return ImageTk.PhotoImage(patch)
        except Exception:
            return None

    def _refresh_bg_patches(self):
        try:
            self.root.update_idletasks()
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()

            lx = self.logo_canvas.winfo_rootx() - rx
            ly = self.logo_canvas.winfo_rooty() - ry
            lw = max(1, self.logo_canvas.winfo_width())
            lh = max(1, self.logo_canvas.winfo_height())
            p1 = self._crop_from_bg(lx, ly, lw, lh)
            if p1:
                self.logo_canvas.itemconfig(self.logo_bg_item, image=p1)
                self.logo_canvas._bg_patch_ref = p1

            mx = self.mic_canvas.winfo_rootx() - rx
            my = self.mic_canvas.winfo_rooty() - ry
            mw = max(1, self.mic_canvas.winfo_width())
            mh = max(1, self.mic_canvas.winfo_height())
            p2 = self._crop_from_bg(mx, my, mw, mh)
            if p2:
                self.mic_canvas.itemconfig(self.mic_bg_item, image=p2)
                self.mic_canvas._bg_patch_ref = p2
        except Exception:
            pass

    def _ensure_above_taskbar(self):
        try:
            wa = _windows_work_area_for_root(self.root)
            if wa:
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
                return

            if IS_LINUX_OR_WSL:
                sh = self.root.winfo_screenheight()
                safe = 72
                geo = self.root.winfo_geometry()
                parts = geo.split("+")
                w, h = map(int, parts[0].split("x"))
                x = int(parts[1]); y = int(parts[2])
                if (y + h) > (sh - safe):
                    y = max(8, sh - h - safe)
                    self.root.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _set_alpha(self, a: float):
        try:
            self.root.wm_attributes("-alpha", float(a))
        except Exception:
            pass

    def _reveal_window_fade_in(self):
        self._set_alpha(0.0)
        self.root.deiconify()
        self.root.update_idletasks()
        margin = 120 if IS_LINUX_OR_WSL else 64
        _place_main_window_safely(self.root, y_percent=0.26, bottom_margin=margin)
        if IS_LINUX_OR_WSL:
            _linux_center_after_map(self.root)
        self.root.after(260, lambda: (self._set_alpha(1.0), self._ensure_above_taskbar()))

    def _animate_logo_and_sparkles(self):
        if self._closing:
            return
        try:
            if not self.logo_canvas or not self.logo_canvas.winfo_exists():
                return
        except Exception:
            return

        now = time.perf_counter()
        dt = max(0.0, min(0.1, now - getattr(self, "_last_anim_t", now)))
        self._last_anim_t = now

        face_speed = 60.0
        ring_speed = 60.0

        self.face_angle = (self.face_angle + face_speed * dt) % 360.0
        rad = math.radians(self.face_angle)
        cx, cy = self.face_center
        fx = cx + self.face_orbit_r * math.cos(rad)
        fy = cy + self.face_orbit_r * math.sin(rad)
        try:
            self.logo_canvas.coords(self.face_id, fx, fy)
        except tk.TclError:
            return

        self.sparkle_angle = (self.sparkle_angle + ring_speed * dt) % 360.0
        try:
            for i, s in enumerate(self.sparkles):
                ang = math.radians(self.sparkle_angle + (360 / len(self.sparkles)) * i)
                cx = self.face_center[0] + self.sparkle_r * math.cos(ang)
                cy = self.face_center[1] + self.sparkle_r * math.sin(ang)
                size = 4 + 2 * (0.5 + 0.5 * math.sin(self.sparkle_angle + i))
                pts = _star_points(cx, cy, size, size * 0.45, points=4, angle_offset=ang / 2)
                self.logo_canvas.coords(s, *pts)
                self.logo_canvas.itemconfig(s, fill=self.glow_color, outline=self.glow_color)
        except tk.TclError:
            return

        if not self.animation_ready:
            self._anim_started_frames += 1
            if self._anim_started_frames >= 3:
                self.animation_ready = True

        self._after(33, self._animate_logo_and_sparkles)

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
            self.ghost_scroll.set_accent(self.glow_color)
        except Exception: pass

        for tag in list(self._url_tag_map.keys()):
            try:
                self.text_display.tag_config(tag, foreground=self.glow_color, underline=True)
            except Exception:
                pass
        self._update_status_pills()
        self.update_typing_label()

        try:
            f = self._tip_font()
            for tip in (self.tip_math, self.tip_plot, self.tip_physics, self.tip_chemistry):
                tip.set_font_family(f)
                tip.set_fg(self.glow_color)
            self.tip_math.set_text(self._tip("math"))
            self.tip_plot.set_text(self._tip("plot"))
            self.tip_physics.set_text(self._tip("physics"))
            self.tip_chemistry.set_text(self._tip("chemistry"))
        except Exception:
            pass

    def _tip(self, key: str) -> str:
        lang = (self.language or "en").split("-")[0].lower()
        return (TIP_TEXTS.get(lang) or TIP_TEXTS["en"]).get(key, "")

    def _tip_font(self) -> str:
        if (self.language or "en").startswith("hi"):
            if os.name == "nt":
                return "Nirmala UI"
            else:
                return "Noto Sans Devanagari"
        return "Consolas"

    def _pulse_checkbox_glow(self):
        bases = [self.checkbox_canvas.bbox(oid) for oid in getattr(self, "_glow_ids", [])]
        min_r, max_r = 3, 8
        radius = [min_r]; growing = [True]

        def animate():
            try:
                if not self.root.winfo_exists() or not self.checkbox_canvas.winfo_exists():
                    return
            except Exception:
                return
            if growing[0]:
                radius[0] += 0.5
                if radius[0] >= max_r:
                    growing[0] = False
            else:
                radius[0] -= 0.5
                if radius[0] <= min_r:
                    growing[0] = True
            for i, base in enumerate(bases):
                if not base:
                    continue
                x0, y0, x1, y1 = base
                try:
                    self.checkbox_canvas.coords(
                        self._glow_ids[i],
                        x0 - radius[0], y0 - radius[0],
                        x1 + radius[0], y1 + radius[0]
                    )
                except Exception:
                    return
            try:
                self.root.after(80, animate)
            except Exception:
                pass

        try:
            self.root.after(800, animate)
        except Exception:
            pass

    def _compact_linux_ui(self):
        if not IS_LINUX_OR_WSL:
            return
        try:
            self.logo_canvas.config(width=128, height=128)
            try: self.logo_canvas.pack_configure(pady=(4, 0))
            except Exception: pass
            self.face_center = (64, 64)
            self.sparkle_r = 54
            try:
                self.logo_canvas.coords(self.face_id, *self.face_center)
            except Exception:
                pass
            try: self.status_bar.pack_configure(pady=(0, 4))
            except Exception: pass
            self.checkbox_canvas.config(height=36)
            try: self.checkbox_canvas.pack_configure(pady=(0, 6))
            except Exception: pass
            for cb in getattr(self, "_cb_widgets", []):
                try: cb.config(font=("Consolas", 10, "bold"))
                except Exception: pass
            self.text_display.config(height=14, width=80)
            self.input_entry.config(width=54, font=("Consolas", 10))
            self.send_button.config(width=10)
            self.clear_button.config(width=10)
            try: self.mic_canvas.pack_configure(pady=0)
            except Exception: pass
            self.root.update_idletasks()
            _fit_linux_size(self.root, bottom_margin=72)
        except Exception:
            pass

    def _dispatch_in_background(self, user_text: str):
        def worker():
            if callable(getattr(self, "external_callback", None)):
                try:
                    self.external_callback(user_text)
                    return
                except Exception as e:
                    try:
                        self.root.after(0, lambda: self.show_message("Nova", f"Routing error: {e}"))
                    except Exception:
                        pass
            try:
                from core_engine import process_command
                process_command(
                    user_text,
                    is_math_override=self.math_mode_var.get(),
                    is_plot_override=self.plot_mode_var.get(),
                    is_physics_override=self.physics_mode_var.get(),
                    is_chemistry_override=self.chemistry_mode_var.get(),
                )
            except TypeError:
                from core_engine import process_command
                process_command(
                    user_text,
                    is_math_override=self.math_mode_var.get(),
                    is_plot_override=self.plot_mode_var.get(),
                    is_physics_override=self.physics_mode_var.get(),
                )
            except Exception as e:
                try:
                    self.root.after(0, lambda: self.show_message("Nova", f"Unhandled error: {e}"))
                except Exception:
                    pass
        threading.Thread(target=worker, daemon=True).start()

    def _on_send(self, *_):
        try:
            user_text = (self.input_entry.get() or "").strip()
        except Exception:
            user_text = ""

        if not user_text:
            return

        try:
            self.input_entry.delete(0, tk.END)
        except Exception:
            pass

        try:
            self.show_message("You", user_text)
        except Exception:
            pass

        # Let typed text satisfy any waiting follow-up
        try:
            from followup import submit_typed_followup
            submit_typed_followup(user_text)
        except Exception:
            pass

        self._dispatch_in_background(user_text)

        try:
            self.input_entry.focus_set()
        except Exception:
            pass

    def _on_clear(self):
        self.text_display.delete('1.0', tk.END)

    def _normalize_url(self, u: str) -> str:
        u = u.strip()
        while u and u[-1] in self.TRAIL_PUNCT:
            u = u[:-1]
        if u.lower().startswith("www."):
            u = "http://" + u
        return u

    def _add_url_tag(self, start_idx: str, end_idx: str, url: str):
        tag = f"url_{len(self._url_tag_map)+1}"
        self._url_tag_map[tag] = url
        self.text_display.tag_add(tag, start_idx, end_idx)
        self.text_display.tag_config(tag, foreground=self.glow_color, underline=True)

        def _enter(_e, t=tag):
            self.text_display.config(cursor="hand2")
            try:
                hover = self._mix_to_white(self.glow_color, 0.50)
            except Exception:
                hover = self.glow_color
            self.text_display.tag_config(t, foreground=hover)

        def _leave(_e, t=tag):
            self.text_display.config(cursor="xterm")
            self.text_display.tag_config(t, foreground=self.glow_color)

        self.text_display.tag_bind(tag, "<Enter>", _enter)
        self.text_display.tag_bind(tag, "<Leave>", _leave)

        def _click(e, u=url):
            self._open_url_debounced(u)
            return "break"

        self.text_display.tag_bind(tag, "<Button-1>", _click)
        self.text_display.tag_bind(tag, "<Double-Button-1>", _click)

    def _open_url_debounced(self, url: str, debounce_ms: int = 500):
        if not url:
            return
        now = time.monotonic()
        last_t = getattr(self, "_last_link_open_time", 0.0)
        last_u = getattr(self, "_last_link_open_url", "")
        if url == last_u and (now - last_t) < (debounce_ms / 1000.0):
            return
        self._last_link_open_time = now
        self._last_link_open_url  = url

        success = False
        try:
            success = bool(webbrowser.open(url, new=2))
        except Exception:
            success = False
        if not success:
            try:
                success = self._open_url_platform_fallback(url)
            except Exception:
                success = False
        if not success:
            self._on_link_open_failed(url)

    def _insert_with_links(self, text: str):
        i = 0
        for m in self.URL_RE.finditer(text or ""):
            start, end = m.span()
            url_raw = m.group(0)
            if start > i:
                self.text_display.insert(tk.END, text[i:start])
            clean = self._normalize_url(url_raw)
            before = self.text_display.index(tk.END)
            self.text_display.insert(tk.END, url_raw)
            after  = self.text_display.index(tk.END)
            self._add_url_tag(before, after, clean)
            i = end
        if i < len(text or ""):
            self.text_display.insert(tk.END, text[i:])

    def _accent_emoji_for_lang(self) -> str:
        lang = (getattr(self, "language", "en") or "en").lower()
        return {
            "en": "🔵",
            "hi": "🟠",
            "fr": "🔵",
            "de": "🟢",
            "es": "🔴",
        }.get(lang, "🔵")

    def _user_display_name(self) -> str:
        try:
            from utils import get_user_name
            name = get_user_name()
        except Exception:
            name = None
        if not name:
            name = getattr(self, "user_name", None)
        return name or "You"

    def show_message(self, who: str, text: str):
        w = (who or "").strip()
        key = w.casefold()
        is_nova = (key == "nova")
        user_aliases = {"", "you", "me", "user"}
        name = "Nova" if is_nova else (self._user_display_name() if key in user_aliases else w)
        icon = self._accent_emoji_for_lang() if is_nova else "👤"
        prefix = f"{icon} {name}: "
        self.text_display.insert(tk.END, prefix)
        self._insert_with_links(text)
        self.text_display.insert(tk.END, "\n")
        self.text_display.see(tk.END)

    def update_typing_label(self):
        from utils import get_wake_mode
        mode_texts = {
            "en": {"on": "🎤 Say 'Hey Nova' or type below.", "off": "🎤 Click the mic to talk, or type below."},
            "hi": {"on": "🎤 'हे नोवा' बोलें या नीचे टाइप करें।", "off": "🎤 बोलने के लिए माइक पर क्लिक करें, या टाइप करें।"},
            "fr": {"on": "🎤 Dites « Hey Nova » ou tapez ci-dessous.", "off": "🎤 Cliquez sur le micro pour parler, ou tapez ci-dessous."},
            "de": {"on": "🎤 Sag „Hey Nova“ oder tippe unten.", "off": "🎤 Klicke auf das Mikro, um zu sprechen, oder tippe unten."},
            "es": {"on": "🎤 Di «Hey Nova» o escribe abajo.", "off": "🎤 Haz clic en el micrófono para hablar, o escribe abajo."}
        }
        is_on = bool(get_wake_mode())
        key = "on" if is_on else "off"
        msg = mode_texts.get(self.language, mode_texts["en"])[key]
        self.typing_label.config(text=msg)

    def set_wake_label(self, is_on: bool):
        try:
            self.wake_button.config(text=("Wake Mode: ON" if is_on else "Wake Mode: OFF"))
        except Exception:
            pass

    def _toggle_wake_mode(self):
        from utils import get_wake_mode, set_wake_mode
        if get_wake_mode():
            set_wake_mode(False)
            try:
                from wake_word_listener import stop_wake_listener_thread
                stop_wake_listener_thread()
            except Exception:
                pass
            self.set_wake_label(False)
            self.update_mic_icon(False)
            self.show_message("Nova", "Wake mode disabled. Click the mic to talk or type below.")
        else:
            set_wake_mode(True)
            try:
                from wake_word_listener import start_wake_listener_thread
                start_wake_listener_thread()
            except Exception:
                pass
            self.set_wake_label(True)
            self.update_mic_icon(True)
            self.show_message("Nova", "Wake mode enabled. Say 'Hey Nova' to begin.")
        self.update_typing_label()

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
        if not self.glow_active or self._closing:
            return
        try:
            if not self.mic_canvas or not self.mic_canvas.winfo_exists():
                return
        except Exception:
            return

        try:
            if self.pulse_circle:
                self.mic_canvas.delete(self.pulse_circle)
                self.pulse_circle = None
            r = self.pulse_radius
            self.pulse_circle = self.mic_canvas.create_oval(
                20 - r, 20 - r, 20 + r, 20 + r, outline=self.glow_color, width=2
            )
        except tk.TclError:
            return

        if self.pulse_growing:
            self.pulse_radius += 1
            if self.pulse_radius >= 28:
                self.pulse_growing = False
        else:
            self.pulse_radius -= 1
            if self.pulse_radius <= 22:
                self.pulse_growing = True

        self._after(80, self._pulse_animation)

    def _start_hover_glow(self, event=None):
        if self.hover_circle is None:
            self.hover_circle = self.mic_canvas.create_oval(5, 5, 35, 35, outline=self.glow_color, width=1)

    def _stop_hover_glow(self, event=None):
        if self.hover_circle:
            self.mic_canvas.delete(self.hover_circle)
            self.hover_circle = None

    # -----------------------------
    # PUSH-ONCE-TO-TALK CHANGES
    # -----------------------------

    def _msg_listening(self) -> str:
        try:
            return _multilang(
                en="Listening… (push once to talk)",
                hi="सुन रही हूँ… (एक बार टैप करें)",
                fr="À l’écoute… (appuyez une fois)",
                es="Escuchando… (pulsa una vez)",
                de="Höre zu… (einmal tippen)",
            )
        except Exception:
            return "Listening… (push once to talk)"

    def _msg_already_listening(self) -> str:
        try:
            return _multilang(
                en="Already listening — just speak.",
                hi="पहले से सुन रही हूँ — बोलिए।",
                fr="J’écoute déjà — parlez.",
                es="Ya estoy escuchando — habla.",
                de="Ich höre bereits zu — sprich einfach.",
            )
        except Exception:
            return "Already listening — just speak."

    def _on_mic_click(self, _evt=None):
        # Allow push-to-talk regardless of Wake Mode.
        if getattr(self, "_ptt_busy", False):
            # User clicked again while recording — gentle feedback
            try:
                self.show_message("Nova", self._msg_already_listening())
            except Exception:
                pass
            return

        self._ptt_busy = True

        # Immediate visible feedback so users know something happened
        try:
            self.show_message("Nova", self._msg_listening())
        except Exception:
            pass

        # Optional: if you have a mic enable/disable hook, disable during PTT
        try:
            if hasattr(self, "set_mic_enabled"):
                self.set_mic_enabled(False)
        except Exception:
            pass

        self.start_pulse()

        threading.Thread(target=self._ptt_capture_once, daemon=True).start()

    def _ptt_capture_once(self):
        from utils import listen_command, get_wake_mode
        paused = False
        # Pause wake detection during PTT to avoid double triggers
        try:
            if get_wake_mode():
                try:
                    from utils import pause_wake_detection
                    pause_wake_detection(True)  # if helper exists
                    paused = True
                except Exception:
                    paused = False
        except Exception:
            pass

        try:
            text = ""
            try:
                text = listen_command(skip_tts_gate=True)
            except TypeError:
                # older signature
                text = listen_command()
        except Exception:
            text = ""

        def _finish(t=text, _paused=paused):
            # Resume wake detection if we paused it
            if _paused:
                try:
                    from utils import resume_wake_detection
                    resume_wake_detection()
                except Exception:
                    pass
            self._ptt_handle_result(t)

        self.root.after(0, _finish)

    def _ptt_handle_result(self, text: str):
        self.stop_pulse()
        self._ptt_busy = False

        # Optional: re-enable mic button if you disabled it above
        try:
            if hasattr(self, "set_mic_enabled"):
                self.set_mic_enabled(True)
        except Exception:
            pass

        if not text:
            try:
                import utils
                if (
                    getattr(utils, "NAME_CAPTURE_IN_PROGRESS", False)
                    or getattr(self, "language_capture_active", False)
                    or getattr(self, "name_capture_active", False)
                    or getattr(utils, "LANGUAGE_FLOW_ACTIVE", False)
                ):
                    return
            except Exception:
                pass
            if time.time() < getattr(utils, "SUPPRESS_SR_TTS_PROMPTS_UNTIL", 0.0):
                return
            self.show_message("Nova", "Sorry, I didn't catch that. Could you please repeat?")
            return

        self.show_message("You", text)

        # Let typed/voice result satisfy any waiting follow-up
        try:
            from followup import submit_typed_followup
            submit_typed_followup(text)
        except Exception:
            pass
        
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

    # -----------------------------

    def _url_under_pointer(self, x, y) -> str | None:
        idx = self.text_display.index(f"@{x},{y}")
        for tag in self.text_display.tag_names(idx):
            if tag.startswith("url_"):
                return self._url_tag_map.get(tag)
        return None

    def _on_right_click(self, event):
        try:
            self._ctx_menu.unpost()
        except Exception:
            pass
        self._ctx_menu = tk.Menu(self.root, tearoff=0)
        self._ctx_menu.add_command(label="Copy", command=lambda: self.text_display.event_generate("<<Copy>>"))
        url = self._url_under_pointer(event.x, event.y)
        if url:
            self._ctx_menu.add_separator()
            self._ctx_menu.add_command(label="Open link", command=lambda u=url: self._open_url_debounced(u))
            self._ctx_menu.add_command(label="Copy link", command=lambda u=url: (self.root.clipboard_clear(), self.root.clipboard_append(u)))
        try:
            self._ctx_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._ctx_menu.grab_release()

    def _start_idle_check(self):  # placeholder
        pass

    def mainloop(self):
        self.root.mainloop()

    def _after(self, ms: int, fn):
        aid = self.root.after(ms, fn)
        self._after_ids.add(aid)
        return aid

    def _cancel_all_after(self):
        for aid in list(self._after_ids):
            try:
                self.root.after_cancel(aid)
            except Exception:
                pass
            self._after_ids.discard(aid)

    def destroy(self):
        self._closing = True
        self._cancel_all_after()
        try:
            from tts_driver import get_tts
            get_tts().stop()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def hide(self):
        try: self.root.withdraw()
        except Exception: pass

    def show(self):
        try: self.root.deiconify()
        except Exception: pass

_nova_gui = None
def get_gui():
    global _nova_gui
    if _nova_gui is None:
        _nova_gui = NovaGUI()
    return _nova_gui

def gui_if_ready():
    return _nova_gui

_MODE_META = {
    "math": ("Math Mode", "🧠"),
    "plot": ("Plot Mode", "📈"),
    "physics": ("Physics Mode", "⚛️"),
    "chemistry": ("Chemistry Mode", "🧪"),
}

def _wait_and_open_solution(self, mode: str, emoji: str, answer_text: str):
    # Gate until TTS / language flow is idle, then open the window
    try:
        from utils import LANGUAGE_FLOW_ACTIVE, tts_busy
        is_busy = bool(LANGUAGE_FLOW_ACTIVE or (tts_busy and tts_busy.is_set()))
    except Exception:
        is_busy = False

    if not is_busy:
        try:
            if self._solution_popup and self._solution_popup.winfo_exists():
                self._solution_popup.destroy()
        except Exception:
            pass
        self._solution_popup = _SolutionPopup(self.root, mode=mode, emoji=emoji, first_answer=answer_text)
    else:
        # check again shortly
        self.root.after(120, lambda: self._wait_and_open_solution(mode, emoji, answer_text))


def show_solution(self, mode: str, emoji: str, answer_text: str):
    # SHOW (open popup only after TTS/language-flow is idle)
    self._wait_and_open_solution(mode, emoji, answer_text)


def append_mode_solution(mode_key: str, text: str):
    g = gui_if_ready()
    if not g: return
    try:
        g.root.after(0, lambda: g.append_solution(text))
    except Exception:
        pass

class _NovaGUIProxy:
    @property
    def root(self):
        g = gui_if_ready()
        if g:
            return g.root
        class _NoOp:
            def after(self, *_args, **_kwargs): pass
        return _NoOp()

nova_gui = _NovaGUIProxy()

import utils
def _gui_solution_bridge(channel, payload):
    g = gui_if_ready()
    MODE_MAP = _MODE_META
    ch = str(channel or "").strip().lower()

    if ch not in MODE_MAP:
        txt = payload if isinstance(payload, str) else (payload or {}).get("html", "")
        if txt and g:
            try:
                g.root.after(0, lambda: g.show_message("Nova", txt))
            except Exception:
                pass
        return

    if isinstance(payload, str):
        html = payload
        actions = {}
        ctx = {}
        action_hint = None
    else:
        html        = (payload or {}).get("html", "")
        actions     = (payload or {}).get("actions") or {}
        ctx         = (payload or {}).get("ctx") or {}
        action_hint = (payload or {}).get("action")

    if not html or not g:
        return

    name, emoji = MODE_MAP[ch]

    def _apply():
        if action_hint == "append":
            g.append_solution(html)
        else:
            if getattr(g, "_solution_popup", None) and g._solution_popup.winfo_exists():
                g.append_solution(html)
            else:
                g.show_solution(mode=name, emoji=emoji, answer_text=html)

        primary = actions.get("primary")
        chips   = actions.get("chips") or []
        inline  = actions.get("inline")
        original_text = ctx.get("original_text", "") or (payload or {}).get("question", "")

        primary_label = None
        primary_cmd   = None
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
                    try:
                        g.append_solution(f"(Could not plot: {e})")
                    except Exception:
                        pass
            primary_cmd = _on_plot_it

        for chip in chips:
            lab = chip.get("label") if isinstance(chip, dict) else str(chip)
            if not lab:
                continue
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
                        try:
                            g.append_solution(f"(Could not plot: {e})")
                        except Exception:
                            pass
                try:
                    if hasattr(g._solution_popup, "add_inline_button"):
                        g._solution_popup.add_inline_button(inline_label, _on_plot_it_inline, anchor_text=anchor_text)
                    elif hasattr(g._solution_popup, "set_actions"):
                        g._solution_popup.set_actions(inline_label, _on_plot_it_inline, [], [])
                except Exception:
                    pass

    try:
        g.root.after(0, _apply)
    except Exception:
        pass

set_gui_callback(_gui_solution_bridge)
