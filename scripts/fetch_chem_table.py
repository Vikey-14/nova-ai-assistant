# scripts/fetch_chem_table.py
import json, os, ssl, tempfile, urllib.request
from typing import Optional

# 📦 Source dataset (maintained on GitHub)
SRC = "https://raw.githubusercontent.com/Bowserinator/Periodic-Table-JSON/master/PeriodicTableJSON.json"

# 📁 Default output path (…/data/chemistry_table.json) — project root
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "chemistry_table.json"))

# 🏷 Attribution metadata (license requirement)
ATTR = {
    "source": "Bowserinator/Periodic-Table-JSON",
    "license": "CC BY-SA 3.0",
    "url": "https://github.com/Bowserinator/Periodic-Table-JSON",
}

def _atomic_write(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="chem_tbl_", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)  # atomic on Windows & POSIX
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass

def fetch_to(out_path: Optional[str] = None, src: str = SRC) -> None:
    """Download the periodic table JSON and write it atomically to out_path."""
    # Priority: explicit arg > env var > default OUT
    out_file = os.path.abspath(out_path or os.environ.get("CHEM_TABLE_PATH") or OUT)

    ctx = ssl.create_default_context()
    req = urllib.request.Request(src, headers={"User-Agent": "nova-ai-assistant/1.0"})
    print(f"⬇️  Downloading periodic table from {src} …")
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        payload = r.read()

    data = json.loads(payload.decode("utf-8"))

    # Add Nova-specific attribution (for provenance)
    try:
        data["_nova_attribution"] = ATTR
    except Exception:
        pass

    bytes_out = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    _atomic_write(out_file, bytes_out)
    print(f"✅ Saved full periodic table to {out_file}")

def main(output_path: Optional[str] = None) -> None:
    fetch_to(output_path or OUT)

if __name__ == "__main__":
    main()
