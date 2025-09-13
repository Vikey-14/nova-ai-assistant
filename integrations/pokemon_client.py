# integrations/pokemon_client.py
"""
Nova ⇄ FastAPI Pokémon client (cross-platform).

- Loads config from <nova_root>/settings.json (pathlib, OS-safe)
- Optional ENV overrides:
    POKEMON_API_BASE_URL / POKEMON_API_USERNAME / POKEMON_API_PASSWORD
    POKEMON_API_SECURE_UPLOAD_KEY
- Caches JWT token (thread-safe), auto re-login / refresh on 401
- Uses requests.Session for keep-alive + timeouts
- JSON requests + multipart (image/CSV) uploads + binary download helpers
- Gentle retry/backoff on 429 (rate-limited)
- Includes Pokémon CRUD, Team, Trainer, Gallery, and Download helpers

Exported bits you might use from handlers:
- list_pokemon(), add_pokemon(), update_pokemon(), delete_pokemon(), get_pokemon()
- upload_image(), upload_images_bulk(), upload_image_secure()
- gallery_url(), image_download_url(), download_image()
- download_battle_log(), download_file()
- upload_csv()
- get_team(), add_to_team(), remove_from_team(), team_upgrade(), team_average_level()
- get_trainer_profile(), trainer_update()
- Compatibility wrappers used by handlers:
    upload_image_single(), upload_images_multi(), get_gallery_url(),
    team_list(), team_add(), team_remove(), team_upgrade(), team_average_level(),
    trainer_me(), trainer_update()

Also exposes: BASE_URL, _settings
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Optional, Any, Iterable

import requests
from utils import logger  # ensure utils.logger exists


# ──────────────────────────────────────────────────────────────────────────────
# Config loading (pathlib; robust across Windows/macOS/Linux)
# ──────────────────────────────────────────────────────────────────────────────

SETTINGS_PATH = (Path(__file__).resolve().parent.parent / "settings.json")


def _load_settings() -> dict[str, Any]:
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(
            f"[pokemon_client] settings.json not found at {SETTINGS_PATH} — using defaults/env."
        )
        return {}
    except Exception as e:
        logger.error(f"[pokemon_client] Failed to read settings.json: {e}")
        return {}


_settings = _load_settings()
_cfg = _settings.get("pokemon_api", {}) if isinstance(_settings, dict) else {}

# Allow environment overrides (useful on mac/Linux packagers)
BASE_URL = os.getenv("POKEMON_API_BASE_URL", _cfg.get("base_url", "http://127.0.0.1:8000")).rstrip("/")
USERNAME = os.getenv("POKEMON_API_USERNAME", _cfg.get("username", "professoroak"))
PASSWORD = os.getenv("POKEMON_API_PASSWORD", _cfg.get("password", "pallet123"))
SECURE_UPLOAD_API_KEY = _cfg.get("secure_upload_api_key") or os.getenv("POKEMON_API_SECURE_UPLOAD_KEY", "")

# NOTE: kept for backward-compat with old handlers; GUI now shows a clickable link instead of auto-opening.
IMAGE_OPEN_AFTER_UPLOAD = bool(_cfg.get("image_open_after_upload", True))

# Optional refresh-token toggle (if your API supports it)
USE_REFRESH_TOKEN = bool(_cfg.get("use_refresh_token", True))


# ──────────────────────────────────────────────────────────────────────────────
# HTTP session / auth
# ──────────────────────────────────────────────────────────────────────────────

_SESSION = requests.Session()
_TOKEN: Optional[str] = None
_TOK_LOCK = threading.Lock()
_LAST_LOGIN = 0.0
_TOKEN_TTL_SECONDS = 50 * 60  # refresh token every ~50 minutes by default
_TIMEOUT = (5, 20)            # (connect, read) seconds for JSON endpoints
_UPLOAD_TIMEOUT = (10, 60)    # slightly higher for multipart uploads


def _login() -> str:
    """Login (thread-safe) and cache JWT token."""
    global _TOKEN, _LAST_LOGIN
    with _TOK_LOCK:
        if _TOKEN and (time.time() - _LAST_LOGIN) < _TOKEN_TTL_SECONDS:
            return _TOKEN
        url = f"{BASE_URL}/auth/login"
        payload = {"username": USERNAME, "password": PASSWORD}
        logger.info(f"[pokemon_client] Logging in to {url} as '{USERNAME}'")
        r = _SESSION.post(url, json=payload, timeout=_TIMEOUT)
        _raise_for_status_with_detail(r, url)
        data = r.json() if r.content else {}
        tok = data.get("access_token") or data.get("token")
        if not tok:
            raise RuntimeError("Login succeeded but no token found in response.")
        _TOKEN = tok
        _LAST_LOGIN = time.time()
        return _TOKEN


def _refresh_token() -> str:
    """
    Try to refresh the token (if server supports /auth/refresh-token).
    Falls back to a full login() if refresh is unavailable/fails.
    """
    global _TOKEN, _LAST_LOGIN
    with _TOK_LOCK:
        try:
            if not _TOKEN:
                return _login()
            url = f"{BASE_URL}/auth/refresh-token"
            logger.info("[pokemon_client] Attempting token refresh …")
            r = _SESSION.post(url, headers={"Authorization": f"Bearer {_TOKEN}"}, timeout=_TIMEOUT)
            if r.status_code >= 400:
                # Some servers may return 404/405 if refresh isn't exposed.
                logger.warning(f"[pokemon_client] Refresh-token failed ({r.status_code}); falling back to login.")
                _LAST_LOGIN = 0.0
                return _login()
            data = r.json() if r.content else {}
            tok = data.get("access_token") or data.get("token")
            if not tok:
                logger.warning("[pokemon_client] Refresh returned no token; logging in.")
                _LAST_LOGIN = 0.0
                return _login()
            _TOKEN = tok
            _LAST_LOGIN = time.time()
            return _TOKEN
        except Exception as e:
            logger.warning(f"[pokemon_client] Refresh-token error: {e}; logging in.")
            _LAST_LOGIN = 0.0
            return _login()


def _auth_header() -> dict[str, str]:
    tok = _login()
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def _retry_after_delay(resp: requests.Response, *, attempt: int = 0) -> float:
    """
    Parse Retry-After (seconds) if present; otherwise exponential backoff
    based on attempt count. Clamp to a polite upper bound.
    """
    try:
        if "Retry-After" in resp.headers:
            delay = float(resp.headers["Retry-After"])
        else:
            delay = 1.0 * (2 ** attempt)
    except Exception:
        delay = 1.0
    return max(0.5, min(delay, 10.0))


def _extract_detail(resp: requests.Response) -> str:
    """
    Pull a concise error detail from JSON or text.
    """
    try:
        js = resp.json()
        if isinstance(js, dict):
            # Common FastAPI patterns
            for key in ("detail", "message", "error"):
                if key in js:
                    return str(js[key])
            # Validation errors
            if "errors" in js:
                return str(js["errors"])
        return resp.text.strip()[:500]
    except Exception:
        return resp.text.strip()[:500]


def _raise_for_status_with_detail(resp: requests.Response, url: str) -> None:
    """
    Like raise_for_status(), but includes server-provided 'detail' if available.
    """
    if resp.ok:
        return
    detail = _extract_detail(resp)
    msg = f"HTTP {resp.status_code} for {url}"
    if detail:
        msg += f" — {detail}"
    raise requests.HTTPError(msg, response=resp, request=resp.request)


# ──────────────────────────────────────────────────────────────────────────────
# Core request helpers (JSON / multipart / binary)
# ──────────────────────────────────────────────────────────────────────────────

def _request(method: str, path: str, *, json_body: Any | None = None) -> Any:
    """
    Internal JSON request wrapper with auth, timeouts,
    one retry on 401 (refresh/login) and one retry on 429 (backoff).
    """
    url = f"{BASE_URL}{path}"
    headers = _auth_header()

    # First attempt
    r = _SESSION.request(method, url, headers=headers, json=json_body, timeout=_TIMEOUT)

    # 401 → attempt refresh/login then retry once
    if r.status_code == 401:
        logger.info("[pokemon_client] 401 received; refreshing token and retrying once.")
        _refresh_token() if USE_REFRESH_TOKEN else _login()
        headers = _auth_header()
        r = _SESSION.request(method, url, headers=headers, json=json_body, timeout=_TIMEOUT)

    # 429 → gentle backoff then retry once
    if r.status_code == 429:
        delay = _retry_after_delay(r, attempt=1)
        logger.warning(f"[pokemon_client] 429 rate-limited; retrying after {delay}s")
        time.sleep(delay)
        r = _SESSION.request(method, url, headers=headers, json=json_body, timeout=_TIMEOUT)

    _raise_for_status_with_detail(r, url)
    return r.json() if r.content else None


def _rewind_files(files: Any) -> None:
    """
    Best-effort: rewind file-like streams before a retry.
    Supports dict {"file": (name, fh, mime)} or list of tuples for bulk uploads.
    """
    try:
        if isinstance(files, dict):
            for _, tup in files.items():
                if isinstance(tup, (tuple, list)) and len(tup) >= 2:
                    fh = tup[1]
                    try:
                        fh.seek(0)
                    except Exception:
                        pass
        elif isinstance(files, list):
            for entry in files:
                if isinstance(entry, (tuple, list)) and len(entry) >= 2:
                    tup = entry[1]
                    if isinstance(tup, (tuple, list)) and len(tup) >= 2:
                        fh = tup[1]
                        try:
                            fh.seek(0)
                        except Exception:
                            pass
    except Exception:
        pass


def _request_files(
    path: str,
    files: Any,
    extra_headers: Optional[dict[str, str]] = None,
    method: str = "POST",
) -> Any:
    """
    Multipart upload with auth and one retry on 401 and 429.
    `files` can be a dict (single) or list of tuples for bulk.
    """
    url = f"{BASE_URL}{path}"
    headers = _auth_header()
    if extra_headers:
        headers.update(extra_headers)

    # First attempt
    r = _SESSION.request(method, url, headers=headers, files=files, timeout=_UPLOAD_TIMEOUT)

    # 401 → refresh/login then retry once
    if r.status_code == 401:
        logger.info("[pokemon_client] 401 on upload; refreshing token and retrying once.")
        _refresh_token() if USE_REFRESH_TOKEN else _login()
        headers = _auth_header()
        if extra_headers:
            headers.update(extra_headers)
        _rewind_files(files)
        r = _SESSION.request(method, url, headers=headers, files=files, timeout=_UPLOAD_TIMEOUT)

    # 429 → gentle backoff then retry once
    if r.status_code == 429:
        delay = _retry_after_delay(r, attempt=1)
        logger.warning(f"[pokemon_client] 429 on upload; retrying after {delay}s")
        time.sleep(delay)
        _rewind_files(files)
        r = _SESSION.request(method, url, headers=headers, files=files, timeout=_UPLOAD_TIMEOUT)

    _raise_for_status_with_detail(r, url)
    return r.json() if r.content else None


def _request_binary(path: str) -> bytes:
    """
    Simple binary GET with 401/429 retry. Returns raw bytes.
    """
    url = f"{BASE_URL}{path}"
    headers = _auth_header()

    # First attempt
    r = _SESSION.get(url, headers=headers, timeout=_TIMEOUT)

    # 401 → refresh/login then retry once
    if r.status_code == 401:
        logger.info("[pokemon_client] 401 on binary GET; refreshing token and retrying once.")
        _refresh_token() if USE_REFRESH_TOKEN else _login()
        headers = _auth_header()
        r = _SESSION.get(url, headers=headers, timeout=_TIMEOUT)

    # 429 → gentle backoff then retry once
    if r.status_code == 429:
        delay = _retry_after_delay(r, attempt=1)
        logger.warning(f"[pokemon_client] 429 on binary GET; retrying after {delay}s")
        time.sleep(delay)
        r = _SESSION.get(url, headers=headers, timeout=_TIMEOUT)

    _raise_for_status_with_detail(r, url)
    return r.content


# ──────────────────────────────────────────────────────────────────────────────
# Pokémon CRUD
# ──────────────────────────────────────────────────────────────────────────────

def list_pokemon():
    """GET /pokemon → list of Pokémon entries."""
    return _request("GET", "/pokemon")


def get_pokemon(pid: int):
    """
    Try GET /pokemon/{id}. If your API doesn't expose it, fall back to list() and filter.
    """
    try:
        return _request("GET", f"/pokemon/{int(pid)}")
    except Exception:
        rows = list_pokemon() or []
        for r in rows:
            try:
                if int(r.get("id")) == int(pid):
                    return r
            except Exception:
                continue
        return None


def add_pokemon(poke_name: str, level: int, ptype: str, nickname: Optional[str] = None):
    """
    POST /pokemon → create Pokémon (admin required).
    Body: { poke_name, level, ptype, nickname? }
    """
    payload = {"poke_name": poke_name, "level": int(level), "ptype": ptype}
    if nickname:
        payload["nickname"] = nickname
    return _request("POST", "/pokemon", json_body=payload)


def update_pokemon(
    pid: int,
    level: Optional[int] = None,
    ptype: Optional[str] = None,
    nickname: Optional[str] = None,
):
    """
    PATCH /pokemon/{id} → update fields (admin required).
    Body: subset of { level, ptype, nickname }
    """
    payload: dict[str, Any] = {}
    if level is not None:
        payload["level"] = int(level)
    if ptype:
        payload["ptype"] = ptype
    if nickname is not None:
        payload["nickname"] = nickname
    return _request("PATCH", f"/pokemon/{int(pid)}", json_body=payload)


def delete_pokemon(pid: int):
    """DELETE /pokemon/{id} (admin required)."""
    return _request("DELETE", f"/pokemon/{int(pid)}")


# ──────────────────────────────────────────────────────────────────────────────
# Image upload(s) + gallery helpers
# ──────────────────────────────────────────────────────────────────────────────

def upload_image(file_path: str, override_filename: Optional[str] = None):
    """
    POST /upload/image → returns {"message","filename","size","type"} (per server).
    """
    file_path = str(file_path)
    fn = override_filename or os.path.basename(file_path)
    with open(file_path, "rb") as fh:
        files = {"file": (fn, fh, None)}
        return _request_files("/upload/image", files)


def upload_images_bulk(file_paths: Iterable[str]):
    """
    POST /upload/images → bulk upload. Server typically returns a summary.
    """
    file_paths = [str(p) for p in file_paths]
    files = []
    fhs = []
    try:
        for p in file_paths:
            fh = open(p, "rb")
            fhs.append(fh)
            files.append(("files", (os.path.basename(p), fh, None)))
        return _request_files("/upload/images", files)
    finally:
        for fh in fhs:
            try:
                fh.close()
            except Exception:
                pass


def upload_image_secure(file_path: str, override_filename: Optional[str] = None):
    """
    POST /upload/secure-image with X-Api-Key (if configured).
    """
    if not SECURE_UPLOAD_API_KEY:
        raise RuntimeError("secure_upload_api_key not configured in settings.json or env.")
    file_path = str(file_path)
    fn = override_filename or os.path.basename(file_path)
    with open(file_path, "rb") as fh:
        files = {"file": (fn, fh, None)}
        extra = {"X-Api-Key": SECURE_UPLOAD_API_KEY}
        return _request_files("/upload/secure-image", files, extra_headers=extra)


def gallery_url() -> str:
    """Return the /gallery URL (for opening in a browser)."""
    return f"{BASE_URL}/gallery"


def image_download_url(filename: str) -> str:
    """Direct URL to download a saved image by filename."""
    safe = str(filename).lstrip("/").replace("\\", "/")
    return f"{BASE_URL}/download/image/{safe}"


def download_image(filename: str) -> bytes:
    """
    GET /download/image/{filename} and return raw bytes (you can save to disk).
    """
    safe = str(filename).lstrip("/").replace("\\", "/")
    return _request_binary(f"/download/image/{safe}")


# NEW: generic file download (CSV/log/etc.)
def download_file(filename: str) -> bytes:
    """
    GET /download/{filename} and return raw bytes (CSV, logs, etc.).
    """
    safe = str(filename).lstrip("/").replace("\\", "/")
    return _request_binary(f"/download/{safe}")


# NEW: battle log download helper
def download_battle_log() -> bytes:
    """
    GET /download/log and return raw bytes of the battle log text file.
    """
    return _request_binary("/download/log")


# ──────────────────────────────────────────────────────────────────────────────
# Team helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_team():
    """GET /team → list of team entries."""
    return _request("GET", "/team")


def add_to_team(pid: int):
    """POST /team { id } → add a Pokémon to team."""
    return _request("POST", "/team", json_body={"id": int(pid)})


def remove_from_team(pid: int):
    """DELETE /team/{id} → remove Pokémon from team."""
    return _request("DELETE", f"/team/{int(pid)}")


def team_upgrade(pid: int, level: int):
    """PATCH /team/{id} → set a team member's level."""
    return _request("PATCH", f"/team/{int(pid)}", json_body={"level": int(level)})


