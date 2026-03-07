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
- Use the actual Wikipedia page titles:
  - `selected_anchor_text` should match the EN page title used.
  - `hebrew_term` should match the HE page title used.
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
  - sum `talmud_corpus_count`
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

## Output Hygiene
- Keep CSV formatting stable.
- Avoid broad rewrites that change unrelated fields or URL encoding across the whole file.
- Make focused diffs.

## Git Workflow
- Commit glossary edits directly to the tracked CSV.
- Pushing `main` republishes the GitHub Pages glossary data; there is no separate glossary build step in this repo.
