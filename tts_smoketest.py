from tts_driver import speak_natural
tests = [
    ("en", "Hello, I am Nova."),
    ("hi", "नमसत, म नव ह"),
    ("de", "Hallo, ich bin Nova."),
    ("es", "Hola, soy Nova."),
    ("fr", "Bonjour, je suis Nova.")
]
for lang, text in tests:
    print(f"--> {lang}")
    speak_natural(text, lang)
print("Done.")
