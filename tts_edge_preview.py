from tts_driver import EdgeSynth, EDGE_FEMALE, EDGE_MALE_EN
e = EdgeSynth()
print("Edge EN male:", EDGE_MALE_EN)
e.speak("Hello, I am Nova.", "en", voice=EDGE_MALE_EN, rate="+0%")

samples = {
  "hi": "नमसत, म नव ह",
  "de": "Hallo, ich bin Nova.",
  "es": "Hola, soy Nova.",
  "fr": "Bonjour, je suis Nova."
}
for lang, voice in EDGE_FEMALE.items():
    print(f"Edge {lang} female:", voice)
    e.speak(samples[lang], lang, voice=voice, rate="+0%")
