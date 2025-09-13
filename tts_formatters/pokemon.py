# tts_formatters/pokemon.py
# Multilingual TTS builders for Pokémon actions with type-based flair.
# Rules:
# - list/show: NO "by who"
# - flair: used for "show"; for "list" only when filtered to a single type
# - add/update/delete: include "by {who}"
# - Name support: show/update/delete accept an optional name and speak "Name (Pokémon 7)"

from memory_handler import load_from_memory
import re

# --- Flair words per type (short, TTS-friendly) ---
FLAIR = {
    "en": {
        "Electric":"Zap!", "Fire":"Blaze!", "Water":"Splash!", "Grass":"Bloom!", "Ice":"Frost!",
        "Rock":"Rumble!", "Ground":"Quake!", "Flying":"Whoosh!", "Bug":"Buzz!", "Poison":"Venom!",
        "Fighting":"Strike!", "Psychic":"Focus!", "Ghost":"Boo!", "Dark":"Shadow!",
        "Dragon":"Roar!", "Steel":"Clang!", "Fairy":"Twinkle!", "Normal":"Ready!"
    },
    "hi": {
        "Electric":"चमक!", "Fire":"धधक!", "Water":"छपाक!", "Grass":"खिल!", "Ice":"बर्फ!",
        "Rock":"धड़ाम!", "Ground":"कंपन!", "Flying":"फुर्र!", "Bug":"भनभन!", "Poison":"विष!",
        "Fighting":"वार!", "Psychic":"ध्यान!", "Ghost":"भूत!", "Dark":"छाया!",
        "Dragon":"दहाड़!", "Steel":"खनक!", "Fairy":"झिलमिल!", "Normal":"तैयार!"
    },
    "de": {
        "Electric":"Blitz!", "Fire":"Flamm!", "Water":"Platsch!", "Grass":"Blüh!", "Ice":"Frost!",
        "Rock":"Rums!", "Ground":"Beben!", "Flying":"Wusch!", "Bug":"Summ!", "Poison":"Gift!",
        "Fighting":"Schlag!", "Psychic":"Fokus!", "Ghost":"Buh!", "Dark":"Schatten!",
        "Dragon":"Brüll!", "Steel":"Klang!", "Fairy":"Glitzer!", "Normal":"Bereit!"
    },
    "fr": {
        "Electric":"Éclair!", "Fire":"Flamme!", "Water":"Plouf!", "Grass":"Pousse!", "Ice":"Givre!",
        "Rock":"Boum!", "Ground":"Tremble!", "Flying":"Fiu!", "Bug":"Bzz!", "Poison":"Venin!",
        "Fighting":"Coup!", "Psychic":"Esprit!", "Ghost":"Bouh!", "Dark":"Ombre!",
        "Dragon":"Rugis!", "Steel":"Clang!", "Fairy":"Étincelle!", "Normal":"Prêt!"
    },
    "es": {
        "Electric":"¡Chispa!", "Fire":"¡Llama!", "Water":"¡Chof!", "Grass":"¡Brota!", "Ice":"¡Escarcha!",
        "Rock":"¡Pum!", "Ground":"¡Temblor!", "Flying":"¡Fiuuu!", "Bug":"¡Bzz!", "Poison":"¡Veneno!",
        "Fighting":"¡Golpe!", "Psychic":"¡Foco!", "Ghost":"¡Buu!", "Dark":"¡Sombra!",
        "Dragon":"¡Rugido!", "Steel":"¡Clang!", "Fairy":"¡Brillo!", "Normal":"¡Listo!"
    }
}

