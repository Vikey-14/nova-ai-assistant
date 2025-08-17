import re
import logging
from memory_handler import (
    load_notes, save_note, search_notes,
    delete_specific_note, clear_all_notes, update_note
)

# 📘 Logger setup
logger = logging.getLogger(__name__)

# 📝 Voice Note — multilingual note-taking
def create_note(command: str):
    from utils import _speak_multilang, speak, listen_command  # ✅ Lazy import

    try:
        speak("What would you like me to note down?")
        note_content = listen_command().strip()

        if note_content:
            save_note(note_content)
            logger.info(f"[📝 Note Created] {note_content}")
            _speak_multilang(
                "Noted successfully.",
                hi="नोट बना ली गई है।",
                fr="Note enregistrée avec succès.",
                es="Nota guardada con éxito.",
                de="Notiz erfolgreich gespeichert."
            )
        else:
            raise ValueError("Empty note")

    except Exception as e:
        logger.error(f"[❌ Note Creation Failed] {e}")
        _speak_multilang(
            "Sorry, I couldn’t save your note.",
            hi="माफ़ कीजिए, मैं आपकी नोट सहेज नहीं सकी।",
            fr="Désolée, je n’ai pas pu enregistrer ta note.",
            es="Lo siento, no he podido guardar tu nota.",
            de="Entschuldigung, ich konnte deine Notiz nicht speichern."
        )

# 📖 Read all saved notes
def read_notes(command: str):
    from utils import _speak_multilang

    notes = load_notes()
    if not notes:
        logger.info("[📖 Read Notes] No saved notes found.")
        _speak_multilang(
            "You have no saved notes.",
            hi="आपके पास कोई सहेजी गई नोट्स नहीं हैं।",
            fr="Tu n’as aucune note enregistrée.",
            es="No tienes notas guardadas.",
            de="Du hast keine gespeicherten Notizen."
        )
    else:
        logger.info(f"[📖 Read Notes] Found {len(notes)} notes.")
        _speak_multilang(
            f"You have {len(notes)} notes. Reading them now.",
            hi=f"आपके पास {len(notes)} नोट्स हैं। मैं उन्हें अब पढ़ रही हूँ।",
            fr=f"Tu as {len(notes)} notes. Je vais les lire maintenant.",
            es=f"Tienes {len(notes)} notas. Te las leo ahora.",
            de=f"Du hast {len(notes)} Notizen. Ich lese sie dir vor."
        )
        for idx, note in enumerate(notes, start=1):
            print(f"📝 [{idx}] ({note['timestamp']}): {note['content']}")
        for note in notes:
            _speak_multilang(note['content'])

# 🔍 Search notes
def search_notes_by_keyword(command: str):
    from utils import _speak_multilang, listen_command

    try:
        keyword = re.sub(
            r"(search notes|find notes|look for note|नोट खोजें|नोट ढूंढो|chercher des notes|trouve des notes|buscar notas|encontrar notas|suche notizen|finde notizen)",
            "", command, flags=re.IGNORECASE).strip()

        results = search_notes(keyword)

        if not results:
            logger.info(f"[🔍 Search Notes] No match for keyword: {keyword}")
            _speak_multilang(
                "No notes found with that keyword.",
                hi="उस कीवर्ड से कोई नोट्स नहीं मिलीं।",
                fr="Aucune note trouvée avec ce mot-clé.",
                es="No se encontraron notas con esa palabra clave.",
                de="Keine Notizen mit diesem Stichwort gefunden."
            )
        else:
            logger.info(f"[🔍 Search Notes] Found {len(results)} notes for keyword: {keyword}")
            _speak_multilang(
                f"I found {len(results)} notes with that keyword.",
                hi=f"मुझे उस कीवर्ड से {len(results)} नोट्स मिली हैं।",
                fr=f"J’ai trouvé {len(results)} notes avec ce mot-clé.",
                es=f"He encontrado {len(results)} notas con esa palabra clave.",
                de=f"Ich habe {len(results)} Notizen mit diesem Stichwort gefunden."
            )

            print("\n🔎 Matching Notes:")
            for i, note in enumerate(results, 1):
                print(f"{i}. [{note['timestamp']}] {note['content']}")

            _speak_multilang(
                "Would you like me to read one of them? Say the note number or say cancel.",
                hi="क्या आप उनमें से कोई एक नोट सुनना चाहेंगी? नंबर बताइए या कैंसिल कहिए।",
                fr="Souhaites-tu que je lise l’une d’elles ? Dis le numéro ou dis « annule ».",
                es="¿Quieres que lea una de ellas? Di el número o di cancelar.",
                de="Möchtest du, dass ich eine davon vorlese? Sag die Nummer oder 'abbrechen'."
            )

            user_reply = listen_command().lower()
            if any(word in user_reply for word in ["cancel", "कैंसिल", "annule", "cancela", "abbrechen"]):
                logger.info("[🔍 Search Cancelled by User]")
                _speak_multilang(
                    "Okay, cancelled reading.",
                    hi="ठीक है, पढ़ना रद्द कर दिया गया है।",
                    fr="D’accord, j’annule la lecture.",
                    es="De acuerdo, he cancelado la lectura.",
                    de="Okay, ich habe das Vorlesen abgebrochen."
                )
            else:
                match = re.search(r"\d+", user_reply)
                if match:
                    index = int(match.group())
                    if 1 <= index <= len(results):
                        selected_note = results[index - 1]['content']
                        logger.info(f"[🔍 Note Read] Note #{index}: {selected_note}")
                        _speak_multilang(selected_note)
                    else:
                        _speak_multilang(
                            "That number is out of range.",
                            hi="वह संख्या सीमा से बाहर है।",
                            fr="Ce numéro est hors de portée.",
                            es="Ese número está fuera de rango.",
                            de="Diese Nummer ist außerhalb des gültigen Bereichs."
                        )
                else:
                    _speak_multilang(
                        "Sorry, I didn't understand the number.",
                        hi="माफ़ कीजिए, मैं संख्या नहीं समझ सकी।",
                        fr="Désolée, je n’ai pas compris le numéro.",
                        es="Lo siento, no entendí el número.",
                        de="Entschuldigung, ich habe die Nummer nicht verstanden."
                    )

    except Exception as e:
        logger.error(f"[❌ Search Failed] {e}")
        _speak_multilang(
            "Something went wrong while searching the notes.",
            hi="नोट्स खोजते समय कुछ गड़बड़ हो गई।",
            fr="Une erreur s’est produite lors de la recherche des notes.",
            es="Algo salió mal al buscar las notas.",
            de="Beim Durchsuchen der Notizen ist ein Fehler aufgetreten."
        )

