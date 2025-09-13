# tools/make_icons.py
from pathlib import Path
from PIL import Image

PROJECT = Path(__file__).resolve().parents[1]
ASSETS  = PROJECT / "assets"
SRC_PNG = ASSETS / "nova_face.png"
ICO_OUT = ASSETS / "nova_icon_big.ico"
PNG_OUT = ASSETS / "nova_icon_256.png"

print(f"[make_icons] Project: {PROJECT}")
print(f"[make_icons] Source : {SRC_PNG}")

if not SRC_PNG.exists():
    raise FileNotFoundError(f"Missing {SRC_PNG}. Put your crisp logo there (no blur).")

src = Image.open(SRC_PNG).convert("RGBA")
# Ensure we have at least 256x256 as the max frame for the ICO
if max(src.size) < 256:
    print(f"[make_icons] Upscaling source from {src.size} -> (256, 256)")
    src_256 = src.resize((256, 256), Image.LANCZOS)
else:
    src_256 = src

sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
src_256.save(ICO_OUT, sizes=[(s, s) for s in sizes])
print(f"[make_icons] Wrote: {ICO_OUT}")

src_256.save(PNG_OUT, optimize=True)
print(f"[make_icons] Wrote: {PNG_OUT}")

print("[make_icons] Done.")
