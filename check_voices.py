import pyttsx3
engine = pyttsx3.init()
voices = engine.getProperty('voices')

for i, voice in enumerate(voices):
    print(f"{i}. Name: {voice.name}")
    print(f"   ID: {voice.id}")
    print(f"   Lang: {voice.languages}")
    print(f"   Gender: {voice.gender}")
    print(f"   Age: {voice.age}")
    print("---------------")