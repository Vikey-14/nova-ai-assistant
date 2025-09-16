# tools/make_icns_iconset.py
from pathlib import Path
from PIL import Image

SRC = Path("assets/nova_face.png")  # your master 1024x1024 logo
OUT = Path("icons/nova.iconset")
OUT.mkdir(parents=True, exist_ok=True)

targets = [
    (16,   "icon_16x16.png"),
    (32,   "icon_16x16@2x.png"),
    (32,   "icon_32x32.png"),
    (64,   "icon_32x32@2x.png"),
    (128,  "icon_128x128.png"),
    (256,  "icon_128x128@2x.png"),
    (256,  "icon_256x256.png"),
    (512,  "icon_256x256@2x.png"),
    (512,  "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
]

img = Image.open(SRC).convert("RGBA")
for size, name in targets:
    out_path = OUT / name
    img.resize((size, size), Image.LANCZOS).save(out_path, "PNG")
    print(f"[iconset] wrote: {out_path}")

print("\nOK. Next step happens in CI on macOS.\n")
