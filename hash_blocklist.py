# hash_blocklist.py
# Reads a private word list, canonicalizes each token, and prints SHA-256 hashes (one per line).
# Keep this canonicalization EXACTLY in sync with main.py:_canonicalize_for_hash()

import sys
import re
import hashlib
import unicodedata

# Leetspeak normalization
LEET = str.maketrans({
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
    "$": "s",
    "@": "a",
})

# Collapse all vowels to 'a' so laude/laudi/lauda -> laada
VOWEL_CLASS = str.maketrans({"a": "a", "e": "a", "i": "a", "o": "a", "u": "a"})

# Tokenizer: split on spaces, hyphens, Unicode dashes, straight/curly apostrophes
TOKEN_SPLIT_RE = re.compile(r"[ \-\u2010-\u2015'’]+")

def strip_diacritics(s: str) -> str:
    # NFKD + remove combining marks
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

def collapse_repeats(s: str) -> str:
    # Reduce aaa → a, etc.
    out = []
    prev = None
    for ch in s:
        if ch != prev:
            out.append(ch)
            prev = ch
    return "".join(out)

def canon(token: str) -> str:
    """
    MUST MATCH main.py:_canonicalize_for_hash.
    Steps:
      - casefold+strip
      - keep letters only (across scripts)
      - leet map (4->a, 1->i, etc.)
      - strip diacritics
      - collapse repeats (lawwwda -> lawda)
      - family normalization:
          w -> u            (lawda ≈ lauda/laudi/laude)
          vowels -> 'a'     (laude/laudi/lauda -> laada)
          'dh' -> 'd'       (chodh -> chod)
    """
    t = (token or "").casefold().strip()
    # keep letters only; drop digits/punct so "l4wd@" -> "lwd"
    t = "".join(ch for ch in t if ch.isalpha())
    if not t:
        return ""

    t = t.translate(LEET)
    t = strip_diacritics(t)
    t = collapse_repeats(t)

    # Family normalization (GLOBAL; applies to every token)
    t = t.replace("w", "u")
    t = t.translate(VOWEL_CLASS)
    t = t.replace("dh", "d")

    return t

def main(path: str):
    seen_hashes = set()

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            # Strip comments and whitespace
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue

            # Split into tokens and process each
            tokens = [t for t in TOKEN_SPLIT_RE.split(line) if t]
            for tok in tokens:
                c = canon(tok)
                if not c:
                    continue
                h = hashlib.sha256(c.encode("utf-8")).hexdigest()
                if h not in seen_hashes:
                    seen_hashes.add(h)

    # Deterministic output
    for h in sorted(seen_hashes):
        print(h)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python hash_blocklist.py <path-to-private_slurs.txt>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
