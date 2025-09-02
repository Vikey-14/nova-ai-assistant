# 🚀 NOVA AI Desktop Assistant
[![Latest release](https://img.shields.io/github/v/release/Vikey-14/nova-ai-assistant?label=release)](https://github.com/Vikey-14/nova-ai-assistant/releases/latest)

NOVA is a multilingual, voice-powered AI desktop assistant — inspired by J.A.R.V.I.S. and custom-built in Python.  
She listens to your commands, speaks in 5 languages, opens apps, takes notes, sets reminders, controls system settings, and more!

---

## ⬇️ Download (pick your OS)

- 🪟 **Windows** — [NovaSetup.exe](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/NovaSetup.exe)  
  (Portable: [NOVA_windows_portable.zip](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/NOVA_windows_portable.zip))
- 🍎 **macOS** — [NOVA_mac.pkg](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/NOVA_mac.pkg)  
  (or [NOVA_mac.dmg](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/NOVA_mac.dmg))
- 🐧 **Linux (Debian/Ubuntu)** — [.deb](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/nova_ai_assistant_amd64.deb)
- 🔐 **Checksums** — [SHA256SUMS.txt](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/SHA256SUMS.txt)

---

### 🔐 Verify your download (optional but recommended)

Use the published **SHA256SUMS.txt** to confirm files weren’t corrupted or tampered with.

1) Download your installer(s) **and** `SHA256SUMS.txt` from the latest release.  
2) Put them in the **same folder** (e.g., `~/Downloads` on macOS/Linux or `Downloads` on Windows).

<details>
<summary>🍎/🐧 macOS & Linux</summary>

**Run in Terminal:**
```bash
# macOS
cd ~/Downloads
shasum -a 256 -c SHA256SUMS.txt

# Linux (ignore assets you didn't download)
cd ~/Downloads
sha256sum -c --ignore-missing SHA256SUMS.txt
```

You should see lines ending with `OK` for the files you have.  
**If you see a mismatch / FAILED**, re-download the installer and `SHA256SUMS.txt`, then try again.
</details>

<details>
<summary>🪟 Windows (PowerShell)</summary>

**Option A — print the file hash and compare with SHA256SUMS.txt manually**
**Run in PowerShell:**
```powershell
cd $env:USERPROFILE\Downloads

Get-FileHash .\NovaSetup.exe -Algorithm SHA256
# (Optional) Check other assets you downloaded:
# Get-FileHash .\NOVA_mac.pkg -Algorithm SHA256
# Get-FileHash .\NOVA_mac.dmg -Algorithm SHA256
# Get-FileHash .\nova_ai_assistant_amd64.deb -Algorithm SHA256
```

**Option B — auto-check a file against SHA256SUMS.txt**
**Run in PowerShell:**
```powershell
cd $env:USERPROFILE\Downloads

# Change the file name to verify other assets (e.g., 'NOVA_mac.pkg')
$filename = 'NovaSetup.exe'

$expected = (Select-String -Path .\SHA256SUMS.txt -Pattern ([regex]::Escape($filename))).Line.Split()[0]
$actual   = (Get-FileHash .\$filename -Algorithm SHA256).Hash.ToLower()

if ($actual -eq $expected) { "$filename: OK" } else { "$filename: MISMATCH" }
```

**If you see `MISMATCH`**, re-download the installer and `SHA256SUMS.txt`, then run the check again.
</details>

---


## 🧭 Install & Quickstart

<details>
<summary>🪟 Windows</summary>

**Download:**  
[👉 NovaSetup.exe](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/NovaSetup.exe)  
(Optional portable build: [NOVA_windows_portable.zip](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/NOVA_windows_portable.zip))

**Install (recommended):**
1. Double-click `NovaSetup.exe`.
2. If SmartScreen appears, click **More info → Run anyway**.
3. Follow the wizard. Start Menu shortcuts are created; **Nova Tray** auto-starts after login.

**Portable (no install):**
1. Unzip `NOVA_windows_portable.zip`.
2. Run `NOVA.exe` (and `NovaTray.exe` if you want the tray).

**Uninstall:** *Settings → Apps → NOVA → Uninstall.*
</details>

---

<details>
<summary>🍎 macOS</summary>

**Download:**  
[👉 NOVA_mac.pkg](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/NOVA_mac.pkg)  
(or [NOVA_mac.dmg](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/NOVA_mac.dmg))

