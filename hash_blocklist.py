# hash_blocklist.py
# Reads a private word list, canonicalizes each token, and prints SHA-256 hashes (one per line).

import sys, re, hashlib, unicodedata

LEET = str.maketrans({"0":"o","1":"i","3":"e","4":"a","5":"s","7":"t","$":"s","@":"a"})

def strip_diacritics(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

def collapse_repeats(s: str) -> str:
    out = []
    prev = None
    for ch in s:
        if ch != prev:
            out.append(ch)
            prev = ch
    return "".join(out)

def canon(token: str) -> str:
    t = (token or "").casefold().strip()
    t = "".join(ch for ch in t if ch.isalpha())
    t = t.translate(LEET)
    t = strip_diacritics(t)
    t = collapse_repeats(t)
    return t

def main(path: str):
    seen = set()
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            tokens = [t for t in re.split(r"[ \-\u2010-\u2015'’]+", line) if t]
            for tok in tokens:
                c = canon(tok)
                if not c:
                    continue
                h = hashlib.sha256(c.encode("utf-8")).hexdigest()
                if h not in seen:
                    seen.add(h)
    for h in sorted(seen):
        print(h)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python hash_blocklist.py <path-to-private_slurs.txt>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
