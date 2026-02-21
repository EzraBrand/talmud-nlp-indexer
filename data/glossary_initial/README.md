# Initial Glossary Database

This folder contains an initial glossary database for the ChavrutAI glossary sprint.

## File

- `glossary_initial_v2.csv`

## What It Is

A first-pass merged glossary table built from Talmud NLP gazetteers, enriched with best-effort Wikipedia mappings and basic variant grouping.

Each row is a term (English transliteration/source spelling) with:

- one or more gazetteer categories
- optional English and Hebrew Wikipedia URLs
- selected anchor text used for matching
- optional Hebrew term (from Hebrew Wikipedia title)
- ChavrutAI search URL
- match-source metadata
- `variant_names` for known alternate spellings/names mapped to the same underlying entry

## Primary Sources

- Gazetteers in `data/`:
  - `talmud_concepts_gazetteer.txt`
  - `talmud_names_gazetteer.txt`
  - `bible_names_gazetteer.txt`
  - `nations_and_demonyms_gazetteer.txt`
  - `bible_places_gazetteer.txt`
  - `talmud_toponyms_gazetteer.txt`
- Curated/derived Wikipedia links from:
  - blog HTML hyperlink extraction (deduplicated to `wikipedia_links_fixed.csv`)
  - `comparative_topic_tree_hyperlinked.html` from `jewish-law-tree`
- Additional EN->HE Wikipedia expansion via MediaWiki `langlinks` API for matched EN pages.

## Important Limitations

- This is intentionally an initial database, not a final curated mapping.
- Wikipedia matches are partial and may include false positives/false negatives.
- `variant_names` currently relies mainly on shared Wikipedia mapping; unmatched aliases may still be separate rows.
- Sefaria links and Talmud in-context examples are not yet included here.

## Future Improvements

- Manual curation pass for high-value terms and ambiguous entries.
- Stronger alias normalization (apostrophes, ben/bar variants, transliteration variants, singular/plural).
- Add confidence score and provenance per mapping decision.
- Add Sefaria term/page mappings.
- Add sampled Talmud occurrences/snippets per term.
- Add automated QA checks (invalid URLs, duplicate canonical entities, category conflicts).

<img width="643" height="486" alt="image" src="https://github.com/user-attachments/assets/d952314f-48a4-4872-a7f5-fbe2ae82c03d" />
(Do this in VS Code, to view csv as grid:

Press Ctrl+Shift+P
Type Edit csv: Edit
Press Enter)