# ✏️ Update a note
def update_note_handler(command: str):
    from utils import _speak_multilang

    try:
        index = None
        keyword = None
        new_content = None

        match = re.search(r"note\s*(number\s*)?(\d+)\s*(to|into)?\s*(.+)", command)
        if match:
            index = int(match.group(2))
            new_content = match.group(4).strip()
        else:
            match_kw = re.search(r"(?:update|change|edit)\s+note\s+(.*?)\s+(to|into)\s+(.+)", command)
            if match_kw:
                keyword = match_kw.group(1).strip()
                new_content = match_kw.group(3).strip()

        if new_content and (index or keyword):
            success = update_note(index=index, keyword=keyword, new_content=new_content)
            if success:
                logger.info(f"[✏️ Note Updated] index={index} | keyword={keyword} → {new_content}")
                _speak_multilang(
                    "Note updated successfully.",
                    hi="नोट को सफलतापूर्वक अपडेट कर दिया गया है।",
                    fr="Note mise à jour avec succès.",
                    es="Nota actualizada con éxito.",
                    de="Notiz erfolgreich aktualisiert."
                )
            else:
                raise ValueError("Note not found")
        else:
            raise ValueError("Could not parse command")

    except Exception as e:
        logger.error(f"[❌ Update Failed] {e}")
        _speak_multilang(
            "Sorry, I couldn't update the note.",
            hi="माफ़ कीजिए, मैं नोट अपडेट नहीं कर सकी।",
            fr="Désolée, je n’ai pas pu mettre à jour la note.",
            es="Lo siento, no he podido actualizar la nota.",
            de="Entschuldigung, ich konnte die Notiz nicht aktualisieren."
        )

# ❌ Delete note(s)
def delete_note_handler(command: str):
    from utils import _speak_multilang

    try:
        if "all notes" in command or "सभी" in command or "toutes" in command or "todas" in command or "alle" in command:
            clear_all_notes()
            logger.info("[❌ Notes Cleared] All notes deleted.")
            _speak_multilang(
                "All notes deleted successfully.",
                hi="सभी नोट्स सफलतापूर्वक हटा दी गई हैं।",
                fr="Toutes les notes ont été supprimées avec succès.",
                es="Todas las notas han sido eliminadas con éxito.",
                de="Alle Notizen wurden erfolgreich gelöscht."
            )
        else:
            index = None
            keyword = None

            match = re.search(r"note\s*(number\s*)?(\d+)", command)
            if match:
                index = int(match.group(2))
            else:
                keyword = re.sub(
                    r"(delete note|remove note|delete my note|remove my note|नोट हटाओ|मेरी नोट हटाओ|supprime la note|borra la nota|lösche die notiz|meine notiz löschen)",
                    "", command, flags=re.IGNORECASE).strip()

            success = delete_specific_note(index=index, keyword=keyword)

            if success:
                logger.info(f"[❌ Note Deleted] index={index} | keyword={keyword}")
                _speak_multilang(
                    "Note deleted successfully.",
                    hi="नोट सफलतापूर्वक हटा दी गई है।",
                    fr="Note supprimée avec succès.",
                    es="Nota eliminada con éxito.",
                    de="Notiz erfolgreich gelöscht."
                )
            else:
                _speak_multilang(
                    "Sorry, I couldn't find that note.",
                    hi="माफ़ कीजिए, मैं वह नोट नहीं ढूंढ सकी।",
                    fr="Désolée, je n’ai pas trouvé cette note.",
                    es="Lo siento, no he podido encontrar esa nota.",
                    de="Entschuldigung, ich konnte die Notiz nicht finden."
                )

    except Exception as e:
        logger.error(f"[❌ Delete Failed] {e}")
        _speak_multilang(
            "Something went wrong while trying to delete the note.",
            hi="नोट हटाने में कुछ गड़बड़ हो गई।",
            fr="Une erreur s’est produite lors de la suppression de la note.",
            es="Algo salió mal al intentar eliminar la nota.",
            de="Beim Löschen der Notiz ist ein Fehler aufgetreten."
        )
