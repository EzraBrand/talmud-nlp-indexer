# Initial Glossary Database

This folder now documents only the current glossary dataset and live browser view.

## Current Canonical Dataset

Use `docs/glossary/glossary_initial_v4.csv` as the working DB.

Each row is a canonical entry with:

- `term`: canonical entry name
- `categories`: one or more gazetteer categories (`;` separated)
- `variant_names`: alternate names merged into the canonical row
- `talmud_corpus_count`: rough occurrence count in the corpus
- `wikipedia_en`: mapped English Wikipedia URL
- `wikipedia_he`: mapped Hebrew Wikipedia URL
- `selected_anchor_text`: anchor text used in earlier mapping steps
- `hebrew_term`: Hebrew label intended to reflect how the term appears in the Talmud
- `chavrutai_search_url`: `https://chavrutai.com/search?q=...&type=talmud`
- `wiki_match_source`: short provenance/status note for the mapping path
- `wikidata_id`: Wikidata item ID (`Q...`) derived from the mapped Wikipedia page, preferring the HE-linked item when EN and HE differ

## Primary Sources

- Gazetteers in `data/`
- The Steinsaltz English and Hebrew corpora
- Manual Wikipedia review and targeted enrichment passes

## Important Limitations

- This is still an initial DB, not final manual curation.
- Some entities remain unmatched or only partially reviewed.
- `hebrew_term` still needs further normalization against the Steinsaltz Hebrew corpus in some rows.

## Browser Page

- Page source: `docs/glossary/index.html`
- Data file used by the page: `docs/glossary/glossary_initial_v4.csv`
- Live URL: `https://ezrabrand.github.io/talmud-nlp-indexer/glossary/`
