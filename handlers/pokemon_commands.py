# handlers/pokemon_commands.py
from __future__ import annotations

import os
import re
import csv
import webbrowser
import difflib
from typing import List, Dict, Optional, Tuple

# GUI + TTS
from gui_interface import nova_gui
from utils import speak, selected_language, load_settings, resource_path  # load_settings/resource_path used
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
    tts_add, tts_update, tts_delete, tts_list, tts_show, TYPE_NAMES
)

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
    "en": {"type": "type", "nickname": "nickname"},
    "hi": {"type": "टाइप", "nickname": "निकनेम"},
    "fr": {"type": "type", "nickname": "surnom"},
    "es": {"type": "tipo", "nickname": "apodo"},
    "de": {"type": "typ", "nickname": "spitzname"},
}

# ────────────────────────────────────────────────────────────────
# Generic multilingual messages (added missing + new ones)
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
}

# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────
def _who():
    n = (load_from_memory("name") or "").strip()
    return n if n else "You"


def _open_in_browser(url: str) -> None:
    try:
        webbrowser.open(url, new=2)
    except Exception:
        pass  # silent fail; we still print URL in GUI


def speak_then_show(tts_text: str, gui_text: str, title: str = "Nova") -> None:
    """Speak first (keeps Nova mouth anim), then show the bubble."""
    speak(tts_text)
    nova_gui.show_message(title, gui_text)


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
        root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
        patterns = [("Images", "*.png *.jpg *.jpeg *.webp *.gif"), ("All files", "*.*")]
        if multiple:
            paths = filedialog.askopenfilenames(title="Select Images", filetypes=patterns)
            return list(paths) if paths else []
        else:
            path = filedialog.askopenfilename(title="Select Image", filetypes=patterns)
            return [path] if path else []
    except Exception:
        return []

