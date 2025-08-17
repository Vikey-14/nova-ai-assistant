# demo_solution_popup_v13.py
import os, math, tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

# ✅ use the app-wide resolver so it works in dev + frozen exe
from utils import resource_path

# --- Theme ---
BG="#0f0f0f"; CARD_BG="#131313"; TEXT_FG="#e8e8e8"; SOFT_FG="#b4b4b4"
DIVIDER="#dcdcdc"; ACCENT="#ffd166"; DIVIDER_CHAR="━"

def default_documents_dir():
    home = os.path.expanduser("~")
    for name in ("Documents","Documenti","Dokumente","Mes documents","Documentos"):
        d = os.path.join(home, name)
        if os.path.isdir(d): return d
    fallback = os.path.abspath(os.path.join(".", "exports", "solutions"))
    os.makedirs(fallback, exist_ok=True)
    return fallback

# ---------------- Nova badge (right side) ----------------
class NovaBadge(tk.Canvas):
    def __init__(self, master, size=40, accent=ACCENT,
                 fade_strength=0.80, face_bleach=0.28,
                 orbit_speed=0.55, precess_speed=0.035,
                 ellipticity=0.88, swell_strength=0.06,
                 shimmer_strength=0.06, **kw):
        super().__init__(master, width=size, height=size, bg=BG, highlightthickness=0, **kw)
        self.size = size
        self.accent = accent
        self.cx = self.cy = size // 2

        self.fade_strength   = fade_strength
        self.face_bleach     = face_bleach
        self.orbit_speed     = orbit_speed
        self.precess_speed   = precess_speed
        self.ellipticity     = ellipticity
        self.swell_strength  = swell_strength
        self.shimmer_strength= shimmer_strength

        self._pulse_phase = 0.0
        self._precess     = 0.0

        # Load face (fixed size) – safe fallback if asset missing
        self._pil_base = None
        try:
            pil = Image.open(resource_path(os.path.join("assets","nova_face.png"))).convert("RGBA")
            target_h = int(size * 0.78)
            r = target_h / pil.height
            self._pil_base = pil.resize((int(pil.width * r), target_h), Image.LANCZOS)
        except Exception:
            pass
        self._white_img = Image.new("RGBA", self._pil_base.size, (255,255,255,255)) if self._pil_base else None

        # Halo
        self.halo_id = self.create_oval(0, 0, 0, 0, outline=self.accent, width=2)
        self.itemconfig(self.halo_id, fill="")

        # Stars (two swarms)
        self.N = 6
        self.base_orbit_r = (size / 2) - 6
        self.stars_a, self.stars_b = [], []
        for i in range(self.N):
            pa = self.create_polygon(0,0,0,0,0,0,0,0, fill=self.accent, outline=self.accent, width=1)
            pb = self.create_polygon(0,0,0,0,0,0,0,0, fill=self.accent, outline=self.accent, width=1)
            phase = i * (2*math.pi / self.N)
            self.stars_a.append({"poly": pa, "phase": phase})
            self.stars_b.append({"poly": pb, "phase": phase})

        # Face holder
        self.img_id = None
        self._img_tk = None
        if self._pil_base:
            self._set_face_tint(bleach_frac=0.0)
            self.img_id = self.create_image(self.cx, self.cy, image=self._img_tk)
            self.tag_raise(self.img_id)

        self._fps_ms = 16
        self.after(self._fps_ms, self._animate)

    @staticmethod
    def _mix_to_white(hex_color, frac):
        r = int(hex_color[1:3], 16); g = int(hex_color[3:5], 16); b = int(hex_color[5:7], 16)
        r = int(r + (255 - r) * frac)
        g = int(g + (255 - g) * frac)
        b = int(b + (255 - b) * frac)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _star_points(self, cx, cy, r_out, r_in, angle_offset=0.0):
        pts = []
        for k in range(8):
            ang = angle_offset + k * (math.pi/4.0)
            r = r_out if (k % 2 == 0) else r_in
            pts.extend([cx + r * math.cos(ang), cy + r * math.sin(ang)])
        return pts

    def _set_face_tint(self, bleach_frac: float):
        if not (self._pil_base and self._white_img): return
        pil = Image.blend(self._pil_base, self._white_img,
                          max(0.0, min(1.0, bleach_frac)) * self.face_bleach)
        self._img_tk = ImageTk.PhotoImage(pil)
        if self.img_id:
            self.itemconfig(self.img_id, image=self._img_tk)

    def _animate(self):
        self._pulse_phase = (self._pulse_phase + 0.12) % (2 * math.pi)
        self._precess     = (self._precess     + self.precess_speed) % (2 * math.pi)

        luma = 0.5 + 0.5 * math.sin(self._pulse_phase)
        p = self.fade_strength * luma
        base_color = self._mix_to_white(self.accent, p)

        halo_r = (self.size * 0.42)
        self.coords(self.halo_id, self.cx - halo_r, self.cy - halo_r, self.cx + halo_r, self.cy + halo_r)
        self.itemconfig(self.halo_id, outline=base_color, width=2)

        R0 = self.base_orbit_r
        Rx = R0 * (1.00 + self.swell_strength * math.sin(self._pulse_phase))
        Ry = R0 * (self.ellipticity + self.swell_strength * math.cos(self._pulse_phase))

        t = self._pulse_phase * self.orbit_speed
        size_scale = 1.0 + self.shimmer_strength * (2.0 * luma - 1.0)
        angle_offset = math.pi / 8.0

        def draw_swarm(stars, base_tilt, sign):
            tilt = base_tilt + self._precess
            ct, st = math.cos(tilt), math.sin(tilt)
            for s in stars:
                theta = sign * t + s["phase"]
                x = Rx * math.cos(theta); y = Ry * math.sin(theta)
                xr = x * ct - y * st; yr = x * st + y * ct
                cx, cy = (self.cx + xr, self.cy + yr)
                r_out = 2.4 * size_scale
                r_in  = r_out * 0.52
                self.coords(s["poly"], *self._star_points(cx, cy, r_out, r_in, angle_offset))
                self.itemconfig(s["poly"], fill=base_color, outline=base_color)

        draw_swarm(self.stars_a, base_tilt= math.pi/4.0,  sign=+1.0)
        draw_swarm(self.stars_b, base_tilt=-math.pi/4.0,  sign=-1.0)

        self._set_face_tint(bleach_frac=p)
        self.after(self._fps_ms, self._animate)


