"""
Build a concordance of Bible name entries from the Steinsaltz Talmud.
For each name in the gazetteer, find up to 5 Talmud sections that mention it.
Output as a human-readable HTML file, sorted alphabetically by name.
"""

import argparse
import csv
import re
import html
import sys
import time
from collections import defaultdict

# Increase CSV field size limit for large HTML fields
csv.field_size_limit(2**31 - 1)

GAZETTEER_PATH = "bible_names_gazetteer.txt"
CSV_PATH = "steinsaltz_talmud_combined_richHTML.csv"
OUTPUT_PATH = "bible_names_concordance.html"
MAX_RESULTS = 5


def load_names(path):
    """Load names from gazetteer, one per line, stripping whitespace."""
    names = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            name = line.strip()
            if name:
                names.append(name)
    return sorted(set(names), key=str.casefold)


def fix_diacritics(text):
    """Replace literal '?' used as placeholder for h-with-dot-below.
    Mid-word ? -> ḥ (lowercase), word-initial ? before lowercase -> Ḥ (uppercase)."""
    # Mid-word: letter?letter -> ḥ
    text = re.sub(r'(?<=[A-Za-z])\?(?=[A-Za-z])', '\u1E25', text)
    # Word-initial: ?followed by lowercase letter (e.g. ?iyya) -> Ḥ
    text = re.sub(r'(?<![A-Za-z])\?(?=[a-z])', '\u1E24', text)
    return text


def load_talmud_rows(path):
    """Load all Talmud rows as (location, text) tuples."""
    rows = []
    with open(path, "r", encoding="cp1252") as f:
        reader = csv.reader(f)
        header = next(reader)  # skip header
        for row in reader:
            if len(row) >= 2:
                rows.append((row[0], fix_diacritics(row[1])))
    return rows


def strip_html(text):
    """Remove HTML tags to get plain text for matching."""
    return re.sub(r"<[^>]+>", "", text)


def extract_bold_text(rich_text):
    """Extract only text inside <b>...</b> and <strong>...</strong> tags."""
    bold_parts = re.findall(r'<(?:b|strong)>(.*?)</(?:b|strong)>', rich_text, re.DOTALL | re.IGNORECASE)
    return ' '.join(strip_html(part) for part in bold_parts)


def tokenize_to_ngrams(text, max_n):
    """
    Tokenize text into words, then generate all n-grams (n=1..max_n)
    as lowercased joined strings. Returns a set for O(1) lookup.
    """
    words = re.findall(r"[A-Za-z\u0100-\u024F\u1E00-\u1EFF'-]+", text)
    lower_words = [w.lower() for w in words]
    ngrams = set()
    for n in range(1, min(max_n + 1, len(lower_words) + 1)):
        for i in range(len(lower_words) - n + 1):
            ngrams.add(" ".join(lower_words[i:i + n]))
    return ngrams


def build_concordance(names, rows):
    """
    For each row, tokenize into n-grams once, then check all names via set lookup.
    Returns:
        concordance: dict name -> list of (location, rich_html_text), up to MAX_RESULTS
        total_counts: dict name -> total number of matching rows across entire corpus
    """
    concordance = defaultdict(list)
    total_counts = defaultdict(int)

    # Determine max token count among names for n-gram window size
    max_n = max(len(name.split()) for name in names)
    name_set = set(name.lower() for name in names)
    # Build reverse lookup: lowered name -> original name
    lower_to_name = {}
    for name in names:
        key = name.lower()
        if key not in lower_to_name:
            lower_to_name[key] = name

    print(f"Stripping HTML and tokenizing {len(rows)} rows (max n-gram: {max_n})...")
    t0 = time.time()

    for idx, (loc, rich_text) in enumerate(rows):
        if (idx + 1) % 10000 == 0:
            elapsed = time.time() - t0
            print(f"  Row {idx+1}/{len(rows)} ({elapsed:.1f}s)")

        bold_text = extract_bold_text(rich_text)
        if not bold_text:
            continue
        ngrams = tokenize_to_ngrams(bold_text, max_n)

        # Check which names appear in this row's n-grams
        matched_names = name_set & ngrams
        for match in matched_names:
            name = lower_to_name[match]
            total_counts[name] += 1
            if len(concordance[name]) < MAX_RESULTS:
                concordance[name].append((loc, rich_text))

    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s")
    return dict(concordance), dict(total_counts)


