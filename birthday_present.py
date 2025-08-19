# 📦 birthday_present.py

import os
import json
import random
import re
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

# -------------------------
# 🧠 Semantic role buckets (expanded, with cuisine tweak)
# -------------------------
THEME_WORDS = {
    # space / nature / seasons
    "space","stars","starlight","moon","sun","planet","planets","cosmos","galaxy","universe","nebula","comet","aurora",
    "sky","clouds","rain","ocean","sea","beach","mountain","mountains","forest","river","desert","snow","winter","summer","spring","autumn","nature",
    "night","sunrise","sunset","rainbow","stargazing",

    # art / media / culture
    "music","musique","musik","música","संगीत","cinema","movies","film","anime","manga","comics","literature","poetry","painting","art","theatre","photography",
    "podcasts","dance","jazz","rock","hiphop","classical","lofi","indie","folk","kpop",

    # tech / science / learning
    "technology","coding","programming","software","hardware","ai","robotics","science","physics","chemistry","math","mathematics","biology","astronomy",
    "history","philosophy","psychology","economics","design","ux","ui",

    # hobbies / lifestyle
    "gaming","travel","adventure","hiking","camping","meditation","yoga","mindfulness","reading","writing","journaling","baking","cooking","gardening",
    "photography","blogging","vlogging",

    # sports
    "football","soccer","basketball","cricket","tennis","badminton","tabletennis","volleyball","swimming","running","cycling","skateboarding","chess",
    "kabaddi","hockey","rugby","baseball","f1","athletics",

    # animals / nature add-ons
    "cats","dogs","wildlife","animals","petcare","beaches","waterfalls","islands","rainforest","campfires","roadtrips",

    # arts/craft add-ons
    "calligraphy","origami","watercolor","knitting","crochet","handlettering","storytelling","screenwriting","cinematography","soundtracks",

    # lifestyle/vibes add-ons
    "minimalism","productivity","aesthetics","wellbeing","selfcare",

    # fandoms / games add-ons (single-token)
    "marvel","dc","starwars","lotr","harrypotter","pokemon","zelda","minecraft","valorant","fortnite","roblox","genshin",

    # cuisines / foods as interests (moved from OBJECTS)
    "pizza","burger","sushi","noodles","pasta","sandwich",
    "biryani","samosa","dosa","idli",
    "ramen","pho","kimchi","bibimbap",
    "taco","burrito","dumplings","gelato",

    # vibes / abstracts (theme-ish)
    "silence","peace","hope","dreams","imagination","infinity","solitude","friendship","family","freedom","coziness","nostalgia","serenity","wonder",
}

OBJECT_WORDS = {
    # study / work
    "notebook","journal","diary","pen","pencil","marker","highlighter","laptop","computer","pc","keyboard","mouse","monitor","tablet","phone","camera",
    "headphones","earbuds","microphone","tripod","lens","charger","backpack","bag","notepad",

    # music / art gear
    "guitar","piano","violin","drums","ukulele","synth","brush","palette","canvas","easel","sketchbook","crayons","markers",

    # home / cozy
    "mug","cup","teacup","bottle","thermos","flask","candle","lamp","blanket","pillow","cushion","plant","cactus","flower","rose","tulip","succulent",

    # wearables
    "watch","bracelet","ring","necklace","earrings","glasses","sunglasses","hoodie","jacket","sneakers","shoes","boots","cap","hat",

    # food / drink (kept hand-friendly)
    "coffee","tea","chai","matcha","latte","espresso","cappuccino",
    "chocolate","cookie","cake","brownie","mochi","icecream",

    # fun / gadgets / games
    "book","novel","comic","controller","console","playstation","xbox","switch","boardgame","dice","cards","telescope","binoculars",

    # sports gear
    "ball","football","basketball","cricketbat","racket","shuttlecock","skateboard","bicycle","helmet",

    # instruments add-ons
    "flute","saxophone","trumpet","cello","clarinet","harmonica","viola","tabla","sitar","dholak","mridangam","veena",

    # cozy/decor add-ons
    "diffuser","humidifier","notecard","stickers","posters",

    # tech/gadget add-ons
    "kindle","smartwatch","stabilizer","gamepad","joystick","streamdeck",

    # more sports gear add-ons
    "hockeystick","cricketball","tennisball","badmintonracket","footballboots",
}

EMOTION_WORDS = {
    "joy","love","happiness","delight","cheer","bliss","serenity","calm","peace","gratitude","wonder","awe","curiosity","interest","inspiration",
    "motivation","passion","excitement","thrill","adventure","comfort","coziness","warmth","kindness","empathy","compassion","hope","optimism",
    "confidence","courage","pride","trust","loyalty","nostalgia","bittersweet","melancholy","resilience","patience","mindfulness","clarity",
    "euphoria","tranquility","zen","whimsy","playfulness","affection","tenderness","authenticity","belonging","contentment",
    "determination","drive","ambition","focus","flow","gratification","uplift","soothing","spark","zest",
}

