# 📂 handlers/news_handler.py — prompt-free, data-only fetcher (no TTS/UI)

from __future__ import annotations

import os
import requests
from typing import List, Optional, Tuple, Any

# 🚀 Load env (dev/BYO fallback; main may already call load_dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()
BASE_TOP = "https://newsapi.org/v2/top-headlines"
TIMEOUT_S = 12


# ─────────────────────────────────────────────────────────────────────────────
# Internal utils (lazy imports; data-only ⇒ no speaking here)
def _lazy_utils():
    try:
        from utils import logger, selected_language
        return logger, selected_language
    except Exception:
        class _Null:
            def info(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def error(self, *a, **k): pass
        return _Null(), "en"


def _ui_lang() -> str:
    _, selected_language = _lazy_utils()
    return (selected_language or "en").split("-")[0].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Managed Relay helpers (reads settings written on first run)
def _relay_conf() -> Tuple[bool, str, str]:
    """
    Reads Managed Services settings from generated settings.json:
      - use_managed_services: bool
      - relay_base_url: str
      - relay_token: str
    """
    try:
        from utils import load_settings
        s = load_settings()
    except Exception:
        s = {}
    base = (s.get("relay_base_url") or "").rstrip("/")
    token = s.get("relay_token") or ""
    use = bool(s.get("use_managed_services")) and bool(base)
    return use, base, token


def _relay_get(path: str, params: dict, timeout: float = TIMEOUT_S) -> Optional[Any]:
    """
    Calls the relay if enabled. Returns parsed JSON (dict/list) or None on any error.
    Accepted params:
      - topic: str (optional)
      - lang:  str (optional, e.g., "en")
      - country: str (optional, e.g., "in")
      - count: int (optional)
    """
    use, base, token = _relay_conf()
    if not use or not base:
        return None
    try:
        r = requests.get(
            f"{base}{path}",
            params=params,
            headers=({"X-Nova-Key": token} if token else {}),
            timeout=timeout,
        )
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def _extract_titles(obj: Any) -> List[str]:
    """
    Normalizes various response shapes into a list of headline strings.
    Supports:
      - {"articles": [{"title": ...}, ...]}
      - [{"title": ...}, ...]
      - ["headline 1", "headline 2", ...]
    """
    if obj is None:
        return []
    if isinstance(obj, dict):
        arts = obj.get("articles") or []
        if isinstance(arts, list):
            out = []
            for a in arts:
                if isinstance(a, dict):
                    t = a.get("title")
                    if t:
                        out.append(t)
            return out
        return []
    if isinstance(obj, list):
        out = []
        for a in obj:
            if isinstance(a, dict):
                t = a.get("title")
                if t:
                    out.append(t)
            elif isinstance(a, str):
                out.append(a)
        return out
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Direct NewsAPI path (BYO key fallback)
def _api_get(params: dict) -> Optional[dict]:
    """
    Direct NewsAPI request with basic error handling.
    Used when relay is off/unavailable.
    """
    logger, _ = _lazy_utils()
    if not NEWS_API_KEY:
        logger.warning("NEWS_API_KEY not set; direct NewsAPI path disabled.")
        return None
    try:
        params = {**params, "apiKey": NEWS_API_KEY}
        resp = requests.get(BASE_TOP, params=params, timeout=TIMEOUT_S)
        data = resp.json()
        if data.get("status") != "ok":
            logger.warning(f"NewsAPI error: {data}")
            return None
        return data
    except Exception as e:
        logger.error(f"NewsAPI fetch crashed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers (data-only; no side effects)
def fetch_top_headlines(country: str = "in", count: int = 5) -> List[str]:
    """
    Generic top headlines by country.
    Tries relay first, then falls back to direct NewsAPI (BYO key).
    """
    logger, _ = _lazy_utils()
    count = max(1, min(count, 20))
    # 1) Relay (language derived from UI where it helps your server)
    rel = _relay_get("/news", {
        "topic": "",
        "country": country,
        "lang": _ui_lang(),
        "count": count,
    })
    titles = _extract_titles(rel)
    if titles:
        logger.info(f"[news] relay top {len(titles)}")
        return titles[:count]

    # 2) Direct NewsAPI fallback
    data = _api_get({"country": country, "pageSize": count})
    if not data:
        logger.warning("[news] direct fallback returned no data")
        return []
    titles = _extract_titles(data)[:count]
    logger.info(f"[news] direct top {len(titles)}")
    return titles


def fetch_topic_headlines(topic: str, country: Optional[str] = "in", count: int = 5) -> List[str]:
    """
    Headlines filtered by topic (q) and optional country.
    Tries relay first, then falls back to direct NewsAPI (BYO key).
    """
    logger, _ = _lazy_utils()
    topic = (topic or "").strip()
    count = max(1, min(count, 20))

    # 1) Relay
    rel = _relay_get("/news", {
        "topic": topic,
        "country": country or "",
        "lang": _ui_lang(),
        "count": count,
    })
    titles = _extract_titles(rel)
    if titles:
        logger.info(f"[news] relay topic '{topic}' {len(titles)}")
        return titles[:count]

    # 2) Direct NewsAPI fallback
    params = {"q": topic, "pageSize": count}
    if country:
        params["country"] = country
    data = _api_get(params)
    if not data:
        logger.warning(f"[news] direct topic '{topic}' returned no data")
        return []
    titles = _extract_titles(data)
    if not titles and country:
        # Graceful fallback to generic
        logger.info(f"[news] topic empty; falling back to generic for country={country}")
        return fetch_top_headlines(country=country, count=count)
    logger.info(f"[news] direct topic '{topic}' {len(titles)}")
    return titles[:count]


# ─────────────────────────────────────────────────────────────────────────────
# Public API (used by commands layer). No follow-ups; returns data only.
def get_headlines(topic: Optional[str] = None,
                  country: str = "in",
                  count: int = 5) -> List[str]:
    """
    Fetch headlines. If `topic` is empty → generic by country.
    If `topic` provided → topic headlines (falls back to generic if empty).
    Returns the list of headline strings. (No speaking here.)
    """
    topic = (topic or "").strip()
    if topic:
        return fetch_topic_headlines(topic=topic, country=country, count=count)
    return fetch_top_headlines(country=country, count=count)