def highlight_name_in_html(rich_text, name):
    """Highlight occurrences of name inside bold tags with <mark> tag."""
    pattern = re.compile(re.escape(name), re.IGNORECASE)

    def highlight_bold_block(match):
        tag_open = match.group(1)   # e.g. <b>
        tag_name = match.group(2)   # e.g. b
        content = match.group(3)    # text between tags
        # Split content on nested tags to only replace in text nodes
        parts = re.split(r'(<[^>]+>)', content)
        for i, part in enumerate(parts):
            if not part.startswith('<'):
                parts[i] = pattern.sub(r'<mark>\g<0></mark>', part)
        return f'{tag_open}{"".join(parts)}</{tag_name}>'

    return re.sub(
        r'(<(b|strong)>)(.*?)(</\2>)',
        lambda m: highlight_bold_block(m),
        rich_text,
        flags=re.DOTALL | re.IGNORECASE
    )


def apply_text_substitutions(rich_text):
    """Apply display substitutions to output text, only in text nodes."""
    replacements = [
        ('the Holy One, Blessed be He', 'God'),
        ('the Lord', 'YHWH'),
        ('Gemara ', 'Talmud '),
        ('Rabbi ', "R' "),
    ]
    parts = re.split(r'(<[^>]+>)', rich_text)
    for i, part in enumerate(parts):
        if not part.startswith('<'):
            for old, new in replacements:
                part = part.replace(old, new)
            parts[i] = part
    return ''.join(parts)


def location_to_chavrutai_url(location):
    """Convert 'Berakhot 2a:1' to 'https://chavrutai.com/talmud/berakhot/2a#section-1'"""
    match = re.match(r'^(.+?)\s+(\d+[ab]):(\d+)$', location)
    if not match:
        return None
    tractate = match.group(1).lower().replace(' ', '-')
    daf = match.group(2)
    section = match.group(3)
    return f'https://chavrutai.com/talmud/{tractate}/{daf}#section-{section}'


def generate_html(concordance, total_counts, names):
    """Generate a human-readable HTML concordance file."""

    # Collect only names that have results, in alphabetical order
    active_names = [n for n in names if n in concordance]

    # Group by first letter for navigation
    letter_groups = defaultdict(list)
    for name in active_names:
        first = name[0].upper()
        if not first.isalpha():
            first = "#"
        letter_groups[first].append(name)

    letters_present = sorted(letter_groups.keys())

    total_entries = sum(total_counts.get(n, 0) for n in active_names)

    html_parts = []
    html_parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bible Names Concordance — Steinsaltz Talmud</title>
