# memory_handler.py
from __future__ import annotations

import json
import os
import io
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Use utils helpers so paths/logs work in dev + PyInstaller
from utils import pkg_path, logger
from platform_adapter import get_backend
_backend = get_backend()

# ------------------------------------------------------------------------------
# Paths (stable per-user dir, with one-time migration from legacy bundle dir)
# ------------------------------------------------------------------------------
# Legacy location (inside app/repo bundle) that caused the issue:
LEGACY_DATA_DIR: Path = pkg_path("data")

# New stable per-user location (never bundled into the exe):
DATA_DIR: Path = (_backend.user_data_dir() / "data").resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

MEMORY_PATH: Path = DATA_DIR / "memory.json"
NOTES_PATH:  Path = DATA_DIR / "notes.json"

# One-time migration from legacy to per-user (copy only if new files don't exist)
try:
    legacy_memory = LEGACY_DATA_DIR / "memory.json"
    legacy_notes  = LEGACY_DATA_DIR / "notes.json"
    if legacy_memory.exists() and not MEMORY_PATH.exists():
        shutil.copy2(legacy_memory, MEMORY_PATH)
        logger.info("Migrated legacy memory.json to user data dir")
    if legacy_notes.exists() and not NOTES_PATH.exists():
        shutil.copy2(legacy_notes, NOTES_PATH)
        logger.info("Migrated legacy notes.json to user data dir")
except Exception as e:
    try:
        logger.error(f"Memory migration skipped: {e}")
    except Exception:
        pass

# Single process-wide lock to protect JSON read/writes
_LOCK = threading.Lock()