**Install (PKG):**
1. Double-click `NOVA_mac.pkg` and follow the prompts.  
2. *CLI alternative:*
   ```bash
   sudo installer -pkg ~/Downloads/NOVA_mac.pkg -target /
   ```

**First-run note (Gatekeeper):**  
If macOS blocks the app, use either method:

- **Method A – Open via context menu:**  
  Right-click **NOVA.app** (or **Nova Tray.app**) → **Open** → **Open**.

- **Method B – Allow from Settings:**  
  - **Ventura / Sonoma:** *System Settings → Privacy & Security* → **Open Anyway**.  
  - **Monterey / Big Sur or earlier:** *System Preferences → Security & Privacy → General* → **Open Anyway** (unlock with the padlock if needed).

**Run now:**
- From **Applications**: open **NOVA** and **Nova Tray**
- Or via Terminal:
  ```bash
  open -a "NOVA"
  open -a "Nova Tray"
  ```

**Uninstall:**
```bash
sudo rm -rf "/Applications/NOVA.app" "/Applications/Nova Tray.app"
sudo rm -f /Library/LaunchAgents/com.novaai.tray.plist
```
Log out/in (or reboot) to make sure the tray isn’t running.

**Apple Silicon (M1/M2/M3):**  
If prompted on first run, allow Rosetta to be installed.

</details>

---

<details>
<summary>🐧 Linux (Debian/Ubuntu)</summary>

**Download:**  
[👉 nova_ai_assistant_amd64.deb](https://github.com/Vikey-14/nova-ai-assistant/releases/latest/download/nova_ai_assistant_amd64.deb)

**Install (APT recommended):**
```bash
sudo apt update
sudo apt install ./nova_ai_assistant_amd64.deb
```

*Alternative (dpkg):*
```bash
sudo dpkg -i nova_ai_assistant_amd64.deb || sudo apt -f install
```

**Run now:**
- From your app menu: **Nova (AI Assistant)**
- The tray helper **Nova Tray** auto-starts next login
- Or via Terminal:
  ```bash
  NOVA &
  NovaTray &
  ```

**Uninstall:**
```bash
sudo apt remove nova-ai-assistant
```

**Notes**
- If the tray icon doesn’t appear on some desktops, install AppIndicator runtime:
  ```bash
  sudo apt install libayatana-appindicator3-1
  ```

</details>

---

## 🧠 Features

- 🎙️ **Voice Command Recognition**
- 🗣️ **Text-to-Speech (TTS)** in 🇬🇧 English, 🇮🇳 Hindi, 🇩🇪 German, 🇪🇸 Spanish, 🇫🇷 French
- 🔎 **Wikipedia + Web Search** with multilingual support
- 💡 **System Control** (volume, brightness, shutdown)
- 📝 **Notes + Reminders** with voice
- 🌤️ **Weather & News** (via API)
- 💻 **Dynamic GUI** (Nova's visual face and chat interface)
- 📦 Installers for Windows (.exe), macOS (.pkg/.dmg) and Linux (.deb)

---

## 🗂️ Project Structure

📦 nova_ai_assistant/
├── core_engine.py           # Main command processor  
├── gui_interface.py         # GUI + visual interface  
├── main.py                  # App entry point  
├── memory_handler.py        # Notes & reminder engine  
├── news_handler.py          # News API logic  
├── utils.py                 # Voice I/O, language utils  
├── weather_handler.py       # Weather API integration  
├── nova_face.png            # GUI branding image (NOVA face)
├── assets/                  # (Reserved) images, icons, GUI assets  
├── data/                    # Saved notes and config  
├── .env                     # API keys and configs  
├── .gitignore               # Git ignore rules  
└── README.md                # Project documentation  

---

## 🖼️ NOVA Branding

<p align="center">
  <img src="assets/nova_face.png" alt="NOVA GUI Face" width="300">
</p>

---

## 🛠️ Tech Stack

- 🐍 Python 3.11  
- 🔉 Pyttsx3 + SpeechRecognition  
- 🪟/🍎/🐧 Tkinter GUI  
- 🌐 Requests, Wikipedia API  
- ⚙️ PowerShell / System APIs  
- 🌍 Multilingual i18n  
- 📦 Installers for Windows (.exe), macOS (.pkg/.dmg) and Linux (.deb)

---


## 👨‍💻 Author

**Vikey Sharma**  
GitHub: [Vikey-14](https://github.com/Vikey-14)
