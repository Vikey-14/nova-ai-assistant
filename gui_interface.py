import tkinter as tk
from PIL import Image, ImageTk
import threading
import os

# 👽 Global GUI handler (imported in main/utils)
class NovaGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("NOVA - AI Assistant")
        self.root.geometry("480x580")
        self.root.configure(bg="#0f0f0f")
        self.root.resizable(False, False)

        # 🖼️ Nova Branding Face
        image_path = os.path.join("assets", "nova_gui_face.png")
        if not os.path.exists(image_path):
            raise FileNotFoundError("nova_face.png not found in project directory.")

        image = Image.open(image_path).resize((120, 120))
        self.nova_photo = ImageTk.PhotoImage(image)
        self.image_label = tk.Label(self.root, image=self.nova_photo, bg="#0f0f0f")
        self.image_label.pack(pady=5)

        # 💬 Chat log display
        self.text_display = tk.Text(self.root, height=18, width=56, bg="#1a1a1a", fg="#00ffcc", font=("Consolas", 10))
        self.text_display.pack(padx=10, pady=5)
        self.text_display.insert(tk.END, "🟢 NOVA: Hello Commander V. GUI is online.\n")
        self.text_display.configure(state='disabled')

        # 📝 User input field
        self.input_entry = tk.Entry(self.root, width=35, font=("Consolas", 11))
        self.input_entry.pack(pady=8)

        # 🖱️ Button row
        button_frame = tk.Frame(self.root, bg="#0f0f0f")
        button_frame.pack()

        self.send_button = tk.Button(button_frame, text="Send", command=self._on_send, width=10, bg="#202020", fg="white")
        self.send_button.grid(row=0, column=0, padx=5)

        self.clear_button = tk.Button(button_frame, text="Clear", command=self._on_clear, width=10, bg="#202020", fg="white")
        self.clear_button.grid(row=0, column=1, padx=5)

        # 🔄 Hook for external command processor (set externally)
        self.external_callback = None

        # 🚀 Run GUI in a separate thread
        gui_thread = threading.Thread(target=self.root.mainloop)
        gui_thread.daemon = True
        gui_thread.start()

    # 💬 Add message to chat log
    def show_message(self, speaker, message):
        self.text_display.configure(state='normal')
        self.text_display.insert(tk.END, f"{speaker}: {message}\n")
        self.text_display.configure(state='disabled')
        self.text_display.see(tk.END)

    # 🧠 Send button triggers this
    def _on_send(self):
        user_text = self.input_entry.get().strip()
        if user_text:
            self.show_message("YOU", user_text)
            self.input_entry.delete(0, tk.END)

            if self.external_callback:
                self.external_callback(user_text)

        # 🖱️ Auto-focus input for next message
        self.input_entry.focus_set()

    # 🧹 Clear chat
    def _on_clear(self):
        self.text_display.configure(state='normal')
        self.text_display.delete('1.0', tk.END)
        self.text_display.configure(state='disabled')


# 🌟 Global GUI object
nova_gui = NovaGUI()