# ------------------------------------------------------------------------------
# Low-level JSON helpers (safe + atomic with fsync)
# ------------------------------------------------------------------------------
def _atomic_dump_json(path: Path, obj: Any) -> None:
    """
    Write JSON atomically to avoid corruption (TMP -> flush -> fsync -> replace).
    Guaranteed to be durable on disk when this function returns.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create a temp file in the same directory so os.replace is atomic
    fd, tmp_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        # Write JSON and force it to disk
        with io.open(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        # Atomic swap
        os.replace(tmp_path, path)
    finally:
        # If anything went wrong before replace, clean up the temp file
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def _load_json_or_default(path: Path, default: Any) -> Any:
    """
    Read JSON safely. If missing or invalid, return default.
    """
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[memory_handler] Failed to read {path.name}: {e} — using default")
        return default


def _ensure_files():
    """
    Ensure memory.json and notes.json exist (with sane defaults).
    """
    with _LOCK:
        if not MEMORY_PATH.exists():
            _atomic_dump_json(MEMORY_PATH, {})
            logger.info("🧠 Created new memory.json")
        if not NOTES_PATH.exists():
            _atomic_dump_json(NOTES_PATH, [])
            logger.info("🗒️  Created new notes.json")

# ------------------------------------------------------------------------------
# Public API — Memory (key/value)
# ------------------------------------------------------------------------------
def init_memory() -> None:
    _ensure_files()


def save_to_memory(key: str, value: Any) -> None:
    """
    Synchronous, atomic save. When this returns, the data is durably on disk.
    """
    _ensure_files()
    with _LOCK:
        data: Dict[str, Any] = _load_json_or_default(MEMORY_PATH, {})
        data[key] = value
        _atomic_dump_json(MEMORY_PATH, data)

    # Optional: mirror specific keys (like language) into settings.json as well
    # so other subsystems that read settings stay in sync.
    if key == "language":
        try:
            import utils  # local import to avoid circulars at module import time
            s = utils.load_settings()
            s["language"] = str(value).lower()
            utils.save_settings(s)  # utils should also write synchronously/atomically
        except Exception as e:
            logger.warning(f"[memory_handler] Failed to mirror 'language' into settings: {e}")

    logger.info(f"💾 Saved to memory: {key} = {value}")


def load_from_memory(key: str) -> Any:
    _ensure_files()
    with _LOCK:
        data: Dict[str, Any] = _load_json_or_default(MEMORY_PATH, {})
        value = data.get(key)
    logger.info(f"🔎 Loaded from memory: {key} = {value}")
    return value


def clear_memory(key: Optional[str] = None) -> None:
    _ensure_files()
    with _LOCK:
        data: Dict[str, Any] = _load_json_or_default(MEMORY_PATH, {})
        if key is None:
            data.clear()
            logger.info("🧹 Cleared entire memory")
        else:
            removed = data.pop(key, None)
            logger.info(f"🧹 Cleared memory key: {key} — Found: {removed is not None}")
        _atomic_dump_json(MEMORY_PATH, data)

# ------------------------------------------------------------------------------
# Public API — Notes (list of {timestamp, content})
# ------------------------------------------------------------------------------
def save_note(content: str) -> None:
    _ensure_files()
    with _LOCK:
        notes: List[Dict[str, str]] = _load_json_or_default(NOTES_PATH, [])
        notes.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "content": content
        })
        _atomic_dump_json(NOTES_PATH, notes)
    logger.info(f"📝 Saved new note: {content}")


def load_notes() -> List[Dict[str, str]]:
    _ensure_files()
    with _LOCK:
        notes: List[Dict[str, str]] = _load_json_or_default(NOTES_PATH, [])
    logger.info(f"📖 Loaded {len(notes)} notes")
    return notes


def delete_specific_note(index: Optional[int] = None, keyword: Optional[str] = None) -> bool:
    _ensure_files()
    with _LOCK:
        notes: List[Dict[str, str]] = _load_json_or_default(NOTES_PATH, [])
        original_count = len(notes)
        success = False

        if index is not None and 1 <= index <= len(notes):
            del notes[index - 1]
            success = True
            logger.info(f"🗑️ Deleted note at index {index}")

        elif keyword:
            notes = [n for n in notes if keyword.lower() not in n.get("content", "").lower()]
            success = len(notes) < original_count
            logger.info(f"🗑️ Deleted notes matching keyword: {keyword}")

        if success:
            _atomic_dump_json(NOTES_PATH, notes)

    return success


def clear_all_notes() -> None:
    _ensure_files()
    with _LOCK:
        _atomic_dump_json(NOTES_PATH, [])
    logger.info("🗑️ Cleared all notes")


def search_notes(keyword: str) -> List[Dict[str, str]]:
    if not keyword:
        return []
    notes = load_notes()
    results = [n for n in notes if keyword.lower() in n.get("content", "").lower()]
    logger.info(f"🔍 Found {len(results)} matching notes for: {keyword}")
    return results


def update_note(index: int, new_content: str) -> bool:
    _ensure_files()
    with _LOCK:
        notes: List[Dict[str, str]] = _load_json_or_default(NOTES_PATH, [])
        if 1 <= index <= len(notes):
            old = notes[index - 1].get("content", "")
            notes[index - 1]["content"] = new_content
            _atomic_dump_json(NOTES_PATH, notes)
            logger.info(f"✏️ Updated note {index}: '{old}' → '{new_content}'")
            return True
        else:
            logger.warning(f"⚠️ Invalid note index: {index}")
            return False

# ------------------------------------------------------------------------------
# Optional helpers for dev/diagnostics
# ------------------------------------------------------------------------------
def print_all_notes() -> None:
    """
    Prints to stdout. In the frozen GUI build (console=False) this won’t be visible,
    but it’s handy during development.
    """
    notes = load_notes()
    if not notes:
        print("📝 No notes found.")
        return

    print("\n📒 Saved Notes:")
    for i, note in enumerate(notes, 1):
        print(f"{i}. [{note.get('timestamp','')}] {note.get('content','')}")


def read_notes() -> str:
    """
    Returns raw JSON text for quick inspection (dev helper).
    """
    _ensure_files()
    with _LOCK:
        if NOTES_PATH.exists():
            return NOTES_PATH.read_text(encoding="utf-8")
    return "No notes found."
