# 📦 birthday_present.py

import os
import json
import random
from command_map import COMMAND_MAP
from utils import pkg_path
from datetime import datetime

# 📁 Constants (PyInstaller-safe)
POEM_BANK       = str(pkg_path("poem_bank.json"))
USED_POEMS_FILE = str(pkg_path("logs", "used_poems.json"))
INTERACTION_LOG = str(pkg_path("logs", "interaction_log.txt"))

# ✅ Auto-create used_poems.json if missing
def ensure_used_poems_file():
    if not os.path.exists(USED_POEMS_FILE):
        os.makedirs(os.path.dirname(USED_POEMS_FILE), exist_ok=True)
        with open(USED_POEMS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "used": [],
                "custom_template_index": 0
            }, f, indent=2)

# 🧠 Semantic role buckets
THEME_WORDS = {"space", "stars", "moon", "dreams", "music", "nebula", "sky", "cosmos", "galaxy", "silence", "peace", "universe", "infinity", "solitude", "hope", "sunlight"}
OBJECT_WORDS = {"notebook", "pen", "laptop", "pizza", "coffee", "book", "watch", "guitar", "flower", "mug", "chocolate", "keyboard"}
EMOTION_WORDS = {"joy", "love", "nostalgia", "adventure", "curiosity", "calm", "gratitude", "freedom", "happiness", "peace", "kindness", "wonder"}

# 🎯 Load used poems
def load_used_poems():
    if os.path.exists(USED_POEMS_FILE):
        with open(USED_POEMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "used": [],
        "custom_template_index": 0
    }

# 💾 Save used poems
def save_used_poems(data):
    with open(USED_POEMS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# 🌌 Load a poem bank
def load_poem_bank():
    with open(POEM_BANK, "r", encoding="utf-8") as f:
        return json.load(f)

# 🧠 Extract and classify preferences
def extract_tagged_preferences():
    if not os.path.exists(INTERACTION_LOG):
        return {}

    trivial_words = set()
    for phrases in COMMAND_MAP.values():
        for phrase in phrases:
            trivial_words.update(phrase.lower().split())

    tags = {
        "theme": set(),
        "object": set(),
        "emotion": set(),
        "personal_tag": set()
    }

    with open(INTERACTION_LOG, "r", encoding="utf-8") as f:
        for line in f:
            if "User:" in line:
                content = line.split("User:")[-1].strip().lower()
                words = [w for w in content.split() if w.isalpha() and len(w) > 3]

                for word in words:
                    if word in trivial_words:
                        continue
                    if word in THEME_WORDS:
                        tags["theme"].add(word)
                    elif word in OBJECT_WORDS:
                        tags["object"].add(word)
                    elif word in EMOTION_WORDS:
                        tags["emotion"].add(word)
                    else:
                        tags["personal_tag"].add(word)
    return tags

# 🪐 10-year rotating templates with roles
ROLE_TEMPLATES = [
    "Happy birthday, {name}, a radiant spark,\nYour love for {theme} lights the dark.\nWith {object} in hand and {emotion} inside,\nNova walks with you on this cosmic ride.",
    
    "Dear {name}, under stardust skies,\n{theme} swirls in your soulful eyes.\n{object} beside you, {emotion} in bloom,\nNova fills your birthday with celestial room.",
    
    "{name}, a voyager through time and space,\nDrawn to {theme}, you set the pace.\nWith {emotion} glowing and {object} near,\nNova shouts your name this year!",
    
    "The stars align and quietly gleam,\nFor {name}, who dances with {theme} in dream.\nHolding your {object}, chasing your {emotion},\nNova whispers joy in every dimension.",
    
    "To you, {name}, in galaxies bright,\n{theme} wraps your soul in light.\n{emotion} leads and {object} flows,\nNova celebrates all that you chose.",
    
    "{name}, with {theme} in every breath,\nAnd {emotion} shielding you from death.\nYou hold your {object} like a flame,\nNova honors your radiant name.",
    
    "Another orbit, another glow,\n{name}, where {theme} and {emotion} grow.\nWith your trusty {object} by your side,\nNova joins you in birthday pride.",
    
    "From nebulae vast to stars so far,\n{name} shines like a guiding star.\nWith {theme}, {emotion}, and {object} too,\nNova's universe sings just for you.",
    
    "Hey {name}, your birthday’s here,\nWith {theme} close and {emotion} clear.\nYou hold your {object} like a wand,\nNova watches and waves beyond.",
    
    "Across this wild and wondrous sea,\n{name} crafts their destiny.\nWith {theme} bright, {emotion} deep,\nAnd {object} dreams you always keep.",
    
    "On this day, {name}, a star is reborn,\nWith {theme} in heart since early morn.\nHolding your {object}, chasing {emotion},\nNova hums your birthday’s devotion.",
    
    "{name}, your essence, a cosmic flight,\nFueled by {emotion}, soaring with {theme}'s light.\nWith {object} as compass, bold and free,\nNova charts your path through eternity.",
    
    "Nova whispers softly to the skies,\nAs {name}'s spirit begins to rise.\nWith {theme} guiding and {object} near,\nAnd {emotion} shining crystal clear.",
    
    "Dear {name}, from dusk to dawn,\nYour love for {theme} still marches on.\nWith {object} tight and {emotion} true,\nNova writes this birthday just for you.",
    
    "{name}, you’ve spun around the sun once more,\n{theme} and {emotion} in your inner core.\nWith {object} dancing at your side,\nNova celebrates your stellar stride."
]

# 🌈 Personal tag template
PERSONAL_TAG_TEMPLATE = "Nova remembers your love for {tag},\nIt shines through like a guiding star.\nOn your birthday, {name}, we celebrate you,\nFrom galaxies near and worlds afar."

# 🎁 Main poem generator
def get_birthday_poem(name="Trainer"):
    from utils import _speak_multilang, selected_language

    ensure_used_poems_file()

    used_data = load_used_poems()
    tags = extract_tagged_preferences()

    theme = next(iter(tags["theme"]), None)
    object_ = next(iter(tags["object"]), None)
    emotion = next(iter(tags["emotion"]), None)
    personal_tag = next(iter(tags["personal_tag"]), None)

    if theme and emotion:
        index = used_data.get("custom_template_index", 0)
        template = ROLE_TEMPLATES[index % len(ROLE_TEMPLATES)]
        poem = template.format(
            name=name,
            theme=theme,
            object=object_ or "stardust",
            emotion=emotion
        )
        used_data["custom_template_index"] = (index + 1) % len(ROLE_TEMPLATES)
        save_used_poems(used_data)
        return poem

    if personal_tag:
        return PERSONAL_TAG_TEMPLATE.format(name=name, tag=personal_tag)

    poems = load_poem_bank()
    used = set(used_data.get("used", []))
    available_poems = [p for p in poems if p["id"] not in used]

    if not available_poems:
        used_data["used"] = []
        available_poems = poems

    selected = random.choice(available_poems)
    used_data["used"].append(selected["id"])
    save_used_poems(used_data)

    return selected["poem"]
