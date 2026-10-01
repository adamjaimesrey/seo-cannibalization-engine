"""Scan this folder for terms listed in .leakcheck-denylist.txt.

Exit codes: 0 clean, 1 hits found, 2 deny list missing/empty (never reports clean by default).
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DENYLIST = ROOT / ".leakcheck-denylist.txt"
SKIP_DIRS = {".git", ".venv"}
WHOLE_WORD_MAX_LEN = 5


def load_terms() -> list:
    if not DENYLIST.exists():
        print(f"ERROR: deny list not found: {DENYLIST.name}. Cannot certify clean.", file=sys.stderr)
        sys.exit(2)
    lines = DENYLIST.read_text(encoding="utf-8", errors="ignore").splitlines()
    terms = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    if not terms:
        print(f"ERROR: deny list is empty: {DENYLIST.name}. Cannot certify clean.", file=sys.stderr)
        sys.exit(2)
    return terms


def compile_term(term: str) -> re.Pattern:
    body = re.escape(term)
    if len(term) <= WHOLE_WORD_MAX_LEN:
        body = rf"\b{body}\b"
    return re.compile(body, re.IGNORECASE)


def iter_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            if path != DENYLIST:
                yield path


def main() -> None:
    patterns = [(t, compile_term(t)) for t in load_terms()]
    hits, scanned = 0, 0
    for path in iter_files():
        scanned += 1
        rel = path.relative_to(ROOT)
        for term, pat in patterns:
            if pat.search(str(rel)):
                print(f"{rel}:0:{term}")
                hits += 1
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            for term, pat in patterns:
                if pat.search(line):
                    print(f"{rel}:{lineno}:{term}")
                    hits += 1
    if scanned == 0:
        print("ERROR: no files scanned.", file=sys.stderr)
        sys.exit(2)
    if hits:
        print(f"{hits} hit(s) in {scanned} files scanned.", file=sys.stderr)
        sys.exit(1)
    print(f"Clean: 0 hits in {scanned} files scanned.")


if __name__ == "__main__":
    main()
