# Claude Assistant Guide - Talmud NLP Indexer

## Quick Start for New Claude Assistants

This is a sophisticated NLP project that analyzes and indexes the Babylonian Talmud using modern natural language processing. Here's what you need to know to get started quickly.

## Essential Files to Read First

### 1. Project Overview
- **`README.md`** - High-level project description and setup instructions
- **`STATUS.md`** - Current project status, completed work, and next steps (CRITICAL for understanding current state)

### 2. Core Codebase (Read in this order)
- **`main.py`** - Orchestration script, main pipeline, and Markdown generation logic
- **`processor.py`** - Bilingual text processing (English with spaCy + Hebrew with AlephBERT)
- **`tagging.py`** - Comprehensive tagging system with gazetteers and NER
- **`api.py`** - Sefaria API client for fetching Talmudic texts

### 3. Current "Hero" Output Example
- **`data/Sanhedrin_91a.md`** - Our best current output example showing:
  - Tag quality and variety
  - Hebrew text formatting (RTL, nikud-stripped, no numbering)
  - English text annotation with term replacements
  - Issues to be aware of

### 4. Sample Data Files
- **`data/Berakhot_2a.md`** - Earlier example from a different tractate
- **`data/talmud_names_gazetteer.txt`** - Sample of Talmudic names (3,264 entries)
- **`data/bible_names_gazetteer.txt`** - Biblical names (1,328 entries)
- **`data/talmud_concepts_gazetteer.txt`** - Key concepts (64 entries)

## Architecture Summary

### Pipeline Flow
```
Sefaria API → Text Processing → Tag Generation → Dual Output
    ↓              ↓               ↓              ↓
Raw Hebrew/   spaCy (EN) +    NER + Gazetteers  JSON + 
English       AlephBERT (HE)  + Topic Model    Markdown
```

### Key Components

**1. Text Processing (`processor.py`)**
- English: spaCy NER, noun chunks, italicized word extraction
- Hebrew: AlephBERT embeddings, HTML cleaning
- Smart HTML parsing preserves formatting cues

**2. Tagging System (`tagging.py`)**
- Multi-source: spaCy NER + 6 gazetteers + topic modeling
- Prioritization: Biblical > Talmudic > spaCy tags
- Smart conflict resolution (names vs places)
- Categories: `person:`, `place:`, `concept:`, `topic:`, `person:bible:`, `place:bible:`

**3. Output Generation (`main.py`)**
- **JSON**: Structured data for processing
- **Markdown**: Human-readable with:
  - Hebrew text (RTL formatted, nikud-stripped, no numbering)
  - Annotated English text with entity tagging and scholarly term replacements
  - Tag lists and italicized words
  - Term standardization (33 scholarly mappings: "Rabbi" → "R'", "the Holy One, Blessed be He" → "God", etc.)

## Current Status & Quality

### What's Working Well
- ✅ Bilingual processing pipeline
- ✅ Good biblical entity recognition (`person:bible:abraham`, `place:bible:canaan`)
- ✅ Clean Hebrew text formatting (RTL, nikud-stripped)
- ✅ English term standardization (33 scholarly mappings)
- ✅ Comprehensive gazetteer system (5,000+ entries)
- ✅ Dual output formats

### Known Issues (from Sanhedrin_91a.md analysis)
- ❌ Some incorrect person tags: `person:lest`
- ❌ Mixed quality in entity boundary detection

### Current Scope
- **Active Range**: Sanhedrin 90b-91a (recently updated from Berakhot 2a-7a)
- **Primary Tractate**: Currently processing Sanhedrin
- **Focus Page**: `data/Sanhedrin_91a.md` (our best example)

### Recent Improvements (Latest Session)
- ✅ **Hebrew formatting enhanced**: Removed numbering, added nikud stripping, maintained RTL display
- ✅ **Term replacement system**: 33 scholarly mappings implemented ("Rabbi" → "R'", "the Holy One, Blessed be He" → "God", etc.)
- ✅ **Processing range updated**: Changed from Berakhot 2a-7a to Sanhedrin 90b-91a
- ✅ **Code organization**: Clean separation of original and processed English text

## Next Steps Priority (from STATUS.md)

### Immediate 

3. **Entity linking**: Connect to Wikipedia/wiki IDs
4. **Tag refinement**: Fix spaCy issues (full names, exclude 'cardinal' from 'one')
5. **Scope expansion**: Test on more Berakhot pages



## Quick Commands for Development

```bash
# Run the main pipeline
python main.py


```

## File Structure Guide

```
├── main.py              # Main orchestration + Markdown generation
├── processor.py         # Bilingual NLP processing  
├── tagging.py          # Multi-source tagging system
├── api.py              # Sefaria API client
├── requirements.txt    # Dependencies
├── data/               # Input gazetteers + output files
│   ├── *_gazetteer.txt # Reference data (names, places, concepts)
│   ├── *.json          # Structured output
│   └── *.md            # Human-readable output
└── tests/              # Unit tests with mocks
```

## Tips for New Assistants

1. **Start with STATUS.md** - It's your roadmap to current state
2. **Check Sanhedrin_91a.md** - See actual output quality and issues
3. **Understand the tag prioritization** in `main.py` (lines 25-53)
4. **Gazetteer system is key** - 6 different reference files drive tagging
5. **Hebrew + English processing** - Different pipelines, different challenges
6. **Both JSON and Markdown matter** - Different use cases

## Key Functions to Understand

- `main.py:generate_markdown()` - Complex annotation logic with prioritization and term replacements
- `main.py:apply_term_replacements()` - Scholarly term standardization (33 mappings)
- `processor.py:clean_text()` - HTML processing, italics extraction, and nikud stripping
- `tagging.py:generate_tags()` - Multi-source tag generation with conflict resolution
- `tagging.py:_find_term_in_text()` - Gazetteer matching logic

---

**Remember**: This is a scholarly project requiring both technical precision and domain knowledge. The goal is creating useful tools for Talmudic study and research.
