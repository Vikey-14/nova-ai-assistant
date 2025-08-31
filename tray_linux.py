# tray_linux.py — minimal Linux tray for Nova (optional)
from __future__ import annotations
import threading, os

def start_tray_in_thread():
    t = threading.Thread(target=_run_tray, daemon=True)
    t.start()
    return t

def _run_tray():
    # soft deps
    try:
        import pystray
        from PIL import Image, ImageDraw
    except Exception:
        return

    # icon
    try:
        from utils import resource_path
        from PIL import Image
        ico = resource_path("assets/nova_icon_256.png")
        if not os.path.exists(ico):
            raise FileNotFoundError
        icon_img = Image.open(ico)
    except Exception:
        icon_img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(icon_img)
        d.ellipse((6, 6, 58, 58), fill=(0, 255, 204, 255))

    def _toggle_wake(_icon, _item):
        from utils import get_wake_mode, set_wake_mode
        on = bool(get_wake_mode())
        try:
            if on:
                from wake_word_listener import stop_wake_listener_thread
                stop_wake_listener_thread()
                set_wake_mode(False)
            else:
                from wake_word_listener import start_wake_listener_thread
                set_wake_mode(True)
                start_wake_listener_thread()
        except Exception:
            pass
        _refresh_menu(_icon)

    def _show_window(_icon, _item):
        try:
            from gui_interface import get_gui
            g = get_gui()
            g.show()
        except Exception:
            pass

    def _quit(icon, _item):
        try:
            icon.stop()
        except Exception:
            pass
        try:
            from gui_interface import get_gui
            g = get_gui()
            g.root.after(0, g.root.quit)
        except Exception:
            os._exit(0)

    def _refresh_menu(icon):
        from utils import get_wake_mode
        on = bool(get_wake_mode())
        label = f"Wake Mode: {'On' if on else 'Off'}"
        icon.menu = pystray.Menu(
            pystray.MenuItem("Open Nova", _show_window),
            pystray.MenuItem(label, _toggle_wake),
            pystray.MenuItem("Quit", _quit),
        )

    icon = pystray.Icon("Nova", icon=icon_img, title="Nova")
    _refresh_menu(icon)
    try:
        icon.run()
    except Exception:
        pass
