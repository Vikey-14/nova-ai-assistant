# 🚀 NOVA AI Desktop Assistant

NOVA is a multilingual, voice-powered AI desktop assistant — inspired by J.A.R.V.I.S. and custom-built in Python.  
She listens to your commands, speaks in 5 languages, opens apps, takes notes, sets reminders, controls system settings, and more!

---

## 🧠 Features

- 🎙️ **Voice Command Recognition**
- 🗣️ **Text-to-Speech (TTS)** in 🇬🇧 English, 🇮🇳 Hindi, 🇩🇪 German, 🇪🇸 Spanish, 🇫🇷 French
- 🔎 **Wikipedia + Web Search** with multilingual support
- 💡 **System Control** (volume, brightness, shutdown)
- 📝 **Notes + Reminders** with voice
- 🌤️ **Weather & News** (via API)
- 💻 **Dynamic GUI** (Nova's visual face and chat interface)
- 🔐 Packaged as `.EXE` (Coming Soon)

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

- Python 3.11  
- Pyttsx3 + SpeechRecognition  
- Tkinter GUI  
- Requests, Wikipedia API  
- PowerShell/System APIs  
- Multilingual i18n  
- Soon: `pyinstaller` for `.exe` build

---

## 👨‍💻 Author

**Vikey Sharma**  
GitHub: [Vikey-14](https://github.com/Vikey-14)
