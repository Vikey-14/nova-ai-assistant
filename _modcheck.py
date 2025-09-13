import importlib, sys
mods = [
  "fastapi","uvicorn","slowapi","jose","pydantic","pydantic_settings",
  "requests","dotenv","orjson","ujson","email_validator","defusedxml","rich","click",
  "PIL","numpy","matplotlib","sympy","wikipedia","langdetect","dateparser",
  "pyttsx3","playsound","speech_recognition","pystray","psutil","platformdirs",
  "gtts","pyaudio"
]
fail = 0
for m in mods:
    try:
        import importlib; importlib.import_module(m)
        print("OK  -", m)
    except Exception as e:
        print("FAIL-", m, "-", e)
        fail += 1
print("\nTotal FAIL:", fail)
sys.exit(fail)