# ---------------- Solution popup ----------------
class SolutionPopup(tk.Toplevel):
    def __init__(self, master, mode="Chemistry", emoji="🧪", first_answer="", **kw):
        super().__init__(master, **kw)
        self.title("Solution")
        self.configure(bg=BG)
        self.geometry("920x660+180+120")
        self.minsize(680, 480)

        self.mode = mode
        self.emoji = emoji
        self.accent = ACCENT

        self._build_header()
        self._build_body()
        self._build_actions()

        self.start_new_solution_block(first_answer or "...")

        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-s>", lambda e: self._save_txt())
        self.bind("<Command-s>", lambda e: self._save_txt())
        self.bind("<Control-c>", lambda e: self._copy_all())
        self.bind("<Command-c>", lambda e: self._copy_all())

        try:
            self.attributes("-alpha", 0.0)
            self.after(10, self._fade_in)
        except Exception:
            pass

    def _build_header(self):
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="x", padx=12, pady=(10,0))

        left = tk.Frame(wrap, bg=BG); left.pack(side="left")
        self.title_label = tk.Label(
            left, text=f"{self.emoji} {self.mode} Mode",
            bg=BG, fg=self.accent, font=("Consolas", 17, "bold")
        )
        self.title_label.pack(side="left")

        tk.Frame(wrap, bg=BG).pack(side="left", expand=True, fill="x")
        NovaBadge(wrap, size=42, accent=self.accent).pack(side="right")

        tk.Frame(self, bg="#1b1b1b", height=1).pack(fill="x", padx=12, pady=(10,8))

        self._pulse_phase = 0.0
        self._pulse_title_color()

    def _build_body(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=(0,8))

        card = tk.Frame(body, bg=CARD_BG); card.pack(fill="both", expand=True)

        scroll = tk.Scrollbar(card, orient="vertical")
        self.text = tk.Text(
            card, wrap="word",
            bg=CARD_BG, fg=TEXT_FG, insertbackground=TEXT_FG,
            font=("Consolas", 13), bd=0, padx=16, pady=16,
            yscrollcommand=scroll.set
        )
        scroll.config(command=self.text.yview)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        self.text.tag_config("divider1", foreground=DIVIDER, font=("Consolas", 12, "bold"))
        self.text.tag_config("divider2", foreground=DIVIDER, font=("Consolas", 12, "bold"))
        self.text.config(state="disabled")

    def _build_actions(self):
        bar = tk.Frame(self, bg=BG); bar.pack(fill="x", padx=12, pady=(0,10))
        tk.Label(bar, text="ESC to close • Ctrl/Cmd+C to copy • Ctrl/Cmd+S to save",
                 bg=BG, fg=SOFT_FG, font=("Consolas", 11)).pack(side="left")

        btns = tk.Frame(bar, bg=BG); btns.pack(side="right")
        def btn(t, fn):
            b = tk.Button(btns, text=t, width=14, bg="#202020", fg="white",
                          font=("Consolas", 12, "bold"), command=fn)
            b.pack(side="left", padx=6); return b
        btn("Copy All", self._copy_all)
        btn("Save Solution", self._save_txt)
        btn("Close", self.destroy)

    # ---- Helpers ----
    def _fade_in(self, a=0.0):
        a = round(a + 0.05, 2)
        if a <= 1.0:
            try:
                self.attributes("-alpha", a)
                self.after(12, self._fade_in, a)
            except Exception:
                pass

    def _pulse_title_color(self):
        self._pulse_phase = (self._pulse_phase + 0.12) % (2 * math.pi)
        p = 0.60 * (0.5 + 0.5 * math.sin(self._pulse_phase))
        def mix(hx, frac):
            r = int(hx[1:3], 16); g = int(hx[3:5], 16); b = int(hx[5:7], 16)
            r = int(r + (255 - r) * frac); g = int(g + (255 - g) * frac); b = int(b + (255 - b) * frac)
            return f"#{r:02x}{g:02x}{b:02x}"
        self.title_label.config(fg=mix(ACCENT, p))
        self.after(50, self._pulse_title_color)

    def _insert_divider(self):
        line = DIVIDER_CHAR * 72 + "\n"
        self.text.insert("end", "\n", ())
        self.text.insert("end", line, ("divider1",))
        self.text.insert("end", line, ("divider2",))
        self.text.insert("end", "\n", ())

    def start_new_solution_block(self, txt: str):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        if txt: self.text.insert("end", txt.rstrip() + "\n")
        self.text.config(state="disabled")
        self.text.see("end")

    def append_followup(self, txt: str):
        self.text.config(state="normal")
        self._insert_divider()
        if txt: self.text.insert("end", txt.rstrip() + "\n")
        self.text.config(state="disabled")
        self.text.see("end")

    def _copy_all(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.text.get("1.0", "end-1c"))
        except Exception as e:
            messagebox.showerror("Copy failed", str(e))

    def _save_txt(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text","*.txt")],
            initialdir=default_documents_dir(),
            initialfile="solution.txt",
            title="Save solution as..."
        )
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text.get("1.0", "end-1c"))
        except Exception as e:
            messagebox.showerror("Save failed", str(e))


# ---- Demo run ----
if __name__ == "__main__":
    root = tk.Tk(); root.withdraw()

    demo = SolutionPopup(
        root, mode="Chemistry", emoji="🧪",
        first_answer=(
            "pH of 25 mM HCl\n\n"
            "Given:\n"
            "  Strong monoprotic acid (HCl)\n"
            "  Concentration c = 0.025 mol/L\n\n"
            "Steps:\n"
            "  1) For strong acids, [H+] ≈ c\n"
            "  2) pH = −log10([H+]) = −log10(0.025)\n"
            "  3) pH ≈ 1.6021\n\n"
            "Result:\n"
            "  pH ≈ 1.60 (at 25 °C)"
        )
    )
    demo.after(1400, lambda: demo.append_followup(
        "Bonus:\n"
        "  pOH = 14 − pH = 12.3979\n"
        "  [OH−] = 10^(−pOH) ≈ 4.0×10⁻¹³ mol/L"
    ))

    demo.mainloop()