# -------------------------
# NEW: Multilingual command / mode filters
# -------------------------

# Buckets from COMMAND_MAP we treat as generic commands (not interests)
GENERIC_SKIP_BUCKET_KEYS = [
    "open_youtube", "open_chatgpt", "search_google", "play_music",
    "adjust_volume", "adjust_brightness", "get_weather", "get_news",
    "wiki_search", "date_queries", "exit_app", "shutdown_system",
    "restart_system", "sleep_system", "lock_system", "logout_system",
    "set_alarm", "set_reminder"
]

def _build_skip_phrases_from_command_map(cmd_map, keys):
    """Collect phrases across languages from COMMAND_MAP for the given keys."""
    phrases = set()
    for k in keys:
        if k in cmd_map:
            for p in cmd_map[k]:
                p = (p or "").strip().lower()
                if p:
                    phrases.add(p)
    return phrases

# Phrases to skip entirely if they appear in a user line (generic app/OS commands)
SKIP_PHRASES = _build_skip_phrases_from_command_map(COMMAND_MAP, GENERIC_SKIP_BUCKET_KEYS)

# Multilingual patterns for name/language management
LANG_NAME_PATTERNS = [
    # EN
    r"\b(change|switch|set)\s+(app\s+)?language\b",
    r"\b(my\s+name\s+is|set\s+name|change\s+name|call\s+me|rename\s+me)\b",
    # HI (Hindi)
    r"(भाषा).*(बदल|सेट)|\bहिंदी\b|\bअंग्रेजी\b",
    r"(नाम).*(बदल|सेट|कह|बुला)",
    # FR
    r"\b(je\s+m['’]appelle|mon\s+nom\s+est)\b",
    r"\b(changer|modifier|définir)\s+la\s+langue\b",
    # ES
    r"\b(me\s+llamo|mi\s+nombre\s+es)\b",
    r"\b(cambiar|establecer|poner)\s+idioma\b",
    # DE
    r"\b(ich\s+heiße|mein\s+name\s+ist)\b",
    r"\b(sprache)\s*(ändern|wechseln|setzen)\b",
]

# Study/solver prompts in EN/HI/FR/ES/DE (verbs & subject terms)
STUDY_MODE_PATTERNS = [
    # EN
    r"\b(plot|graph|sketch|draw|solve|calculate|compute|evaluate|differentiate|derivative|integral|integrate|limit|matrix|determinant|eigen)\b",
    r"\b(stoichiometry|molarity|molality|titration|buffer|pH|balance(?:d)?\s+equation)\b",
    r"\b(show\s+steps|step\s+by\s+step|tldr|tl;dr|brief|quick\s+answer)\b",
    r"\b(use|turn\s*on|start|full)\s+(physics|chemistry|math|graph(?:ing)?)\s+mode\b",
    # HI (loose)
    r"(हल|समाधान|गणना|निकाल|अवकलन|समाकलन|सीमा|रेखाचित्र|ग्राफ)",
    # FR
    r"\b(résoudre|calculer|évaluer|dériver|dérivée|intégrer|intégrale|limite|tracer|graphe|matrice|déterminant|valeur\s+propre)\b",
    r"\b(stœchiométrie|molarité|titrage|tampon|pH)\b",
    r"\b(montrer\s+les\s+étapes|étape\s+par\s+étape|résumé|réponse\s+rapide)\b",
    # ES
    r"\b(resolver|calcular|evaluar|derivar|derivada|integrar|integral|límite|graficar|trazar|matriz|determinante|autovalor)\b",
    r"\b(estequiometría|molaridad|titulación|amortiguador|pH)\b",
    r"\b(mostrar\s+pasos|paso\s+por\s+paso|resumen|respuesta\s+rápida)\b",
    # DE
    r"\b(lösen|berechnen|ausrechnen|ableiten|ableitung|integrieren|integral|grenze|plotten|zeichnen|graf|matrix|determinante|eigenwert)\b",
    r"\b(stöchiometrie|molarität|titration|pH)\b",
    r"\b(schritte\s+zeigen|schritt\s+für\s+schritt|kurze\s+antwort)\b",
]

# Quick test for “homework/command-like” content: equations, many digits, operators, units/symbols
_HW_OR_CMD_REGEXES = [
    r"[=^<>*/+\-]{1}",                         # operators / equals
    r"\d",                                     # any digits
    r"\b(?:sin|cos|tan|log|ln)\b",
    r"\b(?:m/s|kg|N|J|W|Pa|Hz|Ω|°C|mol|M)\b",  # common units/symbols
]

