import csv
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

REPO = Path(__file__).resolve().parents[2]
CSV_PATH = REPO / 'data' / 'glossary_initial' / 'glossary_initial_v4.csv'
DOCS_CSV_PATH = REPO / 'docs' / 'glossary' / 'glossary_initial_v4.csv'
CORPUS_PATH = REPO / 'data' / 'talmud_full_english.txt'

APOSTROPHES = {
    "\u2019", "\u2018", "\u02BC", "\u02BB", "\u0060", "\u00B4", "\u2032",
}


def normalize_text(s: str) -> str:
    if not s:
        return ''
    for ch in APOSTROPHES:
        s = s.replace(ch, "'")
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.lower()


def tokenize(s: str):
    s = normalize_text(s)
    out, cur = [], []
    n = len(s)
    for i, ch in enumerate(s):
        if ch.isalnum():
            cur.append(ch)
            continue
        if ch == "'":
            prev_is_alnum = i > 0 and s[i - 1].isalnum()
            next_is_alnum = i + 1 < n and s[i + 1].isalnum()
            if prev_is_alnum and next_is_alnum:
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


def split_variants(s: str):
    if not s:
        return []
    return [v.strip() for v in s.split(';') if v.strip()]


def unique_preserve(items):
    seen = set()
    out = []
    for x in items:
        k = x.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out


def build_alias_phrase_counts(rows, corpus_tokens):
    needed_by_n = defaultdict(set)
    alias_token_map = {}

    for r in rows:
        aliases = unique_preserve([r.get('term', '').strip(), *split_variants(r.get('variant_names', ''))])
        for a in aliases:
            if not a:
                continue
            t = tokenize(a)
            if not t:
                continue
            alias_token_map[a] = t
            needed_by_n[len(t)].add(t)

    counts = defaultdict(int)
    N = len(corpus_tokens)
    for n in sorted(needed_by_n.keys()):
        needed = needed_by_n[n]
        if n > N:
            continue
        for i in range(0, N - n + 1):
            ng = tuple(corpus_tokens[i:i+n])
            if ng in needed:
                counts[ng] += 1

    alias_counts = {}
    for a, t in alias_token_map.items():
        alias_counts[a] = counts.get(t, 0)
    return alias_counts


def choose_canonical(aliases, alias_counts, current_term):
    # Highest corpus count wins. Tie-breakers: keep current term, then shortest alias.
    ranked = sorted(
        aliases,
        key=lambda a: (
            -(alias_counts.get(a, 0)),
            0 if a.lower() == current_term.lower() else 1,
            len(a),
            a.lower(),
        ),
    )
    return ranked[0] if ranked else current_term


def main():
    with CSV_PATH.open('r', encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise RuntimeError('No rows found.')

    corpus = CORPUS_PATH.read_text(encoding='utf-8', errors='replace')
    corpus_tokens = list(tokenize(corpus))

    alias_counts = build_alias_phrase_counts(rows, corpus_tokens)

    changed = 0
    for r in rows:
        term = (r.get('term') or '').strip()
        variants = split_variants(r.get('variant_names', ''))
        aliases = unique_preserve([term, *variants])
        if not aliases:
            continue

        new_term = choose_canonical(aliases, alias_counts, term)
        if new_term.lower() != term.lower():
            changed += 1

        new_variants = [a for a in aliases if a.lower() != new_term.lower()]
        new_variants = sorted(unique_preserve(new_variants), key=lambda x: x.lower())

        r['term'] = new_term
        r['variant_names'] = '; '.join(new_variants)
        r['chavrutai_search_url'] = 'https://chavrutai.com/search?q=' + quote(new_term, safe='')

        # Keep row count as combined alias frequency under current alias set.
        r['talmud_corpus_count'] = str(sum(alias_counts.get(a, 0) for a in aliases))

    fieldnames = list(rows[0].keys())
    for out_path in (CSV_PATH, DOCS_CSV_PATH):
        with out_path.open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    print(f'rows={len(rows)}')
    print(f'canonical_changed={changed}')


if __name__ == '__main__':
    main()