def team_average_level():
    """
    Try GET /team/average-level; if not present, compute client-side average.
    """
    try:
        data = _request("GET", "/team/average-level")
        if isinstance(data, dict) and "average_level" in data:
            return data
    except Exception:
        pass
    team = get_team() or []
    levels = [int(t.get("level", 0) or 0) for t in team if isinstance(t, dict)]
    avg = round(sum(levels) / len(levels), 2) if levels else 0.0
    return {"average_level": avg}


# ──────────────────────────────────────────────────────────────────────────────
# Trainer profile
# ──────────────────────────────────────────────────────────────────────────────

def get_trainer_profile():
    """GET /trainer/profile → dict with trainer info (depends on your API)."""
    return _request("GET", "/trainer/profile")


def trainer_update(
    *,
    nickname: Optional[str] = None,
    location: Optional[str] = None,
    pronouns: Optional[str] = None,
):
    """
    PATCH /trainer/profile → update any subset of nickname/location/pronouns.
    """
    payload: dict[str, Any] = {}
    if nickname is not None:
        payload["nickname"] = nickname
    if location is not None:
        payload["location"] = location
    if pronouns is not None:
        payload["pronouns"] = pronouns
    if not payload:
        return {"Message": "No changes."}
    return _request("PATCH", "/trainer/profile", json_body=payload)


