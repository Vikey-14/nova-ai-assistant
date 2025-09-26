# handlers/pokemon_commands.py
from __future__ import annotations

import os
import re
import csv
import difflib
from typing import List, Dict, Optional, Tuple
from followup import confirm_did_you_mean
from say_show import say_show_texts


# GUI + TTS
from gui_interface import nova_gui
from utils import selected_language, resource_path
from memory_handler import load_from_memory

# FastAPI clients (all-in-one client in integrations/pokemon_client.py)
from integrations.pokemon_client import (
    list_pokemon, add_pokemon, update_pokemon, delete_pokemon,
    # images
    upload_image_single, upload_images_multi, get_gallery_url,
    # team
    team_list, team_add, team_remove, team_upgrade, team_average_level,
    # trainer
    trainer_me, trainer_update,
)

# Optional helpers (download + server-side CSV)
try:
    from integrations.pokemon_client import download_image, download_battle_log, download_file, upload_csv  # type: ignore
except Exception:  # keep app running even if helper isn't present yet
    download_image = download_battle_log = download_file = upload_csv = None  # type: ignore

# Fuzzy + command map (multilingual triggers)
from command_map import COMMAND_MAP
from fuzzy_utils import fuzzy_in

# TTS formatters (add/update/delete/list/show — multilingual + flair)
from tts_formatters.pokemon import (
    tts_add, tts_list, tts_show, TYPE_NAMES
)


# FOLLOW-UP (typed + voice) helpers — lazy to avoid circular imports
def _lazy_followup():
    # bring these in only when needed (prevents circular-import headaches)
    from utils import _speak_multilang, speak, listen_command
    from followup import await_followup
    from gui_interface import nova_gui
    return _speak_multilang, speak, listen_command, await_followup, nova_gui


# ────────────────────────────────────────────────────────────────
# Multilingual help
# ────────────────────────────────────────────────────────────────
HELP_TEXT: dict[str, str] = {
    "en": (
        "Pokémon commands:\n"
        "• list pokemon\n"
        "• list electric type\n"
        "• show pokemon 3\n"
        "• add pikachu level 12 electric nickname pika\n"
        "• update pokemon 3 level 20\n"
        "• update pokemon 3 type water nickname buddy\n"
        "• delete pokemon 4\n"
        "\nImages & Gallery:\n"
        "• upload pokemon image (add 'secure' for signed upload)\n"
        "• upload pokemon images (add 'secure' for signed upload)\n"
        "• open pokemon gallery\n"
        "• download pokemon image <filename>\n"
        "• download battle log\n"
        "• download file <name.csv|.txt>\n"
        "\nImport/Export:\n"
        "• import pokemon csv\n"
        "• upload csv to server (validated)\n"
        "\nTeam:\n"
        "• show team\n"
        "• add 5 to team / remove 5 from team\n"
        "• upgrade team 5 to level 20\n"
        "• team average level\n"
        "\nTrainer:\n"
        "• my trainer profile\n"
        "• trainer nickname is Amy\n"
        "• location is Pallet Town\n"
        "• pronouns are she/her"
    ),
    "hi": (
        "पोकेमोन कमांड्स:\n"
        "• पोकेमोन सूची दिखाओ\n"
        "• इलेक्ट्रिक टाइप की सूची\n"
        "• पोकेमोन 3 दिखाओ\n"
        "• पिकाचू जोड़ो — लेवल 12, टाइप इलेक्ट्रिक, निकनेम 'pika'\n"
        "• पोकेमोन 3 का लेवल 20 कर दो\n"
        "• पोकेमोन 3 का टाइप वॉटर कर दो, निकनेम 'buddy'\n"
        "• पोकेमोन 4 हटाओ\n"
        "\nइमेज व गैलरी:\n"
        "• पोकेमोन इमेज अपलोड करो (सिक्योर कहें तो साइन किया हुआ)\n"
        "• कई इमेज अपलोड करो (सिक्योर कहें तो साइन किया हुआ)\n"
        "• पोकेमोन गैलरी खोलो\n"
        "• पोकेमोन इमेज डाउनलोड <filename>\n"
        "• बैटल लॉग डाउनलोड\n"
        "• फाइल डाउनलोड <name.csv|.txt>\n"
        "\nइम्पोर्ट/एक्सपोर्ट:\n"
        "• पोकेमोन CSV इम्पोर्ट\n"
        "• CSV सर्वर पर अपलोड (validated)\n"
        "\nटीम:\n"
        "• टीम दिखाओ\n"
        "• 5 को टीम में जोड़ो / 5 को टीम से हटाओ\n"
        "• टीम के 5 का लेवल 20 करो\n"
        "• टीम का औसत लेवल\n"
        "\nट्रेनर:\n"
        "• मेरा ट्रेनर प्रोफ़ाइल\n"
        "• ट्रेनर निकनेम Amy है\n"
        "• लोकेशन Pallet Town है\n"
        "• प्रोनाउन्स she/her हैं"
    ),
    "fr": (
        "Commandes Pokémon :\n"
        "• lister les Pokémon\n"
        "• lister le type électrique\n"
        "• afficher Pokémon 3\n"
        "• ajouter Pikachu niveau 12 type électrique surnom pika\n"
        "• mettre à jour Pokémon 3 niveau 20\n"
        "• mettre à jour Pokémon 3 type eau surnom buddy\n"
        "• supprimer Pokémon 4\n"
        "\nImages & Galerie :\n"
        "• téléverser une image Pokémon (ajouter « secure » pour signé)\n"
        "• téléverser des images Pokémon (ajouter « secure » pour signé)\n"
        "• ouvrir la galerie Pokémon\n"
        "• télécharger une image Pokémon <filename>\n"
        "• télécharger le journal de combat\n"
        "• télécharger le fichier <name.csv|.txt>\n"
        "\nImport/Export :\n"
        "• importer un CSV Pokémon\n"
        "• téléverser le CSV vers le serveur (validé)\n"
        "\nÉquipe :\n"
        "• afficher l’équipe\n"
        "• ajouter 5 à l’équipe / retirer 5 de l’équipe\n"
        "• améliorer l’équipe 5 au niveau 20\n"
        "• niveau moyen de l’équipe\n"
        "\nDresseur :\n"
        "• mon profil de dresseur\n"
        "• le surnom du dresseur est Amy\n"
        "• la localisation est Bourg Palette\n"
        "• les pronoms sont she/her"
    ),
    "es": (
        "Comandos de Pokémon:\n"
        "• listar pokémon\n"
        "• listar tipo eléctrico\n"
        "• mostrar pokémon 3\n"
        "• agregar pikachu nivel 12 tipo eléctrico apodo pika\n"
        "• actualizar pokémon 3 a nivel 20\n"
        "• actualizar pokémon 3 a tipo agua apodo buddy\n"
        "• borrar pokémon 4\n"
        "\nImágenes y galería:\n"
        "• subir imagen de pokémon (añade 'secure' para firmado)\n"
        "• subir imágenes de pokémon (añade 'secure' para firmado)\n"
        "• abrir galería de pokémon\n"
        "• descargar imagen de pokémon <filename>\n"
        "• descargar registro de batalla\n"
        "• descargar archivo <name.csv|.txt>\n"
        "\nImportar/Exportar:\n"
        "• importar csv de pokémon\n"
        "• subir csv al servidor (validado)\n"
        "\nEquipo:\n"
        "• mostrar equipo\n"
        "• añadir 5 al equipo / quitar 5 del equipo\n"
        "• subir al equipo 5 al nivel 20\n"
        "• nivel promedio del equipo\n"
        "\nEntrenador:\n"
        "• mi perfil de entrenador\n"
        "• el apodo del entrenador es Amy\n"
        "• la ubicación es Pueblo Paleta\n"
        "• los pronombres son she/her"
    ),
    "de": (
        "Pokémon-Befehle:\n"
        "• pokémon auflisten\n"
        "• elektrischer typ auflisten\n"
        "• pokémon 3 anzeigen\n"
        "• pikachu hinzufügen — level 12, typ elektrisch, spitzname pika\n"
        "• pokémon 3 auf level 20 setzen\n"
        "• pokémon 3 auf typ wasser setzen, spitzname buddy\n"
        "• pokémon 4 löschen\n"
        "\nBilder & Galerie:\n"
        "• pokémon-bild hochladen (mit „secure“ signiert)\n"
        "• pokémon-bilder hochladen (mit „secure“ signiert)\n"
        "• pokémon-galerie öffnen\n"
        "• pokémon-bild herunterladen <filename>\n"
        "• kampfprotokoll herunterladen\n"
        "• datei herunterladen <name.csv|.txt>\n"
        "\nImport/Export:\n"
        "• pokémon-csv importieren\n"
        "• csv zum server hochladen (validiert)\n"
        "\nTeam:\n"
        "• team anzeigen\n"
        "• 5 zum team hinzufügen / 5 aus dem team entfernen\n"
        "• team-mitglied 5 auf level 20 upgraden\n"
        "• durchschnittliches team-level\n"
        "\nTrainer:\n"
        "• mein trainer-profil\n"
        "• trainer-spitzname ist Amy\n"
        "• ort ist Alabastia (Pallet Town)\n"
        "• pronomen sind she/her"
    ),
}

SPEAK_HELP: dict[str, str] = {
    "en": "Showing Pokémon help.",
    "hi": "पोकेमोन मदद दिखा रही हूँ.",
    "fr": "J’affiche l’aide Pokémon.",
    "es": "Mostrando la ayuda de Pokémon.",
    "de": "Ich zeige die Pokémon-Hilfe an.",
}

# Localized field labels for GUI change-lists
LABELS = {
    "en": {"type": "type", "nickname": "nickname", "level": "level"},
    "hi": {"type": "टाइप", "nickname": "निकनेम", "level": "लेवल"},
    "fr": {"type": "type", "nickname": "surnom", "level": "niveau"},
    "es": {"type": "tipo", "nickname": "apodo", "level": "nivel"},
    "de": {"type": "typ", "nickname": "spitzname", "level": "Level"},
}


YOU_WORD = {
    "en": "You",
    "hi": "आप",
    "fr": "Vous",
    "es": "Tú",
    "de": "Du",
}

PROFILE_LABELS = {
    "en": {"nickname": "Nickname", "location": "Location", "pronouns": "Pronouns"},
    "hi": {"nickname": "निकनेम", "location": "स्थान", "pronouns": "प्रोनाउन्स"},
    "fr": {"nickname": "Surnom", "location": "Localisation", "pronouns": "Pronoms"},
    "es": {"nickname": "Apodo", "location": "Ubicación", "pronouns": "Pronombres"},
    "de": {"nickname": "Spitzname", "location": "Ort", "pronouns": "Pronomen"},
}


