# Install NOVA

Get the latest installers for **Windows**, **macOS**, and **Linux** from the repo’s **Releases** page.

---

## Windows
1) Download **NovaSetup.exe** from Releases.  
2) Run it. It installs **NOVA** and **Nova Tray**, creates a **Desktop shortcut**, adds Start Menu entries, auto-starts the tray at login, and launches it immediately.

---

## macOS
**Recommended:** `NOVA_<version>_mac.pkg`

1) Download **NOVA_<version>_mac.pkg** from Releases and open it.  
2) It installs **NOVA.app** and **Nova Tray.app** to `/Applications`, creates a **Desktop alias** to **NOVA.app**, starts the tray now (menu bar icon), and auto-starts it at login.

> If Gatekeeper blocks the app: **System Settings → Privacy & Security → Open Anyway** (or control-click the app → **Open**).

**Alternative:** use `NOVA_<version>_mac.dmg` and drag both apps to **Applications** (PKG is preferred).

---

## Linux (Debian/Ubuntu)

1) Download the `.deb` (e.g. `nova_ai_assistant_<version>_amd64.deb`) from Releases.  
2) Install:
```bash
sudo apt install ./nova_ai_assistant_<version>_amd64.deb
```