# ──────────────────────────────────────────────────────────────────────────────
# CSV upload (server-side) — optional parity with API
# ──────────────────────────────────────────────────────────────────────────────

def upload_csv(csv_path: str, validated: bool = False) -> Any:
    """
    POST /upload/csv or /upload/csv/validated with a CSV file.
    Returns server JSON response.
    """
    route = "/upload/csv/validated" if validated else "/upload/csv"
    csv_path = str(csv_path)
    with open(csv_path, "rb") as fh:
        files = {"file": (os.path.basename(csv_path), fh, "text/csv")}
        return _request_files(route, files, method="POST")


# ──────────────────────────────────────────────────────────────────────────────
# Compatibility aliases (exact names your handler imports)
# ──────────────────────────────────────────────────────────────────────────────

# Images
def upload_image_single(file_path: str, override_filename: Optional[str] = None, secure: bool = False):
    """
    Wrapper: handler calls this. Uses secure endpoint only if secure=True and key is set.
    """
    if secure and SECURE_UPLOAD_API_KEY:
        return upload_image_secure(file_path, override_filename)
    return upload_image(file_path, override_filename)


def upload_images_multi(file_paths: list[str], secure: bool = False):
    """
    Wrapper: handler calls this. If secure=True (and key available), loop single-secure uploads.
    """
    if secure and SECURE_UPLOAD_API_KEY:
        results = []
        for p in file_paths:
            results.append(upload_image_secure(p))
        return {"uploaded": len(results), "results": results}
    return upload_images_bulk(file_paths)


def get_gallery_url() -> str:
    return gallery_url()


# Team
def team_list():
    return get_team()


def team_add(pid: int):
    return add_to_team(pid)


def team_remove(pid: int):
    return remove_from_team(pid)


# Note: team_upgrade and team_average_level already defined with matching names.

# Trainer
def trainer_me():
    return get_trainer_profile()

# trainer_update already defined above with the same name.