def _pick_csv() -> Optional[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
        path = filedialog.askopenfilename(title="Select Pokémon CSV",
                                          filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        return path or None
    except Exception:
        return None

def _should_open_after_upload() -> bool:
    """
    Auto-open-after-upload is *disabled* by design.
    We keep this function for backward compatibility with older configs.
    """
    return False  # always disabled — we show a clickable link in the GUI bubble instead

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
        import math, random
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
    if _COUNT_RE.search(c): return True
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
        # no _open_in_browser(url) — user clicks or copies the link in the chat
        return

    # upload multiple images — secure toggle via keyword
    if re.search(r"\b(upload|add)\b.*\b(images|photos|pictures)\b", text, re.I) and re.search(r"pok[eé]mon|पोकेमोन", text, re.I):
        files = _pick_files(multiple=True)
        if not files:
            msg = _t(lang, "no_images_selected"); speak_then_show(msg, msg); return

        is_secure = bool(re.search(r"\b(secure|signed)\b", text, re.I))
        close_popup = _show_uploading_dialog("Uploading Images…", use_system_border=True, title="Nova — Uploading Images", auto_close_ms=0)
        try:
            upload_images_multi(files, secure=is_secure)
            tts = _t(lang, "images_uploaded_say", n=len(files))
            gui = _t(lang, "images_uploaded_gui", n=len(files), who=who) + f"\n{get_gallery_url()}"
            speak_then_show(tts, gui)  # no auto-open; URL shown for user to click/copy
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
        close_popup = _show_uploading_dialog("Uploading Image…", use_system_border=True, title="Nova — Uploading Image", auto_close_ms=0)
        try:
            upload_image_single(path, override_filename=override_name, secure=is_secure)
            base = override_name or os.path.basename(path); url = get_gallery_url()
            speak_then_show(_t(lang, "image_uploaded_say"), _t(lang, "image_uploaded_gui", base=base, who=who) + f"\n{url}")
            # no auto-open; URL shown for user to click/copy
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
            msg = _t(lang, "image_download_need_name"); speak_then_show(msg, msg); return
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
                # backward compatibility (older client that saves to disk)
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
    m = re.search(r"\bdownload\b.*\b(file|csv|log)\b\s+([A-Za-z0-9._-]+\.\w+)\b", text, re.I)
    if m:
        filename = m.group(2); dest = _downloads_dir()
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

    # add to team
    m = re.search(r"\badd\b.*?(?:pokemon\s+)?(\d+)\b.*\bto\b.*\bteam\b", text, re.I)
    if m:
        pid = int(m.group(1))
        try:
            resp = team_add(pid)
            server = (resp.get("Message") if isinstance(resp, dict) else None) or f"Added Pokémon {pid} to team."
            gui = f"{server} — {_t(lang, 'by_word')} {who}."
            speak_then_show(_t(lang, "team_updated"), gui)
        except Exception as e:
            msg = f"{_t(lang, 'team_add_failed')} ({e})"; speak_then_show(msg, msg)
        return

    # remove from team
    m = re.search(r"\b(remove|delete)\b.*?(?:pokemon\s+)?(\d+)\b.*\bfrom\b.*\bteam\b", text, re.I)
    if m:
        pid = int(m.group(2))
        try:
            resp = team_remove(pid)
            server = (resp.get("Message") if isinstance(resp, dict) else None) or f"Removed Pokémon {pid} from team."
            gui = f"{server} — {_t(lang, 'by_word')} {who}."
            speak_then_show(_t(lang, "team_updated"), gui)
        except Exception as e:
            msg = f"{_t(lang, 'team_remove_failed')} ({e})"; speak_then_show(msg, msg)
        return

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
    if re.search(r"\bteam\b.*\b(average|avg)\b.*\b(level|lvl)\b", text, re.I):
        try:
            resp = team_average_level()
            data = resp.get("Data") if isinstance(resp, dict) else resp
            avg = None
            if isinstance(data, dict): avg = data.get("average") or data.get("avg") or data.get("average_level")
            if avg is None and isinstance(resp, dict): avg = resp.get("average") or resp.get("avg") or resp.get("average_level")
            if avg is None:
                msg = f"{_t(lang, 'team_avg_shown')}\n{resp}"; speak_then_show(msg, msg)
            else:
                speak_then_show(_t(lang, "team_avg_is", avg=avg), _t(lang, "team_avg_gui", avg=avg))
        except Exception as e:
            msg = f"{_t(lang, 'team_avg_failed')} ({e})"; speak_then_show(msg, msg)
        return

    # ============================================================
    # Trainer (profile get/update)
    # ============================================================

    # show trainer profile
    if re.search(r"\b(trainer|profile)\b.*\b(show|who am i|me)\b", text, re.I) or re.search(r"\bmy trainer profile\b", text, re.I):
        try:
            prof = trainer_me()
            gui = f"{_t(lang, 'trainer_profile_show')}\n{prof}"
            speak_then_show(_t(lang, 'trainer_profile_show'), gui)
        except Exception as e:
            msg = f"{_t(lang, 'trainer_profile_failed')} ({e})"; speak_then_show(msg, msg)
        return

    # set/update trainer nickname
    m = re.search(r"\b(trainer )?(nickname|name)\b.*\b(is|=)\b\s*([A-Za-z0-9 _-]{2,32})", text, re.I)
    if m:
        nick = m.group(4).strip()
        try:
            trainer_update(nickname=nick)
            speak_then_show(_t(lang, "trainer_nick_updated_say"),
                            _t(lang, "trainer_nick_updated_gui", nick=nick, who=who))
        except Exception as e:
            msg = f"{_t(lang, 'trainer_nick_failed')} ({e})"; speak_then_show(msg, msg)
        return

    # set/update trainer location
    m = re.search(r"\b(location|city|place)\b.*\b(is|=)\b\s*([A-Za-z0-9 ,._-]{2,48})", text, re.I)
    if m:
        loc = m.group(3).strip()
        try:
            trainer_update(location=loc)
            speak_then_show(_t(lang, "trainer_loc_updated_say"),
                            _t(lang, "trainer_loc_updated_gui", loc=loc, who=who))
        except Exception as e:
            msg = f"{_t(lang, 'trainer_loc_failed')} ({e})"; speak_then_show(msg, msg)
        return

    # set/update trainer pronouns
    m = re.search(r"\b(pronoun|pronouns)\b.*\b(is|are|=)\b\s*([A-Za-z /-]{2,24})", text, re.I)
    if m:
        pr = m.group(3).strip()
        try:
            trainer_update(pronouns=pr)
            speak_then_show(_t(lang, "trainer_pron_updated_say"),
                            _t(lang, "trainer_pron_updated_gui", pr=pr, who=who))
        except Exception as e:
            msg = f"{_t(lang, 'trainer_pron_failed')} ({e})"; speak_then_show(msg, msg)
        return

    # ============================================================
    # Core Pokémon CRUD + LIST/COUNT INTENTS
    # ============================================================

    # 0) “Count / How many … ?” (multilingual) → same output style as list
    if _COUNT_RE.search(text):
        types, mode = _extract_types_and_mode(text, lang)
        rows = list_pokemon()

        if not types:
            header = tts_list(n=len(rows), lang=lang)
            final = header + (_names_suffix(rows, lang, limit=15) if len(rows) else "")
            speak_then_show(final, final); return

        if mode == "dual" and len(types) >= 2:
            filtered = _filter_rows_dual(rows, types[0], types[1])
            combo = _join_types_for_header(types[:2], lang, dual=True)
            header = f"You have {len(filtered)} {combo} Pokémon."
            final = header + (_names_suffix(filtered, lang, limit=15) if len(filtered) else "")
            speak_then_show(final, final); return

        if len(types) == 1:
            filtered = _filter_rows_union(rows, types)
            header = tts_list(n=len(filtered), lang=lang, ptype=types[0])
            final = header + (_names_suffix(filtered, lang, limit=15) if len(filtered) else "")
            speak_then_show(final, final); return

        filtered = _filter_rows_union(rows, types)
        combo = _join_types_for_header(types, lang, dual=False)
        header = f"You have {len(filtered)} {combo} Pokémon."
        final = header + (_names_suffix(filtered, lang, limit=15) if len(filtered) else "")
        speak_then_show(final, final); return

    # 1) list by type (strict "list/show <type>")
    m = re.search(fr"\b(list|show)\s+{_TYPES_RE}\b", text, re.I)
    if m:
        ptype = m.group(2).title()
        rows = list_pokemon()
        filtered = _filter_rows_union(rows, [ptype])
        header = tts_list(n=len(filtered), lang=lang, ptype=ptype)
        final = header + (_names_suffix(filtered, lang, limit=15) if len(filtered) else "")
        speak_then_show(final, final); return

    # 2) list by type (loose follow-up)
    if re.search(fr"\b{_TYPES_RE}\b", text, re.I) and re.search(r"\b(pokemon|pokémon|पोकेमोन|type|team|ones?|mine|my|i have)\b", text, re.I):
        typ = re.search(fr"\b{_TYPES_RE}\b", text, re.I).group(1).title()
        rows = list_pokemon()
        filtered = _filter_rows_union(rows, [typ])
        header = tts_list(n=len(filtered), lang=lang, ptype=typ)
        final = header + (_names_suffix(filtered, lang, limit=15) if len(filtered) else "")
        speak_then_show(final, final); return

    # 3) list all
    if re.search(r"\b(list|show)\b.*\b(pokemon|pokémon|pokedex)\b", text, re.I) or text.lower().strip() in {"list pokemon", "show pokemon", "show pokémon"}:
        rows = list_pokemon()
        header = tts_list(n=len(rows), lang=lang)
        final = header + (_names_suffix(rows, lang, limit=15) if len(rows) else "")
        speak_then_show(final, final); return

    # 4) show one by id
    m = re.search(r"\bshow\b.*\b(pokemon|pokémon)\s+(\d+)\b", text, re.I)
    if m:
        pid = int(m.group(2))
        rows = list_pokemon()
        row = next((r for r in rows if int(r.get("id")) == pid), None)
        if not row:
            msg = _t(lang, "pokemon_not_found", pid=pid); speak_then_show(msg, msg); return
        tts = tts_show(pid=pid, lvl=row.get("level"), ptype=row.get("ptype", ""), lang=lang, name=row.get("name"), use_flair=True)
        speak_then_show(tts, tts); return

    # 5) add (single OR repeated 'add …' blocks)
    adds = list(re.finditer(r"\badd\b\s+([a-zA-Z]+)\s+level\s+(\d+)\s+([a-zA-Z/]+)(?:\s+nickname\s+([a-zA-Z0-9_-]+))?", text, re.I))
    if adds:
        added_rows: List[Dict] = []
        for m in adds:
            name, lvl, ptype, nick = m.group(1).title(), int(m.group(2)), m.group(3).title(), (m.group(4) or None)
            try: add_pokemon(name, lvl, ptype, nick); added_rows.append({"name": name})
            except Exception: continue
        if len(added_rows) == 1:
            single = adds[0]
            tts = tts_add(name=single.group(1).title(), ptype=single.group(3).title(), lang=lang)
            speak_then_show(tts, tts)
        else:
            header = f"Added {len(added_rows)} Pokémon — by {who}."
            final = header + (_names_suffix(added_rows, lang, limit=15) if added_rows else "")
            speak_then_show(final, final)
        return

    # 6) update level (single or bulk: ids list/range)
    m = re.search(r"\bupdate\b\s+(?:pokemon|pokémon)?\s*([0-9,\s\-and]+)\s+\blevel\s+(\d+)\b", text, re.I)
    if m:
        ids = _parse_id_list(m.group(1)); lvl = int(m.group(2))
        rows_all = list_pokemon(); by_id = _rows_by_id(rows_all)
        touched: List[Dict] = []
        for pid in ids:
            try: update_pokemon(pid, level=lvl); r = by_id.get(pid, {"name": f"Pokémon {pid}"}); touched.append({"name": (r.get("name") or f"Pokémon {pid}")})
            except Exception: continue
        if len(touched) == 1:
            pid = ids[0]; row = by_id.get(pid, {"ptype": "Normal", "name": None})
            tts = tts_update(pid=pid, lvl=lvl, ptype=row.get("ptype", ""), lang=lang, name=row.get("name"))
            speak_then_show(tts, tts)
        else:
            header = f"Updated {len(touched)} Pokémon to level {lvl} — by {who}."
            final = header + (_names_suffix(touched, lang, limit=15) if touched else "")
            speak_then_show(final, final)
        return

    # 7) update type/nickname (single or bulk: ids list/range)
    m = re.search(r"\bupdate\b\s+(?:pokemon|pokémon)?\s*([0-9,\s\-and]+)(?:.*?\btype\s+([A-Za-z/]+))?(?:.*?\bnickname\s+([A-Za-z0-9_-]+))?", text, re.I)
    if m and (m.group(2) or m.group(3)):
        ids = _parse_id_list(m.group(1)); ptype = m.group(2).title() if m.group(2) else None; nick = (m.group(3) or None)
        rows_all = list_pokemon(); by_id = _rows_by_id(rows_all); touched: List[Dict] = []
        for pid in ids:
            try: update_pokemon(pid, ptype=ptype, nickname=nick); r = by_id.get(pid, {"name": f"Pokémon {pid}", "ptype": "Normal"}); touched.append({"name": (r.get("name") or f"Pokémon {pid}")})
            except Exception: continue
        if len(touched) == 1:
            pid = ids[0]; rows = list_pokemon(); row = next((r for r in rows if int(r.get("id")) == pid), {"ptype": "Normal", "level": 0})
            tts = tts_update(pid=pid, lvl=row.get("level", 0), ptype=row.get("ptype", ""), lang=lang, name=row.get("name"))
            speak_then_show(tts, tts)
        else:
            what=[]
            if ptype: what.append(f"type {ptype}")
            if nick: what.append(f"nickname {nick}")
            header = f"Updated {len(touched)} Pokémon ({' and '.join(what) if what else 'fields'}) — by {who}."
            final = header + (_names_suffix(touched, lang, limit=15) if touched else "")
            speak_then_show(final, final)
        return

    # 8) delete (single or bulk: ids list/range)
    m = re.search(r"\b(delete|remove)\b\s+(?:pokemon|pokémon)?\s*([0-9,\s\-and]+)\b", text, re.I)
    if m:
        ids = _parse_id_list(m.group(2)); rows_all = list_pokemon(); by_id = _rows_by_id(rows_all); removed: List[Dict] = []
        for pid in ids:
            r = by_id.get(pid, {"name": None, "ptype": "Normal"})
            try: delete_pokemon(pid); removed.append({"name": (r.get("name") or f"Pokémon {pid}")})
            except Exception: continue
        if len(removed) == 1:
            pid = ids[0]; r = by_id.get(pid, {"ptype": "Normal"})
            tts = tts_delete(pid=pid, ptype=r.get("ptype", "Normal"), lang=lang, name=r.get("name")); speak_then_show(tts, tts)
        else:
            header = f"Deleted {len(removed)} Pokémon — by {who}."
            final = header + (_names_suffix(removed, lang, limit=15) if removed else "")
            speak_then_show(final, final)
        return

    # ============================================================
    # Help fallback (multilingual)
    # ============================================================
    help_text = HELP_TEXT.get(lang, HELP_TEXT["en"])
    speak_then_show(SPEAK_HELP.get(lang, SPEAK_HELP["en"]), help_text)