# ────────────────────────────────────────────────────────────────
# Generic multilingual messages
# ────────────────────────────────────────────────────────────────
MSG: Dict[str, Dict[str, str]] = {
    # Images/Gallery
    "gallery_open": {
        "en": "Opening the Pokémon gallery.",
        "hi": "पोकेमोन गैलरी खोल रही हूँ.",
        "fr": "J’ouvre la galerie Pokémon.",
        "es": "Abriendo la galería de Pokémon.",
        "de": "Ich öffne die Pokémon-Galerie.",
    },
    "open_gallery_gui": {
        "en": "Opening Pokémon gallery:\n{url}",
        "hi": "पोकेमोन गैलरी खोल रही हूँ:\n{url}",
        "fr": "Ouverture de la galerie Pokémon :\n{url}",
        "es": "Abriendo la galería de Pokémon:\n{url}",
        "de": "Pokémon-Galerie wird geöffnet:\n{url}",
    },
    "no_images_selected": {
        "en": "No Images selected.",
        "hi": "कोई इमेज चयन नहीं की गई.",
        "fr": "Aucune image sélectionnée.",
        "es": "No se seleccionaron imágenes.",
        "de": "Keine Bilder ausgewählt.",
    },
    "no_image_selected": {
        "en": "No Image selected.",
        "hi": "कोई इमेज चयन नहीं की गई.",
        "fr": "Aucune image sélectionnée.",
        "es": "No se seleccionó ninguna imagen.",
        "de": "Kein Bild ausgewählt.",
    },
    "images_uploaded_say": {
        "en": "Uploaded {n} Images.",
        "hi": "{n} इमेज अपलोड कर दी हैं.",
        "fr": "{n} images téléversées.",
        "es": "Se subieron {n} imágenes.",
        "de": "{n} Bilder hochgeladen.",
    },
    "images_uploaded_gui": {
        "en": "Uploaded {n} Images by {who}.",
        "hi": "{who} द्वारा {n} इमेज अपलोड की गईं.",
        "fr": "{n} images téléversées par {who}.",
        "es": "{n} imágenes subidas por {who}.",
        "de": "{n} Bilder hochgeladen von {who}.",
    },
    "image_uploaded_say": {
        "en": "Image Uploaded.",
        "hi": "इमेज अपलोड हो गई.",
        "fr": "Image téléversée.",
        "es": "Imagen subida.",
        "de": "Bild hochgeladen.",
    },
    "image_uploaded_gui": {
        "en": "Uploaded Image “{base}” by {who}.",
        "hi": "“{base}” इमेज {who} द्वारा अपलोड की गई.",
        "fr": "Image « {base} » téléversée par {who}.",
        "es": "Imagen “{base}” subida por {who}.",
        "de": "Bild „{base}“ hochgeladen von {who}.",
    },
    "image_upload_failed": {
        "en": "Image Upload failed.",
        "hi": "इमेज अपलोड असफल रहा.",
        "fr": "Échec du téléversement de l’image.",
        "es": "Falló la subida de la imagen.",
        "de": "Bild-Upload fehlgeschlagen.",
    },

    # Downloads
    "image_download_started": {
        "en": "Downloading Image…",
        "hi": "इमेज डाउनलोड कर रही हूँ…",
        "fr": "Téléchargement de l’image…",
        "es": "Descargando imagen…",
        "de": "Bild wird heruntergeladen…",
    },
    "image_download_ok": {
        "en": "Image downloaded to {path}.",
        "hi": "इमेज {path} पर डाउनलोड हो गई है.",
        "fr": "Image téléchargée dans {path}.",
        "es": "Imagen descargada en {path}.",
        "de": "Bild nach {path} heruntergeladen.",
    },
    "image_download_failed": {
        "en": "Image download failed.",
        "hi": "इमेज डाउनलोड असफल रहा.",
        "fr": "Échec du téléchargement de l’image.",
        "es": "Falló la descarga de la imagen.",
        "de": "Bild-Download fehlgeschlagen.",
    },
    "image_download_need_name": {
        "en": "Please specify a filename to download (e.g., download pokemon image pikachu.png).",
        "hi": "कृपया डाउनलोड के लिए फ़ाइलनाम बताइए (उदा., download pokemon image pikachu.png).",
        "fr": "Veuillez préciser un nom de fichier à télécharger (p. ex. : download pokemon image pikachu.png).",
        "es": "Especifica un nombre de archivo para descargar (p. ej., download pokemon image pikachu.png).",
        "de": "Bitte einen Dateinamen zum Herunterladen angeben (z. B.: download pokemon image pikachu.png).",
    },
    "battle_log_download_ok": {
        "en": "Battle log downloaded to {path}.",
        "hi": "बैटल लॉग {path} पर डाउनलोड किया गया.",
        "fr": "Journal de combat téléchargé dans {path}.",
        "es": "Registro de batalla descargado en {path}.",
        "de": "Kampfprotokoll nach {path} heruntergeladen.",
    },
    "battle_log_download_failed": {
        "en": "Battle log download failed.",
        "hi": "बैटल लॉग डाउनलोड असफल रहा.",
        "fr": "Échec du téléchargement du journal de combat.",
        "es": "Error al descargar el registro de batalla.",
        "de": "Kampfprotokoll-Download fehlgeschlagen.",
    },
    "file_download_ok": {
        "en": "File downloaded to {path}.",
        "hi": "फ़ाइल {path} पर डाउनलोड हो गई.",
        "fr": "Fichier téléchargé dans {path}.",
        "es": "Archivo descargado en {path}.",
        "de": "Datei nach {path} heruntergeladen.",
    },
    "file_download_failed": {
        "en": "File download failed.",
        "hi": "फ़ाइल डाउनलोड असफल रहा.",
        "fr": "Échec du téléchargement du fichier.",
        "es": "Error al descargar el archivo.",
        "de": "Datei-Download fehlgeschlagen.",
    },

    # CSV Import
    "csv_pick_none": {
        "en": "No CSV selected.",
        "hi": "कोई CSV चयन नहीं की गई.",
        "fr": "Aucun CSV sélectionné.",
        "es": "No se seleccionó ningún CSV.",
        "de": "Keine CSV ausgewählt.",
    },
    "csv_import_started": {
        "en": "Importing Pokémon from CSV…",
        "hi": "CSV से पोकेमोन इम्पोर्ट कर रही हूँ…",
        "fr": "Importation des Pokémon depuis le CSV…",
        "es": "Importando Pokémon desde el CSV…",
        "de": "Importiere Pokémon aus CSV…",
    },
    "csv_import_ok": {
        "en": "Imported {ok} Pokémon. {fail} failed.",
        "hi": "{ok} पोकेमोन इम्पोर्ट हुए. {fail} असफल रहे.",
        "fr": "{ok} Pokémon importés. {fail} en échec.",
        "es": "Se importaron {ok} Pokémon. {fail} fallaron.",
        "de": "{ok} Pokémon importiert. {fail} fehlgeschlagen.",
    },
    "csv_import_failed": {
        "en": "CSV import failed.",
        "hi": "CSV इम्पोर्ट असफल रहा.",
        "fr": "Échec de l’import CSV.",
        "es": "Error en la importación del CSV.",
        "de": "CSV-Import fehlgeschlagen.",
    },
    "csv_upload_ok": {
        "en": "CSV uploaded to server.",
        "hi": "CSV सर्वर पर अपलोड किया गया.",
        "fr": "CSV téléversé sur le serveur.",
        "es": "CSV subido al servidor.",
        "de": "CSV auf den Server hochgeladen.",
    },
    "csv_upload_failed": {
        "en": "CSV upload failed.",
        "hi": "CSV अपलोड असफल रहा.",
        "fr": "Échec du téléversement du CSV.",
        "es": "Error al subir el CSV.",
        "de": "CSV-Upload fehlgeschlagen.",
    },

    # Team
    "team_count": {
        "en": "Your team has {n} Pokémon.",
        "hi": "आपकी टीम में {n} पोकेमोन हैं.",
        "fr": "Votre équipe compte {n} Pokémon.",
        "es": "Tu equipo tiene {n} Pokémon.",
        "de": "Dein Team hat {n} Pokémon.",
    },
    "team_updated": {
        "en": "Team Updated.",
        "hi": "टीम अपडेट कर दी है.",
        "fr": "Équipe mise à jour.",
        "es": "Equipo actualizado.",
        "de": "Team aktualisiert.",
    },
    "team_add_failed": {
        "en": "Add to team failed.",
        "hi": "टीम में जोड़ना असफल रहा.",
        "fr": "Échec de l’ajout à l’équipe.",
        "es": "Error al añadir al equipo.",
        "de": "Hinzufügen zum Team fehlgeschlagen.",
    },
    "team_remove_failed": {
        "en": "Remove from team failed.",
        "hi": "टीम से हटाना असफल रहा.",
        "fr": "Échec du retrait de l’équipe.",
        "es": "Error al quitar del equipo.",
        "de": "Entfernen aus dem Team fehlgeschlagen.",
    },
    "team_upgrade_failed": {
        "en": "Team Upgrade failed.",
        "hi": "टीम अपग्रेड असफल रहा.",
        "fr": "Échec de la montée de niveau de l’équipe.",
        "es": "Error al mejorar el equipo.",
        "de": "Team-Upgrade fehlgeschlagen.",
    },
    "team_member_set_level_say": {
        "en": "Team member {pid} set to level {lvl}.",
        "hi": "टीम सदस्य {pid} का लेवल {lvl} कर दिया है.",
        "fr": "Membre d’équipe {pid} réglé au niveau {lvl}.",
        "es": "Miembro del equipo {pid} puesto al nivel {lvl}.",
        "de": "Teammitglied {pid} auf Level {lvl} gesetzt.",
    },
    "team_member_set_level_gui": {
        "en": "Team Pokémon {pid} → level {lvl} — by {who}.",
        "hi": "टीम पोकेमोन {pid} → लेवल {lvl} — {who} द्वारा.",
        "fr": "Pokémon d’équipe {pid} → niveau {lvl} — par {who}.",
        "es": "Pokémon del equipo {pid} → nivel {lvl} — por {who}.",
        "de": "Team-Pokémon {pid} → Level {lvl} — von {who}.",
    },
    "team_avg_shown": {
        "en": "Team average level shown.",
        "hi": "टीम का औसत स्तर दिखा रही हूँ.",
        "fr": "Niveau moyen de l’équipe affiché.",
        "es": "Nivel promedio del equipo mostrado.",
        "de": "Durchschnittslevel des Teams angezeigt.",
    },
    "team_avg_is": {
        "en": "Team average level is {avg}.",
        "hi": "टीम का औसत लेवल {avg} है.",
        "fr": "Le niveau moyen de l’équipe est {avg}.",
        "es": "El nivel promedio del equipo es {avg}.",
        "de": "Das durchschnittliche Team-Level ist {avg}.",
    },
    "team_avg_failed": {
        "en": "Could not compute team average.",
        "hi": "टीम का औसत निकाल नहीं पाई.",
        "fr": "Impossible de calculer la moyenne de l’équipe.",
        "es": "No se pudo calcular el promedio del equipo.",
        "de": "Team-Durchschnitt konnte nicht berechnet werden.",
    },
    "team_avg_gui": {
        "en": "Team average level: {avg}",
        "hi": "टीम का औसत स्तर: {avg}",
        "fr": "Niveau moyen de l’équipe : {avg}",
        "es": "Nivel promedio del equipo: {avg}",
        "de": "Durchschnittliches Team-Level: {avg}",
    },
    "team_fetch_failed": {
        "en": "Could not fetch team.",
        "hi": "टीम लाने में समस्या आई.",
        "fr": "Impossible de récupérer l’équipe.",
        "es": "No se pudo obtener el equipo.",
        "de": "Team konnte nicht abgerufen werden.",
    },

    # Pokémon generic GUI / errors
    "you_have_n": {
        "en": "You have {n} Pokémon.",
        "hi": "आपके पास {n} पोकेमोन हैं.",
        "fr": "Vous avez {n} Pokémon.",
        "es": "Tienes {n} Pokémon.",
        "de": "Du hast {n} Pokémon.",
    },
    "pokemon_summary": {
        "en": "Pokémon {pid}: level → {lvl}, type → {ptype}.",
        "hi": "पोकेमोन {pid}: लेवल → {lvl}, टाइप → {ptype}.",
        "fr": "Pokémon {pid} : niveau → {lvl}, type → {ptype}.",
        "es": "Pokémon {pid}: nivel → {lvl}, tipo → {ptype}.",
        "de": "Pokémon {pid}: Level → {lvl}, Typ → {ptype}.",
    },
    "added_by": {
        "en": "{name} added by {who}!",
        "hi": "{name} को {who} द्वारा जोड़ा गया!",
        "fr": "{name} ajouté·e par {who} !",
        "es": "¡{name} añadido por {who}!",
        "de": "{name} wurde von {who} hinzugefügt!",
    },
    "updated_level_gui": {
        "en": "Updated Pokémon {pid} to level → {lvl} by {who}.",
        "hi": "पोकेमोन {pid} का लेवल → {lvl} कर दिया — {who} द्वारा.",
        "fr": "Pokémon {pid} mis au niveau → {lvl} — par {who}.",
        "es": "Pokémon {pid} actualizado al nivel → {lvl} — por {who}.",
        "de": "Pokémon {pid} auf Level → {lvl} gesetzt — von {who}.",
    },
    "updated_fields_gui": {
        "en": "Updated Pokémon {pid}: {changes} — by {who}.",
        "hi": "पोकेमोन {pid} अपडेट: {changes} — {who} द्वारा.",
        "fr": "Pokémon {pid} mis à jour : {changes} — par {who}.",
        "es": "Pokémon {pid} actualizado: {changes} — por {who}.",
        "de": "Pokémon {pid} aktualisiert: {changes} — von {who}.",
    },
    "deleted_gui": {
        "en": "Deleted Pokémon {pid} by {who}.",
        "hi": "पोकेमोन {pid} हटाया — {who} द्वारा.",
        "fr": "Pokémon {pid} supprimé — par {who}.",
        "es": "Pokémon {pid} eliminado — por {who}.",
        "de": "Pokémon {pid} gelöscht — von {who}.",
    },
    "pokemon_not_found": {
        "en": "Pokémon {pid} not found.",
        "hi": "पोकेमोन {pid} नहीं मिला.",
        "fr": "Pokémon {pid} introuvable.",
        "es": "Pokémon {pid} no encontrado.",
        "de": "Pokémon {pid} nicht gefunden.",
    },

    "type_unknown": {
        "en": "Sorry, I couldn't understand the type.",
        "hi": "माफ़ करें, मैं टाइप समझ नहीं पाई।",
        "fr": "Désolé, je n’ai pas compris le type.",
        "es": "Lo siento, no entendí el tipo.",
        "de": "Entschuldigung, den Typ habe ich nicht verstanden.",
    },

    # Trainer
    "trainer_profile_show": {
        "en": "Trainer profile:",
        "hi": "ट्रेनर प्रोफ़ाइल:",
        "fr": "Profil du dresseur :",
        "es": "Perfil del entrenador:",
        "de": "Trainerprofil:",
    },
    "trainer_profile_failed": {
        "en": "Could not fetch trainer profile.",
        "hi": "ट्रेनर प्रोफ़ाइल लाने में समस्या आई.",
        "fr": "Impossible de récupérer le profil du dresseur.",
        "es": "No se pudo obtener el perfil del entrenador.",
        "de": "Trainerprofil konnte nicht abgerufen werden.",
    },
    "trainer_nick_updated_say": {
        "en": "Trainer nickname updated.",
        "hi": "ट्रेनर निकनेम अपडेट कर दिया.",
        "fr": "Surnom du dresseur mis à jour.",
        "es": "Apodo del entrenador actualizado.",
        "de": "Trainer-Spitzname aktualisiert.",
    },
    "trainer_nick_updated_gui": {
        "en": "Trainer nickname → {nick} — by {who}.",
        "hi": "ट्रेनर निकनेम → {nick} — {who} द्वारा.",
        "fr": "Surnom du dresseur → {nick} — par {who}.",
        "es": "Apodo del entrenador → {nick} — por {who}.",
        "de": "Trainer-Spitzname → {nick} — von {who}.",
    },
    "trainer_nick_failed": {
        "en": "Nickname update failed.",
        "hi": "निकनेम अपडेट असफल रहा.",
        "fr": "Échec de la mise à jour du surnom.",
        "es": "Error al actualizar el apodo.",
        "de": "Aktualisierung des Spitznamens fehlgeschlagen.",
    },
    "trainer_loc_updated_say": {
        "en": "Trainer location updated.",
        "hi": "ट्रेनर लोकेशन अपडेट कर दी.",
        "fr": "Localisation du dresseur mise à jour.",
        "es": "Ubicación del entrenador actualizada.",
        "de": "Trainer-Standort aktualisiert.",
    },
    "trainer_loc_updated_gui": {
        "en": "Trainer location → {loc} — by {who}.",
        "hi": "ट्रेनर लोकेशन → {loc} — {who} द्वारा.",
        "fr": "Localisation du dresseur → {loc} — par {who}.",
        "es": "Ubicación del entrenador → {loc} — por {who}.",
        "de": "Trainer-Standort → {loc} — von {who}.",
    },
    "trainer_loc_failed": {
        "en": "Location update failed.",
        "hi": "लोकेशन अपडेट असफल रहा.",
        "fr": "Échec de la mise à jour de la localisation.",
        "es": "Error al actualizar la ubicación.",
        "de": "Aktualisierung des Standorts fehlgeschlagen.",
    },
    "trainer_pron_updated_say": {
        "en": "Trainer pronouns updated.",
        "hi": "ट्रेनर प्रोनाउन्स अपडेट कर दिए.",
        "fr": "Pronoms du dresseur mis à jour.",
        "es": "Pronombres del entrenador actualizados.",
        "de": "Trainer-Pronomen aktualisiert.",
    },
    "trainer_pron_updated_gui": {
        "en": "Trainer pronouns → {pr} — by {who}.",
        "hi": "ट्रेनर प्रोनाउन्स → {pr} — {who} द्वारा.",
        "fr": "Pronoms du dresseur → {pr} — par {who}.",
        "es": "Pronombres del entrenador → {pr} — por {who}.",
        "de": "Trainer-Pronomen → {pr} — von {who}.",
    },
    "trainer_pron_failed": {
        "en": "Pronouns update failed.",
        "hi": "प्रोनाउन्स अपडेट असफल रहा.",
        "fr": "Échec de la mise à jour des pronoms.",
        "es": "Error al actualizar los pronombres.",
        "de": "Aktualisierung der Pronomen fehlgeschlagen.",
    },

    "by_word": {
        "en": "by",
        "hi": "द्वारा",
        "fr": "par",
        "es": "por",
        "de": "von",
    },

    "error_generic": {
        "en": "Error: {err}",
        "hi": "त्रुटि: {err}",
        "fr": "Erreur : {err}",
        "es": "Error: {err}",
        "de": "Fehler: {err}",
    },

    "uploading_image": {
        "en": "Uploading Image…",
        "hi": "इमेज अपलोड कर रही हूँ…",
        "fr": "Téléversement de l’image…",
        "es": "Subiendo imagen…",
        "de": "Bild wird hochgeladen…",
    },
    "uploading_images": {
        "en": "Uploading Images…",
        "hi": "इमेजेज़ अपलोड कर रही हूँ…",
        "fr": "Téléversement des images…",
        "es": "Subiendo imágenes…",
        "de": "Bilder werden hochgeladen…",
    },
    "uploading_title_image": {
        "en": "Nova — Uploading Image",
        "hi": "Nova — इमेज अपलोड",
        "fr": "Nova — Téléversement d’image",
        "es": "Nova — Subiendo imagen",
        "de": "Nova — Bild wird hochgeladen",
    },
    "uploading_title_images": {
        "en": "Nova — Uploading Images",
        "hi": "Nova — इमेजेज़ अपलोड",
        "fr": "Nova — Téléversement d’images",
        "es": "Nova — Subiendo imágenes",
        "de": "Nova — Bilder werden hochgeladen",
    },

    "select_images": {
        "en": "Select Images",
        "hi": "इमेज चुनें",
        "fr": "Sélectionner des images",
        "es": "Seleccionar imágenes",
        "de": "Bilder auswählen",
    },
    "select_image": {
        "en": "Select Image",
        "hi": "इमेज चुनें",
        "fr": "Sélectionner une image",
        "es": "Seleccionar imagen",
        "de": "Bild auswählen",
    },
    "select_pokemon_csv": {
        "en": "Select Pokémon CSV",
        "hi": "पोकेमोन CSV चुनें",
        "fr": "Sélectionner le CSV Pokémon",
        "es": "Seleccionar CSV de Pokémon",
        "de": "Pokémon-CSV auswählen",
    },

    "team_added_fallback": {
        "en": "Added Pokémon {pid} to team.",
        "hi": "पोकेमोन {pid} टीम में जोड़ दिया गया.",
        "fr": "Pokémon {pid} ajouté à l’équipe.",
        "es": "Pokémon {pid} añadido al equipo.",
        "de": "Pokémon {pid} zum Team hinzugefügt.",
    },
    "team_removed_fallback": {
        "en": "Removed Pokémon {pid} from team.",
        "hi": "पोकेमोन {pid} टीम से हटाया गया.",
        "fr": "Pokémon {pid} retiré de l’équipe.",
        "es": "Se quitó el Pokémon {pid} del equipo.",
        "de": "Pokémon {pid} aus dem Team entfernt.",
    }
}

