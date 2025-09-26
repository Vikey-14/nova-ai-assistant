# 📂 handlers/notes_commands.py — SAY→SHOW (via say_show) + typed/voice follow-ups (UI-language aware)

from __future__ import annotations

import re
import logging
from typing import Optional, List, Dict

from memory_handler import (
    load_notes, save_note, search_notes,
    delete_specific_note, clear_all_notes, update_note
)
from say_show import say_show  # speak first (blocking), then show localized bubble

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Lazy utils (avoid circular imports)
def _get_utils():
    from utils import selected_language, listen_command
    from followup import await_followup
    return selected_language, listen_command, await_followup

def _ui_lang() -> str:
    selected_language, *_ = _get_utils()
    return (selected_language or "en").split("-")[0].lower()

def _pick(d: Dict[str, str], **fmt) -> str:
    """Pick text for current UI lang; fallback to en; safely format."""
    txt = d.get(_ui_lang(), d.get("en", ""))
    try:
        return txt.format(**fmt) if fmt else txt
    except Exception:
        return txt

# ─────────────────────────────────────────────────────────────────────────────
# Multilingual texts (ALL lines localized)
T = {
    # Prompts
    "ask_note_text": {
        "en": "What would you like me to note down? You can type or say it.",
        "hi": "आप क्या नोट करवाना चाहेंगे? आप टाइप कर सकते हैं या बोल सकते हैं।",
        "fr": "Que veux-tu que je note ? Tu peux écrire ou parler.",
        "es": "¿Qué quieres que anote? Puedes escribir o hablar.",
        "de": "Was soll ich notieren? Du kannst tippen oder sprechen.",
    },
    "ask_pick_note": {
        "en": "Would you like me to read one? Type or say the note number, or say 'cancel'.",
        "hi": "क्या आप उनमें से कोई एक नोट सुनना चाहेंगे? नंबर टाइप/बोलें, या 'cancel' कहें।",
        "fr": "Souhaites-tu que je lise l’une d’elles ? Dis le numéro de la note ou « cancel ».",
        "es": "¿Quieres que lea una de ellas? Di el número de la nota o di 'cancel'.",
        "de": "Soll ich eine davon vorlesen? Sage die Notiznummer oder 'cancel'.",
    },

    # Generic follow-up didn’t get it (if you want to reuse elsewhere)
    "didnt_get_it": {
        "en": "I couldn't get that.",
        "hi": "मैं समझ नहीं पाई।",
        "fr": "Je n’ai pas compris.",
        "es": "No entendí eso.",
        "de": "Ich habe das nicht verstanden.",
    },

    # Create
    "create_ok": {
        "en": "Noted successfully.",
        "hi": "नोट बना ली गई है।",
        "fr": "Note enregistrée avec succès.",
        "es": "Nota guardada con éxito.",
        "de": "Notiz erfolgreich gespeichert.",
    },
    "create_fail": {
        "en": "Sorry, I couldn’t save your note.",
        "hi": "माफ़ कीजिए, मैं आपकी नोट सहेज नहीं सकी।",
        "fr": "Désolée, je n’ai pas pu enregistrer tu nota.",
        "es": "Lo siento, no he podido guardar tu nota.",
        "de": "Entschuldigung, ich konnte deine Notiz nicht speichern.",
    },

    # Read
    "read_none": {
        "en": "You have no saved notes.",
        "hi": "आपके पास कोई सहेजी गई नोट्स नहीं हैं।",
        "fr": "Tu n’as aucune note enregistrée.",
        "es": "No tienes notas guardadas.",
        "de": "Du hast keine gespeicherten Notizen.",
    },
    "read_intro": {
        "en": "You have {n} notes. Reading them now.",
        "hi": "आपके पास {n} नोट्स हैं। मैं उन्हें अब पढ़ रही हूँ।",
        "fr": "Tu as {n} notes. Je vais les lire maintenant.",
        "es": "Tienes {n} notas. Te las leo ahora.",
        "de": "Du hast {n} Notizen. Ich lese sie dir vor.",
    },

    # Search
    "search_none": {
        "en": "No notes found with that keyword.",
        "hi": "उस कीवर्ड से कोई नोट्स नहीं मिलीं।",
        "fr": "Aucune note trouvée avec ce mot-clé.",
        "es": "No se encontraron notas con esa palabra clave.",
        "de": "Keine Notizen mit diesem Stichwort gefunden.",
    },
    "search_count": {
        "en": "I found {n} notes with that keyword.",
        "hi": "मुझे उस कीवर्ड से {n} नोट्स मिली हैं।",
        "fr": "J’ai trouvé {n} notes avec ce mot-clé.",
        "es": "He encontrado {n} notas con esa palabra clave.",
        "de": "Ich habe {n} Notizen mit diesem Stichwort gefunden.",
    },
    "cancel_ok": {
        "en": "Okay, cancelled reading.",
        "hi": "ठीक है, पढ़ना रद्द कर दिया गया है।",
        "fr": "D’accord, j’annule la lecture.",
        "es": "De acuerdo, he cancelado la lectura.",
        "de": "Okay, ich habe das Vorlesen abgebrochen.",
    },
    "out_of_range": {
        "en": "That number is out of range.",
        "hi": "वह संख्या सीमा से बाहर है।",
        "fr": "Ce numéro est hors de portée.",
        "es": "Ese número está fuera de rango.",
        "de": "Diese Nummer ist außerhalb des gültigen Bereichs.",
    },
    "bad_number": {
        "en": "Sorry, I didn't understand the number.",
        "hi": "माफ़ कीजिए, मैं संख्या नहीं समझ सकी।",
        "fr": "Désolée, je n’ai pas compris le numéro.",
        "es": "Lo siento, no entendí el número.",
        "de": "Entschuldigung, ich habe die Nummer nicht verstanden.",
    },

    # Update
    "update_ok": {
        "en": "Note updated successfully.",
        "hi": "नोट को सफलतापूर्वक अपडेट कर दिया गया है।",
        "fr": "Note mise à jour avec succès.",
        "es": "Nota actualizada con éxito.",
        "de": "Notiz erfolgreich aktualisiert.",
    },
    "update_fail": {
        "en": "Sorry, I couldn't update the note.",
        "hi": "माफ़ कीजिए, मैं नोट अपडेट नहीं कर सकी।",
        "fr": "Désolée, je n’ai pas pu mettre à jour la note.",
        "es": "Lo siento, no he podido actualizar la nota.",
        "de": "Entschuldigung, ich konnte die Notiz nicht aktualisieren.",
    },

    # Delete
    "delete_all_ok": {
        "en": "All notes deleted successfully.",
        "hi": "सभी नोट्स सफलतापूर्वक हटा दी गई हैं।",
        "fr": "Toutes les notes ont été supprimées avec succès.",
        "es": "Todas las notas han sido eliminadas con éxito.",
        "de": "Alle Notizen wurden erfolgreich gelöscht.",
    },
    "delete_one_ok": {
        "en": "Note deleted successfully.",
        "hi": "नोट सफलतापूर्वक हटा दी गई है।",
        "fr": "Note supprimée avec succès.",
        "es": "Nota eliminada con éxito.",
        "de": "Notiz erfolgreich gelöscht.",
    },
    "delete_fail": {
        "en": "Sorry, I couldn't find that note.",
        "hi": "माफ़ कीजिए, मैं वह नोट नहीं ढूंढ सकी।",
        "fr": "Désolée, je n’ai pas trouvé cette note.",
        "es": "Lo siento, no he podido encontrar esa nota.",
        "de": "Entschuldigung, ich konnte die Notiz nicht finden.",
    },
    "delete_err": {
        "en": "Something went wrong while trying to delete the note.",
        "hi": "नोट हटाने में कुछ गड़बड़ हो गई।",
        "fr": "Une erreur s’est produite lors de la suppression de la note.",
        "es": "Algo salió mal al intentar eliminar la nota.",
        "de": "Beim Löschen der Notiz ist ein Fehler aufgetreten.",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Create note (typed/voice follow-up; SAY→SHOW via say_show)
def create_note(command: str) -> None:
    try:
        _, listen_command, await_followup = _get_utils()

        # SAY→SHOW prompt
        say_show(
            T["ask_note_text"]["en"],
            hi=T["ask_note_text"]["hi"],
            fr=T["ask_note_text"]["fr"],
            es=T["ask_note_text"]["es"],
            de=T["ask_note_text"]["de"],
            title="Nova",
        )

        # Await a single barge-in/typed response (no re-say/re-show inside await)
        note_content = await_followup(
            _pick(T["ask_note_text"]),
            speak_fn=lambda *_a, **_k: None,
            show_fn=lambda *_a, **_k: None,
            listen_fn=listen_command,
            allow_typed=True,
            allow_voice=True,
            timeout=18.0
        )
        note_content = (note_content or "").strip()
        if not note_content:
            raise ValueError("Empty note content")

        save_note(note_content)
        logger.info(f"[📝 Note Created] {note_content}")

        say_show(
            T["create_ok"]["en"],
            hi=T["create_ok"]["hi"],
            fr=T["create_ok"]["fr"],
            es=T["create_ok"]["es"],
            de=T["create_ok"]["de"],
            title="Nova",
        )

    except Exception as e:
        logger.error(f"[❌ Note Creation Failed] {e}")
        say_show(
            T["create_fail"]["en"],
            hi=T["create_fail"]["hi"],
            fr=T["create_fail"]["fr"],
            es=T["create_fail"]["es"],
            de=T["create_fail"]["de"],
            title="Nova",
        )

# ─────────────────────────────────────────────────────────────────────────────
# Read all notes (SAY intro, SHOW list)
def read_notes_handler(command: str) -> None:
    notes = load_notes()
    if not notes:
        logger.info("[📖 Read Notes] No saved notes found.")
        say_show(
            T["read_none"]["en"],
            hi=T["read_none"]["hi"],
            fr=T["read_none"]["fr"],
            es=T["read_none"]["es"],
            de=T["read_none"]["de"],
            title="Nova",
        )
        return

    logger.info(f"[📖 Read Notes] Found {len(notes)} notes.")
    say_show(
        T["read_intro"]["en"].format(n=len(notes)),
        hi=T["read_intro"]["hi"].format(n=len(notes)),
        fr=T["read_intro"]["fr"].format(n=len(notes)),
        es=T["read_intro"]["es"].format(n=len(notes)),
        de=T["read_intro"]["de"].format(n=len(notes)),
        title="Nova",
    )

    # Build text list for bubble (contents are user text → language-neutral)
    lines = [f"{i+1}. [{n.get('timestamp','')}] {n.get('content','')}" for i, n in enumerate(notes)]
    say_show("\n".join(lines), title="Nova")

# ─────────────────────────────────────────────────────────────────────────────
# Search notes → list → optional read-one follow-up
def search_notes_by_keyword(command: str) -> None:
    try:
        _, listen_command, await_followup = _get_utils()

        # Strip common triggers in multiple languages
        keyword = re.sub(
            r"(search notes|find notes|look for note|नोट खोजें|नोट ढूंढो|chercher des notes|trouve des notes|buscar notas|encontrar notas|suche notizen|finde notizen)",
            "", command, flags=re.IGNORECASE
        ).strip()

        results = search_notes(keyword)
        if not results:
            logger.info(f"[🔍 Search Notes] No match for keyword: {keyword}")
            say_show(
                T["search_none"]["en"],
                hi=T["search_none"]["hi"],
                fr=T["search_none"]["fr"],
                es=T["search_none"]["es"],
                de=T["search_none"]["de"],
                title="Nova",
            )
            return

        logger.info(f"[🔍 Search Notes] Found {len(results)} notes for keyword: {keyword}")
        say_show(
            T["search_count"]["en"].format(n=len(results)),
            hi=T["search_count"]["hi"].format(n=len(results)),
            fr=T["search_count"]["fr"].format(n=len(results)),
            es=T["search_count"]["es"].format(n=len(results)),
            de=T["search_count"]["de"].format(n=len(results)),
            title="Nova",
        )

        # Show list
        list_lines = [f"{i+1}. [{n['timestamp']}] {n['content']}" for i, n in enumerate(results)]
        say_show("\n".join(list_lines), title="Nova")

        # Ask which to read (SAY→SHOW once), then await without re-speaking
        say_show(
            T["ask_pick_note"]["en"],
            hi=T["ask_pick_note"]["hi"],
            fr=T["ask_pick_note"]["fr"],
            es=T["ask_pick_note"]["es"],
            de=T["ask_pick_note"]["de"],
            title="Nova",
        )
        user_reply = await_followup(
            _pick(T["ask_pick_note"]),
            speak_fn=lambda *_a, **_k: None,
            show_fn=lambda *_a, **_k: None,
            listen_fn=listen_command,
            allow_typed=True,
            allow_voice=True,
            timeout=18.0
        )
        user_reply = (user_reply or "").strip().lower()

        # Cancel in common languages
        if any(w in user_reply for w in ["cancel", "कैंसिल", "annule", "cancela", "abbrechen"]):
            logger.info("[🔍 Search Cancelled by User]")
            say_show(
                T["cancel_ok"]["en"],
                hi=T["cancel_ok"]["hi"],
                fr=T["cancel_ok"]["fr"],
                es=T["cancel_ok"]["es"],
                de=T["cancel_ok"]["de"],
                title="Nova",
            )
            return

        # Extract note number
        m = re.search(r"\d+", user_reply)
        if not m:
            say_show(
                T["bad_number"]["en"],
                hi=T["bad_number"]["hi"],
                fr=T["bad_number"]["fr"],
                es=T["bad_number"]["es"],
                de=T["bad_number"]["de"],
                title="Nova",
            )
            return

        idx = int(m.group())
        if not (1 <= idx <= len(results)):
            say_show(
                T["out_of_range"]["en"],
                hi=T["out_of_range"]["hi"],
                fr=T["out_of_range"]["fr"],
                es=T["out_of_range"]["es"],
                de=T["out_of_range"]["de"],
                title="Nova",
            )
            return

        selected = results[idx - 1]['content']
        logger.info(f"[🔍 Note Read] Note #{idx}: {selected}")
        say_show(selected, title="Nova")

    except Exception as e:
        logger.error(f"[❌ Search Failed] {e}")
        say_show(
            T["search_none"]["en"],
            hi=T["search_none"]["hi"],
            fr=T["search_none"]["fr"],
            es=T["search_none"]["es"],
            de=T["search_none"]["de"],
            title="Nova",
        )

# ─────────────────────────────────────────────────────────────────────────────
# Update a note (by index or first keyword match)
def update_note_handler(command: str) -> None:
    try:
        idx: Optional[int] = None
        keyword: Optional[str] = None
        new_content: Optional[str] = None

        # e.g. "update note 3 to Buy milk"
        m_idx = re.search(r"(?:update|change|edit)\s+note\s*(?:number\s*)?(\d+)\s*(?:to|into)\s+(.+)", command, re.I)
        if m_idx:
            idx = int(m_idx.group(1))
            new_content = m_idx.group(2).strip()
        else:
            # e.g. "update note shopping to Buy bread"
            m_kw = re.search(r"(?:update|change|edit)\s+note\s+(.+?)\s+(?:to|into)\s+(.+)", command, re.I)
            if m_kw:
                keyword = m_kw.group(1).strip()
                new_content = m_kw.group(2).strip()

        if not new_content or (idx is None and not keyword):
            raise ValueError("parse")

        if idx is None and keyword:
            all_notes = load_notes()
            idx = next(
                (i for i, n in enumerate(all_notes, 1)
                 if keyword.lower() in n.get("content", "").lower()),
                None
            )

        if not idx:
            raise ValueError("index")

        ok = update_note(idx, new_content)
        if not ok:
            raise ValueError("notfound")

        logger.info(f"[✏️ Note Updated] index={idx} → {new_content}")
        say_show(
            T["update_ok"]["en"],
            hi=T["update_ok"]["hi"],
            fr=T["update_ok"]["fr"],
            es=T["update_ok"]["es"],
            de=T["update_ok"]["de"],
            title="Nova",
        )

    except Exception as e:
        logger.error(f"[❌ Update Failed] {e}")
        say_show(
            T["update_fail"]["en"],
            hi=T["update_fail"]["hi"],
            fr=T["update_fail"]["fr"],
            es=T["update_fail"]["es"],
            de=T["update_fail"]["de"],
            title="Nova",
        )

# ─────────────────────────────────────────────────────────────────────────────
# Delete note(s)
def delete_note_handler(command: str) -> None:
    try:
        # Delete ALL?
        if any(kw in command.lower() for kw in ["all notes", "सभी", "toutes", "todas", "alle"]):
            clear_all_notes()
            logger.info("[❌ Notes Cleared] All notes deleted.")
            say_show(
                T["delete_all_ok"]["en"],
                hi=T["delete_all_ok"]["hi"],
                fr=T["delete_all_ok"]["fr"],
                es=T["delete_all_ok"]["es"],
                de=T["delete_all_ok"]["de"],
                title="Nova",
            )
            return

        # Delete by index or by keyword
        idx = None
        keyword = None

        m = re.search(r"note\s*(?:number\s*)?(\d+)", command, re.I)
        if m:
            idx = int(m.group(1))
        else:
            keyword = re.sub(
                r"(delete note|remove note|delete my note|remove my note|नोट हटाओ|मेरी नोट हटाओ|supprime la note|borra la nota|lösche die notiz|meine notiz löschen)",
                "", command, flags=re.IGNORECASE
            ).strip()

        success = delete_specific_note(index=idx, keyword=keyword)

        if success:
            logger.info(f"[❌ Note Deleted] index={idx} | keyword={keyword}")
            say_show(
                T["delete_one_ok"]["en"],
                hi=T["delete_one_ok"]["hi"],
                fr=T["delete_one_ok"]["fr"],
                es=T["delete_one_ok"]["es"],
                de=T["delete_one_ok"]["de"],
                title="Nova",
            )
        else:
            say_show(
                T["delete_fail"]["en"],
                hi=T["delete_fail"]["hi"],
                fr=T["delete_fail"]["fr"],
                es=T["delete_fail"]["es"],
                de=T["delete_fail"]["de"],
                title="Nova",
            )

    except Exception as e:
        logger.error(f"[❌ Delete Failed] {e}")
        say_show(
            T["delete_err"]["en"],
            hi=T["delete_err"]["hi"],
            fr=T["delete_err"]["fr"],
            es=T["delete_err"]["es"],
            de=T["delete_err"]["de"],
            title="Nova",
        )