# For extra safety, treat these single tokens as trivial command nouns across languages
TRIVIAL_COMMAND_TOKENS = {
    "language","langue","sprache","idioma","भाषा",
    "name","nom","nombre","नाम",
    "youtube","google","browser","chrome","music","song","video",
    "mode","physics","chemistry","math","graph","plot","solve","steps","answer",
}

def _contains_any_phrase(text: str, phrases: set[str]) -> bool:
    t = text.lower()
    for p in phrases:
        if p and p in t:
            return True
    return False

def _skip_line_for_preferences(line: str) -> bool:
    """Return True if this line looks like a command/mode/homework and must not feed poem tags."""
    t = (line or "").strip().lower()
    if not t:
        return True
    # Explicit skip phrases from COMMAND_MAP (YouTube/open/search/music/etc.)
    if _contains_any_phrase(t, SKIP_PHRASES):
        return True
    # Name/language management in any supported language
    for pat in LANG_NAME_PATTERNS:
        if re.search(pat, t, flags=re.IGNORECASE):
            return True
    # Study/solver requests (multilingual)
    for pat in STUDY_MODE_PATTERNS:
        if re.search(pat, t, flags=re.IGNORECASE):
            return True
    # Heuristic: math/homework symbols or units
    for pat in _HW_OR_CMD_REGEXES:
        if re.search(pat, t):
            return True
    # Question form with solver-y verbs (multilingual)
    if t.endswith("?") and re.search(
        r"\b(solve|how\s+to|what\s+is|find|calculate|derive|prove|graph|plot|résoudre|comment|qué\s+es|wie|lösen|berechnen)\b",
        t, flags=re.IGNORECASE
    ):
        return True
    return False

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

# -------------------------
# Natural phrasing for objects (drinks/sweets/pairs/articles)
# -------------------------
DRINKS = {"coffee","tea","chai","matcha","latte","espresso","cappuccino"}
# map sweets to their best unit phrase
_SWEET_UNITS = {
    "chocolate": "a piece of chocolate",
    "cookie": "a cookie",
    "cake": "a slice of cake",
    "brownie": "a brownie",
    "mochi": "a mochi",
    "icecream": "a scoop of ice cream",  # stored as "icecream" in OBJECT_WORDS
}
PAIRABLE = {"headphones","earbuds","glasses","sunglasses"}

def _a_or_an(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"

def _naturalize_object(obj):
    if not obj:
        return None
    o = obj.lower()
    if o in DRINKS:
        return f"a cup of {o}"
    if o in _SWEET_UNITS:
        return _SWEET_UNITS[o]
    if o in PAIRABLE:
        return f"a pair of {o}"
    # sensible default for everything else
    return f"{_a_or_an(o)} {o}"

# 🧠 Extract and classify preferences
def extract_tagged_preferences():
    """
    Mine light-weight, safe 'interests' from past chat without grabbing:
    - generic app/OS commands (YouTube/open/search/music/etc.) across EN/HI/FR/ES/DE
      → pulled from COMMAND_MAP buckets dynamically
    - name/language management lines (set/remember name, change language)
    - study-mode/solver prompts (physics/chem/math/plot/steps, equations/units)
    """
    if not os.path.exists(INTERACTION_LOG):
        return {}

    # Start with phrases from COMMAND_MAP as trivial tokens (split into words)
    trivial_words = set()
    for phrases in COMMAND_MAP.values():
        for phrase in phrases:
            for token in phrase.lower().split():
                if token.isalpha():
                    trivial_words.add(token)

    # Also mark single-token command nouns as trivial
    trivial_words.update(TRIVIAL_COMMAND_TOKENS)

    tags = {
        "theme": set(),
        "object": set(),
        "emotion": set(),
        "personal_tag": set()
    }

    with open(INTERACTION_LOG, "r", encoding="utf-8") as f:
        for line in f:
            if "User:" not in line:
                continue
            content = line.split("User:")[-1].strip()

            # Skip commands, modes, homework-style lines entirely
            if _skip_line_for_preferences(content):
                continue

            # Tokenize similar to original (keep isalpha to allow unicode letters)
            words = [w for w in content.lower().split() if w.isalpha() and len(w) > 3]

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
                    # Only accept as 'personal tag' if it isn't command-y by itself
                    if not re.search(r"\b(mode|solve|plot|graph|open|launch|play|steps)\b", word):
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
        pretty_obj = _naturalize_object(object_) if object_ else None
        poem = template.format(
            name=name,
            theme=theme,
            object=pretty_obj or "stardust",
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
