# Install Nova

## Download (latest)
- **Windows:** [NovaSetup.exe](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/NovaSetup.exe)
- **macOS:**  [Nova_mac.pkg](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/Nova_mac.pkg) · [Nova_mac.dmg](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/Nova_mac.dmg)
- **Linux:**  [.deb (amd64)](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/nova_ai_assistant_amd64.deb)
- **Checksums:** [SHA256SUMS.txt](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/SHA256SUMS.txt)


All versions: see the [Releases](https://github.com/Vikey-14/nova-ai-assistant/releases) page.

---

> **Verify checksums (optional)**
> - **Windows (PowerShell):** `Get-FileHash .\NovaSetup.exe -Algorithm SHA256`
> - **macOS:** `shasum -a 256 Nova_<version>_mac.pkg`  
> - **Linux:** `sha256sum nova_ai_assistant_<version>_amd64.deb`  
> Compare the output to the value in **SHA256SUMS.txt** (from the link above).  
> On macOS/Linux you can also download `SHA256SUMS.txt` and run:  
> `shasum -a 256 -c SHA256SUMS.txt` (macOS) or `sha256sum -c SHA256SUMS.txt` (Linux)

---

## Windows
1) Download **NovaSetup.exe** from Releases.  
2) Run it. It installs **Nova** and **Nova Tray**, creates a **Desktop shortcut**, adds Start Menu entries, and auto-starts the tray at login.

> Tip: In **Settings → Personalization → Taskbar → Other system tray icons**, you’ll see **Nova Tray** (no “.exe”).

---

## macOS
**Recommended:** `Nova_<version>_mac.pkg`

1) Download **Nova_<version>_mac.pkg** and open it.  
2) It installs **Nova.app** and **Nova Tray.app** to `/Applications`, creates a **Desktop alias** to **Nova.app**, starts the tray (menu bar icon), and sets it to start at login.

> After install, the tray icon appears in the menu bar. You can disable auto-start in **System Settings → General → Login Items**.

> If Gatekeeper blocks the app: **System Settings → Privacy & Security → Open Anyway** (or Control-click the app → **Open**).

**Alternative:** use `Nova_<version>_mac.dmg` and drag both apps to **Applications** (PKG is preferred).

---

## Linux (Debian/Ubuntu)
1) Download the `.deb` (e.g. `nova_ai_assistant_<version>_amd64.deb`) from Releases.  
2) Install:
```bash
sudo apt install ./nova_ai_assistant_<version>_amd64.deb
```