# Short, localized follow-up prompts shown/spoken during interactive flows
_PROMPTS = {
    "ask_filename": {
        "en": "Which filename should I download?",
        "hi": "कौन-सी फ़ाइल डाउनलोड करूँ?",
        "fr": "Quel nom de fichier dois-je télécharger ?",
        "es": "¿Qué nombre de archivo debo descargar?",
        "de": "Welche Datei soll ich herunterladen?",
    },
    "ask_pid": {
        "en": "Which Pokémon ID?",
        "hi": "कौन-सा पोकेमोन ID?",
        "fr": "Quel identifiant de Pokémon ?",
        "es": "¿Qué ID de Pokémon?",
        "de": "Welche Pokémon-ID?",
    },
    "ask_level": {
        "en": "What level?",
        "hi": "किस लेवल पर?",
        "fr": "Quel niveau ?",
        "es": "¿Qué nivel?",
        "de": "Welches Level?",
    },
    "ask_type": {
        "en": "Which type?",
        "hi": "कौन-सा टाइप?",
        "fr": "Quel type ?",
        "es": "¿Qué tipo?",
        "de": "Welcher Typ?",
    },
    "ask_name": {
        "en": "What is the Pokémon’s name?",
        "hi": "पोकेमोन का नाम क्या है?",
        "fr": "Quel est le nom du Pokémon ?",
        "es": "¿Cuál es el nombre del Pokémon?",
        "de": "Wie heißt das Pokémon?",
    },
    "ask_nick": {
        "en": "Nickname? (say “skip” to leave blank)",
        "hi": "निकनेम? (खाली छोड़ने के लिए 'skip' कहें)",
        "fr": "Surnom ? (dites « skip » pour laisser vide)",
        "es": "¿Apodo? (di « skip » para dejar en blanco)",
        "de": "Spitzname? (sage „skip“, um leer zu lassen)",
    },
    "ask_update_fields": {
        "en": "What should I update — level, type, nickname (you can list multiple)?",
        "hi": "क्या अपडेट करूँ — level, type, nickname (कई बता सकते हैं)?",
        "fr": "Que dois-je mettre à jour — niveau, type, surnom (plusieurs possibles) ?",
        "es": "¿Qué debo actualizar — nivel, tipo, apodo (puedes indicar varios)?",
        "de": "Was soll ich aktualisieren — Level, Typ, Spitzname (mehrere möglich)?",
    },
    "didnt_get_it": {
        "en": "Sorry, I didn’t catch that.",
        "hi": "माफ़ कीजिए, मैं समझ नहीं पाई।",
        "fr": "Désolé, je n’ai pas compris.",
        "es": "Perdón, no entendí.",
        "de": "Entschuldige, das habe ich nicht verstanden.",
    },
}


