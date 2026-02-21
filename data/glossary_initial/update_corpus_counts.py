import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CSV_PATH = REPO / 'data' / 'glossary_initial' / 'glossary_initial_v4.csv'
DOCS_CSV_PATH = REPO / 'docs' / 'glossary' / 'glossary_initial_v4.csv'
CORPUS_PATH = REPO / 'data' / 'talmud_full_english.txt'

APOSTROPHES = {
    "\u2019",  # right single quote
    "\u2018",  # left single quote
    "\u02BC",  # modifier letter apostrophe
    "\u02BB",  # turned comma
    "\u0060",  # grave
    "\u00B4",  # acute
    "\u2032",  # prime
}


def normalize_text(s: str) -> str:
    if not s:
        return ''
    # Canonicalize apostrophe-like characters first.
    for ch in APOSTROPHES:
        s = s.replace(ch, "'")
    # Strip diacritics so dotted transliteration letters match plain forms (e.g., h-dot -> h).
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    # Keep Unicode letters/digits; lowercase for case-insensitive matching.
    return s.lower()


def tokenize(s: str):
    s = normalize_text(s)
    out = []
    cur = []
    n = len(s)
    for i, ch in enumerate(s):
        if ch.isalnum():
            cur.append(ch)
            continue

        if ch == "'":
            prev_is_alnum = i > 0 and s[i - 1].isalnum()
            next_is_alnum = i + 1 < n and s[i + 1].isalnum()
            if prev_is_alnum and next_is_alnum:
                # Keep internal apostrophes in tokens (e.g., Yoḥanan's after normalization).
                cur.append(ch)
                continue

        if cur:
            tok = ''.join(cur).strip("'")
            if tok:
                out.append(tok)
            cur = []

    if cur:
        tok = ''.join(cur).strip("'")
        if tok:
            out.append(tok)

    return tuple(out)


def count_rows(rows, corpus_tokens):
    row_aliases = []
    needed_by_n = defaultdict(set)

    for r in rows:
        aliases = [r.get('term', '').strip()]
        variants = r.get('variant_names', '')
        if variants:
            aliases.extend(v.strip() for v in variants.split(';') if v.strip())

        aliases_t = set()
        for alias in aliases:
            t = tokenize(alias)
            if not t:
                continue
            aliases_t.add(t)
            needed_by_n[len(t)].add(t)

        row_aliases.append(aliases_t)

    counts = defaultdict(int)
    n_tokens = len(corpus_tokens)

    for n in sorted(needed_by_n):
        needed = needed_by_n[n]
        if n > n_tokens:
            continue
        for i in range(0, n_tokens - n + 1):
            ng = tuple(corpus_tokens[i:i + n])
            if ng in needed:
                counts[ng] += 1

    for r, aliases_t in zip(rows, row_aliases):
        r['talmud_corpus_count'] = str(sum(counts.get(a, 0) for a in aliases_t))


def main():
    with CSV_PATH.open('r', encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise RuntimeError('No rows found in glossary CSV.')

    fieldnames = list(rows[0].keys())
    if 'talmud_corpus_count' not in fieldnames:
        at = fieldnames.index('variant_names') + 1 if 'variant_names' in fieldnames else len(fieldnames)
        fieldnames.insert(at, 'talmud_corpus_count')

    corpus = CORPUS_PATH.read_text(encoding='utf-8', errors='replace')
    corpus_tokens = list(tokenize(corpus))

    count_rows(rows, corpus_tokens)

    for out_path in (CSV_PATH, DOCS_CSV_PATH):
        with out_path.open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    print(f'Updated {len(rows)} rows with talmud_corpus_count.')
    print(f'Wrote: {CSV_PATH}')
    print(f'Wrote: {DOCS_CSV_PATH}')


if __name__ == '__main__':
    main()