<style>
  :root {
    --bg: #faf8f4;
    --text: #2c2417;
    --accent: #8b4513;
    --accent-light: #d4a574;
    --border: #d5c9b1;
    --card-bg: #ffffff;
    --nav-bg: #f0ebe3;
    --highlight: #fff3cd;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Georgia', 'Times New Roman', serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 0;
  }
  header {
    background: var(--accent);
    color: #fff;
    padding: 2rem 1.5rem;
    text-align: center;
    border-bottom: 4px solid var(--accent-light);
  }
  header h1 { font-size: 2rem; margin-bottom: 0.3rem; letter-spacing: 0.02em; }
  header p { font-size: 1rem; opacity: 0.9; }

  nav.alpha-nav {
    position: sticky;
    top: 0;
    z-index: 100;
    background: var(--nav-bg);
    border-bottom: 1px solid var(--border);
    padding: 0.5rem 1rem;
    text-align: center;
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.25rem;
  }
  nav.alpha-nav a {
    display: inline-block;
    padding: 0.25rem 0.55rem;
    text-decoration: none;
    color: var(--accent);
    font-weight: bold;
    font-size: 0.95rem;
    border-radius: 4px;
    transition: background 0.15s;
  }
  nav.alpha-nav a:hover { background: var(--accent-light); color: #fff; }

  .container { max-width: 960px; margin: 0 auto; padding: 1.5rem 1rem; }

  .letter-heading {
    font-size: 1.6rem;
    color: var(--accent);
    border-bottom: 2px solid var(--accent-light);
    padding: 0.5rem 0 0.25rem;
    margin: 2rem 0 1rem;
  }

  .name-entry { margin-bottom: 2rem; }
  .name-entry h3 {
    font-size: 1.2rem;
    color: var(--accent);
    margin-bottom: 0.5rem;
    padding-left: 0.25rem;
    border-left: 3px solid var(--accent-light);
    padding-left: 0.75rem;
  }
  .name-entry h3 .match-count {
    font-size: 0.8rem;
    color: #888;
    font-weight: normal;
    margin-left: 0.5rem;
  }

  .concordance-entry {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    margin-bottom: 0.75rem;
    padding: 0.75rem 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }
  .concordance-entry .location {
    font-family: 'Courier New', monospace;
    font-size: 0.85rem;
    font-weight: bold;
    margin-bottom: 0.35rem;
    display: block;
  }
  span.location { color: var(--accent); }
  a.location { color: #1a0dab; text-decoration: underline; }
  a.location:hover { color: #0b0080; }
  .concordance-entry .text-content {
    font-size: 0.95rem;
    line-height: 1.65;
  }
  .concordance-entry .text-content i { font-style: italic; }
  .concordance-entry .text-content b, .concordance-entry .text-content strong { font-weight: bold; }
  .concordance-entry .text-content mark {
    background: #fff3a8;
    padding: 0.05em 0.15em;
    border-radius: 2px;
  }

  .stats {
    text-align: center;
    color: #888;
    font-size: 0.85rem;
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
  }

  .back-to-top {
    display: inline-block;
    margin-top: 1rem;
    color: var(--accent);
    text-decoration: none;
    font-size: 0.85rem;
  }
  .back-to-top:hover { text-decoration: underline; }
</style>
</head>
<body>
<header>
  <h1>Bible Names Concordance</h1>
  <p>Steinsaltz Talmud — Up to 5 entries per name</p>
</header>
""")

    # Alphabet nav
    html_parts.append('<nav class="alpha-nav" id="top">\n')
    for letter in letters_present:
        html_parts.append(f'  <a href="#letter-{letter}">{letter}</a>\n')
    html_parts.append('</nav>\n')

    html_parts.append('<div class="container">\n')

    current_letter = None
    for name in active_names:
        first = name[0].upper()
        if not first.isalpha():
            first = "#"

        if first != current_letter:
            current_letter = first
            html_parts.append(
                f'<h2 class="letter-heading" id="letter-{current_letter}">{current_letter}</h2>\n'
            )

        entries = concordance[name]
        total_for_name = total_counts.get(name, len(entries))
        shown = len(entries)
        count_label = f"{total_for_name} total match{'es' if total_for_name != 1 else ''}"
        if shown < total_for_name:
            count_label += f", showing {shown}"

        html_parts.append(f'<div class="name-entry">\n')
        html_parts.append(
            f'  <h3>{html.escape(name)}<span class="match-count">({count_label})</span></h3>\n'
        )
        for loc, text in entries:
            highlighted = highlight_name_in_html(text, name)
            highlighted = apply_text_substitutions(highlighted)
            chavrutai_url = location_to_chavrutai_url(loc)
            html_parts.append(f'  <div class="concordance-entry">\n')
            if chavrutai_url:
                html_parts.append(f'    <a class="location" href="{chavrutai_url}" target="_blank">{html.escape(loc)}</a>\n')
            else:
                html_parts.append(f'    <span class="location">{html.escape(loc)}</span>\n')
            html_parts.append(f'    <div class="text-content">{highlighted}</div>\n')
            html_parts.append(f'  </div>\n')
        html_parts.append(f'</div>\n')

    html_parts.append(f'<div class="stats">\n')
    html_parts.append(
        f'  {len(active_names)} names with matches &middot; '
        f'{total_entries} total concordance entries &middot; '
        f'{len(names)} names searched<br>\n'
    )
    html_parts.append(f'  <a href="#top" class="back-to-top">Back to top</a>\n')
    html_parts.append(f'</div>\n')

    html_parts.append('</div>\n</body>\n</html>')

    return "".join(html_parts)


def main():
    parser = argparse.ArgumentParser(description="Build Bible names concordance")
    parser.add_argument("--test", type=int, metavar="N",
                        help="Limit to first N rows for testing")
    args = parser.parse_args()

    print("Loading gazetteer names...")
    names = load_names(GAZETTEER_PATH)
    print(f"  Loaded {len(names)} unique names.")

    print("Loading Talmud sections...")
    rows = load_talmud_rows(CSV_PATH)
    print(f"  Loaded {len(rows)} sections.")

    if args.test:
        rows = rows[:args.test]
        print(f"  TEST MODE: limited to {len(rows)} rows.")

    concordance, total_counts = build_concordance(names, rows)

    print(f"\nFound matches for {len(concordance)} names.")
    total = sum(total_counts.values())
    print(f"Total matches across corpus: {total}")

    print("Generating HTML...")
    html_output = generate_html(concordance, total_counts, names)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_output)
    print(f"Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
