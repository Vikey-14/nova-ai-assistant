# 📁 memory_handler.py

import json
import os
from datetime import datetime

# 📌 Paths
MEMORY_FILE = "data/memory.json"
NOTES_FILE = "data/notes.json"

# 🧠 Ensure memory file exists
def init_memory():
    if not os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

# 💾 Save a key-value pair to memory
def save_to_memory(key, value):
    init_memory()
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data[key] = value
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# 🔎 Retrieve a value by key
def load_from_memory(key):
    init_memory()
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get(key)

# 📝 Save a voice note to notes.json
def save_note(content):
    notes = []

    # Load existing notes
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            notes = json.load(f)

    # Add new note with timestamp
    notes.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "content": content
    })

    # Save back to file
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False)

# 📖 Load all notes
def load_notes():
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# 🗑️ Delete a specific note by index or keyword
def delete_specific_note(index=None, keyword=None):
    if not os.path.exists(NOTES_FILE):
        return False

    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        notes = json.load(f)

    original_count = len(notes)

    # 🎯 Delete by index (1-based)
    if index is not None and 1 <= index <= len(notes):
        del notes[index - 1]

    # 🔍 Delete by keyword
    elif keyword:
        notes = [note for note in notes if keyword.lower() not in note['content'].lower()]

    else:
        return False  # ❌ No valid deletion condition

    # 💾 Save updated notes
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False)

    return len(notes) < original_count  # ✅ True if deletion happened

# 🚫 Delete all notes
def clear_all_notes():
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2, ensure_ascii=False)

# 🔍 Search notes by keyword
def search_notes(keyword):
    if not keyword:
        return []

    notes = load_notes()
    return [note for note in notes if keyword.lower() in note["content"].lower()]

# 🖨️ Print all notes with indexes to terminal (for user reference)
def print_all_notes():
    notes = load_notes()
    if not notes:
        print("📝 No notes found.")
        return

    print("\n📒 Saved Notes:")
    for i, note in enumerate(notes, 1):
        print(f"{i}. [{note['timestamp']}] {note['content']}")

# ✏️ Update a specific note by index
def update_note(index, new_content):
    if not os.path.exists(NOTES_FILE):
        return False

    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        notes = json.load(f)

    if 1 <= index <= len(notes):
        notes[index - 1]["content"] = new_content
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)
        return True
    return False