# Official-ish type names per language (for nicer speech)
TYPE_NAMES = {
    "en": {"Electric":"Electric","Fire":"Fire","Water":"Water","Grass":"Grass","Ice":"Ice","Rock":"Rock","Ground":"Ground","Flying":"Flying","Bug":"Bug","Poison":"Poison","Fighting":"Fighting","Psychic":"Psychic","Ghost":"Ghost","Dark":"Dark","Dragon":"Dragon","Steel":"Steel","Fairy":"Fairy","Normal":"Normal"},
    "hi": {"Electric":"इलेक्ट्रिक","Fire":"फायर","Water":"वॉटर","Grass":"ग्रास","Ice":"आइस","Rock":"रॉक","Ground":"ग्राउंड","Flying":"फ्लाइंग","Bug":"बग","Poison":"पॉइज़न","Fighting":"फाइटिंग","Psychic":"साइकीक","Ghost":"घोस्ट","Dark":"डार्क","Dragon":"ड्रैगन","Steel":"स्टील","Fairy":"फेयरी","Normal":"नॉर्मल"},
    "de": {"Electric":"Elektro","Fire":"Feuer","Water":"Wasser","Grass":"Pflanze","Ice":"Eis","Rock":"Gestein","Ground":"Boden","Flying":"Flug","Bug":"Käfer","Poison":"Gift","Fighting":"Kampf","Psychic":"Psycho","Ghost":"Geist","Dark":"Unlicht","Dragon":"Drache","Steel":"Stahl","Fairy":"Fee","Normal":"Normal"},
    "fr": {"Electric":"Électrik","Fire":"Feu","Water":"Eau","Grass":"Plante","Ice":"Glace","Rock":"Roche","Ground":"Sol","Flying":"Vol","Bug":"Insecte","Poison":"Poison","Fighting":"Combat","Psychic":"Psy","Ghost":"Spectre","Dark":"Ténèbres","Dragon":"Dragon","Steel":"Acier","Fairy":"Fée","Normal":"Normal"},
    "es": {"Electric":"Eléctrico","Fire":"Fuego","Water":"Agua","Grass":"Planta","Ice":"Hielo","Rock":"Roca","Ground":"Tierra","Flying":"Volador","Bug":"Bicho","Poison":"Veneno","Fighting":"Lucha","Psychic":"Psíquico","Ghost":"Fantasma","Dark":"Siniestro","Dragon":"Dragón","Steel":"Acero","Fairy":"Hada","Normal":"Normal"}
}

# Templates: list/show DO NOT include "by who"
# NOTE: update/delete/show use {label} so we can insert "Name (Pokémon 7)" when available.
TEMPLATES = {
    "en": {
        "add":       "{flair} {name} added by {who}.",
        "update":    "{flair} Updated {label} to level {lvl}, type {ptype} — by {who}.",
        "delete":    "{flair} Deleted {label} — by {who}.",
        "list":      "You have {n} Pokémon.",
        "list_type": "You have {n} {ptype} Pokémon.",
        "show":      "{flair}{space}{label}: level {lvl}, type {ptype}."
    },
    "hi": {
        "add":       "{flair} {name} {who} द्वारा जोड़ा गया।",
        "update":    "{flair} {label} अब स्तर {lvl}, प्रकार {ptype} — {who} द्वारा।",
        "delete":    "{flair} {label} हटाया गया — {who} द्वारा।",
        "list":      "आपके पास {n} पोकेमोन हैं।",
        "list_type": "आपके पास {n} {ptype} पोकेमोन हैं।",
        "show":      "{flair}{space}{label}: स्तर {lvl}, प्रकार {ptype}।"
    },
    "de": {
        "add":       "{flair} {name} hinzugefügt — von {who}.",
        "update":    "{flair} {label} auf Level {lvl}, Typ {ptype} — von {who}.",
        "delete":    "{flair} {label} gelöscht — von {who}.",
        "list":      "Du hast {n} Pokémon.",
        "list_type": "Du hast {n} {ptype}-Pokémon.",
        "show":      "{flair}{space}{label}: Level {lvl}, Typ {ptype}."
    },
    "fr": {
        "add":       "{flair} {name} ajouté — par {who}.",
        "update":    "{flair} {label} au niveau {lvl}, type {ptype} — par {who}.",
        "delete":    "{flair} {label} supprimé — par {who}.",
        "list":      "Vous avez {n} Pokémon.",
        "list_type": "Vous avez {n} Pokémon {ptype}.",
        "show":      "{flair}{space}{label} : niveau {lvl}, type {ptype}."
    },
    "es": {
        "add":       "{flair} {name} añadido — por {who}.",
        "update":    "{flair} {label} a nivel {lvl}, tipo {ptype} — por {who}.",
        "delete":    "{flair} {label} eliminado — por {who}.",
        "list":      "Tienes {n} Pokémon.",
        "list_type": "Tienes {n} Pokémon de tipo {ptype}.",
        "show":      "{flair}{space}{label}: nivel {lvl}, tipo {ptype}."
    }
}

