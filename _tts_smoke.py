from time import sleep
from tts_driver import get_tts

tts = get_tts()
tests = [
    ("en-US", "Hello! I'm Nova."),                 # Windows: SAPI David (fallbacks enabled)
    ("es-ES", "Hola! Soy Nova."),                 # Windows: Piper ONLY (female via speaker=1)
    ("hi-IN", "नमसत! म नव ह"),            # Windows: Piper ONLY
    ("de-DE", "Hallo! Ich bin Nova."),             # Windows: Piper ONLY
    ("fr-FR", "Salut ! Je suis Nova."),            # Windows: Piper ONLY
]
for loc, line in tests:
    print("", loc, line)
    tts.speak(line, loc)
    sleep(0.4)
print("Done.")
