# Install Nova


## Download (latest)
- **Windows:** [NovaSetup.exe](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/NovaSetup.exe)
- **macOS:**
  - Apple Silicon (arm64): [Nova_mac_arm64.pkg](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/Nova_mac_arm64.pkg) · [Nova_mac_arm64.dmg](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/Nova_mac_arm64.dmg)
  - Intel (x86_64):        [Nova_mac_x64.pkg](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/Nova_mac_x64.pkg) · [Nova_mac_x64.dmg](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/Nova_mac_x64.dmg)
- **Linux:**
  - [.deb (amd64)](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/nova_ai_assistant_amd64.deb)
  - [.deb (arm64)](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/nova_ai_assistant_arm64.deb)
- **Checksums:** [SHA256SUMS.txt](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/SHA256SUMS.txt)



All versions: see the [Releases](https://github.com/Vikey-14/nova-ai-assistant/releases) page.

---

> **Verify checksums (optional)**
> - **Windows (PowerShell):** `Get-FileHash .\NovaSetup.exe -Algorithm SHA256`
> - **macOS:** `shasum -a 256 Nova_mac_arm64.pkg`  (or `Nova_mac_x64.pkg`; use the `.dmg` name if you downloaded the DMG)
> - **Linux:** `sha256sum nova_ai_assistant_<version>_<arch>.deb`  
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
**Recommended:** use the `.pkg` installer

1) Download the right installer for your Mac:
   - **Apple Silicon (M1/M2/M3, arm64):** `Nova_mac_arm64.pkg`
   - **Intel (x86_64):** `Nova_mac_x64.pkg`
2) Open the `.pkg` and follow the prompts. It installs **Nova.app** and **Nova Tray.app** to `/Applications`, creates a **Desktop alias** to **Nova.app**, starts the tray (menu bar icon), and sets it to start at login.

> If Gatekeeper blocks the app: **System Settings → Privacy & Security → Open Anyway** (or Control-click the app → **Open**).

**Alternative:** use the DMG for your Mac (`Nova_mac_arm64.dmg` or `Nova_mac_x64.dmg`) and drag both apps to **Applications**.

---

## Linux (Debian/Ubuntu)
1) Download the `.deb` for your CPU:
   - `nova_ai_assistant_<version>_amd64.deb` — x86_64 (Intel/AMD)
   - `nova_ai_assistant_<version>_arm64.deb` — ARM64 (Raspberry Pi 4/5 64-bit, ARM laptops/servers)

2) Install:
```bash
# amd64
sudo apt install ./nova_ai_assistant_<version>_amd64.deb

# arm64
sudo apt install ./nova_ai_assistant_<version>_arm64.deb
```