# Localized word for "Pokémon" inside the label (only Hindi differs here)
POKEMON_WORD = {
    "en": "Pokémon",
    "hi": "पोकेमोन",
    "de": "Pokémon",
    "fr": "Pokémon",
    "es": "Pokémon",
}

# --- helpers ---
def _who() -> str:
    n = (load_from_memory("name") or "").strip()
    return n if n else "You"

def _lang(lang: str) -> str:
    return lang if lang in FLAIR else "en"

def _primary(ptype: str) -> str:
    return re.split(r"\s*/\s*", (ptype or "").strip())[0].title()

def _flair(ptype: str, lang: str) -> str:
    L = _lang(lang); P = _primary(ptype)
    return FLAIR[L].get(P, FLAIR[L]["Normal"])

def _ptype_local(ptype: str, lang: str) -> str:
    L = _lang(lang)
    parts = [p.strip().title() for p in re.split(r"\s*/\s*", ptype or "") if p.strip()]
    mapped = [TYPE_NAMES[L].get(p, p) for p in parts]
    return " / ".join(mapped) if mapped else TYPE_NAMES[L]["Normal"]

def _label(pid: int, name: str | None, lang: str) -> str:
    L = _lang(lang)
    poke_word = POKEMON_WORD.get(L, "Pokémon")
    base = f"{poke_word} {pid}"
    return f"{name} ({base})" if name else base

# --- builders ---
def tts_add(name: str, ptype: str, lang: str) -> str:
    L = _lang(lang); tpl = TEMPLATES[L]["add"]
    return tpl.format(flair=_flair(ptype, L), name=name, who=_who())

def tts_update(pid: int, lvl: int, ptype: str, lang: str, name: str | None = None) -> str:
    L = _lang(lang); tpl = TEMPLATES[L]["update"]
    return tpl.format(
        flair=_flair(ptype, L),
        label=_label(pid, name, L),
        lvl=lvl,
        ptype=_ptype_local(ptype, L),
        who=_who()
    )

def tts_delete(pid: int, ptype: str, lang: str, name: str | None = None) -> str:
    L = _lang(lang); tpl = TEMPLATES[L]["delete"]
    return tpl.format(
        flair=_flair(ptype, L),
        label=_label(pid, name, L),
        who=_who()
    )

def tts_list(n: int, lang: str, ptype: str | None = None) -> str:
    """
    If a single type filter is provided, include flair and the localized type name.
    Otherwise just the count.
    """
    L = _lang(lang)
    if ptype:
        primary = _primary(ptype)
        type_local = _ptype_local(primary, L)
        flair = _flair(primary, L)
        tpl = TEMPLATES[L]["list_type"]
        return f"{flair} " + tpl.format(n=n, ptype=type_local)
    else:
        tpl = TEMPLATES[L]["list"]
        return tpl.format(n=n)

def tts_show(pid: int, lvl: int, ptype: str, lang: str, name: str | None = None, use_flair: bool = True) -> str:
    L = _lang(lang)
    tpl = TEMPLATES[L]["show"]
    flair = _flair(ptype, L) if use_flair else ""
    space = " " if flair else ""
    return tpl.format(
        flair=flair,
        space=space,
        label=_label(pid, name, L),
        lvl=lvl,
        ptype=_ptype_local(ptype, L)
    )