def _say_then_show_prompt(key: str) -> str:
    from utils import selected_language
    # pull _speak_multilang from the lazy loader so it exists in this scope
    _speak_multilang, *_ = _lazy_followup()
    p = _PROMPTS[key]
    _speak_multilang(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"])  # SAY (multilingual TTS)
    bubble = p.get((selected_language or "en").lower(), p["en"])  # SHOW in current UI language (safe)
    return bubble


def _await_slot(key: str, parse_fn=None, timeout=18.0):
    _speak_multilang, speak_fn, listen_fn, await_followup, gui = _lazy_followup()

    # SAY → then SHOW happens inside this helper already
    prompt = _say_then_show_prompt(key)

    # Do NOT re-show or re-say inside await_followup:
    ans = await_followup(
        prompt,
        speak_fn=lambda *_a, **_k: None,          # ← no re-TTS
        show_fn=lambda *_a, **_k: None,           # ← no duplicate bubble
        listen_fn=listen_fn,                      # barge-in handled inside await_followup
        allow_typed=True,
        allow_voice=True,
        timeout=timeout,
    )

    if not ans:
        p = _PROMPTS["didnt_get_it"]
        _speak_multilang(p["en"], hi=p["hi"], de=p["de"], fr=p["fr"], es=p["es"])
        return None

    return parse_fn(ans) if parse_fn else (ans or "").strip()


def _parse_int(s: str):
    m = re.search(r"\b(\d+)\b", s or "")
    return int(m.group(1)) if m else None

def _parse_idlist(s: str) -> List[int]:
    return _parse_id_list(s or "")

def _parse_update_fields(s: str) -> List[str]:
    s = (s or "").lower()
    out = []
    if "level" in s or "lvl" in s: out.append("level")
    if "type" in s: out.append("type")
    if "nick" in s or "nickname" in s: out.append("nickname")
    return list(dict.fromkeys(out))

def _best_match(candidate: str, choices: list[str]) -> tuple[Optional[str], float]:
    """
    Return (best, score) using both normal and compact comparisons,
    similar spirit to fuzzy_utils.
    """
    cand = (candidate or "").strip()
    if not cand or not choices:
        return None, 0.0

    def _compact(s: str) -> str:
        return "".join(ch for ch in s.casefold() if ch.isalnum())

    c_norm, c_comp = cand.casefold(), _compact(cand)
    best = None
    best_score = 0.0

    for ch in choices:
        n, k = ch.casefold(), _compact(ch)
        s = max(difflib.SequenceMatcher(None, c_norm, n).ratio(),
                difflib.SequenceMatcher(None, c_comp, k).ratio())
        if s > best_score:
            best, best_score = ch, s
    return best, best_score


# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────
def _who():
    n = (load_from_memory("name") or "").strip()
    if n:
        return n
    from utils import selected_language
    return YOU_WORD.get(selected_language, "You")


def speak_then_show(tts_text: str, gui_text: str, title: str = "Nova") -> None:
    """Speak first (keeps Nova mouth anim), then show the bubble (central helper)."""
    say_show_texts(tts_text, gui_text, title=title)



def _t(lang: str, key: str, **kwargs) -> str:
    bank = MSG.get(key, {})
    text = bank.get(lang) or bank.get("en") or ""
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


# Localized "and" for joining names/types
_AND = {"en": "and", "hi": "और", "fr": "et", "es": "y", "de": "und"}
# Localized "more" for truncated previews
_MORE = {"en": "more", "hi": "अधिक", "fr": "de plus", "es": "más", "de": "weitere"}

def _join_names(names: List[str], lang: str) -> str:
    names = [n for n in names if (n or "").strip()]
    n = len(names)
    if n == 0: return ""
    if n == 1: return names[0]
    if n == 2: return f"{names[0]} {_AND.get(lang, 'and')} {names[1]}"
    return f"{', '.join(names[:-1])} {_AND.get(lang, 'and')} {names[-1]}"

def _names_suffix(rows: List[Dict], lang: str, limit: int = 15, preview: int = 7) -> str:
    def _label(r: Dict) -> str:
        name = (r.get("name") or "").strip()
        if name: return name
        try: return f"Pokémon {int(r.get('id'))}"
        except Exception: return "Pokémon"

    all_names = [_label(r) for r in rows]
    count = len(all_names)
    if count == 0: return ""
    if count < limit: return f": {_join_names(all_names, lang)}"
    shown = all_names[:preview]; rest = count - preview
    return f": {', '.join(shown)}, … +{rest} {_MORE.get(lang, _MORE['en'])}."


# pick files (single/multi)
def _pick_files(multiple: bool) -> List[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
        from utils import selected_language as _sel_lang

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        patterns = [("Images", "*.png *.jpg *.jpeg *.webp *.gif"), ("All files", "*.*")]

        if multiple:
            paths = filedialog.askopenfilenames(
                title=_t(_sel_lang, "select_images"),
                filetypes=patterns
            )
            return list(paths) if paths else []
        else:
            path = filedialog.askopenfilename(
                title=_t(_sel_lang, "select_image"),
                filetypes=patterns
            )
            return [path] if path else []
    except Exception:
        return []


def _pick_csv() -> Optional[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
        from utils import selected_language as _sel_lang

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        path = filedialog.askopenfilename(
            title=_t(_sel_lang, "select_pokemon_csv"),
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        return path or None
    except Exception:
        return None


def _downloads_dir() -> str:
    home = os.path.expanduser("~")
    for path in (os.path.join(home, "Downloads"), os.path.join(home, "downloads"), home, os.getcwd()):
        if os.path.isdir(path): return path
    return os.getcwd()

# --- Nova-style UPLOADING popup (unchanged visual)
def _show_uploading_dialog(
    text: str = "Uploading Image…",
    *,
    auto_close_ms: int = 3000,
    use_system_border: bool = False,
    title: str = "Nova — Uploading",
    pulse_speed_ms: int = 20,
    dim_color: str = "#a1a6ff",
    bright_color: str = "#ffffff",
):
    try:
        import tkinter as tk
        import random
        from pathlib import Path
        try:
            from PIL import Image, ImageTk  # type: ignore
            HAS_PIL = True
        except Exception:
            HAS_PIL = False; Image = ImageTk = None  # type: ignore

        parent = getattr(nova_gui, "root", None)
        created_root = False
        if parent is None:
            parent = tk._default_root
            if parent is None:
                parent = tk.Tk(); parent.withdraw(); created_root = True

        popup = tk.Toplevel(parent); popup.withdraw()
        if use_system_border: popup.overrideredirect(False); popup.title(title); popup.resizable(False, False)
        else: popup.overrideredirect(True)
        try: popup.attributes("-topmost", True)
        except Exception: pass

        WIDTH, HEIGHT = 420, 300
        sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
        popup.geometry(f"{WIDTH}x{HEIGHT}+{(sw - WIDTH)//2}+{(sh - HEIGHT)//2}")

        def _hex_to_rgb(h: str): h = h.strip().lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0,2,4))
        def _rgb_to_hex(rgb): r,g,b = [max(0, min(255, int(v))) for v in rgb]; return f"#{r:02x}{g:02x}{b:02x}"
        def _blend(c1: str, c2: str, t: float): r1,g1,b1=_hex_to_rgb(c1); r2,g2,b2=_hex_to_rgb(c2); return _rgb_to_hex((r1+(r2-r1)*t, g1+(g2-g1)*t, b1+(b2-b1)*t))

        canvas = tk.Canvas(popup, width=WIDTH, height=HEIGHT, bg="#1a103d", highlightthickness=0, bd=0); canvas.pack(fill="both", expand=True)

        star_layers = {1: [], 2: [], 3: []}; rng = random.Random(42)
        for layer in star_layers:
            count = 22 if layer == 1 else 14
            for _ in range(count):
                sx=rng.randint(0,WIDTH); sy=rng.randint(0,HEIGHT); size=layer
                star = canvas.create_oval(sx,sy,sx+size,sy+size, fill="#c9cfff", outline="")
                star_layers[layer].append(star)

        closing=[False]; after={"stars":None,"orbit":None,"pulse":None}
        def _safe_after(ms, fn):
            if closing[0] or not popup.winfo_exists(): return None
            return popup.after(ms, fn)

        def animate_stars():
            if closing[0] or not popup.winfo_exists(): return
            for layer, stars in star_layers.items():
                dx = 0.2 * layer
                for s in stars:
                    canvas.move(s, dx, 0)
                    x0,_,x1,_ = canvas.coords(s)
                    if x0 > WIDTH: canvas.move(s, -WIDTH - (x1 - x0), 0)
            after["stars"] = _safe_after(50, animate_stars)
        after["stars"] = _safe_after(50, animate_stars)

        cx, cy = WIDTH//2, 84; radius=10; angle=0; img_tk=None
        if HAS_PIL:
            img_path = resource_path("assets/nova_face_glow.png")
            if not Path(img_path).exists():
                alt = resource_path("nova_face_glow.png")
                if Path(alt).exists(): img_path = alt
            try:
                from PIL import Image, ImageTk  # type: ignore
                img_tk = ImageTk.PhotoImage(Image.open(img_path).resize((80,80)))
            except Exception: img_tk=None

        if img_tk:
            logo_id = canvas.create_image(cx, cy, image=img_tk); popup._logo_ref = img_tk  # noqa: SLF001
            def orbit_img():
                nonlocal angle
                if closing[0] or not popup.winfo_exists(): return
                angle=(angle+2)%360; import math as _m
                rad=_m.radians(angle); canvas.coords(logo_id, cx+radius*_m.cos(rad), cy+radius*_m.sin(rad))
                after["orbit"]=_safe_after(50, orbit_img)
            after["orbit"]=_safe_after(50, orbit_img)
        else:
            glow = canvas.create_oval(cx-42,cy-42,cx+42,cy+42, fill="#6a5acd", outline="")
            canvas.create_oval(cx-48,cy-48,cx+48,cy+48, outline="#9b8fff")
            canvas.create_text(cx, cy, text="N", fill="#e9e7ff", font=("Segoe UI", 28, "bold"))
            def orbit_vec():
                nonlocal angle
                if closing[0] or not popup.winfo_exists(): return
                angle=(angle+2)%360; import math as _m
                rad=_m.radians(angle); ox=cx+radius*_m.cos(rad); oy=cy+radius*_m.sin(rad)
                x0,y0,x1,y1=canvas.coords(glow); canvas.move(glow, ox-(x0+x1)/2, oy-(y0+y1)/2)
                after["orbit"]=_safe_after(50, orbit_vec)
            after["orbit"]=_safe_after(50, orbit_vec)

        title_id = canvas.create_text(WIDTH//2, HEIGHT//2+20, text=text, fill=dim_color, font=("Segoe UI", 12, "bold"))
        phase=[0.0]
        def pulse_text():
            if closing[0] or not popup.winfo_exists(): return
            phase[0]+=0.12; import math as _m
            t=(_m.sin(phase[0])+1.0)/2.0; canvas.itemconfigure(title_id, fill=_blend(dim_color, bright_color, t))
            after["pulse"]=_safe_after(pulse_speed_ms, pulse_text)
        after["pulse"]=_safe_after(pulse_speed_ms, pulse_text)

        popup.deiconify(); popup.lift()
        try: popup.after(200, lambda: popup.attributes("-topmost", False))
        except Exception: pass

        def close():
            closing[0]=True
            try:
                for h in after.values():
                    if h: popup.after_cancel(h)
            except Exception: pass
            try: popup.destroy()
            finally:
                if created_root:
                    try: parent.destroy()
                    except Exception: pass
        popup.bind("<Escape>", lambda e: close())
        if auto_close_ms and auto_close_ms > 0: popup.after(auto_close_ms, close)
        return close
    except Exception:
        return lambda: None

# Precompiled type regex (English names)
_TYPES_RE = r"(electric|water|fire|grass|ice|rock|ground|flying|bug|poison|fighting|psychic|ghost|dark|dragon|steel|fairy|normal)"

# Multilingual "count" intent (how many / count / number / total…)
_COUNT_RE = re.compile(
    r"\b("
    r"how\s+many|count|number|total|"
    r"cu[aá]ntos?|n[uú]mero|total|"
    r"combien|nombre|total|"
    r"wie\s+viele|anzahl|gesamt|"
    r"कितने|कितनी|गिनती|कुल"
    r")\b",
    re.I
)

# ────────────────────────────────────────────────────────────────
# Type resolution (localized + fuzzy typos)
# ────────────────────────────────────────────────────────────────
_CANON_TYPES = [t for t in TYPE_NAMES["en"].keys()]  # English canonical list

def _rev_local_map(lang: str) -> Dict[str, str]:
    table = TYPE_NAMES.get(lang, TYPE_NAMES["en"])
    return {v.lower(): k for k, v in table.items()}

def _resolve_type_token(tok: str, lang: str, cutoff: float = 0.7) -> Optional[str]:
    if not tok: return None
    t = tok.strip().lower()
    if t in [c.lower() for c in _CANON_TYPES]: return t.title()
    rev = _rev_local_map(lang)
    if t in rev: return rev[t].title()
    candidates = list({*rev.keys(), *[c.lower() for c in _CANON_TYPES]})
    best = difflib.get_close_matches(t, candidates, n=1, cutoff=cutoff)
    if best:
        b = best[0]
        return rev[b].title() if b in rev else b.title()
    return None

def _extract_types_and_mode(text: str, lang: str) -> Tuple[List[str], Optional[str]]:
    s = text.strip()
    dual_pairs = re.findall(r"([^\W\d_]+)\s*/\s*([^\W\d_]+)", s, flags=re.UNICODE)
    for a, b in dual_pairs:
        t1 = _resolve_type_token(a, lang); t2 = _resolve_type_token(b, lang)
        if t1 and t2 and t1 != t2: return [t1, t2], "dual"
    tokens = re.findall(r"[^\W\d_]+", s, flags=re.UNICODE)
    seen: List[str] = []
    for tok in tokens:
        t = _resolve_type_token(tok, lang)
        if t and t not in seen: seen.append(t)
    if len(seen) >= 2:
        if re.search(r"\b(both|dual|combo|with\s+both)\b", s, re.I): return seen[:2], "dual"
        return seen, "union"
    elif len(seen) == 1:
        return seen, None
    else:
        return [], None

def _local_type_name(canon: str, lang: str) -> str:
    table = TYPE_NAMES.get(lang, TYPE_NAMES["en"])
    return table.get(canon, canon)

def _join_types_for_header(types: List[str], lang: str, dual: bool) -> str:
    loc = [_local_type_name(t, lang) for t in types]
    if dual and len(loc) >= 2: return f"{loc[0]} / {loc[1]}"
    return _join_names(loc, lang)

def _filter_rows_union(rows: List[Dict], types: List[str]) -> List[Dict]:
    wants = {t.lower() for t in types}
    out=[]
    for r in rows:
        parts = [(r.get("ptype") or "").lower().split("/")]; parts = [p.strip() for p in parts[0] if p.strip()]
        if any(p in wants for p in parts): out.append(r)
    return out

def _filter_rows_dual(rows: List[Dict], t1: str, t2: str) -> List[Dict]:
    a, b = t1.lower(), t2.lower(); out=[]
    for r in rows:
        parts = [(r.get("ptype") or "").lower().split("/")]; parts = {p.strip() for p in parts[0] if p.strip()}
        if a in parts and b in parts: out.append(r)
    return out

# ────────────────────────────────────────────────────────────────
# Bulk helpers (parse lists/ranges of IDs; collect names)
# ────────────────────────────────────────────────────────────────
def _parse_id_list(s: str) -> List[int]:
    s = re.sub(r"\band\b", " ", s, flags=re.I)
    out: List[int] = []
    for chunk in re.findall(r"\d+(?:\s*-\s*\d+)?", s):
        if "-" in chunk:
            a, b = re.split(r"\s*-\s*", chunk)
            try:
                x, y = int(a), int(b); out.extend(range(min(x,y), max(x,y)+1))
            except Exception:
                continue
        else:
            try: out.append(int(chunk))
            except Exception: continue
    seen=set(); uniq=[]
    for v in out:
        if v not in seen: uniq.append(v); seen.add(v)
    return uniq

def _rows_by_id(rows: List[Dict]) -> Dict[int, Dict]:
    out={}
    for r in rows:
        try: out[int(r.get("id"))]=r
        except Exception: continue
    return out

def _find_by_name(rows: List[Dict], name: str) -> Optional[Dict]:
    target = (name or "").strip().lower()
    if not target: return None
    # Prefer exact match, then case-insensitive, then prefix
    for r in rows:
        if (r.get("name") or "").strip().lower() == target:
            return r
    for r in rows:
        n = (r.get("name") or "").strip().lower()
        if n == target or n.replace("-", " ") == target.replace("-", " "):
            return r
    for r in rows:
        n = (r.get("name") or "").strip().lower()
        if n.startswith(target):
            return r
    return None

# ────────────────────────────────────────────────────────────────
# Command routing helpers
# ────────────────────────────────────────────────────────────────
def is_pokemon_command(cmd: str) -> bool:
    c = (cmd or "").lower().strip()
    if any(k in c for k in ("pokemon", "pokémon", "पोकेमोन", "pokedex", "pokédex")):
        return True
    if ("gallery" in c or "images" in c or "image" in c or "download" in c or "csv" in c) and any(
        kw in c for kw in ("pokemon", "pokémon", "पोकेमोन")
    ):
        return True
    groups = (
        "pokemon_list","pokemon_list_type","pokemon_show","pokemon_add","pokemon_update","pokemon_delete",
        "pokemon_help","pokemon_image","pokemon_image_multi","pokemon_gallery_open","pokemon_download",
        "pokemon_import_csv","team_list","team_add","team_remove","team_upgrade","team_average",
        "trainer_me","trainer_update",
    )
    kws = []
    for g in groups: kws.extend(COMMAND_MAP.get(g, []))
    if any(kw in c for kw in kws) or fuzzy_in(c, kws): return True
    if re.search(fr"\b{_TYPES_RE}\b", c, re.I) and re.search(r"\b(pokemon|pokémon|पोकेमोन|type|team|ones?|mine|my|i have)\b", c, re.I):
        return True
    if _COUNT_RE.search(c) and re.search(r"\b(pokemon|pokémon|पोकेमोन)\b", c, re.I):
        return True
    return False


# ────────────────────────────────────────────────────────────────
# Main handler
# ────────────────────────────────────────────────────────────────
def handle_pokemon_command(cmd: str):
    lang = selected_language  # "en" / "hi" / "de" / "fr" / "es"
    text = (cmd or "").strip()
    who = _who()

    # ============================================================
    # Images / Gallery
    # ============================================================

    # open gallery (show a clickable link in chat; no auto-open)
    if re.search(r"\b(open|show)\b.*\b(gallery|image gallery|images)\b", text, re.I) and re.search(r"pok[eé]mon|पोकेमोन", text, re.I):
        url = get_gallery_url()
        speak_then_show(_t(lang, "gallery_open"), _t(lang, "open_gallery_gui", url=url))
        return

    # upload multiple images — secure toggle via keyword
    if re.search(r"\b(upload|add)\b.*\b(images|photos|pictures)\b", text, re.I) and re.search(r"pok[eé]mon|पोकेमोन", text, re.I):
        files = _pick_files(multiple=True)
        if not files:
            msg = _t(lang, "no_images_selected"); speak_then_show(msg, msg); return

        is_secure = bool(re.search(r"\b(secure|signed)\b", text, re.I))
        close_popup = _show_uploading_dialog(
            _t(lang, "uploading_images"),
            use_system_border=True,
            title=_t(lang, "uploading_title_images"),
            auto_close_ms=0
        )
        try:
            upload_images_multi(files, secure=is_secure)
            tts = _t(lang, "images_uploaded_say", n=len(files))
            gui = _t(lang, "images_uploaded_gui", n=len(files), who=who) + f"\n{get_gallery_url()}"
            speak_then_show(tts, gui)
        except Exception as e:
            msg = f"{_t(lang, 'image_upload_failed')} ({e})"; speak_then_show(msg, msg)
        finally:
            close_popup()
        return

    # upload single image — secure toggle
    if re.search(r"\b(upload|add)\b.*\b(image|photo|picture)\b", text, re.I) and re.search(r"pok[eé]mon|पोकेमोन", text, re.I):
        files = _pick_files(multiple=False)
        if not files:
            msg = _t(lang, "no_image_selected"); speak_then_show(msg, msg); return
        path = files[0]

        # Optional rename: “…for Pokémon 7” → pokemon_7_<timestamp>.ext
        m_for = re.search(r"\b(?:for|के\s*लिए)\b.*\b(?:pok[eé]mon|पोकेमोन)\s*(?:id|#)?\s*(?P<pid>\d+)\b", text, re.I)
        override_name = None
        if m_for:
            import time
            _, ext = os.path.splitext(path)
            pid = int(m_for.group("pid")); stamp = int(time.time())
            override_name = f"pokemon_{pid}_{stamp}{ext or '.png'}"

        is_secure = bool(re.search(r"\b(secure|signed)\b", text, re.I))
        close_popup = _show_uploading_dialog(
            _t(lang, "uploading_image"),
            use_system_border=True,
            title=_t(lang, "uploading_title_image"),
            auto_close_ms=0
        )
        try:
            upload_image_single(path, override_filename=override_name, secure=is_secure)
            base = override_name or os.path.basename(path); url = get_gallery_url()
            speak_then_show(_t(lang, "image_uploaded_say"), _t(lang, "image_uploaded_gui", base=base, who=who) + f"\n{url}")
        except Exception as e:
            msg = f"{_t(lang, 'image_upload_failed')} ({e})"; speak_then_show(msg, msg)
        finally:
            close_popup()
        return

    # ============================================================
    # Downloads / Import
    # ============================================================

    # download image <filename> (save bytes to Downloads)
    if re.search(r"\b(download|save)\b.*\b(image|photo|picture)\b", text, re.I):
        mfile = re.search(r"\b([A-Za-z0-9._-]+\.(?:png|jpe?g|webp|gif))\b", text, re.I)
        if not mfile:
            # FOLLOW-UP: ask missing filename
            filename = _await_slot("ask_filename")
            if not filename: return
        else:
            filename = mfile.group(1)

        speak_then_show(_t(lang, "image_download_started"), _t(lang, "image_download_started"))
        dest = _downloads_dir()
        try:
            if download_image is None:
                raise RuntimeError("download helper not available")
            data = None
            try:
                data = download_image(filename)  # new client: returns bytes
            except TypeError:
                saved_path = download_image(filename, dest)  # type: ignore[arg-type]
                ok = _t(lang, "image_download_ok", path=saved_path or os.path.join(dest, filename))
                speak_then_show(ok, ok); return

            path = os.path.join(dest, filename)
            import pathlib
            pathlib.Path(path).write_bytes(data)
            ok = _t(lang, "image_download_ok", path=path); speak_then_show(ok, ok)
        except Exception as e:
            fail = f"{_t(lang, 'image_download_failed')} ({e})"; speak_then_show(fail, fail)
        return

    # download battle log
    if re.search(r"\b(download|save)\b.*\b(battle|combat)\b.*\blog\b", text, re.I):
        dest = _downloads_dir()
        try:
            if download_battle_log is None:
                raise RuntimeError("download helper not available")
            data = download_battle_log()
            path = os.path.join(dest, "battle_log.txt")
            import pathlib
            pathlib.Path(path).write_bytes(data)
            msg = _t(lang, "battle_log_download_ok", path=path); speak_then_show(msg, msg)
        except Exception as e:
            msg = f"{_t(lang, 'battle_log_download_failed')} ({e})"; speak_then_show(msg, msg)
        return

    # download file <filename>  (csv/log/any)
    mf = re.search(r"\bdownload\b.*\b(file|csv|log)\b\s+([A-Za-z0-9._-]+\.\w+)\b", text, re.I)
    if re.search(r"\bdownload\b.*\b(file|csv|log)\b", text, re.I):
        filename = None
        if mf:
            filename = mf.group(2)
        else:
            # FOLLOW-UP: ask missing filename
            filename = _await_slot("ask_filename")
        if not filename:
            return
        dest = _downloads_dir()
        try:
            if download_file is None:
                raise RuntimeError("download helper not available")
            data = download_file(filename)
            path = os.path.join(dest, filename)
            import pathlib
            pathlib.Path(path).write_bytes(data)
            msg = _t(lang, "file_download_ok", path=path); speak_then_show(msg, msg)
        except Exception as e:
            msg = f"{_t(lang, 'file_download_failed')} ({e})"; speak_then_show(msg, msg)
        return

    # import pokemon csv (local file → add_pokemon)
    if re.search(r"\b(import|add)\b.*\bcsv\b", text, re.I) and not re.search(r"\b(server|api|validated)\b", text, re.I):
        csv_path = _pick_csv()
        if not csv_path:
            msg = _t(lang, "csv_pick_none"); speak_then_show(msg, msg); return

        speak_then_show(_t(lang, "csv_import_started"), _t(lang, "csv_import_started"))
        ok = 0; fail = 0

        def _norm(s: str) -> str: return (s or "").strip()

        try:
            with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                fieldnames = [fn.lower().strip() for fn in (reader.fieldnames or [])]
                if fieldnames and any(fn in fieldnames for fn in ("name", "level", "type", "ptype")):
                    for row in reader:
                        try:
                            name = _norm(row.get("name") or row.get("pokemon") or "")
                            lvl_str = _norm(row.get("level") or row.get("lvl") or "0")
                            ptype = _norm(row.get("type") or row.get("ptype") or "Normal")
                            nick = _norm(row.get("nickname") or row.get("nick") or "")
                            if not name: raise ValueError("missing name")
                            lvl = int(lvl_str)
                            add_pokemon(name, lvl, ptype, nick or None); ok += 1
                        except Exception:
                            fail += 1
                else:
                    f.seek(0); reader2 = csv.reader(f)
                    for row in reader2:
                        try:
                            if not row or row[0].strip().lower().startswith("#"): continue
                            name = _norm(row[0]); lvl = int(_norm(row[1])) if len(row) > 1 else 0
                            ptype = _norm(row[2]) if len(row) > 2 else "Normal"
                            nick = _norm(row[3]) if len(row) > 3 else ""
                            if not name: raise ValueError("missing name")
                            add_pokemon(name, lvl, ptype, nick or None); ok += 1
                        except Exception:
                            fail += 1
            summary = _t(lang, "csv_import_ok", ok=ok, fail=fail); speak_then_show(summary, summary)
        except Exception as e:
            fail_msg = f"{_t(lang, 'csv_import_failed')} ({e})"; speak_then_show(fail_msg, fail_msg)
        return

    # optional: upload CSV to server (validated)
    if re.search(r"\b(import|upload)\b.*\bcsv\b.*\b(server|api|validated)\b", text, re.I):
        csv_path = _pick_csv()
        if not csv_path:
            msg = _t(lang, "csv_pick_none"); speak_then_show(msg, msg); return
        try:
            if upload_csv is None:
                raise RuntimeError("csv upload helper not available")
            upload_csv(csv_path, validated=True)
            msg = _t(lang, "csv_upload_ok"); speak_then_show(msg, msg)
        except Exception as e:
            msg = f"{_t(lang, 'csv_upload_failed')} ({e})"; speak_then_show(msg, msg)
        return

    # ============================================================
    # Team (list/add/remove/upgrade/average)
    # ============================================================

    # list team
    if re.search(r"\b(list|show)\b.*\bteam\b", text, re.I):
        try:
            rows = team_list()
            count = len(rows) if isinstance(rows, list) else 0
            msg = _t(lang, "team_count", n=count); speak_then_show(msg, msg)
        except Exception as e:
            msg = f"{_t(lang, 'team_fetch_failed')} ({e})"; speak_then_show(msg, msg)
        return

    # FOLLOW-UP: add to team with missing ID
    if re.search(r"\badd\b.*\bto\b.*\bteam\b", text, re.I) and not re.search(r"(?:pokemon\s+)?\b\d+\b", text, re.I):
        pid = _await_slot("ask_pid", parse_fn=_parse_int)
        if pid is None: return
        text = f"add {pid} to team"

    # add to team
    m = re.search(r"\badd\b.*?(?:pokemon\s+)?(\d+)\b.*\bto\b.*\bteam\b", text, re.I)
    if m:
        pid = int(m.group(1))
        try:
            resp = team_add(pid)
            server = (resp.get("Message") if isinstance(resp, dict) else None) or _t(lang, "team_added_fallback", pid=pid)
            gui = f"{server} — {_t(lang, 'by_word')} {who}."
            speak_then_show(_t(lang, "team_updated"), gui)
        except Exception as e:
            msg = f"{_t(lang, 'team_add_failed')} ({e})"; speak_then_show(msg, msg)
        return

    # FOLLOW-UP: remove from team with missing ID
    if re.search(r"\b(remove|delete)\b.*\bfrom\b.*\bteam\b", text, re.I) and not re.search(r"(?:pokemon\s+)?\b\d+\b", text, re.I):
        pid = _await_slot("ask_pid", parse_fn=_parse_int)
        if pid is None: return
        text = f"remove {pid} from team"

    # remove from team
    m = re.search(r"\b(remove|delete)\b.*?(?:pokemon\s+)?(\d+)\b.*\bfrom\b.*\bteam\b", text, re.I)
    if m:
        pid = int(m.group(2))
        try:
            resp = team_remove(pid)
            server = (resp.get("Message") if isinstance(resp, dict) else None) or _t(lang, "team_removed_fallback", pid=pid)
            gui = f"{server} — {_t(lang, 'by_word')} {who}."
            speak_then_show(_t(lang, "team_updated"), gui)
        except Exception as e:
            msg = f"{_t(lang, 'team_remove_failed')} ({e})"; speak_then_show(msg, msg)
        return


    # FOLLOW-UP: normalize “upgrade team …” when ID/level missing
    if re.search(r"\b(upgrade|set)\b.*\bteam\b", text, re.I) and not re.search(r"\b(?:pokemon\s*)?\d+.*\blevel\s*\d+\b", text, re.I):
        pid = _parse_int(text) or _await_slot("ask_pid", parse_fn=_parse_int)
        if pid is None: return
        lvl = None
        m_l = re.search(r"\blevel\s*(\d+)\b", text, re.I)
        if m_l: lvl = int(m_l.group(1))
        if lvl is None:
            lvl = _await_slot("ask_level", parse_fn=_parse_int)
            if lvl is None: return
        text = f"upgrade team {pid} to level {lvl}"

    # upgrade team member level
    m = re.search(r"\b(upgrade|set)\b.*\bteam\b.*?(?:pokemon\s+)?(\d+).*\blevel\s+(\d+)\b", text, re.I)
    if m:
        pid, lvl = int(m.group(2)), int(m.group(3))
        try:
            team_upgrade(pid, level=lvl)
            speak_then_show(_t(lang, "team_member_set_level_say", pid=pid, lvl=lvl),
                            _t(lang, "team_member_set_level_gui", pid=pid, lvl=lvl, who=who))
        except Exception as e:
            msg = f"{_t(lang, 'team_upgrade_failed')} ({e})"; speak_then_show(msg, msg)
        return

    # team average level
    if re.search(r"\b(team\s+average(?:\s+level)?|average\s+team)\b", text, re.I):
        try:
            avg = team_average_level()
            speak_then_show(_t(lang, "team_avg_shown"),
                            _t(lang, "team_avg_gui", avg=avg if avg is not None else "—"))
        except Exception as e:
            msg = f"{_t(lang, 'team_avg_failed')} ({e})"; speak_then_show(msg, msg)
        return

    # ============================================================
    # Pokémon list / count / filter by type (with “Did you mean?”)
    # ============================================================

    # quick "how many/total/count" intent
    if _COUNT_RE.search(text) and not re.search(r"\b(show|display)\b", text, re.I):
        try:
            rows = list_pokemon()
            n = len(rows) if isinstance(rows, list) else 0
            speak_then_show(_t(lang, "you_have_n", n=n), _t(lang, "you_have_n", n=n))
        except Exception as e:
            msg = _t(lang, "error_generic", err=str(e))
            speak_then_show(msg, msg)
        return

    # FOLLOW-UP: “list type …” when type token missing → ask + Did you mean?
    if re.search(r"\b(list|show)\b.*\b(type|types)\b", text, re.I) and not re.search(fr"\b{_TYPES_RE}\b", text, re.I):
        ans = _await_slot("ask_type")
        if ans is None: return
        typ = _resolve_type_token(ans, lang)

        if not typ:
            # candidates: canonical + localized
            canon = [t.title() for t in _CANON_TYPES]
            local_rev = _rev_local_map(lang)
            local_names = [k.title() for k in local_rev.keys()]

            best, score = _best_match(ans, list({*canon, *local_names}))
            if best and score >= 0.80:
                typ = _resolve_type_token(best, lang)
            elif best and 0.60 <= score < 0.80:
                ok = confirm_did_you_mean(best)
                if ok is True:
                    typ = _resolve_type_token(best, lang)
                else:
                    ans2 = _await_slot("ask_type")
                    if not ans2: return
                    typ = _resolve_type_token(ans2, lang)
            else:
                ans2 = _await_slot("ask_type")
                if not ans2: return
                typ = _resolve_type_token(ans2, lang)

        if not typ:
            msg = _t(lang, "type_unknown")
            speak_then_show(msg, msg)
            return

        text = f"list {typ} type"  # normalized; falls through

    # list by one/dual/union types (supports “electric”, “electric/water”, “electric and water”)
    if re.search(r"\b(list|show)\b.*\b(type|types)\b", text, re.I) or re.search(fr"\b{_TYPES_RE}\b", text, re.I):
        try:
            rows = list_pokemon()
            # extract requested types from free text
            types, mode = _extract_types_and_mode(text, lang)
            if not types:
                # nothing to filter → plain list
                n = len(rows) if isinstance(rows, list) else 0
                tts = tts_list(rows=rows, lang=lang)
                speak_then_show(tts, tts if n <= 30 else _t(lang, "you_have_n", n=n))
                return

            if mode == "dual" and len(types) >= 2:
                filt = _filter_rows_dual(rows, types[0], types[1])
                header = _join_types_for_header(types[:2], lang, dual=True)
            else:
                filt = _filter_rows_union(rows, types)
                header = _join_types_for_header(types, lang, dual=False)

            tts = tts_list(rows=filt, lang=lang, header=header)
            speak_then_show(tts, tts)
        except Exception as e:
            msg = _t(lang, "error_generic", err=str(e)); speak_then_show(msg, msg)
        return

    # plain “list/show pokemon”
    if re.search(r"\b(list|show)\b.*\b(pokemon|pokémon)\b", text, re.I) and not re.search(r"\b(pokemon|pokémon)\s+\d+\b", text, re.I):
        try:
            rows = list_pokemon()
            tts = tts_list(rows=rows, lang=lang)
            speak_then_show(tts, tts)
        except Exception as e:
            msg = _t(lang, "error_generic", err=str(e)); speak_then_show(msg, msg)
        return

    # ============================================================
    # Show one (ID or name) — “Did you mean…?” wired in both paths
    # ============================================================

    # FOLLOW-UP: “show pokemon …” when ID missing (or support show by name)
    if re.search(r"\bshow\b.*\b(pokemon|pokémon)\b", text, re.I) and not re.search(r"\b(pokemon|pokémon)\s+\d+\b", text, re.I):
        rows = list_pokemon()
        mname = re.search(r"\bshow\b.*?\b(pokemon|pokémon)\b\s+([A-Za-z][A-Za-z0-9._ -]{1,})$", text, re.I)
        if mname:
            candidate = mname.group(2).strip()
            byname = _find_by_name(rows, candidate)
            if byname:
                pid = int(byname.get("id"))
                tts = tts_show(pid=pid, lvl=byname.get("level"), ptype=byname.get("ptype", ""), lang=lang, name=byname.get("name"), use_flair=True)
                speak_then_show(tts, tts); return
            else:
                # Try “Did you mean …?”
                all_names = [(r.get("name") or "").strip() for r in rows if (r.get("name") or "").strip()]
                best, score = _best_match(candidate, all_names)
                if best and score >= 0.80:
                    chosen = next((r for r in rows if (r.get("name") or "") == best), None)
                    if chosen:
                        pid = int(chosen.get("id"))
                        tts = tts_show(pid=pid, lvl=chosen.get("level"), ptype=chosen.get("ptype", ""), lang=lang, name=chosen.get("name"), use_flair=True)
                        speak_then_show(tts, tts); return
                elif best and 0.60 <= score < 0.80:
                    ok = confirm_did_you_mean(best)
                    if ok is True:
                        chosen = next((r for r in rows if (r.get("name") or "") == best), None)
                        if chosen:
                            pid = int(chosen.get("id"))
                            tts = tts_show(pid=pid, lvl=chosen.get("level"), ptype=chosen.get("ptype", ""), lang=lang, name=chosen.get("name"), use_flair=True)
                            speak_then_show(tts, tts); return
        # Ask ID interactively as a fallback
        pid = _await_slot("ask_pid", parse_fn=_parse_int)
        if pid is None: return
        text = f"show pokemon {pid}"  # normalized; falls through

    # 4) show one by id (also supports plain "show pikachu" without the word 'pokemon')
    m = re.search(r"\bshow\b.*\b(pokemon|pokémon)\s+(\d+)\b", text, re.I)
    if not m:
        # fallback: try "show <name>"
        if re.search(r"\bshow\s+[A-Za-z][A-Za-z0-9._ -]{1,}\b", text, re.I) and "team" not in text.lower() and "gallery" not in text.lower():
            rows = list_pokemon()
            nm = re.search(r"\bshow\s+([A-Za-z][A-Za-z0-9._ -]{1,})\b", text, re.I)
            if nm:
                candidate = nm.group(1).strip()
                byname = _find_by_name(rows, candidate)
                if byname:
                    pid = int(byname.get("id"))
                    tts = tts_show(pid=pid, lvl=byname.get("level"), ptype=byname.get("ptype", ""), lang=lang, name=byname.get("name"), use_flair=True)
                    speak_then_show(tts, tts); return
                else:
                    all_names = [(r.get("name") or "").strip() for r in rows if (r.get("name") or "").strip()]
                    best, score = _best_match(candidate, all_names)
                    if best and score >= 0.80:
                        chosen = next((r for r in rows if (r.get("name") or "") == best), None)
                        if chosen:
                            pid = int(chosen.get("id"))
                            tts = tts_show(pid=pid, lvl=chosen.get("level"), ptype=chosen.get("ptype", ""), lang=lang, name=chosen.get("name"), use_flair=True)
                            speak_then_show(tts, tts); return
                    elif best and 0.60 <= score < 0.80:
                        ok = confirm_did_you_mean(best)
                        if ok is True:
                            chosen = next((r for r in rows if (r.get("name") or "") == best), None)
                            if chosen:
                                pid = int(chosen.get("id"))
                                tts = tts_show(pid=pid, lvl=chosen.get("level"), ptype=chosen.get("ptype", ""), lang=lang, name=chosen.get("name"), use_flair=True)
                                speak_then_show(tts, tts); return
        # if still not resolved, continue to ID branch

    m = re.search(r"\bshow\b.*\b(pokemon|pokémon)\s+(\d+)\b", text, re.I)
    if m:
        pid = int(m.group(2))
        try:
            rows = list_pokemon()
            byid = next((r for r in rows if int(r.get("id")) == pid), None)
            if not byid:
                speak_then_show(_t(lang, "pokemon_not_found", pid=pid), _t(lang, "pokemon_not_found", pid=pid))
                return
            tts = tts_show(pid=pid, lvl=byid.get("level"), ptype=byid.get("ptype", ""), lang=lang, name=byid.get("name"), use_flair=True)
            speak_then_show(tts, tts)
        except Exception as e:
            msg = _t(lang, "error_generic", err=str(e)); speak_then_show(msg, msg)
        return

    # ============================================================
    # Add / Update / Delete
    # ============================================================

    # FOLLOW-UP: add pokemon with missing slots (name/level/type/nickname)
    if re.search(r"\b(add|create)\b.*\b(pokemon|pokémon)\b", text, re.I) and not re.search(r"\b(level|type|nickname|nick|name)\b", text, re.I):
        # Ask name then level then type and optional nickname
        name = _await_slot("ask_name")
        if not name: return
        lvl = _await_slot("ask_level", parse_fn=_parse_int)
        if lvl is None: return
        # type with Did you mean?
        ans = _await_slot("ask_type")
        if not ans: return
        ptype = _resolve_type_token(ans, lang)
        if not ptype:
            canon = [t.title() for t in _CANON_TYPES]
            local_rev = _rev_local_map(lang)
            local_names = [k.title() for k in local_rev.keys()]
            best, score = _best_match(ans, list({*canon, *local_names}))
            if best and score >= 0.80:
                ptype = _resolve_type_token(best, lang)
            elif best and 0.60 <= score < 0.80:
                ok = confirm_did_you_mean(best)
                if ok is True:
                    ptype = _resolve_type_token(best, lang)
                else:
                    ans2 = _await_slot("ask_type")
                    if not ans2: return
                    ptype = _resolve_type_token(ans2, lang) or "Normal"
            else:
                ans2 = _await_slot("ask_type")
                if not ans2: return
                ptype = _resolve_type_token(ans2, lang) or "Normal"
        if not ptype:
            ptype = "Normal"
        nick = _await_slot("ask_nick")
        nick = None if (nick or "").strip().lower() == "skip" else (nick or "").strip() or None
        try:
            add_pokemon(name.strip(), int(lvl), ptype, nick)
            tts = tts_add(name=name.strip(), lvl=int(lvl), ptype=ptype, nick=nick, lang=lang, use_flair=True)
            speak_then_show(tts, _t(lang, "added_by", name=name.strip(), who=who))
        except Exception as e:
            msg = _t(lang, "error_generic", err=str(e)); speak_then_show(msg, msg)
        return

    # direct “add <name> level <n> type <t> nickname <x>”
    m_add = re.search(r"\badd\b\s+([A-Za-z][A-Za-z0-9._ -]{1,})\s+(?:level\s+(\d+))?(?:.*?\btype\s+([^\s]+))?(?:.*?\b(?:nickname|nick)\s+([A-Za-z0-9._ -]+))?", text, re.I)
    if m_add:
        name = m_add.group(1).strip()
        lvl = int(m_add.group(2)) if m_add.group(2) else (_await_slot("ask_level", parse_fn=_parse_int) or 0)
        ptype_raw = m_add.group(3)
        nick = m_add.group(4).strip() if m_add.group(4) else None
        ptype = _resolve_type_token(ptype_raw, lang) if ptype_raw else None

        if not ptype:
            ans = _await_slot("ask_type")
            if not ans: return
            ptype = _resolve_type_token(ans, lang)
            if not ptype:
                canon = [t.title() for t in _CANON_TYPES]
                local_rev = _rev_local_map(lang)
                local_names = [k.title() for k in local_rev.keys()]
                best, score = _best_match(ans, list({*canon, *local_names}))
                if best and score >= 0.80:
                    ptype = _resolve_type_token(best, lang)
                elif best and 0.60 <= score < 0.80:
                    ok = confirm_did_you_mean(best)
                    if ok is True:
                        ptype = _resolve_type_token(best, lang)
                    else:
                        ans2 = _await_slot("ask_type")
                        if not ans2: return
                        ptype = _resolve_type_token(ans2, lang) or "Normal"
                else:
                    ans2 = _await_slot("ask_type")
                    if not ans2: return
                    ptype = _resolve_type_token(ans2, lang) or "Normal"
        if not ptype:
            ptype = "Normal"

        try:
            add_pokemon(name, int(lvl), ptype, nick)
            tts = tts_add(name=name, lvl=int(lvl), ptype=ptype, nick=nick, lang=lang, use_flair=True)
            speak_then_show(tts, _t(lang, "added_by", name=name, who=who))
        except Exception as e:
            msg = _t(lang, "error_generic", err=str(e)); speak_then_show(msg, msg)
        return

    # update (fields: level/type/nickname) — supports multiple fields
    m_up = re.search(r"\bupdate\b.*\b(pokemon|pokémon)\s+(\d+)\b(.*)$", text, re.I)
    if m_up:
        pid = int(m_up.group(2))
        tail = m_up.group(3) or ""
        fields = _parse_update_fields(tail)
        if not fields:
            # ask what to update
            picked = _await_slot("ask_update_fields", parse_fn=_parse_update_fields)
            if not picked: return
            fields = picked

        changes_gui = []
        level_only = False 
        try:
            if "level" in fields:
                lvl = _await_slot("ask_level", parse_fn=_parse_int) if not re.search(r"\blevel\s+\d+\b", tail, re.I) else int(re.search(r"\blevel\s+(\d+)\b", tail, re.I).group(1))
                update_pokemon(pid, level=lvl)
                lvl_label = LABELS.get(lang, LABELS["en"]).get("level", "level")
                changes_gui.append(f"{lvl_label} → {lvl}")
                level_only = True

            if "type" in fields:
                # ask for type
                ans = None
                mty = re.search(r"\btype\s+([^\s]+)\b", tail, re.I)
                if mty: ans = mty.group(1)
                if not ans:
                    ans = _await_slot("ask_type")
                    if not ans: return
                ptype = _resolve_type_token(ans, lang)
                if not ptype:
                    canon = [t.title() for t in _CANON_TYPES]
                    local_rev = _rev_local_map(lang)
                    local_names = [k.title() for k in local_rev.keys()]
                    best, score = _best_match(ans, list({*canon, *local_names}))
                    if best and score >= 0.80:
                        ptype = _resolve_type_token(best, lang)
                    elif best and 0.60 <= score < 0.80:
                        ok = confirm_did_you_mean(best)
                        if ok is True:
                            ptype = _resolve_type_token(best, lang)
                        else:
                            ans2 = _await_slot("ask_type")
                            if not ans2: return
                            ptype = _resolve_type_token(ans2, lang)
                    else:
                        ans2 = _await_slot("ask_type")
                        if not ans2: return
                        ptype = _resolve_type_token(ans2, lang)
                if not ptype:
                    msg = _t(lang, "type_unknown"); speak_then_show(msg, msg); return
                update_pokemon(pid, ptype=ptype)
                lab = LABELS.get(lang, LABELS["en"])
                changes_gui.append(f"{lab['type']} → {ptype}")
                level_only = False


            if "nickname" in fields:
                nick = None
                mn = re.search(r"\b(?:nickname|nick)\s+([A-Za-z0-9._ -]+)\b", tail, re.I)
                if mn:
                    nick = mn.group(1).strip()
                else:
                    nick = _await_slot("ask_nick")
                    if nick is None: return
                    if nick.strip().lower() == "skip": nick = ""
                update_pokemon(pid, nickname=(nick or "").strip() or None)
                lab = LABELS.get(lang, LABELS["en"])
                changes_gui.append(f"{lab['nickname']} → {(nick or '').strip() or '—'}")
                level_only = False


            if level_only and len(changes_gui) == 1:
                # pull the numeric level back out for the localized “level updated” line
                lvl_match = re.search(r"\d+", changes_gui[0])
                lvl_val = int(lvl_match.group(0)) if lvl_match else None
                if lvl_val is not None:
                    speak_then_show(
                        _t(lang, "updated_level_gui", pid=pid, lvl=lvl_val, who=who),
                        _t(lang, "updated_level_gui", pid=pid, lvl=lvl_val, who=who),
                    )
                else:
                    # fallback to generic if parsing failed
                    changes_text = ", ".join(changes_gui)
                    gui = _t(lang, "updated_fields_gui", pid=pid, changes=changes_text, who=who)
                    speak_then_show(_t(lang, "team_updated"), gui)
            else:
                changes_text = ", ".join(changes_gui)
                gui = _t(lang, "updated_fields_gui", pid=pid, changes=changes_text, who=who)
                speak_then_show(_t(lang, "team_updated"), gui)

        except Exception as e:
            msg = _t(lang, "error_generic", err=str(e)); speak_then_show(msg, msg)
        return

    # delete
    m_del = re.search(r"\b(delete|remove)\b.*\b(pokemon|pokémon)\s+(\d+)\b", text, re.I)
    if m_del:
        pid = int(m_del.group(3))
        try:
            delete_pokemon(pid)
            speak_then_show(_t(lang, "deleted_gui", pid=pid, who=who),
                            _t(lang, "deleted_gui", pid=pid, who=who))
        except Exception as e:
            msg = _t(lang, "error_generic", err=str(e)); speak_then_show(msg, msg)
        return

    # ============================================================
    # Trainer profile / updates
    # ============================================================
    if re.search(r"\b(my\s+trainer\s+profile|trainer\s+profile|trainer\s+me)\b", text, re.I):
        try:
            prof = trainer_me()
            if not isinstance(prof, dict):
                raise RuntimeError("invalid trainer profile response")

            # build a tiny summary line
            nick = prof.get("nickname") or "—"
            loc  = prof.get("location") or "—"
            pr   = prof.get("pronouns") or "—"

            header = _t(lang, "trainer_profile_show")
            labels = PROFILE_LABELS.get(lang, PROFILE_LABELS["en"])
            gui = (
                f"{header}\n"
                f"• {labels['nickname']}: {nick}\n"
                f"• {labels['location']}: {loc}\n"
                f"• {labels['pronouns']}: {pr}"
            )
            speak_then_show(header, gui)
        except Exception as e:
            msg = f"{_t(lang, 'trainer_profile_failed')} ({e})"
            speak_then_show(msg, msg)
        return

    # trainer nickname/location/pronouns updates
    m_tr_nick = re.search(r"\btrainer\s+(?:nickname|nick)\s+(?:is|=)\s+([A-Za-z0-9._ -]+)\b", text, re.I)
    if m_tr_nick:
        nick = m_tr_nick.group(1).strip()
        try:
            trainer_update(nickname=nick)
            speak_then_show(_t(lang, "trainer_nick_updated_say"),
                            _t(lang, "trainer_nick_updated_gui", nick=nick, who=who))
        except Exception as e:
            msg = f"{_t(lang, 'trainer_nick_failed')} ({e})"; speak_then_show(msg, msg)
        return

    m_tr_loc = re.search(r"\b(?:location|loc)\s+(?:is|=)\s+([A-Za-z0-9._ -]+)\b", text, re.I)
    if m_tr_loc:
        loc = m_tr_loc.group(1).strip()
        try:
            trainer_update(location=loc)
            speak_then_show(_t(lang, "trainer_loc_updated_say"),
                            _t(lang, "trainer_loc_updated_gui", loc=loc, who=who))
        except Exception as e:
            msg = f"{_t(lang, 'trainer_loc_failed')} ({e})"; speak_then_show(msg, msg)
        return

    m_tr_pr = re.search(r"\b(?:pronouns?)\s+(?:are|=)\s+([A-Za-z/ -]{2,20})\b", text, re.I)
    if m_tr_pr:
        pr = m_tr_pr.group(1).strip()
        try:
            trainer_update(pronouns=pr)
            speak_then_show(_t(lang, "trainer_pron_updated_say"),
                            _t(lang, "trainer_pron_updated_gui", pr=pr, who=who))
        except Exception as e:
            msg = f"{_t(lang, 'trainer_pron_failed')} ({e})"; speak_then_show(msg, msg)
        return

    # ============================================================
    # Help
    # ============================================================
    if re.search(r"\b(help|commands?)\b", text, re.I):
        speak_then_show(SPEAK_HELP.get(lang, SPEAK_HELP["en"]),
                        HELP_TEXT.get(lang, HELP_TEXT["en"]))
        return
    

    # ============================================================
    # Catch-all for unclear Pokémon intent → short clarifier
    # ============================================================
    try:
        if is_pokemon_command(text):
            hint = {
                "en": "I can list, show, add, update, or delete Pokémon. What would you like me to do?",
                "hi": "मैं पोकेमोन की सूची दिखा सकती हूँ, किसी एक पोकेमोन को दिखा सकती हूँ, जोड़ सकती हूँ, अपडेट कर सकती हूँ या हटा सकती हूँ। आप क्या करना चाहेंगे?",
                "fr": "Je peux lister, afficher, ajouter, mettre à jour ou supprimer des Pokémon. Que souhaitez-vous faire ?",
                "es": "Puedo listar, mostrar, agregar, actualizar o borrar Pokémon. ¿Qué quieres que haga?",
                "de": "Ich kann Pokémon auflisten, anzeigen, hinzufügen, aktualisieren oder löschen. Was möchtest du tun?"
            }
            msg = hint.get(selected_language, hint["en"])
            speak_then_show(msg, msg)
            return
    except Exception:
        pass

    # Fallback: treat as non-pokemon command
    return
