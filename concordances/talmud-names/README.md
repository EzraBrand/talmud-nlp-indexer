# Talmud names concordance

Open `index.html` in a browser. It is a standalone, searchable HTML concordance, sorted A-Z, with up to three full sections per eligible gazetteer entry. Citations link to Bekiut.

## Rebuild

Python 3; standard library only. From the repository root:

```sh
python concordances/talmud-names/build_concordance.py
```

The builder reads the existing `data/talmud_names_gazetteer.txt` and `data/archive/steinsaltz_talmud_combined_richHTML.csv`; these large inputs are not duplicated here. Override paths with `--gazetteer`, `--corpus`, or `--output-dir`.

Outputs are `index.html` and `summary.json`. The summary records corpus SHA-256 and coverage counts. The checked-in edition was generated October 16, 2026.

## Matching and display

- Exclude entries beginning with a complete word (case insensitive): Rabbi, Rav, Mar, Abba, Ravin, Rava, Rabba, Rabban, Abaye, Avimi, Avin, Avuh.
- Match whole token sequences only within bold translation (`b` / `strong`), including nested formatting. Intervening unbolded commentary breaks a phrase.
- Resolve overlapping occurrences against the **full gazetteer**, longest phrase first. Excluded names block shorter included names inside them. A separate standalone occurrence still counts.
- Normalize apostrophe variants and token separators for matching. This is lexical matching, not entity disambiguation; homonyms can still produce false positives.
- Decode the legacy corpus as Windows-1252. Restore question-mark placeholders between letters or at word starts before lowercase letters as ḥ/Ḥ, following the archived concordance builder's heuristic. Other source defects can remain; no other wording substitutions are applied.
- Preserve the full section's formatting and commentary as context. Highlight only matching translation text in yellow.
- Count distinct section citations, retaining the first three in CSV order. Include eligible entries with no match.

## Current edition

1,598 eligible names; 1,441 with matches; 157 without matches; 81,793 sections searched; 2,449 displayed sections.

## GitHub Pages

This folder stores the reproducible artifact outside the current Pages publishing source (`main/docs`). It does not add a public route automatically. To publish alongside the glossary, place the generated `index.html` at `docs/concordance/index.html`; it will be served at `/talmud-nlp-indexer/concordance/` by the existing Pages site.
