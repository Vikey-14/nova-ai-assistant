from pathlib import Path

def check(path: Path):
    if not path.exists():
        print(f"{path}  ->  MISSING"); return
    size = path.stat().st_size
    with open(path, "rb") as f:
        head = f.read(8)
    magic = head[:4].hex()
    if magic in {"cffaedfe","feedfacf"}:
        kind = "Mach-O 64 (feedfacf)"
    elif magic in {"cafebabe","cafebabf"}:
        kind = "Universal/Fat (cafebabe/cafebabf)"
    else:
        kind = "UNKNOWN"
    print(f"{path}  ->  size={size:,} bytes, magic={magic}, kind={kind}")

for p in [
    Path("third_party/piper/macos-x64/piper"),
    Path("third_party/piper/macos-arm64/piper"),
]:
    check(p)
