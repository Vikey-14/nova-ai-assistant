from utils import (
    greet_user,
    listen_command,
    set_language,
    speak,
    _speak_multilang,
    selected_language,
    language_voice_map
)
from core_engine import process_command
from gui_interface import nova_gui  # 🖥️ GUI support

if __name__ == "__main__":
    # 👋 Greet in English only (before language is set)
    greet_user()

    # 🌐 Ask and set user's preferred language
    set_language()

    # 🔔 Confirm selected language to user (spoken + printed)
    lang_readable = language_voice_map.get(selected_language, "English").capitalize()
    print(f"🛠️ NOVA: I will now speak in {lang_readable} for this session until manually changed.")
    _speak_multilang(
        f"I will now speak in {lang_readable} for this session until manually changed.",
        hi=f"अब मैं इस सत्र में {lang_readable} में बोलूँगा जब तक कि आप इसे मैन्युअली न बदलें।",
        de=f"Ich werde in dieser Sitzung jetzt {lang_readable} sprechen, bis Sie es manuell ändern.",
        fr=f"Je parlerai maintenant en {lang_readable} pendant cette session jusqu'à ce que vous le changiez manuellement.",
        es=f"Ahora hablaré en {lang_readable} durante esta sesión hasta que lo cambies manualmente."
    )
    _speak_multilang(
        f"I will now assist you in {lang_readable}. You can change it anytime during the session.",
        hi=f"अब मैं आपकी सहायता {lang_readable} में करूँगा। आप इसे सत्र के दौरान कभी भी बदल सकते हैं।",
        de=f"Ich werde Sie jetzt auf {lang_readable} unterstützen. Sie können es während der Sitzung jederzeit ändern.",
        fr=f"Je vais maintenant vous aider en {lang_readable}. Vous pouvez le changer à tout moment pendant la session.",
        es=f"A partir de ahora te ayudaré en {lang_readable}. Puedes cambiarlo en cualquier momento durante la sesión."
    )

    # 💡 Hook GUI input to backend processor (Phase 11.5 magic)
    nova_gui.external_callback = process_command

    # 🎯 Prompt user for first task
    _speak_multilang(
        "How can I help you today?",
        hi="मैं आज आपकी कैसे मदद कर सकता हूँ?",
        de="Wie kann ich Ihnen heute helfen?",
        fr="Comment puis-je vous aider aujourd'hui?",
        es="¿Cómo puedo ayudarte hoy?"
    )
    print("🟢 NOVA: I'm ready for your first command.")

    # 🎙️ Start voice command loop
    while True:
        command = listen_command()
        if command:
            # 💬 Show what the user said in GUI
            nova_gui.show_message("YOU", command)

            # 🎯 Process the command with your AI engine
            process_command(command)

            # 🔁 Prompt again
            _speak_multilang(
                "I'm waiting for your next command.",
                hi="मैं आपके अगले आदेश का इंतजार कर रहा हूँ।",
                de="Ich warte auf Ihren nächsten Befehl.",
                fr="J'attends votre prochaine commande.",
                es="Estoy esperando tu próximo comando."
            )
