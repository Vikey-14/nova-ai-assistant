# hooks/rthook_force_local_utils.py
import os, sys, importlib.util
from pathlib import Path

def _app_dir() -> Path:
    # One-file: extract dir is _MEIPASS; One-dir: files sit next to the EXE.
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        return Path(meipass) if meipass else Path(sys.executable).parent
    return Path(__file__).resolve().parent

APP = _app_dir()
LOG = APP / "utils_pin.log"

def _log(msg: str):
    try:
        with LOG.open("w", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

def _pin_from(path: Path):
    spec = importlib.util.spec_from_file_location("utils", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules["utils"] = mod
    _log(f"utils pinned from: {path}")

# 1) Prefer ONLY the root-level utils.py shipped beside the EXE
root_utils = APP / "utils.py"
if root_utils.exists():
    _pin_from(root_utils)
else:
    # 2) Fallback: use bundled 'utils' ONLY if it has our sentinel
    try:
        import importlib
        mod = importlib.import_module("utils")
        if getattr(mod, "IS_NOVA_UTILS", False):
            sys.modules["utils"] = mod
            _log(f"utils imported from bundle: {getattr(mod, '__file__', 'n/a')}")
        else:
            raise ImportError("Found different module named 'utils' without sentinel")
    except Exception as e:
        _log(f"FAILED to bind utils: {e}")
        raise
