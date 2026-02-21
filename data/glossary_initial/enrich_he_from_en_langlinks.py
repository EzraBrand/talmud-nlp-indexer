import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(r'c:\Users\ezrab\Downloads\talmud-nlp-indexer')
CSV_PATH = REPO / 'data' / 'glossary_initial' / 'glossary_initial_v4.csv'
DOCS_CSV_PATH = REPO / 'docs' / 'glossary' / 'glossary_initial_v4.csv'
API = 'https://en.wikipedia.org/w/api.php'
UA = 'codex-he-langlink-enricher/1.0'


def wiki_title_from_en_url(url: str) -> str:
    if not url:
        return ''
    marker = '/wiki/'
    i = url.find(marker)
    if i < 0:
        return ''
    title = url[i + len(marker):].split('#', 1)[0]
    return urllib.parse.unquote(title).replace('_', ' ').strip()


def he_url_from_title(title: str) -> str:
    slug = title.replace(' ', '_')
    return 'https://he.wikipedia.org/wiki/' + urllib.parse.quote(slug, safe='()')


def fetch_langlinks(titles):
    params = {
        'action': 'query',
        'format': 'json',
        'redirects': '1',
        'prop': 'langlinks',
        'lllang': 'he',
        'lllimit': '1',
        'titles': '|'.join(titles),
    }
    url = API + '?' + urllib.parse.urlencode(params)

    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode('utf-8', errors='replace'))
        except Exception:
            if attempt == 5:
                raise
            time.sleep(2 ** attempt)


def main():
    with CSV_PATH.open('r', encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
        fieldnames = f.readline

    titles = []
    for r in rows:
        if r.get('wikipedia_en') and not r.get('wikipedia_he'):
            t = wiki_title_from_en_url(r['wikipedia_en'])
            if t:
                titles.append(t)

    uniq_titles = sorted(set(titles))
    title_to_he = {}

    batch_size = 50
    for i in range(0, len(uniq_titles), batch_size):
        batch = uniq_titles[i:i + batch_size]
        data = fetch_langlinks(batch)
        pages = data.get('query', {}).get('pages', {})
        for page in pages.values():
            title = page.get('title', '')
            links = page.get('langlinks') or []
            if title and links:
                he_title = links[0].get('*', '').strip()
                if he_title:
                    title_to_he[title] = he_title
        time.sleep(0.2)

    updated = 0
    for r in rows:
        if not r.get('wikipedia_en') or r.get('wikipedia_he'):
            continue
        t = wiki_title_from_en_url(r['wikipedia_en'])
        he_title = title_to_he.get(t)
        if not he_title:
            continue
        r['wikipedia_he'] = he_url_from_title(he_title)
        if not r.get('hebrew_term'):
            r['hebrew_term'] = he_title
        updated += 1

    if not rows:
        return
    out_fields = list(rows[0].keys())
    for out_path in (CSV_PATH, DOCS_CSV_PATH):
        with out_path.open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=out_fields)
            w.writeheader()
            w.writerows(rows)

    print(f'rows={len(rows)}')
    print(f'updated_he_links={updated}')
    print(f'unique_titles_checked={len(uniq_titles)}')


if __name__ == '__main__':
    main()
