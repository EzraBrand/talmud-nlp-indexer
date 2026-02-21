# Building a Talmud Glossary You Can Actually Browse

I built a new public glossary page for my Talmud NLP project, and I want to explain what it is, why I made it, and how to use it.

If you study classical Jewish texts, you already know the recurring problem: names, places, and concepts show up constantly, often in variant forms, and often without context. You may recognize a term, but not remember whether it is a person, a place, a biblical reference, or a legal concept. You may remember hearing a name in one tractate and then seeing a slightly different version somewhere else.

I wanted a practical tool for this. Not a polished encyclopedia. Not a giant theory paper. A working glossary that helps with real reading.

The result is this page:

- https://ezrabrand.github.io/talmud-nlp-indexer/glossary/

## What this page does

The glossary page presents a large table of terms that I assembled from multiple gazetteers and then enriched.

Each row is a canonical entry, and each entry includes:

- a term name
- category labels
- variant names
- a corpus count (how often it appears in the English Talmud corpus)
- English and Hebrew Wikipedia links when available
- Hebrew label when available

I added direct links from terms and variants into ChavrutAI search so you can jump from reference data into text exploration immediately.

This matters because the glossary is not the endpoint. It is the bridge.

## Why I built it this way

I did not start from scratch. I used existing structured resources from my Talmud NLP Indexer work, especially the gazetteers that already power term highlighting in ChavrutAI.

Then I did the extra work that usually gets postponed:

- deduping obvious duplicates
- consolidating variants under a canonical entry
- mapping to Wikipedia (English and Hebrew)
- counting term frequency in the Talmud corpus
- building a browsable page instead of leaving the data as raw files

In other words: I moved this material from “internal data artifact” into something usable by readers.

## What is still imperfect

I want to be direct about this. This is useful, but it is not “finished.”

Some entries still need manual curation. Some mappings are incomplete. Some names are tricky because transliteration is inconsistent across sources. Hebrew mappings are much better now, but some English pages still have no straightforward Hebrew link in the API workflow.

I exported unresolved cases for manual review, instead of pretending everything is automatically solved.

That is deliberate: transparent partial coverage is better than false certainty.

## What readers can do with it now

Even in this initial form, the page is already practical for daily use:

1. Filter by category to narrow the scope quickly.
2. Sort by count to see high-frequency terms first.
3. Open a term or a variant in ChavrutAI search and move into actual passages.
4. Use Wikipedia links to get quick orientation when needed.

If you are teaching, this can help build reading lists or review sheets around high-frequency names and concepts.

If you are learning independently, this can reduce the friction of “what is this term again?” while reading.

## The bigger project context

This glossary is one part of a broader project:

- structured extraction of terms from rabbinic corpora
- alignment between named entities, concepts, and places
- practical interfaces for non-specialist readers

I care about this because the barrier to entry in these texts is often not lack of motivation, but lack of navigational tools.

A lot of readers can handle complexity. What they need is orientation.

This glossary is an orientation layer.

## Why this matters for classical text study

Classical Jewish texts are dense, layered, and strongly intertextual. That richness is the point. But the same richness can make reading brittle when you lose track of key names and terms.

By surfacing variants and cross-links in one place, I can reduce that brittleness without flattening the material.

I am not trying to replace close reading. I am trying to support it.

## What comes next

Near-term improvements I plan:

- better manual curation on unresolved Wikipedia mappings
- stronger alias handling for transliteration edge cases
- adding Sefaria mappings where appropriate
- adding in-context examples per term from the corpus index

The long-term goal is a glossary that does not only list terms, but helps you move intelligently between term, context, and source text.

## Closing note

I built this because I wanted something I would personally use while learning and writing.

It is already helping me move faster and with fewer dead ends. If you work in these texts, I expect it will do the same for you.

If you find clear errors or missing links, send them. This project improves through iterative correction, not one-time perfection.

---

# Technical Appendix (One-Page)

This section summarizes the implementation choices for readers who want the engineering details.

## Data sources

Primary source files are in:

- `data/talmud_concepts_gazetteer.txt`
- `data/talmud_names_gazetteer.txt`
- `data/bible_names_gazetteer.txt`
- `data/nations_and_demonyms_gazetteer.txt`
- `data/bible_places_gazetteer.txt`
- `data/talmud_toponyms_gazetteer.txt`

Additional enrichment sources:

- extracted Wikipedia links from blog HTML files
- curated links from `comparative_topic_tree_hyperlinked.html`
- EN->HE Wikipedia langlinks via MediaWiki API

## Canonicalization and variants

Rows were deduped into canonical entities, preferring canonical names from Wikipedia EN when available. Variant forms were merged into `variant_names`.

I also corrected edge cases where a Hebrew-script term became canonical due to missing EN mapping; canonical term display is now kept in English where possible.

## Count column

`talmud_corpus_count` is computed from `data/talmud_full_english.txt` using tokenized phrase matching.

Counting includes:

- canonical term
- all listed variants

Normalization includes:

- transliteration diacritic folding (for example dotted letters)
- apostrophe normalization across Unicode variants

Script used:

- `data/glossary_initial/update_corpus_counts.py`

## Hebrew link enrichment

Script:

- `data/glossary_initial/enrich_he_from_en_langlinks.py`

Method:

- query EN Wikipedia API in batches for Hebrew `langlinks`
- resolve normalized/redirect titles
- fill `wikipedia_he` and `hebrew_term` when available
- export unresolved rows for manual review:
  - `data/glossary_initial/missing_he_wiki_after_langlinks.csv`

## GitHub Pages interface

Published from `docs/`.

Main page:

- `docs/glossary/index.html`

Features implemented:

- text filter + category filter
- sortable columns (including numeric sort for Count)
- row numbering and row highlighting
- term and variant links into ChavrutAI search
- responsive table styling

SEO additions:

- canonical URL
- meta description/robots
- Open Graph and Twitter metadata
- JSON-LD WebPage schema
- `docs/robots.txt`
- `docs/sitemap.xml`

## Scope note

This is a production-oriented prototype, not a final scholarly ontology. The workflow is intentionally iterative: ship useful structure, audit systematically, and improve mappings over time.
