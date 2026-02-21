# Initial Glossary Database

This folder contains iterative glossary database builds for the ChavrutAI glossary sprint.

## Files

- `glossary_initial_v2.csv`: initial merged/enriched dataset.
- `glossary_initial_v3.csv`: strict Wikipedia verification pass for biblical names.
- `glossary_initial_v4.csv`: current canonical dataset with deduped entities.
- `biblical_names_wikipedia_review.csv`: biblical-name verification audit table.

## Current Canonical Dataset

Use `glossary_initial_v4.csv` as the working DB.

Each row is a canonical entry with:

- `term`: canonical entry name (Wikipedia title when available)
- `categories`: one or more gazetteer categories (`;` separated)
- `variant_names`: alternate gazetteer names merged into the canonical row
- `talmud_corpus_count`: tokenized occurrence count in `data/talmud_full_english.txt` (canonical term + variants), with normalization for transliteration diacritics (for example `ḥ -> h`) and apostrophe variants (`'`, `’`, `‘`, etc.)
- `wikipedia_en`: verified/best-mapped English Wikipedia URL
- `wikipedia_he`: Hebrew Wikipedia URL when available
- `selected_anchor_text`: anchor text used in earlier mapping steps
- `hebrew_term`: Hebrew label (from Hebrew Wikipedia title when available)
- `chavrutai_search_url`: `https://chavrutai.com/search?q=...`
- `wiki_match_source`: short provenance/status note for mapping path

## Primary Sources

- Gazetteers in `data/`:
  - `talmud_concepts_gazetteer.txt`
  - `talmud_names_gazetteer.txt`
  - `bible_names_gazetteer.txt`
  - `nations_and_demonyms_gazetteer.txt`
  - `bible_places_gazetteer.txt`
  - `talmud_toponyms_gazetteer.txt`
- Curated/derived Wikipedia links from:
  - blog HTML hyperlink extraction (deduplicated into `wikipedia_links_fixed.csv`)
  - `comparative_topic_tree_hyperlinked.html` from `jewish-law-tree`
- Wikipedia API enrichment:
  - EN->HE `langlinks`
  - strict biblical-name title verification (exact/redirect/disambiguation/missing)

## Important Limitations

- This is still an initial DB, not final manual curation.
- Some entities remain unmatched to Wikipedia.
- Some `variant_names` groupings are conservative and may miss deeper aliases.
- Sefaria mappings and Talmud in-context examples are not included yet.

## Future Improvements

- Manual curation for ambiguous and high-frequency terms.
- Stronger alias normalization (apostrophes, ben/bar, spelling variants).
- Confidence scoring per mapping decision.
- Add Sefaria term/page mappings.
- Add sampled Talmud occurrences/snippets per term.
- Add automated QA checks (invalid URLs, duplicate canonical entities, category conflicts).

## View CSV As Grid In VS Code

Use extension `Edit csv` by `janisdd`:

1. Press `Ctrl+Shift+P`
2. Run `Edit csv: Edit`

## Browser Page (GitHub Pages)

- Page source: `docs/glossary/index.html`
- Data file used by the page: `docs/glossary/glossary_initial_v4.csv`
- If GitHub Pages is configured from `main`/`docs`, this page is available at `/glossary/`.
- Live URL: `https://ezrabrand.github.io/talmud-nlp-indexer/glossary/`

## Changelog

- `2026-02-21 12:35` Added `biblical_names_wikipedia_review.csv` and strict biblical-name verification (`v3`).
- `2026-02-21 12:42` Added `glossary_initial_v4.csv` with deduped canonical entries and expanded `variant_names`.
- `2026-02-21 12:46` Updated schema docs: removed `category_count`, moved `variant_names` after `categories`, set `v4` as canonical.
- `2026-02-21 12:49` Added GitHub Pages browser table (`docs/glossary/index.html`) with clickable Wikipedia anchors.
- `2026-02-21 13:22` Added `talmud_corpus_count` to `glossary_initial_v4.csv` using tokenized counting over `data/talmud_full_english.txt`; surfaced the same column on GitHub Pages.
- `2026-02-21 13:24` Added `update_corpus_counts.py` and refreshed counts with explicit normalization for dotted transliteration letters and apostrophe variants.
- `2026-02-21 13:30` Added `enrich_he_from_en_langlinks.py` and refreshed `wikipedia_he` where programmatically available from EN Wikipedia `langlinks`; updated page UI with wrapped narrower `Variant Names` and a category filter.
