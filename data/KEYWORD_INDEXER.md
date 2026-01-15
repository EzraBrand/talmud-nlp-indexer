# Talmud Keyword Indexer

A focused tool for creating page-level keyword indexes of the Babylonian Talmud based on conceptual gazetteers.

## Overview

This indexer complements the main NLP pipeline by providing a lightweight, frequency-based keyword extraction system. It processes the Steinsaltz Talmud text and generates a searchable index mapping each page to its most frequently mentioned concepts from the `talmud_concepts_gazetteer.txt`.

## Files

- **`create_talmud_index.py`** - Python script that generates the keyword index
- **`talmud_index_final.csv`** - Output index with three columns: location, keywords, sefaria_link
- **`steinsaltz_talmud_combined_richHTML.csv`** - Source data (Steinsaltz Talmud with HTML formatting)
- **`talmud_concepts_gazetteer.txt`** - 182 Jewish theological and legal concepts used for matching

## Technical Approach

### Processing Pipeline

1. **Concept Loading**: Loads 182 unique concepts from the gazetteer
2. **Text Preprocessing**:
   - Strips HTML tags from Talmud text
   - Unescapes HTML entities for accurate matching
   - Handles multiple character encodings (UTF-8, Latin-1, CP1252)
3. **Keyword Matching**:
   - Uses regex pattern matching with case-insensitive search
   - Sorts concepts by length (longest first) to prioritize multi-word phrases
   - Aggregates mentions across all sub-sections within each page
4. **Frequency Analysis**: Counts keyword occurrences per page and sorts by frequency
5. **Output Generation**: Creates CSV with page references, sorted keywords, and Sefaria links

### Sorting Algorithm

Custom sorting function handles Talmud page notation:
- Extracts tractate name, page number, and side (a/b)
- Sorts numerically by page, then alphabetically by side
- Example: `Berakhot 2a → 2b → 3a → 3b`

## Output Format

The index (`talmud_index_final.csv`) contains three columns:

| Column | Description | Example |
|--------|-------------|---------|
| `location` | Tractate and page reference | `Berakhot 2a` |
| `keywords` | Comma-separated concepts, sorted by frequency | `shema, sin, teruma, priest, torah` |
| `sefaria_link` | Direct link to page on Sefaria | `https://www.sefaria.org.il/Berakhot.2a` |

## Usage

From the `data/` directory:

```bash
python create_talmud_index.py
```

This will:
1. Load concepts from `talmud_concepts_gazetteer.txt`
2. Process first 1,000 rows from `steinsaltz_talmud_combined_richHTML.csv`
3. Generate `talmud_index_final.csv` with sorted, aggregated results

## Statistics

- **Pages Indexed**: 41 pages (Berakhot 2a through 22a)
- **Source Rows Processed**: 1,000 text segments
- **Concepts Identified**: 182 unique terms
- **Average Keywords per Page**: ~12 unique concepts

## Example Results

**Berakhot 2a** (13 unique keywords, 87 total occurrences):
- Most frequent: shema, sin, teruma, priest, torah, mitzva, mitzvot
- Link: https://www.sefaria.org.il/Berakhot.2a

**Berakhot 7a** (18 unique keywords, 124 total occurrences):
- Most frequent: righteous, anger, wicked, exodus, mercy, sin
- Link: https://www.sefaria.org.il/Berakhot.7a

## Requirements

- Python 3.x
- Standard library only (csv, re, collections, html)
- No external dependencies required

## Differences from Main NLP Pipeline

This keyword indexer differs from the main project's NLP pipeline:

- **Lighter weight**: No ML models or embeddings required
- **Concept-focused**: Uses only the concepts gazetteer, not names/places
- **Frequency-based**: Simple count-based ranking vs. sophisticated NER tagging
- **Page-level aggregation**: Combines all sub-sections into single page entries
- **Direct Sefaria integration**: Includes clickable links in output

Use this tool when you need quick concept frequency analysis across Talmud pages without running the full NLP pipeline.
