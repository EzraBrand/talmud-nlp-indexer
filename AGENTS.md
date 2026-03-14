# AGENTS.md

## Scope
These instructions apply to work on the Talmud glossary data and the GitHub Pages table in this repo.

## Primary Files
- `docs/glossary/glossary_initial_v4.csv`: canonical glossary table and GitHub Pages data source.
- `docs/glossary/index.html`: browser UI for the glossary table.
- `data/glossary_initial/README.md`: glossary pipeline notes and script references.

## Source of Truth
- Treat `docs/glossary/glossary_initial_v4.csv` as the working database.
- The live page at `/glossary/` reads directly from that CSV. Updating the CSV is the effective site rebuild for glossary data.

## Editing Rules
- Prefer manual curation for high-count rows first.
- Only add Wikipedia links when the match is genuinely relevant to the rabbinic/Talmudic entity.
- Treat `hebrew_term` and `wikipedia_he` as separate fields:
  - `hebrew_term` is the Hebrew label intended for the glossary row as the term appears in the Talmud.
  - `wikipedia_he` is the Hebrew Wikipedia page actually chosen for that row.
  - `wikidata_id` is a derived field, filled programmatically from the mapped EN/HE Wikipedia page and not manually invented.
  - person metadata columns such as `student_of`, `student`, `affiliation`, `date_of_birth`, `place_of_birth`, `date_of_death`, `place_of_death`, and `father` are derived from Wikidata using the row's `wikidata_id`.
  - These can differ when the desired glossary label is not identical to the HE article title.
  - Do not assume `hebrew_term` should just copy the HE Wikipedia title; prefer the Talmudic form when known from the corpus.
- Use the actual Wikipedia page titles:
  - `selected_anchor_text` should match the resolved canonical EN Wikipedia page title exactly, not a local label or redirect label.
  - `wikipedia_he` should point to the correct Hebrew Wikipedia article, i.e. the article whose title is the intended HE wiki value for that row.
  - `hebrew_term` does not need to match that HE Wikipedia article title. If the Talmud-facing Hebrew form differs from the Wikipedia title, keep the Talmud-facing form in `hebrew_term` and use the correct article URL in `wikipedia_he`.
  - If an EN URL is a redirect, normalize the URL and anchor text to the canonical target title.
- Do not force links for ambiguous generic names if multiple rabbis or entities are plausible.
- Remove clearly non-entity fragments or relationship stubs rather than linking them.
- Remove incorrect semantic matches even if they are technically valid pages.
  - Example: `Abba` should not link to `Ab (Semitic)`.

## Matching Heuristics
- Good candidates:
  - canonical rabbinic overview pages like `Rabbi Yohanan`, `Rabbi Yehuda`, `Rabbi Yosei`
  - stable institutional pages like `House of Shammai`
  - exact person pages like `Joshua ben Levi`
- Bad candidates:
  - bare personal names with multiple likely referents
  - patronymic fragments like `bar Abba`, `ben Levi`
  - generic formulas like `son of Rabbi`, `the school of Rabbi`
  - broad lexical pages that are not the Talmudic entity actually intended

## Duplicates
- Merge obvious duplicate canonical rows when they refer to the same entity.
- When merging:
  - keep the best canonical term already in the table
  - do not sum `talmud_corpus_count`
  - move the removed term into `variant_names`
  - preserve or combine valid wiki fields
  - note the merge in `wiki_match_source`
- Typical example: merge a bare form into the established titled form, such as `Akiva` into `Rabbi Akiva`.

## Removal Criteria
- Delete rows that are too ambiguous to support as canonical entities.
- Delete rows that are merely fragments of longer person names.
- Delete rows the maintainer explicitly classifies as non-entities for this table.

## Verification
- Check both EN and HE Wikipedia directly before adding links.
- For HE pages, prefer the corresponding HE article for the exact EN entity when it exists.
- If the EN and HE pages reflect different rabbis or scopes, do not pair them.
- If both `wikipedia_en` and `wikipedia_he` exist but resolve to different Wikidata items, prefer the HE-linked item in `wikidata_id`.
- When refreshing person metadata from Wikidata, resolve linked entities to English labels and store semicolon-separated values when multiple values exist.
- For concept rows derived from the Steinsaltz corpus:
  - use the English Steinsaltz CSV to locate the term in context
  - align by citation with the Hebrew Steinsaltz CSV
  - infer the intended Hebrew expression from the aligned Hebrew passage
  - then verify the HE Wikipedia target from that Hebrew expression
- When reviewing `hebrew_term`, treat the Steinsaltz Hebrew CSV as the authority for Talmud-facing phrasing, even if the current value came from a Wikipedia title.
- In the Steinsaltz English CSV, translation/base text is often bolded and commentary is unbolded; use that signal when deciding whether an English term reflects the underlying base term or only commentary phrasing.
- If the maintainer approves only a small list of rows, edit only those rows and leave broader enrichment proposals uncommitted.

## Output Hygiene
- Keep CSV formatting stable.
- Avoid broad rewrites that change unrelated fields or URL encoding across the whole file.
- Make focused diffs.
- When proposing more glossary enrichments, prioritize the highest `talmud_corpus_count` rows still missing `wikipedia_he` unless the maintainer asks otherwise.

## Git Workflow
- Commit glossary edits directly to the tracked CSV.
- Pushing `main` republishes the GitHub Pages glossary data; there is no separate glossary build step in this repo.
