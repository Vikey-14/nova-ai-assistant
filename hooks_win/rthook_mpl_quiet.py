# Run before your app code
import os, sys
from pathlib import Path

def _app_dir():
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        return Path(meipass) if meipass else Path(sys.executable).parent
    return Path(__file__).resolve().parent

APP = _app_dir()

# Put MPL config/cache inside the app folder so it persists across runs
mpl_cfg = APP / ".mplcache"
mpl_cfg.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(mpl_cfg))

# Quiet Matplotlib logger before any import triggers font manager work
try:
    import logging
    logging.getLogger("matplotlib").setLevel(logging.ERROR)
except Exception:
    pass
